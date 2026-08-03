from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import datetime
from typing import Sequence

from sqlalchemy.orm import Session

from aqos.accounts.models import TradingAccount
from aqos.execution_policy.modes import ExecutionConstraint, ExecutionMode
from aqos.paper_trading.eligibility import (
    PaperEligibilityContext,
    PaperExecutionEligibilityDecision,
    REQUIRED_PAPER_EXECUTION_MODES,
    evaluate_paper_execution_eligibility,
)
from aqos.signal_reasons.taxonomy import SignalReasonCode
from aqos.signals.repositories import TradingSignalRepository
from aqos.trading_settings.models import SymbolPreferenceKind
from aqos.trading_settings.repositories import (
    SymbolPreferenceRepository,
    TradingSettingsRepository,
)
from aqos.paper_trading.contracts import (
    PaperAccountState,
    PaperAction,
    PaperBalance,
    PaperExecutionRequest,
    PaperExecutionResult,
    PaperFill,
    PaperOrder,
    PaperOrderStatus,
    PaperOrderType,
    PaperPosition,
    PaperRejectionReason,
    PaperTrade,
    PaperTradingError,
    side_for_action,
)
from aqos.paper_trading.models import (
    PaperOrderRecord,
    PaperPositionRecord,
    PaperTradeRecord,
    as_amount,
)
from aqos.paper_trading.repositories import (
    PaperAccountSnapshotRepository,
    PaperExecutionDecisionRepository,
    PaperFillRepository,
    PaperOrderRepository,
    PaperPositionRepository,
    PaperTradeRepository,
)
from aqos.paper_trading.simulator import (
    IntrabarExitPolicy,
    PaperExitReason,
    PaperMarketBar,
    PaperSimulatorConfig,
    calculate_fill_price,
    calculate_gross_pnl,
    is_buy_fill,
    resolve_position_exit,
    resolve_reference_price,
)
from aqos.paper_trading.validation import validate_paper_account
from aqos.users.repositories import build_entity_id


AQOS_PAPER_EXECUTION_SERVICE_VERSION = "1.1"

#: How a structured taxonomy code lands on the order row.
#:
#: The taxonomy code stays the authoritative reason; this only picks the coarser
#: order-level enum so ``paper_orders.rejection_reason`` stays meaningful.
REJECTION_REASON_BY_CODE: dict[SignalReasonCode, PaperRejectionReason] = {
    SignalReasonCode.ACCOUNT_NOT_PAPER: PaperRejectionReason.ACCOUNT_NOT_PAPER,
    SignalReasonCode.ACCOUNT_DISABLED: PaperRejectionReason.ACCOUNT_NOT_ACTIVE,
    SignalReasonCode.ACCOUNT_SUSPENDED: PaperRejectionReason.ACCOUNT_NOT_ACTIVE,
    SignalReasonCode.SYMBOL_BLOCKED: PaperRejectionReason.INVALID_SYMBOL,
    SignalReasonCode.INVALID_SYMBOL: PaperRejectionReason.INVALID_SYMBOL,
    SignalReasonCode.DUPLICATE_SIGNAL: PaperRejectionReason.DUPLICATE_EXECUTION,
    SignalReasonCode.AUTO_TRADE_NOT_ALLOWED: (
        PaperRejectionReason.EXECUTION_NOT_ALLOWED
    ),
    SignalReasonCode.UNPROMOTED_MODEL: PaperRejectionReason.EXECUTION_NOT_ALLOWED,
    SignalReasonCode.FUNDED_RULE_BREACHED: (
        PaperRejectionReason.EXECUTION_NOT_ALLOWED
    ),
    SignalReasonCode.RISK_LIMIT_EXCEEDED: (
        PaperRejectionReason.EXECUTION_NOT_ALLOWED
    ),
    SignalReasonCode.VALIDATION_FAILED: PaperRejectionReason.UNSAFE_ACTION,
}


