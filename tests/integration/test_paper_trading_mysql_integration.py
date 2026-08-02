"""
Persisted paper trading execution against real MySQL 8.

Run with::

    AQOS_TEST_DB_URL=mysql+pymysql://user:password@localhost:3306/aqos_test \\
        pytest -m mysql
"""

from __future__ import annotations

import os
from datetime import datetime, timedelta

import pytest
from sqlalchemy import text
from sqlalchemy.exc import DatabaseError, IntegrityError

from aqos.account_analytics.metrics import calculate_trade_metrics
from aqos.accounts.models import AccountStatus, AccountType, BrokerKind
from aqos.accounts.repositories import TradingAccountRepository
from aqos.database.config import parse_database_url
from aqos.database.engine import AqosDatabase
from aqos.database.migration_runner import apply_migrations
from aqos.database.procedures import StoredProcedureService
from aqos.execution_policy.modes import (
    ExecutionConstraint,
    ExecutionConstraintSource,
    ExecutionMode,
)
from aqos.paper_trading.contracts import (
    PaperAction,
    PaperExecutionRequest,
    PaperOrderStatus,
    PaperOrderType,
    PaperPositionStatus,
    PaperRejectionReason,
    PaperSide,
)
from aqos.paper_trading.execution_service import PaperExecutionService
from aqos.paper_trading.repositories import (
    PaperFillRepository,
    PaperOrderRepository,
    PaperPositionRepository,
    PaperTradeRepository,
)
from aqos.paper_trading.simulator import (
    PaperExitReason,
    PaperMarketBar,
    PaperSimulatorConfig,
)
from aqos.signals.models import SignalAction, SignalSource
from aqos.signals.repositories import TradingSignalRepository
from aqos.users.repositories import UserProfileRepository


ENV_TEST_DB_URL = "AQOS_TEST_DB_URL"

FIXED_NOW = datetime(2026, 1, 1, 0, 0, 0)

#: Every constraint permits auto trade, so the resolver's ceiling is not what
#: a test is measuring unless it says so explicitly.
PERMISSIVE_CONSTRAINTS = (
    ExecutionConstraint(
        source=ExecutionConstraintSource.USER_SETTINGS,
        ceiling=ExecutionMode.AUTO_TRADE,
    ),
    ExecutionConstraint(
        source=ExecutionConstraintSource.ACCOUNT,
        ceiling=ExecutionMode.AUTO_TRADE,
    ),
)

pytestmark = pytest.mark.mysql


def requires_mysql() -> str:
    url = os.environ.get(ENV_TEST_DB_URL, "").strip()

    if not url:
        pytest.skip(
            f"{ENV_TEST_DB_URL} is not set, so persisted paper trading is NOT "
            "verified against MySQL by this run. Run it with:\n"
            "  AQOS_TEST_DB_URL=mysql+pymysql://user:password@localhost:3306/"
            "aqos_test pytest -m mysql"
        )

    return url


def reset_tables(database: AqosDatabase) -> None:
    with database.session() as session:
        session.execute(text("SET FOREIGN_KEY_CHECKS = 0"))

        for table in (
            "paper_account_snapshots",
            "paper_trades",
            "paper_fills",
            "paper_positions",
            "paper_orders",
            "account_performance_reports",
            "account_analytics_snapshots",
            "signal_reasons",
            "signal_events",
            "trading_signals",
            "funded_account_rules",
            "funded_rule_templates",
            "trading_accounts",
            "symbol_preferences",
            "trading_settings",
            "user_preferences",
            "user_sessions",
            "user_credentials",
            "user_profiles",
        ):
            session.execute(text(f"TRUNCATE TABLE {table}"))

        session.execute(text("SET FOREIGN_KEY_CHECKS = 1"))


@pytest.fixture
def paper_database() -> AqosDatabase:
    url = requires_mysql()
    database = AqosDatabase(config=parse_database_url(url))

    if not database.ping():
        database.dispose()
        pytest.skip("MySQL server is not reachable; paper trading NOT verified.")

    apply_migrations(database)
    reset_tables(database)

    yield database

    reset_tables(database)
    database.dispose()


@pytest.fixture
def user_id(paper_database) -> str:
    with paper_database.session() as session:
        return UserProfileRepository(session).create_user(
            email="paper@example.com",
            display_name="Paper Trader",
            created_at_utc=FIXED_NOW,
        ).user_id


@pytest.fixture
def paper_account_id(paper_database, user_id: str) -> str:
    with paper_database.session() as session:
        return TradingAccountRepository(session).create_account(
            user_id=user_id,
            name="Paper One",
            account_type=AccountType.PAPER,
            broker=BrokerKind.INTERNAL_PAPER,
            initial_balance=10_000.0,
            execution_mode=ExecutionMode.AUTO_TRADE,
            auto_trade_enabled=True,
            created_at_utc=FIXED_NOW,
        ).account_id


def build_bar(
    open_price: float = 100.0,
    high: float = 105.0,
    low: float = 95.0,
    close: float = 102.0,
    symbol: str = "XAUUSD",
    minutes: int = 0,
) -> PaperMarketBar:
    return PaperMarketBar(
        symbol=symbol,
        timestamp_utc=FIXED_NOW + timedelta(minutes=minutes),
        open=open_price,
        high=high,
        low=low,
        close=close,
        volume=1_000.0,
    )


