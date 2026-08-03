"""
Persisted paper execution rule decisions against real MySQL 8.

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

from aqos.accounts.models import AccountStatus, AccountType, BrokerKind
from aqos.accounts.repositories import TradingAccountRepository
from aqos.database.config import parse_database_url
from aqos.database.engine import AqosDatabase
from aqos.database.migration_runner import apply_migrations
from aqos.database.procedures import StoredProcedureService
from aqos.execution_policy.modes import ExecutionMode
from aqos.model_training.model_evaluation import ModelPromotionStage
from aqos.paper_trading.contracts import (
    PaperAction,
    PaperExecutionRequest,
    PaperOrderType,
    PaperRejectionReason,
)
from aqos.paper_trading.eligibility import PaperEligibilityContext
from aqos.paper_trading.execution_service import PaperExecutionService
from aqos.paper_trading.repositories import (
    PaperExecutionDecisionRepository,
    PaperFillRepository,
    PaperOrderRepository,
    PaperPositionRepository,
    PaperTradeRepository,
)
from aqos.paper_trading.simulator import PaperMarketBar
from aqos.signals.models import SignalAction, SignalSource, SignalStatus
from aqos.signals.repositories import TradingSignalRepository
from aqos.trading_settings.models import SymbolPreferenceKind
from aqos.trading_settings.repositories import (
    SymbolPreferenceRepository,
    TradingSettingsRepository,
)
from aqos.users.repositories import UserProfileRepository


ENV_TEST_DB_URL = "AQOS_TEST_DB_URL"

FIXED_NOW = datetime(2026, 1, 1, 0, 0, 0)

pytestmark = pytest.mark.mysql


def requires_mysql() -> str:
    url = os.environ.get(ENV_TEST_DB_URL, "").strip()

    if not url:
        pytest.skip(
            f"{ENV_TEST_DB_URL} is not set, so paper execution rules are NOT "
            "verified against MySQL by this run. Run them with:\n"
            "  AQOS_TEST_DB_URL=mysql+pymysql://user:password@localhost:3306/"
            "aqos_test pytest -m mysql"
        )

    return url


def reset_tables(database: AqosDatabase) -> None:
    with database.session() as session:
        session.execute(text("SET FOREIGN_KEY_CHECKS = 0"))

        for table in (
            "paper_execution_decisions",
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
def rules_database() -> AqosDatabase:
    url = requires_mysql()
    database = AqosDatabase(config=parse_database_url(url))

    if not database.ping():
        database.dispose()
        pytest.skip("MySQL server is not reachable; paper rules NOT verified.")

    apply_migrations(database)
    reset_tables(database)

    yield database

    reset_tables(database)
    database.dispose()


@pytest.fixture
def user_id(rules_database) -> str:
    with rules_database.session() as session:
        user_id = UserProfileRepository(session).create_user(
            email="rules@example.com",
            display_name="Rule Trader",
            created_at_utc=FIXED_NOW,
        ).user_id

        TradingSettingsRepository(session).create_for_user(
            user_id=user_id,
            execution_mode=ExecutionMode.AUTO_TRADE,
            created_at_utc=FIXED_NOW,
        )

        return user_id


@pytest.fixture
def account_id(rules_database, user_id: str) -> str:
    with rules_database.session() as session:
        return TradingAccountRepository(session).create_account(
            user_id=user_id,
            name="Paper Rules",
            account_type=AccountType.PAPER,
            broker=BrokerKind.INTERNAL_PAPER,
            initial_balance=10_000.0,
            execution_mode=ExecutionMode.AUTO_TRADE,
            auto_trade_enabled=True,
            created_at_utc=FIXED_NOW,
        ).account_id


def build_bar(minutes: int = 0, symbol: str = "XAUUSD") -> PaperMarketBar:
    return PaperMarketBar(
        symbol=symbol,
        timestamp_utc=FIXED_NOW + timedelta(minutes=minutes),
        open=100.0,
        high=105.0,
        low=95.0,
        close=102.0,
        volume=1_000.0,
    )


def build_request(
    user_id: str,
    account_id: str,
    signal_id: str | None = None,
    symbol: str = "XAUUSD",
    minutes: int = 0,
    action: PaperAction = PaperAction.BUY,
) -> PaperExecutionRequest:
    return PaperExecutionRequest(
        user_id=user_id,
        account_id=account_id,
        symbol=symbol,
        action=action,
        quantity=2.0,
        order_type=PaperOrderType.MARKET,
        submitted_at_utc=FIXED_NOW + timedelta(minutes=minutes),
        signal_id=signal_id,
    )


def create_signal(
    session,
    user_id: str,
    account_id: str,
    approve: bool = True,
    symbol: str = "XAUUSD",
    **overrides,
):
    payload = {
        "user_id": user_id,
        "account_id": account_id,
        "symbol": symbol,
        "timeframe": "H1",
        "action": SignalAction.BUY,
        "source": SignalSource.MANUAL,
        "generated_at_utc": FIXED_NOW,
    }
    payload.update(overrides)

    signals = TradingSignalRepository(session)
    signal = signals.create_signal(**payload)

    if approve:
        # An explicit approval time keeps the audit trail ordered against the
        # simulated execution time rather than against wall clock.
        signals.approve_signal(
            signal.signal_id,
            occurred_at_utc=FIXED_NOW + timedelta(minutes=1),
        )

    return signal


def execute(
    session,
    user_id: str,
    account_id: str,
    context: PaperEligibilityContext | None = None,
    **request_kwargs,
):
    account = TradingAccountRepository(session).require(account_id)

    return PaperExecutionService(session).execute(
        request=build_request(user_id, account_id, **request_kwargs),
        account=account,
        bar=build_bar(
            minutes=request_kwargs.get("minutes", 0),
            symbol=request_kwargs.get("symbol", "XAUUSD"),
        ),
        context=context,
    )


class TestSchema:
    def test_the_decision_table_exists(self, rules_database) -> None:
        with rules_database.read_session() as session:
            rows = session.execute(
                text(
                    "SELECT TABLE_NAME FROM information_schema.TABLES "
                    "WHERE TABLE_SCHEMA = DATABASE()"
                )
            ).all()

        assert "paper_execution_decisions" in {str(row[0]) for row in rows}

    def test_the_decision_procedures_exist(self, rules_database) -> None:
        procedures = StoredProcedureService(rules_database).list_procedures()

        assert "sp_aqos_paper_decision_reason_counts" in procedures
        assert "sp_aqos_paper_decision_summary" in procedures


class TestDecisionPersistence:
    def test_an_allowed_execution_records_an_allowed_decision(
        self,
        rules_database,
        user_id,
        account_id,
    ) -> None:
        with rules_database.session() as session:
            result = execute(session, user_id, account_id)

            assert result.accepted is True
            order_id = result.order.order_id

        with rules_database.read_session() as session:
            decisions = PaperExecutionDecisionRepository(session).list_decisions(
                account_id=account_id
            )

            assert len(decisions) == 1
            assert decisions[0].is_allowed is True
            assert decisions[0].primary_reason_code is None
            assert decisions[0].blocking_reason_count == 0
            assert decisions[0].order_id == order_id
            assert decisions[0].effective_execution_mode == ExecutionMode.AUTO_TRADE

    def test_a_refused_execution_records_a_structured_reason(
        self,
        rules_database,
        user_id,
        account_id,
    ) -> None:
        with rules_database.session() as session:
            SymbolPreferenceRepository(session).add_symbol(
                user_id=user_id,
                symbol="XAUUSD",
                kind=SymbolPreferenceKind.BLOCKED,
            )

        with rules_database.session() as session:
            result = execute(session, user_id, account_id)

            assert result.accepted is False
            assert result.rejection_reason == PaperRejectionReason.INVALID_SYMBOL

        with rules_database.read_session() as session:
            decision = PaperExecutionDecisionRepository(session).latest_decision(
                account_id
            )

            assert decision.is_allowed is False
            assert decision.primary_reason_code == "symbol_blocked"
            assert decision.blocking_reason_count == 1
            assert decision.blocking_sources_json == ["symbol_preferences"]
            assert decision.reasons_json[0]["category"] == "account_rule"
            assert decision.reasons_json[0]["severity"] == "blocking"

    def test_a_refused_execution_writes_no_order_fill_or_trade(
        self,
        rules_database,
        user_id,
        account_id,
    ) -> None:
        """A blocked rule must leave the trading tables untouched."""

        with rules_database.session() as session:
            accounts = TradingAccountRepository(session)
            account = accounts.require(account_id)
            account.status = AccountStatus.SUSPENDED
            session.flush()

            result = PaperExecutionService(session).execute(
                request=build_request(user_id, account_id),
                account=account,
                bar=build_bar(),
            )

            assert result.accepted is False
            assert result.order is None

        with rules_database.read_session() as session:
            assert PaperOrderRepository(session).list_orders(
                account_id=account_id
            ) == ()
            assert PaperPositionRepository(session).list_positions(
                account_id=account_id
            ) == ()
            assert PaperFillRepository(session).list_fills(
                account_id=account_id
            ) == ()
            assert PaperTradeRepository(session).list_trades(
                account_id=account_id
            ) == ()
            # The refusal itself is still recorded.
            assert PaperExecutionDecisionRepository(session).count_refusals(
                account_id
            ) == 1

    def test_every_attempt_records_exactly_one_decision(
        self,
        rules_database,
        user_id,
        account_id,
    ) -> None:
        """
        One attempt, one decision record — including the refused ones.

        A refusal that reaches the paper execution boundary without leaving a
        decision row would be unexplainable after the fact.
        """

        with rules_database.session() as session:
            SymbolPreferenceRepository(session).add_symbol(
                user_id=user_id,
                symbol="EURUSD",
                kind=SymbolPreferenceKind.BLOCKED,
            )

        with rules_database.session() as session:
            account = TradingAccountRepository(session).require(account_id)
            service = PaperExecutionService(session)

            # 1. allowed
            execute(session, user_id, account_id)
            # 2. refused by a blocked symbol
            execute(session, user_id, account_id, symbol="EURUSD", minutes=1)
            # 3. refused because the bar is for another instrument
            service.execute(
                request=build_request(user_id, account_id, minutes=2),
                account=account,
                bar=build_bar(minutes=2, symbol="EURUSD"),
            )
            # 4. refused by a malformed request
            service.execute(
                request=PaperExecutionRequest(
                    user_id=user_id,
                    account_id=account_id,
                    symbol="XAUUSD",
                    action=PaperAction.BUY,
                    quantity=2.0,
                    order_type=PaperOrderType.LIMIT,
                    submitted_at_utc=FIXED_NOW + timedelta(minutes=3),
                    requested_price=100.0,
                    stop_loss=105.0,
                ),
                account=account,
                bar=build_bar(minutes=3),
            )

        with rules_database.read_session() as session:
            repository = PaperExecutionDecisionRepository(session)
            decisions = repository.list_decisions(account_id=account_id)

            assert len(decisions) == 4
            assert [decision.is_allowed for decision in decisions] == [
                True,
                False,
                False,
                False,
            ]
            assert [
                decision.primary_reason_code for decision in decisions
            ] == [
                None,
                "symbol_blocked",
                "invalid_symbol",
                "validation_failed",
            ]

    def test_a_wrong_bar_keeps_its_precise_order_reason(
        self,
        rules_database,
        user_id,
        account_id,
    ) -> None:
        with rules_database.session() as session:
            account = TradingAccountRepository(session).require(account_id)

            result = PaperExecutionService(session).execute(
                request=build_request(user_id, account_id),
                account=account,
                bar=build_bar(symbol="EURUSD"),
            )

            assert result.accepted is False
            assert result.rejection_reason == PaperRejectionReason.INVALID_SYMBOL
            assert result.order is None

    def test_reason_counts_group_by_code(
        self,
        rules_database,
        user_id,
        account_id,
    ) -> None:
        with rules_database.session() as session:
            SymbolPreferenceRepository(session).add_symbol(
                user_id=user_id,
                symbol="EURUSD",
                kind=SymbolPreferenceKind.BLOCKED,
            )

        with rules_database.session() as session:
            execute(session, user_id, account_id, symbol="EURUSD")
            execute(session, user_id, account_id, symbol="EURUSD", minutes=1)
            execute(session, user_id, account_id, minutes=2)

        with rules_database.read_session() as session:
            counts = PaperExecutionDecisionRepository(session).count_by_reason_code(
                account_id
            )

            assert counts == {"symbol_blocked": 2}

    def test_decisions_can_be_filtered_by_outcome(
        self,
        rules_database,
        user_id,
        account_id,
    ) -> None:
        with rules_database.session() as session:
            SymbolPreferenceRepository(session).add_symbol(
                user_id=user_id,
                symbol="EURUSD",
                kind=SymbolPreferenceKind.BLOCKED,
            )

        with rules_database.session() as session:
            execute(session, user_id, account_id)
            execute(session, user_id, account_id, symbol="EURUSD", minutes=1)

        with rules_database.read_session() as session:
            repository = PaperExecutionDecisionRepository(session)

            assert len(repository.list_decisions(account_id=account_id)) == 2
            assert len(
                repository.list_decisions(account_id=account_id, is_allowed=True)
            ) == 1
            assert len(
                repository.list_decisions(account_id=account_id, is_allowed=False)
            ) == 1


class TestRulesReadFromTheDatabase:
    def test_a_blocked_symbol_is_read_from_the_users_preferences(
        self,
        rules_database,
        user_id,
        account_id,
    ) -> None:
        """The gate resolves preferences itself rather than trusting a caller."""

        with rules_database.session() as session:
            SymbolPreferenceRepository(session).add_symbol(
                user_id=user_id,
                symbol="XAUUSD",
                kind=SymbolPreferenceKind.BLOCKED,
            )

        with rules_database.session() as session:
            # A bare context cannot weaken the gate.
            result = execute(
                session,
                user_id,
                account_id,
                context=PaperEligibilityContext(),
            )

            assert result.accepted is False
            assert "symbol_blocked" in result.rejection_message

    def test_the_user_execution_mode_ceiling_is_read_from_settings(
        self,
        rules_database,
        user_id,
        account_id,
    ) -> None:
        with rules_database.session() as session:
            TradingSettingsRepository(session).set_execution_mode(
                user_id=user_id,
                execution_mode=ExecutionMode.SIGNAL_ONLY,
            )

        with rules_database.session() as session:
            result = execute(session, user_id, account_id)

            assert result.accepted is False
            assert result.rejection_reason == (
                PaperRejectionReason.EXECUTION_NOT_ALLOWED
            )
            assert "user_settings=signal_only" in result.rejection_message

        with rules_database.read_session() as session:
            decision = PaperExecutionDecisionRepository(session).latest_decision(
                account_id
            )

            assert decision.effective_execution_mode == ExecutionMode.SIGNAL_ONLY
            assert decision.primary_reason_code == "auto_trade_not_allowed"

    def test_a_duplicate_execution_is_detected_from_persisted_orders(
        self,
        rules_database,
        user_id,
        account_id,
    ) -> None:
        with rules_database.session() as session:
            signal = create_signal(session, user_id, account_id)
            signal_id = signal.signal_id

            first = execute(session, user_id, account_id, signal_id=signal_id)

            assert first.accepted is True

        with rules_database.session() as session:
            second = execute(
                session,
                user_id,
                account_id,
                signal_id=signal_id,
                minutes=5,
            )

            assert second.accepted is False
            assert second.rejection_reason == (
                PaperRejectionReason.DUPLICATE_EXECUTION
            )

        with rules_database.read_session() as session:
            decision = PaperExecutionDecisionRepository(session).latest_decision(
                account_id
            )

            assert decision.primary_reason_code == "duplicate_signal"
            assert PaperPositionRepository(session).list_positions(
                account_id=account_id
            ).__len__() == 1


class TestSignalLifecycleIntegration:
    def test_an_approved_signal_becomes_executed(
        self,
        rules_database,
        user_id,
        account_id,
    ) -> None:
        with rules_database.session() as session:
            signal_id = create_signal(session, user_id, account_id).signal_id

            result = execute(
                session,
                user_id,
                account_id,
                signal_id=signal_id,
                minutes=5,
            )

            assert result.accepted is True

        with rules_database.read_session() as session:
            signals = TradingSignalRepository(session)
            signal = signals.require_signal(signal_id)

            assert signal.status == SignalStatus.EXECUTED
            # The transition went through the lifecycle, not around it.
            assert signals.build_status_history(signal_id) == (
                "generated",
                "approved",
                "executed",
            )

    @pytest.mark.parametrize(
        "status",
        [SignalStatus.GENERATED, SignalStatus.PENDING_APPROVAL],
    )
    def test_an_unapproved_signal_cannot_execute(
        self,
        rules_database,
        user_id,
        account_id,
        status: SignalStatus,
    ) -> None:
        """generated may never jump straight to executed."""

        with rules_database.session() as session:
            signals = TradingSignalRepository(session)
            signal_id = create_signal(
                session,
                user_id,
                account_id,
                approve=False,
            ).signal_id

            if status == SignalStatus.PENDING_APPROVAL:
                signals.mark_pending_approval(signal_id)

            result = execute(session, user_id, account_id, signal_id=signal_id)

            assert result.accepted is False

        with rules_database.read_session() as session:
            signal = TradingSignalRepository(session).require_signal(signal_id)

            assert signal.status == status
            assert PaperPositionRepository(session).list_positions(
                account_id=account_id
            ) == ()

    def test_a_rejected_signal_can_never_execute(
        self,
        rules_database,
        user_id,
        account_id,
    ) -> None:
        with rules_database.session() as session:
            signals = TradingSignalRepository(session)
            signal_id = create_signal(
                session,
                user_id,
                account_id,
                approve=False,
            ).signal_id
            signals.reject_signal(signal_id, reason="Not wanted.")

            result = execute(session, user_id, account_id, signal_id=signal_id)

            assert result.accepted is False
            assert "validation_failed" in result.rejection_message

        with rules_database.read_session() as session:
            assert TradingSignalRepository(session).require_signal(
                signal_id
            ).status == SignalStatus.REJECTED


class TestModelPromotionRule:
    def test_a_model_signal_without_a_resolved_stage_is_refused(
        self,
        rules_database,
        user_id,
        account_id,
    ) -> None:
        """An unverifiable model is treated exactly like an unpromoted one."""

        with rules_database.session() as session:
            signal_id = create_signal(
                session,
                user_id,
                account_id,
                source=SignalSource.ML_MODEL,
                model_id="model_1",
                model_version="1.0",
            ).signal_id

            result = execute(session, user_id, account_id, signal_id=signal_id)

            assert result.accepted is False
            assert "unpromoted_model" in result.rejection_message

        with rules_database.read_session() as session:
            assert PaperOrderRepository(session).list_orders(
                account_id=account_id,
                signal_id=signal_id,
            )[0].status.value == "rejected"

    def test_a_model_promoted_to_paper_trading_may_execute(
        self,
        rules_database,
        user_id,
        account_id,
    ) -> None:
        with rules_database.session() as session:
            signal_id = create_signal(
                session,
                user_id,
                account_id,
                source=SignalSource.ML_MODEL,
                model_id="model_1",
                model_version="1.0",
            ).signal_id

            result = execute(
                session,
                user_id,
                account_id,
                signal_id=signal_id,
                context=PaperEligibilityContext(
                    model_promotion_stage=ModelPromotionStage.PAPER_TRADING,
                ),
            )

            assert result.accepted is True

    def test_a_research_stage_model_is_refused(
        self,
        rules_database,
        user_id,
        account_id,
    ) -> None:
        with rules_database.session() as session:
            signal_id = create_signal(
                session,
                user_id,
                account_id,
                source=SignalSource.ML_MODEL,
                model_id="model_1",
                model_version="1.0",
            ).signal_id

            result = execute(
                session,
                user_id,
                account_id,
                signal_id=signal_id,
                context=PaperEligibilityContext(
                    model_promotion_stage=ModelPromotionStage.RESEARCH,
                ),
            )

            assert result.accepted is False
            assert "unpromoted_model" in result.rejection_message


class TestStoredProcedures:
    def test_decision_summary_procedure(
        self,
        rules_database,
        user_id,
        account_id,
    ) -> None:
        with rules_database.session() as session:
            SymbolPreferenceRepository(session).add_symbol(
                user_id=user_id,
                symbol="EURUSD",
                kind=SymbolPreferenceKind.BLOCKED,
            )

        with rules_database.session() as session:
            execute(session, user_id, account_id)
            execute(session, user_id, account_id, symbol="EURUSD", minutes=1)
            execute(session, user_id, account_id, symbol="EURUSD", minutes=2)

        result = StoredProcedureService(rules_database).call(
            "sp_aqos_paper_decision_summary",
            parameters=(account_id,),
            out_parameters=("allowed", "refused"),
        )

        assert result.out_values["allowed"] == 1
        assert result.out_values["refused"] == 2

    def test_decision_summary_procedure_on_an_empty_account(
        self,
        rules_database,
        account_id,
    ) -> None:
        """No decisions means zero, not NULL."""

        result = StoredProcedureService(rules_database).call(
            "sp_aqos_paper_decision_summary",
            parameters=(account_id,),
            out_parameters=("allowed", "refused"),
        )

        assert result.out_values["allowed"] == 0
        assert result.out_values["refused"] == 0

    def test_decision_reason_counts_procedure(
        self,
        rules_database,
        user_id,
        account_id,
    ) -> None:
        with rules_database.session() as session:
            SymbolPreferenceRepository(session).add_symbol(
                user_id=user_id,
                symbol="EURUSD",
                kind=SymbolPreferenceKind.BLOCKED,
            )

        with rules_database.session() as session:
            execute(session, user_id, account_id, symbol="EURUSD")
            execute(session, user_id, account_id, symbol="EURUSD", minutes=1)

        result = StoredProcedureService(rules_database).call_read_only(
            "sp_aqos_paper_decision_reason_counts",
            parameters=(account_id,),
        )

        counts = {row["primary_reason_code"]: row["total"] for row in result.rows}

        assert counts == {"symbol_blocked": 2}


class TestDatabaseConstraints:
    """Raw SQL bypasses the Python guards, so MySQL must refuse the same rows."""

    def insert_decision(self, session, **overrides) -> None:
        payload = {
            "decision_id": "decision_1",
            "symbol": "XAUUSD",
            "is_allowed": 1,
            "requested_mode": "auto_trade",
            "effective_mode": "auto_trade",
            "primary_reason_code": None,
            "blocking_count": 0,
            "now": FIXED_NOW,
        }
        payload.update(overrides)

        session.execute(
            text(
                "INSERT INTO paper_execution_decisions (decision_id, user_id, "
                "account_id, symbol, is_allowed, requested_execution_mode, "
                "effective_execution_mode, primary_reason_code, "
                "blocking_reason_count, blocking_sources_json, reasons_json, "
                "decided_at_utc, metadata_json) VALUES (:decision_id, "
                ":user_id, :account_id, :symbol, :is_allowed, :requested_mode, "
                ":effective_mode, :primary_reason_code, :blocking_count, "
                "'[]', '[]', :now, '{}')"
            ),
            payload,
        )

    def test_a_refusal_without_a_reason_code_is_refused(
        self,
        rules_database,
        user_id,
        account_id,
    ) -> None:
        with pytest.raises(
            DatabaseError,
            match="ck_paper_decisions_refusal_has_reason",
        ):
            with rules_database.session() as session:
                self.insert_decision(
                    session,
                    user_id=user_id,
                    account_id=account_id,
                    is_allowed=0,
                    primary_reason_code=None,
                    blocking_count=0,
                )

    def test_a_refusal_with_a_zero_blocking_count_is_refused(
        self,
        rules_database,
        user_id,
        account_id,
    ) -> None:
        with pytest.raises(
            DatabaseError,
            match="ck_paper_decisions_refusal_has_reason",
        ):
            with rules_database.session() as session:
                self.insert_decision(
                    session,
                    user_id=user_id,
                    account_id=account_id,
                    is_allowed=0,
                    primary_reason_code="symbol_blocked",
                    blocking_count=0,
                )

    def test_an_approval_carrying_a_blocker_is_refused(
        self,
        rules_database,
        user_id,
        account_id,
    ) -> None:
        with pytest.raises(
            DatabaseError,
            match="ck_paper_decisions_allowed_has_no_blockers",
        ):
            with rules_database.session() as session:
                self.insert_decision(
                    session,
                    user_id=user_id,
                    account_id=account_id,
                    is_allowed=1,
                    primary_reason_code="symbol_blocked",
                    blocking_count=1,
                )

    def test_a_decision_for_an_unknown_account_is_refused(
        self,
        rules_database,
        user_id,
    ) -> None:
        with pytest.raises(IntegrityError):
            with rules_database.session() as session:
                self.insert_decision(
                    session,
                    user_id=user_id,
                    account_id="account_missing",
                )

    def test_python_refuses_the_same_unexplained_refusal(self) -> None:
        from aqos.paper_trading.contracts import PaperTradingError
        from aqos.paper_trading.models import PaperExecutionDecisionRecord

        record = PaperExecutionDecisionRecord(
            decision_id="decision_1",
            user_id="user_1",
            account_id="account_1",
            symbol="XAUUSD",
            is_allowed=False,
            requested_execution_mode=ExecutionMode.AUTO_TRADE,
            effective_execution_mode=ExecutionMode.AUTO_TRADE,
            decided_at_utc=FIXED_NOW,
        )

        with pytest.raises(PaperTradingError, match="must carry a blocking"):
            record.assert_decision_is_explained()

    def test_python_refuses_an_approval_claiming_a_blocker(self) -> None:
        from aqos.paper_trading.contracts import PaperTradingError
        from aqos.paper_trading.models import PaperExecutionDecisionRecord

        record = PaperExecutionDecisionRecord(
            decision_id="decision_1",
            user_id="user_1",
            account_id="account_1",
            symbol="XAUUSD",
            is_allowed=True,
            requested_execution_mode=ExecutionMode.AUTO_TRADE,
            effective_execution_mode=ExecutionMode.AUTO_TRADE,
            primary_reason_code="symbol_blocked",
            blocking_reason_count=1,
            decided_at_utc=FIXED_NOW,
        )

        with pytest.raises(PaperTradingError, match="cannot carry blocking"):
            record.assert_decision_is_explained()

    def test_deleting_an_account_cascades_to_decisions(
        self,
        rules_database,
        user_id,
        account_id,
    ) -> None:
        with rules_database.session() as session:
            execute(session, user_id, account_id)

        with rules_database.session() as session:
            TradingAccountRepository(session).delete_account(account_id)

        with rules_database.read_session() as session:
            assert PaperExecutionDecisionRepository(session).list_decisions(
                account_id=account_id
            ) == ()