def rejection_reason_for_code(
    code: SignalReasonCode,
) -> PaperRejectionReason:
    """
    Map a taxonomy code onto the order-level rejection enum.

    An unmapped code falls back to ``UNSAFE_ACTION`` rather than to something
    permissive, so a new code can never widen what gets executed.
    """

    return REJECTION_REASON_BY_CODE.get(code, PaperRejectionReason.UNSAFE_ACTION)


#: Rejections that cannot be written to ``paper_orders``.
#:
#: An invalid quantity violates the table's own CHECK constraint, and a
#: non-paper account must never gain a paper order row at all — that is exactly
#: the "simulated fills against real capital" case the schema exists to prevent.
UNPERSISTABLE_REJECTION_REASONS = (
    PaperRejectionReason.INVALID_QUANTITY,
    PaperRejectionReason.INVALID_SYMBOL,
    PaperRejectionReason.ACCOUNT_NOT_PAPER,
    PaperRejectionReason.MISSING_REQUIRED_FIELD,
)


@dataclass(frozen=True)
class PaperCloseOutcome:
    """What closing one position produced."""

    position: PaperPositionRecord
    trade: PaperTradeRecord
    exit_reason: PaperExitReason
    exit_price: float

    def to_dict(self) -> dict[str, object]:
        return {
            "position_id": self.position.position_id,
            "trade_id": self.trade.trade_id,
            "exit_reason": self.exit_reason.value,
            "exit_price": self.exit_price,
            "net_pnl": as_amount(self.trade.net_pnl),
        }