def build_request(
    user_id: str,
    account_id: str,
    action: PaperAction = PaperAction.BUY,
    quantity: float = 2.0,
    signal_id: str | None = None,
    stop_loss: float | None = None,
    take_profit: float | None = None,
    symbol: str = "XAUUSD",
    minutes: int = 0,
) -> PaperExecutionRequest:
    return PaperExecutionRequest(
        user_id=user_id,
        account_id=account_id,
        symbol=symbol,
        action=action,
        quantity=quantity,
        order_type=PaperOrderType.MARKET,
        submitted_at_utc=FIXED_NOW + timedelta(minutes=minutes),
        signal_id=signal_id,
        stop_loss=stop_loss,
        take_profit=take_profit,
    )


def create_signal(session, user_id: str, account_id: str, symbol: str = "XAUUSD"):
    return TradingSignalRepository(session).create_signal(
        user_id=user_id,
        account_id=account_id,
        symbol=symbol,
        timeframe="H1",
        action=SignalAction.BUY,
        source=SignalSource.MANUAL,
        generated_at_utc=FIXED_NOW,
    )


class TestSchema:
    def test_paper_tables_exist(self, paper_database) -> None:
        with paper_database.read_session() as session:
            rows = session.execute(
                text(
                    "SELECT TABLE_NAME FROM information_schema.TABLES "
                    "WHERE TABLE_SCHEMA = DATABASE()"
                )
            ).all()

        tables = {str(row[0]) for row in rows}

        assert {
            "paper_orders",
            "paper_positions",
            "paper_fills",
            "paper_trades",
            "paper_account_snapshots",
        } <= tables

    def test_paper_procedures_exist(self, paper_database) -> None:
        procedures = StoredProcedureService(paper_database).list_procedures()

        assert "sp_aqos_paper_open_position_count" in procedures
        assert "sp_aqos_paper_trade_summary" in procedures
        assert "sp_aqos_paper_exit_reason_counts" in procedures


class TestExecutionLifecycle:
    def test_a_signal_becomes_an_order_a_fill_and_a_position(
        self,
        paper_database,
        user_id,
        paper_account_id,
    ) -> None:
        with paper_database.session() as session:
            signal = create_signal(session, user_id, paper_account_id)
            account = TradingAccountRepository(session).require(paper_account_id)

            result = PaperExecutionService(session).execute(
                request=build_request(
                    user_id,
                    paper_account_id,
                    signal_id=signal.signal_id,
                    stop_loss=96.0,
                    take_profit=110.0,
                ),
                account=account,
                bar=build_bar(),
                constraints=PERMISSIVE_CONSTRAINTS,
            )

            assert result.accepted is True
            order_id = result.order.order_id
            position_id = result.position.position_id
            signal_id = signal.signal_id

        with paper_database.read_session() as session:
            order = PaperOrderRepository(session).require_order(order_id)
            position = PaperPositionRepository(session).require_position(
                position_id
            )
            fills = PaperFillRepository(session).list_fills(order_id=order_id)

            assert order.status == PaperOrderStatus.FILLED
            assert float(order.filled_quantity) == pytest.approx(2.0)
            assert float(order.average_fill_price) == pytest.approx(100.0)
            assert order.signal_id == signal_id
            assert position.status == PaperPositionStatus.OPEN
            assert position.side == PaperSide.LONG
            assert float(position.entry_price) == pytest.approx(100.0)
            assert position.order_id == order_id
            assert len(fills) == 1
            assert float(fills[0].price) == pytest.approx(100.0)

    def test_costs_move_the_fill_price_against_the_trader(
        self,
        paper_database,
        user_id,
        paper_account_id,
    ) -> None:
        config = PaperSimulatorConfig(spread_points=1.0, slippage_points=0.5)

        with paper_database.session() as session:
            account = TradingAccountRepository(session).require(paper_account_id)

            long_result = PaperExecutionService(session, config).execute(
                request=build_request(user_id, paper_account_id),
                account=account,
                bar=build_bar(),
                constraints=PERMISSIVE_CONSTRAINTS,
            )
            short_result = PaperExecutionService(session, config).execute(
                request=build_request(
                    user_id,
                    paper_account_id,
                    action=PaperAction.SELL,
                    symbol="EURUSD",
                    minutes=1,
                ),
                account=account,
                bar=build_bar(symbol="EURUSD", minutes=1),
                constraints=PERMISSIVE_CONSTRAINTS,
            )

            assert long_result.position.entry_price == pytest.approx(101.5)
            assert short_result.position.entry_price == pytest.approx(98.5)

    def test_a_take_profit_closes_the_position_and_books_a_trade(
        self,
        paper_database,
        user_id,
        paper_account_id,
    ) -> None:
        with paper_database.session() as session:
            account = TradingAccountRepository(session).require(paper_account_id)
            service = PaperExecutionService(session)

            opened = service.execute(
                request=build_request(
                    user_id,
                    paper_account_id,
                    stop_loss=90.0,
                    take_profit=110.0,
                ),
                account=account,
                bar=build_bar(),
                constraints=PERMISSIVE_CONSTRAINTS,
            )
            position_id = opened.position.position_id

            outcomes = service.process_bar(
                account,
                build_bar(open_price=105.0, high=112.0, low=104.0, close=111.0,
                          minutes=60),
            )

            assert len(outcomes) == 1
            assert outcomes[0].exit_reason == PaperExitReason.TAKE_PROFIT
            trade_id = outcomes[0].trade.trade_id

        with paper_database.read_session() as session:
            position = PaperPositionRepository(session).require_position(
                position_id
            )
            trade = PaperTradeRepository(session).require(trade_id)

            assert position.status == PaperPositionStatus.CLOSED
            assert position.closed_at_utc == FIXED_NOW + timedelta(minutes=60)
            assert float(position.realized_pnl) == pytest.approx(20.0)
            assert trade.exit_reason == PaperExitReason.TAKE_PROFIT
            assert float(trade.exit_price) == pytest.approx(110.0)
            assert float(trade.gross_pnl) == pytest.approx(20.0)
            assert float(trade.net_pnl) == pytest.approx(20.0)
            assert float(trade.risk_amount) == pytest.approx(20.0)
            assert float(trade.reward_amount) == pytest.approx(20.0)

    def test_a_stop_loss_closes_the_position_at_the_stop(
        self,
        paper_database,
        user_id,
        paper_account_id,
    ) -> None:
        with paper_database.session() as session:
            account = TradingAccountRepository(session).require(paper_account_id)
            service = PaperExecutionService(session)

            service.execute(
                request=build_request(
                    user_id,
                    paper_account_id,
                    stop_loss=96.0,
                    take_profit=200.0,
                ),
                account=account,
                bar=build_bar(),
                constraints=PERMISSIVE_CONSTRAINTS,
            )

            outcomes = service.process_bar(
                account,
                build_bar(open_price=99.0, high=100.0, low=94.0, close=95.0,
                          minutes=60),
            )

            assert len(outcomes) == 1
            assert outcomes[0].exit_reason == PaperExitReason.STOP_LOSS
            assert outcomes[0].exit_price == pytest.approx(96.0)
            assert float(outcomes[0].trade.net_pnl) == pytest.approx(-8.0)
            assert float(account.current_balance) == pytest.approx(9_992.0)

    def test_a_manual_close_books_a_trade(
        self,
        paper_database,
        user_id,
        paper_account_id,
    ) -> None:
        with paper_database.session() as session:
            account = TradingAccountRepository(session).require(paper_account_id)
            service = PaperExecutionService(session)

            service.execute(
                request=build_request(user_id, paper_account_id),
                account=account,
                bar=build_bar(),
                constraints=PERMISSIVE_CONSTRAINTS,
            )

            closed = service.execute(
                request=build_request(
                    user_id,
                    paper_account_id,
                    action=PaperAction.CLOSE,
                    minutes=30,
                ),
                account=account,
                bar=build_bar(open_price=108.0, high=109.0, low=107.0,
                              close=108.5, minutes=30),
                constraints=PERMISSIVE_CONSTRAINTS,
            )

            assert closed.accepted is True
            assert closed.trade is not None
            assert closed.trade.gross_pnl == pytest.approx(16.0)
            assert closed.position.status == PaperPositionStatus.CLOSED

        with paper_database.read_session() as session:
            trades = PaperTradeRepository(session).list_trades(
                account_id=paper_account_id
            )

            assert len(trades) == 1
            assert trades[0].exit_reason == PaperExitReason.MANUAL_CLOSE

    def test_end_of_data_flattens_open_positions(
        self,
        paper_database,
        user_id,
        paper_account_id,
    ) -> None:
        """A position left open at the end of the feed must still be reported."""

        with paper_database.session() as session:
            account = TradingAccountRepository(session).require(paper_account_id)
            service = PaperExecutionService(session)

            service.execute(
                request=build_request(user_id, paper_account_id),
                account=account,
                bar=build_bar(),
                constraints=PERMISSIVE_CONSTRAINTS,
            )

            outcomes = service.close_all_positions(
                account,
                build_bar(open_price=103.0, high=104.0, low=102.0, close=103.5,
                          minutes=120),
            )

            assert len(outcomes) == 1
            assert outcomes[0].exit_reason == PaperExitReason.END_OF_DATA
            assert outcomes[0].exit_price == pytest.approx(103.5)

        with paper_database.read_session() as session:
            assert PaperPositionRepository(session).list_open_positions(
                account_id=paper_account_id
            ) == ()
            assert PaperTradeRepository(session).count_by_exit_reason(
                paper_account_id
            ) == {"end_of_data": 1}

    def test_commission_is_charged_on_every_fill(
        self,
        paper_database,
        user_id,
        paper_account_id,
    ) -> None:
        config = PaperSimulatorConfig(commission_per_fill=3.0)

        with paper_database.session() as session:
            account = TradingAccountRepository(session).require(paper_account_id)
            service = PaperExecutionService(session, config)

            service.execute(
                request=build_request(user_id, paper_account_id),
                account=account,
                bar=build_bar(),
                constraints=PERMISSIVE_CONSTRAINTS,
            )
            outcomes = service.close_all_positions(
                account,
                build_bar(open_price=100.0, high=101.0, low=99.0, close=100.0,
                          minutes=60),
            )

            trade = outcomes[0].trade

            assert float(trade.gross_pnl) == pytest.approx(0.0)
            assert float(trade.commission) == pytest.approx(3.0)
            assert float(trade.net_pnl) == pytest.approx(-3.0)
            # Entry commission plus exit commission.
            assert float(account.current_balance) == pytest.approx(9_994.0)

        with paper_database.read_session() as session:
            assert PaperFillRepository(session).total_commission(
                paper_account_id
            ) == pytest.approx(6.0)

    def test_an_automatic_exit_books_its_own_order_and_fill(
        self,
        paper_database,
        user_id,
        paper_account_id,
    ) -> None:
        """A stop or target exit is an execution, so it leaves a full record."""

        with paper_database.session() as session:
            account = TradingAccountRepository(session).require(paper_account_id)
            service = PaperExecutionService(session)

            opened = service.execute(
                request=build_request(
                    user_id,
                    paper_account_id,
                    take_profit=110.0,
                ),
                account=account,
                bar=build_bar(),
                constraints=PERMISSIVE_CONSTRAINTS,
            )
            entry_order_id = opened.order.order_id

            service.process_bar(
                account,
                build_bar(open_price=105.0, high=112.0, low=104.0, close=111.0,
                          minutes=60),
            )

        with paper_database.read_session() as session:
            orders = PaperOrderRepository(session).list_orders(
                account_id=paper_account_id
            )
            fills = PaperFillRepository(session).list_fills(
                account_id=paper_account_id
            )

            exit_orders = [
                order for order in orders if order.order_id != entry_order_id
            ]

            assert len(orders) == 2
            assert len(exit_orders) == 1
            assert exit_orders[0].action == PaperAction.CLOSE
            assert exit_orders[0].status == PaperOrderStatus.FILLED
            assert exit_orders[0].extra_metadata["exit_reason"] == "take_profit"
            assert exit_orders[0].extra_metadata["generated_by"] == (
                "paper_execution_service"
            )
            assert len(fills) == 2
            assert {float(fill.price) for fill in fills} == {100.0, 110.0}