class PaperExecutionService:
    """
    The persisted paper execution path.

    The caller owns the session and the transaction; this service only stages
    work through the paper repositories so one signal, its order, its fills, its
    position and its trade all land in a single unit of work.
    """

    def __init__(
        self,
        session: Session,
        config: PaperSimulatorConfig | None = None,
    ) -> None:
        self.session = session
        self.config = config or PaperSimulatorConfig()

        self.orders = PaperOrderRepository(session)
        self.positions = PaperPositionRepository(session)
        self.fills = PaperFillRepository(session)
        self.trades = PaperTradeRepository(session)
        self.snapshots = PaperAccountSnapshotRepository(session)
        self.decisions = PaperExecutionDecisionRepository(session)

    # -- state ------------------------------------------------------------

    def build_balance(self, account: TradingAccount) -> PaperBalance:
        return PaperBalance(
            currency=account.currency,
            starting_balance=as_amount(account.initial_balance),
            current_balance=as_amount(account.current_balance),
            equity=as_amount(account.equity),
        )

    def build_account_state(
        self,
        account: TradingAccount,
        updated_at_utc: datetime | None = None,
    ) -> PaperAccountState:
        return PaperAccountState(
            account_id=account.account_id,
            balance=self.build_balance(account),
            updated_at_utc=updated_at_utc or account.updated_at_utc,
            open_position_count=self.positions.count_open_positions(
                account.account_id
            ),
            open_order_count=self.orders.count_open_orders(account.account_id),
            closed_trade_count=self.trades.count_trades(account.account_id),
        )

    def capture_snapshot(
        self,
        account: TradingAccount,
        captured_at_utc: datetime | None = None,
    ):
        state = self.build_account_state(account, updated_at_utc=captured_at_utc)

        return self.snapshots.capture_snapshot(
            account_id=account.account_id,
            starting_balance=state.balance.starting_balance,
            current_balance=state.balance.current_balance,
            equity=state.balance.equity,
            captured_at_utc=captured_at_utc or account.updated_at_utc,
            currency=state.balance.currency,
            open_position_count=state.open_position_count,
            open_order_count=state.open_order_count,
            closed_trade_count=state.closed_trade_count,
        )

    # -- safety -----------------------------------------------------------

    def build_eligibility_context(
        self,
        request: PaperExecutionRequest,
        overrides: PaperEligibilityContext | None = None,
    ) -> PaperEligibilityContext:
        """
        Resolve everything the rule gate can look up for itself.

        Duplicate execution, the signal's lifecycle status, the user's settings
        and their blocked symbols all come from the database rather than from
        the caller, so a caller cannot weaken the gate by passing a bare
        context. Inputs AQOS cannot derive here — funded state, risk and model
        promotion — are taken from ``overrides`` unchanged.
        """

        supplied = overrides or PaperEligibilityContext()

        settings = supplied.settings

        if settings is None:
            settings = TradingSettingsRepository(self.session).get_for_user(
                request.user_id
            )

        blocked_symbols = supplied.blocked_symbols

        if not blocked_symbols:
            blocked_symbols = SymbolPreferenceRepository(
                self.session
            ).list_symbols(request.user_id, SymbolPreferenceKind.BLOCKED)

        signal = supplied.signal

        if signal is None and request.signal_id is not None:
            signal = TradingSignalRepository(self.session).get(request.signal_id)

        has_existing_execution = (
            supplied.has_existing_execution
            or (
                request.signal_id is not None
                and self.orders.has_execution_for_signal(
                    account_id=request.account_id,
                    signal_id=request.signal_id,
                )
            )
        )

        return replace(
            supplied,
            settings=settings,
            blocked_symbols=tuple(blocked_symbols),
            signal=signal,
            has_existing_execution=has_existing_execution,
            evaluated_at_utc=(
                supplied.evaluated_at_utc or request.submitted_at_utc
            ),
        )

    def evaluate_eligibility(
        self,
        request: PaperExecutionRequest,
        account: TradingAccount,
        constraints: Sequence[ExecutionConstraint] = (),
        requested_mode: ExecutionMode = ExecutionMode.AUTO_TRADE,
        context: PaperEligibilityContext | None = None,
    ) -> PaperExecutionEligibilityDecision:
        """Run the full rule gate without executing anything."""

        return evaluate_paper_execution_eligibility(
            request=request,
            account=account,
            context=self.build_eligibility_context(request, context),
            requested_mode=requested_mode,
            extra_constraints=constraints,
        )

    # -- execution --------------------------------------------------------

    def execute(
        self,
        request: PaperExecutionRequest,
        account: TradingAccount,
        bar: PaperMarketBar,
        constraints: Sequence[ExecutionConstraint] = (),
        requested_mode: ExecutionMode = ExecutionMode.AUTO_TRADE,
        context: PaperEligibilityContext | None = None,
    ) -> PaperExecutionResult:
        """
        Run one paper execution end to end and persist every artefact.

        The rule gate runs first and its decision is always recorded, so a
        refused execution is as auditable as a successful one. A rejection is a
        normal outcome, not an exception.
        """

        eligibility = self.evaluate_eligibility(
            request=request,
            account=account,
            constraints=constraints,
            requested_mode=requested_mode,
            context=replace(
                context or PaperEligibilityContext(),
                market_data_symbol=bar.symbol,
            ),
        )
        decision_record = self.decisions.record_decision(
            eligibility,
            decided_at_utc=request.submitted_at_utc,
        )

        if not eligibility.is_allowed:
            primary = eligibility.primary_reason
            result = self._reject(
                request,
                account,
                # A rule that knows a narrower order-level reason keeps it; the
                # taxonomy code stays authoritative on the decision record.
                primary.order_rejection_reason
                or rejection_reason_for_code(primary.code),
                eligibility.rejection_message(),
                eligibility=eligibility,
            )

            if result.order is not None:
                self.decisions.attach_order(
                    decision_record.decision_id,
                    result.order.order_id,
                )

            return result

        if request.action == PaperAction.CLOSE:
            result = self._execute_close(request, account, bar)
        else:
            result = self._execute_open(request, account, bar)

        if result.order is not None:
            self.decisions.attach_order(
                decision_record.decision_id,
                result.order.order_id,
            )

        if result.accepted:
            self._mark_signal_executed(request, eligibility)

        return result

    def _mark_signal_executed(
        self,
        request: PaperExecutionRequest,
        eligibility: PaperExecutionEligibilityDecision,
    ) -> None:
        """
        Move the signal to ``executed`` through the Sprint 044 lifecycle.

        The gate already refused anything that was not ``approved``, so this
        transition is always legal; it goes through the repository so the audit
        event is written with it rather than around it.
        """

        if request.signal_id is None:
            return

        TradingSignalRepository(self.session).mark_executed(
            signal_id=request.signal_id,
            reason="Executed on a paper account.",
            actor="paper_execution_service",
            occurred_at_utc=request.submitted_at_utc,
        )

    def _execute_open(
        self,
        request: PaperExecutionRequest,
        account: TradingAccount,
        bar: PaperMarketBar,
    ) -> PaperExecutionResult:
        order_record = self._create_order(request, PaperOrderStatus.ACCEPTED)

        reference = self._reference_price(request, bar)
        buying = is_buy_fill(request.action)
        fill_price = calculate_fill_price(reference, buying, self.config)

        fill = PaperFill(
            fill_id=build_entity_id("paperfill"),
            order_id=order_record.order_id,
            quantity=request.quantity,
            price=fill_price,
            filled_at_utc=bar.timestamp_utc,
            commission=self.config.commission_per_fill,
        )

        position = PaperPosition(
            position_id=build_entity_id("paperpos"),
            account_id=request.account_id,
            symbol=request.symbol,
            side=side_for_action(request.action),
            quantity=request.quantity,
            entry_price=fill_price,
            opened_at_utc=bar.timestamp_utc,
            stop_loss=request.stop_loss,
            take_profit=request.take_profit,
            order_id=order_record.order_id,
            signal_id=request.signal_id,
        )
        position_record = self.positions.open_position(position)

        self.fills.record_fill(
            fill,
            account_id=request.account_id,
            position_id=position_record.position_id,
        )
        self.orders.record_fill_on_order(
            order_id=order_record.order_id,
            quantity=fill.quantity,
            price=fill.price,
            filled_at_utc=bar.timestamp_utc,
        )

        self._apply_commission(account, fill.commission, bar.timestamp_utc)

        return PaperExecutionResult(
            accepted=True,
            request=request,
            account_state=self.build_account_state(
                account,
                updated_at_utc=bar.timestamp_utc,
            ),
            order=order_record.to_contract(),
            fills=(fill,),
            position=position_record.to_contract(),
        )

    def _execute_close(
        self,
        request: PaperExecutionRequest,
        account: TradingAccount,
        bar: PaperMarketBar,
    ) -> PaperExecutionResult:
        open_positions = self.positions.list_open_positions(
            account_id=request.account_id,
            symbol=request.symbol,
        )

        if not open_positions:
            return self._reject(
                request,
                account,
                PaperRejectionReason.NO_OPEN_POSITION,
                f"No open {request.symbol} position on account "
                f"{request.account_id}.",
            )

        position_record = open_positions[0]
        open_quantity = position_record.to_contract().open_quantity

        # Partial closes are not simulated yet, so a mismatched quantity is
        # refused rather than quietly closing more than the caller asked for.
        if abs(request.quantity - open_quantity) > 1e-9:
            return self._reject(
                request,
                account,
                PaperRejectionReason.INVALID_QUANTITY,
                f"Close quantity {request.quantity} must match the open "
                f"quantity {open_quantity}.",
            )

        order_record = self._create_order(request, PaperOrderStatus.ACCEPTED)

        reference = self._reference_price(request, bar)
        buying = is_buy_fill(request.action, position_record.side)
        fill_price = calculate_fill_price(reference, buying, self.config)

        outcome = self.close_position(
            position_record=position_record,
            account=account,
            exit_price=fill_price,
            exit_reason=PaperExitReason.MANUAL_CLOSE,
            closed_at_utc=bar.timestamp_utc,
            order_record=order_record,
        )

        fill_records = self.fills.list_fills(order_id=order_record.order_id)

        return PaperExecutionResult(
            accepted=True,
            request=request,
            account_state=self.build_account_state(
                account,
                updated_at_utc=bar.timestamp_utc,
            ),
            order=self.orders.require_order(order_record.order_id).to_contract(),
            fills=tuple(record.to_contract() for record in fill_records),
            position=outcome.position.to_contract(),
            trade=outcome.trade.to_contract(),
        )

    def close_position(
        self,
        position_record: PaperPositionRecord,
        account: TradingAccount,
        exit_price: float,
        exit_reason: PaperExitReason,
        closed_at_utc: datetime,
        order_record: PaperOrderRecord | None = None,
    ) -> PaperCloseOutcome:
        """Close a position in full and book the resulting trade."""

        if not position_record.to_contract().is_open:
            raise PaperTradingError(
                f"Position {position_record.position_id} is already closed."
            )

        quantity = as_amount(position_record.quantity) - as_amount(
            position_record.closed_quantity
        )
        commission = self.config.commission_per_fill

        gross_pnl = calculate_gross_pnl(
            side=position_record.side,
            entry_price=as_amount(position_record.entry_price),
            exit_price=exit_price,
            quantity=quantity,
            point_value=self.config.contract_size,
        )

        # A stop, a target and an end-of-data flatten are all still executions,
        # so each gets its own order rather than a fill with nothing behind it.
        exit_order = order_record or self._create_exit_order(
            position_record=position_record,
            account=account,
            quantity=quantity,
            exit_reason=exit_reason,
            at_utc=closed_at_utc,
        )

        self.fills.record_fill(
            PaperFill(
                fill_id=build_entity_id("paperfill"),
                order_id=exit_order.order_id,
                quantity=quantity,
                price=exit_price,
                filled_at_utc=closed_at_utc,
                commission=commission,
            ),
            account_id=position_record.account_id,
            position_id=position_record.position_id,
        )
        self.orders.record_fill_on_order(
            order_id=exit_order.order_id,
            quantity=quantity,
            price=exit_price,
            filled_at_utc=closed_at_utc,
        )

        net_pnl = gross_pnl - commission

        self._apply_realized_pnl(account, net_pnl, closed_at_utc)

        closed = self.positions.close_position(
            position_id=position_record.position_id,
            closed_quantity=quantity,
            realized_pnl=net_pnl,
            closed_at_utc=closed_at_utc,
        )

        trade = PaperTrade(
            trade_id=build_entity_id("papertrade"),
            position_id=closed.position_id,
            account_id=closed.account_id,
            symbol=closed.symbol,
            side=closed.side,
            quantity=quantity,
            entry_price=as_amount(closed.entry_price),
            exit_price=exit_price,
            opened_at_utc=closed.opened_at_utc,
            closed_at_utc=closed_at_utc,
            gross_pnl=gross_pnl,
            commission=commission,
            risk_amount=self._risk_amount(closed, quantity),
            reward_amount=self._reward_amount(closed, quantity),
            balance_after=as_amount(account.current_balance),
            signal_id=closed.signal_id,
        )
        trade_record = self.trades.record_trade(trade, exit_reason=exit_reason)

        return PaperCloseOutcome(
            position=closed,
            trade=trade_record,
            exit_reason=exit_reason,
            exit_price=exit_price,
        )

    # -- bar processing ---------------------------------------------------

    def process_bar(
        self,
        account: TradingAccount,
        bar: PaperMarketBar,
    ) -> tuple[PaperCloseOutcome, ...]:
        """
        Apply one bar to every open position and close those that hit a level.

        Exit prices are the stop or target itself: a gap through the level is a
        separate modelling question, and inventing a better price here would
        flatter results.
        """

        outcomes: list[PaperCloseOutcome] = []

        for position_record in self.positions.list_open_positions(
            account_id=account.account_id,
            symbol=bar.symbol,
        ):
            decision = resolve_position_exit(
                position_record.to_contract(),
                bar,
                self.config,
            )

            if not decision.should_exit or decision.exit_price is None:
                continue

            outcomes.append(
                self.close_position(
                    position_record=position_record,
                    account=account,
                    exit_price=decision.exit_price,
                    exit_reason=decision.exit_reason or PaperExitReason.STOP_LOSS,
                    closed_at_utc=bar.timestamp_utc,
                )
            )

        return tuple(outcomes)

    def close_all_positions(
        self,
        account: TradingAccount,
        bar: PaperMarketBar,
        exit_reason: PaperExitReason = PaperExitReason.END_OF_DATA,
    ) -> tuple[PaperCloseOutcome, ...]:
        """
        Flatten every open position on the account at the given bar.

        Used when the data feed ends: leaving positions open would hide their
        outcome from the trade history entirely.
        """

        outcomes: list[PaperCloseOutcome] = []

        for position_record in self.positions.list_open_positions(
            account_id=account.account_id,
        ):
            if position_record.symbol != bar.symbol:
                continue

            side = position_record.side
            buying = is_buy_fill(PaperAction.CLOSE, side)
            exit_price = calculate_fill_price(bar.close, buying, self.config)

            outcomes.append(
                self.close_position(
                    position_record=position_record,
                    account=account,
                    exit_price=exit_price,
                    exit_reason=exit_reason,
                    closed_at_utc=bar.timestamp_utc,
                )
            )

        return tuple(outcomes)

    # -- internals --------------------------------------------------------

    def _reference_price(
        self,
        request: PaperExecutionRequest,
        bar: PaperMarketBar,
    ) -> float:
        if (
            request.order_type != PaperOrderType.MARKET
            and request.requested_price is not None
        ):
            return request.requested_price

        return resolve_reference_price(bar, self.config)

    def _create_order(
        self,
        request: PaperExecutionRequest,
        status: PaperOrderStatus,
        rejection_reason: PaperRejectionReason | None = None,
        rejection_message: str | None = None,
    ) -> PaperOrderRecord:
        order = PaperOrder(
            order_id=build_entity_id("paperorder"),
            account_id=request.account_id,
            user_id=request.user_id,
            symbol=request.symbol,
            action=request.action,
            order_type=request.order_type,
            quantity=request.quantity,
            status=status,
            created_at_utc=request.submitted_at_utc,
            updated_at_utc=request.submitted_at_utc,
            signal_id=request.signal_id,
            requested_price=request.requested_price,
            stop_loss=request.stop_loss,
            take_profit=request.take_profit,
            rejection_reason=rejection_reason,
            rejection_message=rejection_message,
            extra_metadata=dict(request.extra_metadata),
        )

        return self.orders.create_order(order)

    def _create_exit_order(
        self,
        position_record: PaperPositionRecord,
        account: TradingAccount,
        quantity: float,
        exit_reason: PaperExitReason,
        at_utc: datetime,
    ) -> PaperOrderRecord:
        """Book the broker-generated order behind an automatic exit."""

        order = PaperOrder(
            order_id=build_entity_id("paperorder"),
            account_id=position_record.account_id,
            user_id=account.user_id,
            symbol=position_record.symbol,
            action=PaperAction.CLOSE,
            order_type=PaperOrderType.MARKET,
            quantity=quantity,
            status=PaperOrderStatus.ACCEPTED,
            created_at_utc=at_utc,
            updated_at_utc=at_utc,
            signal_id=position_record.signal_id,
            extra_metadata={
                "generated_by": "paper_execution_service",
                "exit_reason": exit_reason.value,
                "position_id": position_record.position_id,
            },
        )

        return self.orders.create_order(order)

    def _reject(
        self,
        request: PaperExecutionRequest,
        account: TradingAccount,
        reason: PaperRejectionReason | None,
        message: str,
        eligibility: PaperExecutionEligibilityDecision | None = None,
    ) -> PaperExecutionResult:
        if reason is None:
            raise PaperTradingError("A rejection must carry a reason.")

        order_contract: PaperOrder | None = None

        if self._can_persist_rejection(request, account, reason):
            order_contract = self._create_order(
                request,
                PaperOrderStatus.REJECTED,
                rejection_reason=reason,
                rejection_message=message,
            ).to_contract()

        return PaperExecutionResult(
            accepted=False,
            request=request,
            account_state=self.build_account_state(
                account,
                updated_at_utc=request.submitted_at_utc,
            ),
            order=order_contract,
            rejection_reason=reason,
            rejection_message=message,
            extra_metadata=(
                {"eligibility": eligibility.to_dict()}
                if eligibility is not None
                else {}
            ),
        )

    def _can_persist_rejection(
        self,
        request: PaperExecutionRequest,
        account: TradingAccount,
        reason: PaperRejectionReason,
    ) -> bool:
        if reason in UNPERSISTABLE_REJECTION_REASONS:
            return False

        if request.quantity <= 0:
            return False

        if request.account_id != account.account_id:
            return False

        # A rejected order still lands in paper_orders, so the account behind it
        # must genuinely be a paper account.
        return validate_paper_account(account).accepted

    def _apply_commission(
        self,
        account: TradingAccount,
        commission: float,
        at_utc: datetime,
    ) -> None:
        if commission <= 0:
            return

        self._apply_realized_pnl(account, -commission, at_utc)

    def _apply_realized_pnl(
        self,
        account: TradingAccount,
        amount: float,
        at_utc: datetime,
    ) -> None:
        """
        Move the paper account balance.

        Balances are floored at zero because the column refuses negatives; a
        blown paper account stops at zero rather than failing the write.
        """

        account.current_balance = max(0.0, as_amount(account.current_balance) + amount)
        account.equity = max(0.0, as_amount(account.equity) + amount)
        account.updated_at_utc = at_utc

        self.session.flush()

    def _risk_amount(
        self,
        position: PaperPositionRecord,
        quantity: float,
    ) -> float | None:
        """Risk in currency, or None when the position carried no stop."""

        if position.stop_loss is None:
            return None

        distance = abs(
            as_amount(position.entry_price) - as_amount(position.stop_loss)
        )

        return distance * quantity * self.config.contract_size

    def _reward_amount(
        self,
        position: PaperPositionRecord,
        quantity: float,
    ) -> float | None:
        """Planned reward in currency, or None when there was no target."""

        if position.take_profit is None:
            return None

        distance = abs(
            as_amount(position.take_profit) - as_amount(position.entry_price)
        )

        return distance * quantity * self.config.contract_size


def build_paper_simulator_config(
    spread_points: float = 0.0,
    slippage_points: float = 0.0,
    commission_per_fill: float = 0.0,
    point_size: float = 1.0,
    contract_size: float = 1.0,
    intrabar_exit_policy: IntrabarExitPolicy = IntrabarExitPolicy.STOP_LOSS_FIRST,
    fill_on_bar_open: bool = True,
) -> PaperSimulatorConfig:
    return PaperSimulatorConfig(
        spread_points=spread_points,
        slippage_points=slippage_points,
        commission_per_fill=commission_per_fill,
        point_size=point_size,
        contract_size=contract_size,
        intrabar_exit_policy=intrabar_exit_policy,
        fill_on_bar_open=fill_on_bar_open,
    )


__all__ = [
    "AQOS_PAPER_EXECUTION_SERVICE_VERSION",
    "PaperCloseOutcome",
    "PaperExecutionService",
    "REJECTION_REASON_BY_CODE",
    "REQUIRED_PAPER_EXECUTION_MODES",
    "UNPERSISTABLE_REJECTION_REASONS",
    "build_paper_simulator_config",
    "rejection_reason_for_code",
]