class TestSafetyRails:
    def test_a_non_paper_account_is_rejected_and_writes_nothing(
        self,
        paper_database,
        user_id,
    ) -> None:
        """Simulated fills must never be booked against real capital."""

        with paper_database.session() as session:
            live_account = TradingAccountRepository(session).create_account(
                user_id=user_id,
                name="Live One",
                account_type=AccountType.LIVE,
                broker=BrokerKind.MT5,
                initial_balance=10_000.0,
                created_at_utc=FIXED_NOW,
            )

            result = PaperExecutionService(session).execute(
                request=build_request(user_id, live_account.account_id),
                account=live_account,
                bar=build_bar(),
                constraints=PERMISSIVE_CONSTRAINTS,
            )
            live_account_id = live_account.account_id

        assert result.accepted is False
        assert result.rejection_reason == PaperRejectionReason.ACCOUNT_NOT_PAPER
        assert result.order is None

        with paper_database.read_session() as session:
            assert PaperOrderRepository(session).list_orders(
                account_id=live_account_id
            ) == ()

    @pytest.mark.parametrize(
        "status",
        [AccountStatus.SUSPENDED, AccountStatus.ARCHIVED],
    )
    def test_an_inactive_paper_account_is_rejected(
        self,
        paper_database,
        user_id,
        paper_account_id,
        status: AccountStatus,
    ) -> None:
        with paper_database.session() as session:
            accounts = TradingAccountRepository(session)
            account = accounts.require(paper_account_id)
            account.status = status
            session.flush()

            result = PaperExecutionService(session).execute(
                request=build_request(user_id, paper_account_id),
                account=account,
                bar=build_bar(),
                constraints=PERMISSIVE_CONSTRAINTS,
            )

            assert result.accepted is False
            assert result.rejection_reason == (
                PaperRejectionReason.ACCOUNT_NOT_ACTIVE
            )
            assert result.order is None

    def test_a_signal_may_only_execute_once_per_account(
        self,
        paper_database,
        user_id,
        paper_account_id,
    ) -> None:
        with paper_database.session() as session:
            signal = create_signal(session, user_id, paper_account_id)
            account = TradingAccountRepository(session).require(paper_account_id)
            service = PaperExecutionService(session)

            first = service.execute(
                request=build_request(
                    user_id,
                    paper_account_id,
                    signal_id=signal.signal_id,
                ),
                account=account,
                bar=build_bar(),
                constraints=PERMISSIVE_CONSTRAINTS,
            )
            second = service.execute(
                request=build_request(
                    user_id,
                    paper_account_id,
                    signal_id=signal.signal_id,
                    minutes=5,
                ),
                account=account,
                bar=build_bar(minutes=5),
                constraints=PERMISSIVE_CONSTRAINTS,
            )

            assert first.accepted is True
            assert second.accepted is False
            assert second.rejection_reason == (
                PaperRejectionReason.DUPLICATE_EXECUTION
            )
            # The rejection is recorded, so the refusal is auditable.
            assert second.order is not None
            assert second.order.status == PaperOrderStatus.REJECTED

        with paper_database.read_session() as session:
            positions = PaperPositionRepository(session).list_positions(
                account_id=paper_account_id
            )

            assert len(positions) == 1

    def test_an_execution_ceiling_below_order_capability_blocks_the_order(
        self,
        paper_database,
        user_id,
        paper_account_id,
    ) -> None:
        with paper_database.session() as session:
            account = TradingAccountRepository(session).require(paper_account_id)

            result = PaperExecutionService(session).execute(
                request=build_request(user_id, paper_account_id),
                account=account,
                bar=build_bar(),
                constraints=(
                    ExecutionConstraint(
                        source=ExecutionConstraintSource.USER_SETTINGS,
                        ceiling=ExecutionMode.AUTO_TRADE,
                    ),
                    ExecutionConstraint(
                        source=ExecutionConstraintSource.MODEL_PROMOTION,
                        ceiling=ExecutionMode.SIGNAL_ONLY,
                        reason="Model is not promoted.",
                    ),
                ),
            )

            assert result.accepted is False
            assert result.rejection_reason == (
                PaperRejectionReason.EXECUTION_NOT_ALLOWED
            )
            assert "model_promotion=signal_only" in result.rejection_message

        with paper_database.read_session() as session:
            assert PaperPositionRepository(session).list_positions(
                account_id=paper_account_id
            ) == ()

    def test_manual_approval_still_allows_a_paper_order(
        self,
        paper_database,
        user_id,
        paper_account_id,
    ) -> None:
        with paper_database.session() as session:
            account = TradingAccountRepository(session).require(paper_account_id)

            result = PaperExecutionService(session).execute(
                request=build_request(user_id, paper_account_id),
                account=account,
                bar=build_bar(),
                constraints=(
                    ExecutionConstraint(
                        source=ExecutionConstraintSource.ACCOUNT,
                        ceiling=ExecutionMode.MANUAL_APPROVAL,
                    ),
                ),
            )

            assert result.accepted is True

    def test_executing_with_no_constraints_is_refused_outright(
        self,
        paper_database,
        user_id,
        paper_account_id,
    ) -> None:
        """An unchecked execution path must not be reachable by omission."""

        with paper_database.session() as session:
            account = TradingAccountRepository(session).require(paper_account_id)

            with pytest.raises(ValueError, match="At least one execution constraint"):
                PaperExecutionService(session).execute(
                    request=build_request(user_id, paper_account_id),
                    account=account,
                    bar=build_bar(),
                    constraints=(),
                )

    def test_a_wrong_side_stop_loss_is_rejected(
        self,
        paper_database,
        user_id,
        paper_account_id,
    ) -> None:
        with paper_database.session() as session:
            account = TradingAccountRepository(session).require(paper_account_id)

            request = PaperExecutionRequest(
                user_id=user_id,
                account_id=paper_account_id,
                symbol="XAUUSD",
                action=PaperAction.BUY,
                quantity=1.0,
                order_type=PaperOrderType.LIMIT,
                submitted_at_utc=FIXED_NOW,
                requested_price=100.0,
                stop_loss=105.0,
            )

            result = PaperExecutionService(session).execute(
                request=request,
                account=account,
                bar=build_bar(),
                constraints=PERMISSIVE_CONSTRAINTS,
            )

            assert result.accepted is False
            assert result.rejection_reason == PaperRejectionReason.INVALID_PRICE
            assert "below the entry price" in result.rejection_message

    def test_a_bar_for_the_wrong_symbol_is_rejected(
        self,
        paper_database,
        user_id,
        paper_account_id,
    ) -> None:
        with paper_database.session() as session:
            account = TradingAccountRepository(session).require(paper_account_id)

            result = PaperExecutionService(session).execute(
                request=build_request(user_id, paper_account_id),
                account=account,
                bar=build_bar(symbol="EURUSD"),
                constraints=PERMISSIVE_CONSTRAINTS,
            )

            assert result.accepted is False
            assert result.rejection_reason == PaperRejectionReason.INVALID_SYMBOL
            assert result.order is None

    def test_closing_without_a_position_is_rejected(
        self,
        paper_database,
        user_id,
        paper_account_id,
    ) -> None:
        with paper_database.session() as session:
            account = TradingAccountRepository(session).require(paper_account_id)

            result = PaperExecutionService(session).execute(
                request=build_request(
                    user_id,
                    paper_account_id,
                    action=PaperAction.CLOSE,
                ),
                account=account,
                bar=build_bar(),
                constraints=PERMISSIVE_CONSTRAINTS,
            )

            assert result.accepted is False
            assert result.rejection_reason == (
                PaperRejectionReason.NO_OPEN_POSITION
            )

    def test_a_partial_close_quantity_is_refused(
        self,
        paper_database,
        user_id,
        paper_account_id,
    ) -> None:
        with paper_database.session() as session:
            account = TradingAccountRepository(session).require(paper_account_id)
            service = PaperExecutionService(session)

            service.execute(
                request=build_request(user_id, paper_account_id, quantity=2.0),
                account=account,
                bar=build_bar(),
                constraints=PERMISSIVE_CONSTRAINTS,
            )

            result = service.execute(
                request=build_request(
                    user_id,
                    paper_account_id,
                    action=PaperAction.CLOSE,
                    quantity=1.0,
                    minutes=10,
                ),
                account=account,
                bar=build_bar(minutes=10),
                constraints=PERMISSIVE_CONSTRAINTS,
            )

            assert result.accepted is False
            assert result.rejection_reason == (
                PaperRejectionReason.INVALID_QUANTITY
            )

    def test_a_rejection_after_a_cancelled_signal_order_is_allowed_to_retry(
        self,
        paper_database,
        user_id,
        paper_account_id,
    ) -> None:
        """A refused attempt never consumed the signal, so retrying is fine."""

        with paper_database.session() as session:
            signal = create_signal(session, user_id, paper_account_id)
            account = TradingAccountRepository(session).require(paper_account_id)
            service = PaperExecutionService(session)

            blocked = service.execute(
                request=build_request(
                    user_id,
                    paper_account_id,
                    signal_id=signal.signal_id,
                ),
                account=account,
                bar=build_bar(),
                constraints=(
                    ExecutionConstraint(
                        source=ExecutionConstraintSource.RISK_ENGINE,
                        ceiling=ExecutionMode.SIGNAL_ONLY,
                    ),
                ),
            )
            retried = service.execute(
                request=build_request(
                    user_id,
                    paper_account_id,
                    signal_id=signal.signal_id,
                    minutes=5,
                ),
                account=account,
                bar=build_bar(minutes=5),
                constraints=PERMISSIVE_CONSTRAINTS,
            )

            assert blocked.accepted is False
            assert retried.accepted is True


class TestAnalyticsHandoff:
    def test_persisted_trades_feed_the_analytics_contract(
        self,
        paper_database,
        user_id,
        paper_account_id,
    ) -> None:
        """Sprint 046 metrics finally read real trades instead of nothing."""

        with paper_database.session() as session:
            account = TradingAccountRepository(session).require(paper_account_id)
            service = PaperExecutionService(session)

            service.execute(
                request=build_request(user_id, paper_account_id),
                account=account,
                bar=build_bar(),
                constraints=PERMISSIVE_CONSTRAINTS,
            )
            service.close_all_positions(
                account,
                build_bar(open_price=105.0, high=106.0, low=104.0, close=105.0,
                          minutes=60),
            )

            service.execute(
                request=build_request(
                    user_id,
                    paper_account_id,
                    action=PaperAction.SELL,
                    minutes=120,
                ),
                account=account,
                bar=build_bar(open_price=105.0, high=106.0, low=104.0,
                              close=105.0, minutes=120),
                constraints=PERMISSIVE_CONSTRAINTS,
            )
            service.close_all_positions(
                account,
                build_bar(open_price=108.0, high=109.0, low=107.0, close=108.0,
                          minutes=180),
            )

        with paper_database.read_session() as session:
            records = PaperTradeRepository(session).build_account_trade_records(
                paper_account_id
            )

        metrics = calculate_trade_metrics(records, starting_balance=10_000.0)

        assert len(records) == 2
        assert metrics.is_available is True
        assert metrics.total_trades == 2
        assert metrics.winning_trades == 1
        assert metrics.losing_trades == 1
        assert metrics.net_pnl == pytest.approx(4.0)
        assert metrics.win_rate == pytest.approx(0.5)

    def test_net_pnl_is_none_when_the_account_never_traded(
        self,
        paper_database,
        paper_account_id,
    ) -> None:
        """An empty history is unknown, not zero."""

        with paper_database.read_session() as session:
            trades = PaperTradeRepository(session)

            assert trades.count_trades(paper_account_id) == 0
            assert trades.net_pnl(paper_account_id) is None

    def test_a_snapshot_records_the_account_state(
        self,
        paper_database,
        user_id,
        paper_account_id,
    ) -> None:
        with paper_database.session() as session:
            account = TradingAccountRepository(session).require(paper_account_id)
            service = PaperExecutionService(session)

            service.execute(
                request=build_request(user_id, paper_account_id),
                account=account,
                bar=build_bar(),
                constraints=PERMISSIVE_CONSTRAINTS,
            )
            snapshot = service.capture_snapshot(
                account,
                captured_at_utc=FIXED_NOW + timedelta(minutes=5),
            )

            assert snapshot.open_position_count == 1
            assert snapshot.open_order_count == 0
            assert snapshot.closed_trade_count == 0
            assert float(snapshot.starting_balance) == pytest.approx(10_000.0)

        with paper_database.read_session() as session:
            from aqos.paper_trading.repositories import (
                PaperAccountSnapshotRepository,
            )

            latest = PaperAccountSnapshotRepository(session).latest_snapshot(
                paper_account_id
            )

            assert latest is not None
            assert latest.currency == "USD"
            assert latest.to_dict()["open_position_count"] == 1


class TestStoredProcedures:
    def test_open_position_count_procedure(
        self,
        paper_database,
        user_id,
        paper_account_id,
    ) -> None:
        with paper_database.session() as session:
            account = TradingAccountRepository(session).require(paper_account_id)

            PaperExecutionService(session).execute(
                request=build_request(user_id, paper_account_id),
                account=account,
                bar=build_bar(),
                constraints=PERMISSIVE_CONSTRAINTS,
            )

        result = StoredProcedureService(paper_database).call(
            "sp_aqos_paper_open_position_count",
            parameters=(paper_account_id,),
            out_parameters=("open_positions",),
        )

        assert result.out_values["open_positions"] == 1

    def test_trade_summary_procedure(
        self,
        paper_database,
        user_id,
        paper_account_id,
    ) -> None:
        with paper_database.session() as session:
            account = TradingAccountRepository(session).require(paper_account_id)
            service = PaperExecutionService(session)

            service.execute(
                request=build_request(user_id, paper_account_id),
                account=account,
                bar=build_bar(),
                constraints=PERMISSIVE_CONSTRAINTS,
            )
            service.close_all_positions(
                account,
                build_bar(open_price=105.0, high=106.0, low=104.0, close=105.0,
                          minutes=60),
            )

        result = StoredProcedureService(paper_database).call_read_only(
            "sp_aqos_paper_trade_summary",
            parameters=(paper_account_id,),
        )

        row = result.rows[0]

        assert row["total_trades"] == 1
        assert row["winning_trades"] == 1
        assert row["losing_trades"] == 0
        assert float(row["net_pnl"]) == pytest.approx(10.0)

    def test_exit_reason_counts_procedure(
        self,
        paper_database,
        user_id,
        paper_account_id,
    ) -> None:
        with paper_database.session() as session:
            account = TradingAccountRepository(session).require(paper_account_id)
            service = PaperExecutionService(session)

            service.execute(
                request=build_request(
                    user_id,
                    paper_account_id,
                    take_profit=110.0,
                ),
                account=account,
                bar=build_bar(),
                constraints=PERMISSIVE_CONSTRAINTS,
            )
            service.process_bar(
                account,
                build_bar(open_price=105.0, high=112.0, low=104.0, close=111.0,
                          minutes=60),
            )

            service.execute(
                request=build_request(user_id, paper_account_id, minutes=120),
                account=account,
                bar=build_bar(minutes=120),
                constraints=PERMISSIVE_CONSTRAINTS,
            )
            service.close_all_positions(
                account,
                build_bar(minutes=180),
            )

        result = StoredProcedureService(paper_database).call_read_only(
            "sp_aqos_paper_exit_reason_counts",
            parameters=(paper_account_id,),
        )

        counts = {row["exit_reason"]: row["total"] for row in result.rows}

        assert counts == {"end_of_data": 1, "take_profit": 1}


class TestDatabaseConstraints:
    """Raw SQL bypasses the Python guards, so MySQL must refuse the same rows."""

    def test_an_order_for_an_unknown_account_is_refused(
        self,
        paper_database,
        user_id,
    ) -> None:
        with pytest.raises(IntegrityError):
            with paper_database.session() as session:
                session.execute(
                    text(
                        "INSERT INTO paper_orders (order_id, user_id, "
                        "account_id, symbol, action, order_type, status, "
                        "quantity, created_at_utc, updated_at_utc, "
                        "metadata_json) VALUES ('o_ghost', :user_id, "
                        "'acc_missing', 'XAUUSD', 'buy', 'market', 'accepted', "
                        "1, :now, :now, '{}')"
                    ),
                    {"user_id": user_id, "now": FIXED_NOW},
                )

    def test_a_rejected_order_without_a_reason_is_refused(
        self,
        paper_database,
        user_id,
        paper_account_id,
    ) -> None:
        with pytest.raises(
            DatabaseError,
            match="ck_paper_orders_rejection_reason_present",
        ):
            with paper_database.session() as session:
                session.execute(
                    text(
                        "INSERT INTO paper_orders (order_id, user_id, "
                        "account_id, symbol, action, order_type, status, "
                        "quantity, created_at_utc, updated_at_utc, "
                        "metadata_json) VALUES ('o_silent', :user_id, "
                        ":account_id, 'XAUUSD', 'buy', 'market', 'rejected', "
                        "1, :now, :now, '{}')"
                    ),
                    {
                        "user_id": user_id,
                        "account_id": paper_account_id,
                        "now": FIXED_NOW,
                    },
                )

    def test_a_non_positive_order_quantity_is_refused(
        self,
        paper_database,
        user_id,
        paper_account_id,
    ) -> None:
        with pytest.raises(
            DatabaseError,
            match="ck_paper_orders_quantity_positive",
        ):
            with paper_database.session() as session:
                session.execute(
                    text(
                        "INSERT INTO paper_orders (order_id, user_id, "
                        "account_id, symbol, action, order_type, status, "
                        "quantity, created_at_utc, updated_at_utc, "
                        "metadata_json) VALUES ('o_zero', :user_id, "
                        ":account_id, 'XAUUSD', 'buy', 'market', 'accepted', "
                        "0, :now, :now, '{}')"
                    ),
                    {
                        "user_id": user_id,
                        "account_id": paper_account_id,
                        "now": FIXED_NOW,
                    },
                )

    def test_a_closed_position_without_a_timestamp_is_refused(
        self,
        paper_database,
        paper_account_id,
    ) -> None:
        with pytest.raises(
            DatabaseError,
            match="ck_paper_positions_closed_has_timestamp",
        ):
            with paper_database.session() as session:
                session.execute(
                    text(
                        "INSERT INTO paper_positions (position_id, account_id, "
                        "symbol, side, status, quantity, closed_quantity, "
                        "entry_price, opened_at_utc, metadata_json) VALUES "
                        "('p_untimed', :account_id, 'XAUUSD', 'long', "
                        "'closed', 1, 1, 100, :now, '{}')"
                    ),
                    {"account_id": paper_account_id, "now": FIXED_NOW},
                )

    def test_a_trade_whose_net_pnl_disagrees_with_its_inputs_is_refused(
        self,
        paper_database,
        paper_account_id,
    ) -> None:
        with pytest.raises(
            DatabaseError,
            match="ck_paper_trades_net_pnl_matches",
        ):
            with paper_database.session() as session:
                session.execute(
                    text(
                        "INSERT INTO paper_trades (trade_id, account_id, "
                        "symbol, side, quantity, entry_price, exit_price, "
                        "gross_pnl, commission, net_pnl, exit_reason, "
                        "opened_at_utc, closed_at_utc, metadata_json) VALUES "
                        "('t_wrong', :account_id, 'XAUUSD', 'long', 1, 100, "
                        "110, 10, 2, 10, 'manual_close', :now, :now, '{}')"
                    ),
                    {"account_id": paper_account_id, "now": FIXED_NOW},
                )

    def test_a_trade_closing_before_it_opened_is_refused(
        self,
        paper_database,
        paper_account_id,
    ) -> None:
        with pytest.raises(
            DatabaseError,
            match="ck_paper_trades_close_after_open",
        ):
            with paper_database.session() as session:
                session.execute(
                    text(
                        "INSERT INTO paper_trades (trade_id, account_id, "
                        "symbol, side, quantity, entry_price, exit_price, "
                        "gross_pnl, commission, net_pnl, exit_reason, "
                        "opened_at_utc, closed_at_utc, metadata_json) VALUES "
                        "('t_reversed', :account_id, 'XAUUSD', 'long', 1, 100, "
                        "110, 10, 0, 10, 'manual_close', :opened, :closed, "
                        "'{}')"
                    ),
                    {
                        "account_id": paper_account_id,
                        "opened": datetime(2026, 2, 1),
                        "closed": datetime(2026, 1, 1),
                    },
                )

    def test_python_refuses_the_same_dishonest_net_pnl(self) -> None:
        from aqos.paper_trading.models import PaperTradeRecord
        from aqos.paper_trading.contracts import PaperTradingError

        record = PaperTradeRecord(
            trade_id="t_wrong",
            account_id="acc_1",
            symbol="XAUUSD",
            side=PaperSide.LONG,
            quantity=1.0,
            entry_price=100.0,
            exit_price=110.0,
            gross_pnl=10.0,
            commission=2.0,
            net_pnl=10.0,
            exit_reason=PaperExitReason.MANUAL_CLOSE,
            opened_at_utc=FIXED_NOW,
            closed_at_utc=FIXED_NOW,
        )

        with pytest.raises(PaperTradingError, match="gross_pnl minus commission"):
            record.assert_net_pnl_is_derived()

    def test_deleting_an_account_cascades_to_paper_rows(
        self,
        paper_database,
        user_id,
        paper_account_id,
    ) -> None:
        with paper_database.session() as session:
            account = TradingAccountRepository(session).require(paper_account_id)
            service = PaperExecutionService(session)

            service.execute(
                request=build_request(user_id, paper_account_id),
                account=account,
                bar=build_bar(),
                constraints=PERMISSIVE_CONSTRAINTS,
            )
            service.close_all_positions(
                account,
                build_bar(minutes=60),
            )

        with paper_database.session() as session:
            TradingAccountRepository(session).delete_account(paper_account_id)

        with paper_database.read_session() as session:
            assert PaperOrderRepository(session).list_orders(
                account_id=paper_account_id
            ) == ()
            assert PaperPositionRepository(session).list_positions(
                account_id=paper_account_id
            ) == ()
            assert PaperTradeRepository(session).list_trades(
                account_id=paper_account_id
            ) == ()
            assert PaperFillRepository(session).list_fills(
                account_id=paper_account_id
            ) == ()

    def test_deleting_a_signal_leaves_the_order_but_clears_the_link(
        self,
        paper_database,
        user_id,
        paper_account_id,
    ) -> None:
        """History must survive: only the reference is dropped."""

        with paper_database.session() as session:
            signal = create_signal(session, user_id, paper_account_id)
            account = TradingAccountRepository(session).require(paper_account_id)

            result = PaperExecutionService(session).execute(
                request=build_request(
                    user_id,
                    paper_account_id,
                    signal_id=signal.signal_id,
                ),
                account=account,
                bar=build_bar(),
                constraints=PERMISSIVE_CONSTRAINTS,
            )
            order_id = result.order.order_id
            signal_id = signal.signal_id

        with paper_database.session() as session:
            TradingSignalRepository(session).delete_signal(signal_id)

        with paper_database.read_session() as session:
            order = PaperOrderRepository(session).require_order(order_id)

            assert order.signal_id is None
            assert order.status == PaperOrderStatus.FILLED
