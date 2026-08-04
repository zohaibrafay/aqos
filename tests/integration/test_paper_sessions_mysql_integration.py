"""
Paper trading sessions and results against real MySQL 8.

Run with::

    AQOS_TEST_DB_URL=mysql+pymysql://user:password@localhost:3306/aqos_test \\
        pytest -m mysql
"""

from __future__ import annotations

import math
import os
from datetime import datetime, timedelta

import pytest
from sqlalchemy import text
from sqlalchemy.exc import DatabaseError, IntegrityError

from aqos.accounts.models import AccountType, BrokerKind
from aqos.accounts.repositories import TradingAccountRepository
from aqos.database.config import parse_database_url
from aqos.database.engine import AqosDatabase
from aqos.database.migration_runner import apply_migrations
from aqos.database.procedures import StoredProcedureService
from aqos.database.repository import RepositoryError
from aqos.execution_policy.modes import ExecutionMode
from aqos.paper_trading.contracts import (
    PaperAction,
    PaperExecutionRequest,
    PaperOrderType,
    PaperTradingError,
)
from aqos.paper_trading.execution_service import PaperExecutionService
from aqos.paper_trading.repositories import (
    PaperExecutionDecisionRepository,
    PaperFillRepository,
    PaperOrderRepository,
    PaperPositionRepository,
    PaperTradeRepository,
)
from aqos.paper_trading.session_service import (
    PaperSessionRepository,
    PaperSessionResultService,
    PaperSessionService,
)
from aqos.paper_trading.sessions import (
    InvalidPaperSessionTransitionError,
    PaperProfitFactorState,
    PaperSessionStatus,
    PaperSessionType,
)
from aqos.paper_trading.simulator import PaperMarketBar
from aqos.trading_settings.models import SymbolPreferenceKind
from aqos.trading_settings.repositories import (
    SymbolPreferenceRepository,
    TradingSettingsRepository,
)
from aqos.users.repositories import UserProfileRepository


ENV_TEST_DB_URL = "AQOS_TEST_DB_URL"

FIXED_NOW = datetime(2026, 1, 1, 0, 0, 0)
STARTING_BALANCE = 10_000.0

pytestmark = pytest.mark.mysql


def requires_mysql() -> str:
    url = os.environ.get(ENV_TEST_DB_URL, "").strip()

    if not url:
        pytest.skip(
            f"{ENV_TEST_DB_URL} is not set, so paper sessions are NOT verified "
            "against MySQL by this run. Run them with:\n"
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
            "paper_sessions",
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
def sessions_database() -> AqosDatabase:
    url = requires_mysql()
    database = AqosDatabase(config=parse_database_url(url))

    if not database.ping():
        database.dispose()
        pytest.skip("MySQL server is not reachable; paper sessions NOT verified.")

    apply_migrations(database)
    reset_tables(database)

    yield database

    reset_tables(database)
    database.dispose()


@pytest.fixture
def user_id(sessions_database) -> str:
    with sessions_database.session() as session:
        user_id = UserProfileRepository(session).create_user(
            email="sessions@example.com",
            display_name="Session Trader",
            created_at_utc=FIXED_NOW,
        ).user_id

        TradingSettingsRepository(session).create_for_user(
            user_id=user_id,
            execution_mode=ExecutionMode.AUTO_TRADE,
            created_at_utc=FIXED_NOW,
        )

        return user_id


@pytest.fixture
def account_id(sessions_database, user_id: str) -> str:
    with sessions_database.session() as session:
        return TradingAccountRepository(session).create_account(
            user_id=user_id,
            name="Paper Sessions",
            account_type=AccountType.PAPER,
            broker=BrokerKind.INTERNAL_PAPER,
            initial_balance=STARTING_BALANCE,
            execution_mode=ExecutionMode.AUTO_TRADE,
            auto_trade_enabled=True,
            created_at_utc=FIXED_NOW,
        ).account_id


@pytest.fixture
def session_id(sessions_database, account_id: str) -> str:
    with sessions_database.session() as session:
        account = TradingAccountRepository(session).require(account_id)

        return PaperSessionService(session).start_session(
            account=account,
            session_name="Forward test one",
            session_type=PaperSessionType.MANUAL_PAPER_SESSION,
            started_at_utc=FIXED_NOW,
        ).session_id


def build_bar(
    minutes: int = 0,
    symbol: str = "XAUUSD",
    price: float = 100.0,
) -> PaperMarketBar:
    return PaperMarketBar(
        symbol=symbol,
        timestamp_utc=FIXED_NOW + timedelta(minutes=minutes),
        open=price,
        high=price + 5,
        low=price - 5,
        close=price,
        volume=1_000.0,
    )


def run_trade(
    session,
    user_id: str,
    account_id: str,
    session_id: str | None,
    symbol: str = "XAUUSD",
    entry: float = 100.0,
    exit_price: float = 110.0,
    open_minutes: int = 0,
    close_minutes: int = 60,
):
    account = TradingAccountRepository(session).require(account_id)
    service = PaperExecutionService(session, session_id=session_id)

    service.execute(
        request=PaperExecutionRequest(
            user_id=user_id,
            account_id=account_id,
            symbol=symbol,
            action=PaperAction.BUY,
            quantity=1.0,
            order_type=PaperOrderType.MARKET,
            submitted_at_utc=FIXED_NOW + timedelta(minutes=open_minutes),
        ),
        account=account,
        bar=build_bar(minutes=open_minutes, symbol=symbol, price=entry),
    ).raise_if_rejected()

    return service.close_all_positions(
        account,
        build_bar(minutes=close_minutes, symbol=symbol, price=exit_price),
    )[0]


class TestSchema:
    def test_the_session_table_exists(self, sessions_database) -> None:
        with sessions_database.read_session() as session:
            rows = session.execute(
                text(
                    "SELECT TABLE_NAME FROM information_schema.TABLES "
                    "WHERE TABLE_SCHEMA = DATABASE()"
                )
            ).all()

        assert "paper_sessions" in {str(row[0]) for row in rows}

    def test_session_id_was_added_to_the_existing_paper_tables(
        self,
        sessions_database,
    ) -> None:
        """The forward migration links prior activity tables to a session."""

        with sessions_database.read_session() as session:
            rows = session.execute(
                text(
                    "SELECT TABLE_NAME FROM information_schema.COLUMNS "
                    "WHERE TABLE_SCHEMA = DATABASE() "
                    "AND COLUMN_NAME = 'session_id'"
                )
            ).all()

        assert {str(row[0]) for row in rows} >= {
            "paper_orders",
            "paper_fills",
            "paper_positions",
            "paper_trades",
            "paper_execution_decisions",
        }

    def test_the_session_procedures_exist(self, sessions_database) -> None:
        procedures = StoredProcedureService(sessions_database).list_procedures()

        assert "sp_aqos_paper_session_status_counts" in procedures
        assert "sp_aqos_paper_latest_sessions" in procedures
        assert "sp_aqos_paper_session_result_summary" in procedures
        assert "sp_aqos_paper_session_decision_breakdown" in procedures


class TestSessionLifecycle:
    def test_a_started_session_is_running(
        self,
        sessions_database,
        session_id,
    ) -> None:
        with sessions_database.read_session() as session:
            record = PaperSessionRepository(session).require_session(session_id)

            assert record.status == PaperSessionStatus.RUNNING
            assert record.ended_at_utc is None
            assert float(record.initial_balance) == pytest.approx(
                STARTING_BALANCE
            )

    def test_pause_and_resume(self, sessions_database, session_id) -> None:
        with sessions_database.session() as session:
            service = PaperSessionService(session)

            paused = service.pause_session(
                session_id,
                reason="Waiting for the London open.",
                occurred_at_utc=FIXED_NOW + timedelta(minutes=30),
            )

            assert paused.status == PaperSessionStatus.PAUSED
            assert paused.ended_at_utc is None

            resumed = service.resume_session(
                session_id,
                occurred_at_utc=FIXED_NOW + timedelta(minutes=60),
            )

            assert resumed.status == PaperSessionStatus.RUNNING

    def test_completing_a_session_timestamps_it(
        self,
        sessions_database,
        session_id,
    ) -> None:
        with sessions_database.session() as session:
            completed = PaperSessionService(session).complete_session(
                session_id,
                occurred_at_utc=FIXED_NOW + timedelta(hours=2),
            )

            assert completed.status == PaperSessionStatus.COMPLETED
            assert completed.ended_at_utc == FIXED_NOW + timedelta(hours=2)
            assert completed.is_terminal is True

    def test_a_completed_session_cannot_restart(
        self,
        sessions_database,
        session_id,
    ) -> None:
        with sessions_database.session() as session:
            service = PaperSessionService(session)
            service.complete_session(
                session_id,
                occurred_at_utc=FIXED_NOW + timedelta(hours=2),
            )

            with pytest.raises(
                InvalidPaperSessionTransitionError,
                match="cannot move from completed",
            ):
                service.resume_session(session_id)

    def test_a_created_session_cannot_jump_to_completed(
        self,
        sessions_database,
        account_id,
    ) -> None:
        with sessions_database.session() as session:
            account = TradingAccountRepository(session).require(account_id)
            service = PaperSessionService(session)

            created = service.create_session(
                account=account,
                session_name="Never started",
                session_type=PaperSessionType.MANUAL_PAPER_SESSION,
                started_at_utc=FIXED_NOW,
            )

            with pytest.raises(
                InvalidPaperSessionTransitionError,
                match="cannot move from created to completed",
            ):
                service.complete_session(created.session_id)

    def test_failing_a_session_requires_a_reason(
        self,
        sessions_database,
        session_id,
    ) -> None:
        with sessions_database.session() as session:
            with pytest.raises(PaperTradingError, match="must record a reason"):
                PaperSessionService(session).fail_session(session_id, reason="  ")

    def test_a_failed_session_records_why(
        self,
        sessions_database,
        session_id,
    ) -> None:
        with sessions_database.session() as session:
            failed = PaperSessionService(session).fail_session(
                session_id,
                reason="Data feed stopped.",
                occurred_at_utc=FIXED_NOW + timedelta(hours=1),
            )

            assert failed.status == PaperSessionStatus.FAILED
            assert failed.status_reason == "Data feed stopped."
            assert failed.ended_at_utc is not None

    def test_cancelling_requires_a_reason(
        self,
        sessions_database,
        session_id,
    ) -> None:
        with sessions_database.session() as session:
            with pytest.raises(PaperTradingError, match="must record a reason"):
                PaperSessionService(session).cancel_session(session_id, reason="")

    def test_only_a_running_session_accepts_executions(
        self,
        sessions_database,
        session_id,
    ) -> None:
        with sessions_database.session() as session:
            service = PaperSessionService(session)

            service.require_running_session(session_id)

            service.pause_session(session_id, reason="Paused.")

            with pytest.raises(PaperTradingError, match="cannot accept new"):
                service.require_running_session(session_id)

    def test_a_session_cannot_be_created_on_a_live_account(
        self,
        sessions_database,
        user_id,
    ) -> None:
        """A session on a live account would group real capital as simulated."""

        with sessions_database.session() as session:
            live = TradingAccountRepository(session).create_account(
                user_id=user_id,
                name="Live One",
                account_type=AccountType.LIVE,
                broker=BrokerKind.MT5,
                initial_balance=STARTING_BALANCE,
                created_at_utc=FIXED_NOW,
            )

            with pytest.raises(PaperTradingError, match="only run on paper"):
                PaperSessionService(session).create_session(
                    account=live,
                    session_name="Should not exist",
                    session_type=PaperSessionType.MANUAL_PAPER_SESSION,
                )

        with sessions_database.read_session() as session:
            assert PaperSessionRepository(session).list_sessions() == ()

    def test_a_session_cannot_be_created_as_running(
        self,
        sessions_database,
        user_id,
        account_id,
    ) -> None:
        with sessions_database.session() as session:
            with pytest.raises(RepositoryError, match="cannot be created as"):
                PaperSessionRepository(session).create_session(
                    user_id=user_id,
                    account_id=account_id,
                    session_name="Bad start",
                    session_type=PaperSessionType.MANUAL_PAPER_SESSION,
                    initial_balance=STARTING_BALANCE,
                    status=PaperSessionStatus.RUNNING,
                )

    def test_a_model_forward_test_must_name_its_model(
        self,
        sessions_database,
        account_id,
    ) -> None:
        with sessions_database.session() as session:
            account = TradingAccountRepository(session).require(account_id)

            with pytest.raises(PaperTradingError, match="must name the model"):
                PaperSessionService(session).create_session(
                    account=account,
                    session_name="Unattributed forward test",
                    session_type=PaperSessionType.MODEL_FORWARD_TEST,
                )


class TestSessionQueries:
    def test_sessions_can_be_filtered(
        self,
        sessions_database,
        account_id,
        session_id,
    ) -> None:
        with sessions_database.session() as session:
            account = TradingAccountRepository(session).require(account_id)
            PaperSessionService(session).start_session(
                account=account,
                session_name="Model forward test",
                session_type=PaperSessionType.MODEL_FORWARD_TEST,
                model_id="model_1",
                model_version="1.0",
                started_at_utc=FIXED_NOW + timedelta(days=1),
            )

        with sessions_database.read_session() as session:
            repository = PaperSessionRepository(session)

            assert len(repository.list_sessions(account_id=account_id)) == 2
            assert len(
                repository.list_sessions(
                    session_type=PaperSessionType.MODEL_FORWARD_TEST
                )
            ) == 1
            assert len(repository.list_sessions(model_id="model_1")) == 1
            assert len(
                repository.list_sessions(
                    started_since_utc=FIXED_NOW + timedelta(hours=12)
                )
            ) == 1
            assert repository.latest_session(account_id).session_name == (
                "Model forward test"
            )

    def test_active_sessions_exclude_finished_ones(
        self,
        sessions_database,
        account_id,
        session_id,
    ) -> None:
        with sessions_database.session() as session:
            account = TradingAccountRepository(session).require(account_id)
            second = PaperSessionService(session).start_session(
                account=account,
                session_name="Second run",
                session_type=PaperSessionType.MANUAL_PAPER_SESSION,
                started_at_utc=FIXED_NOW + timedelta(days=1),
            ).session_id

            PaperSessionService(session).complete_session(
                second,
                occurred_at_utc=FIXED_NOW + timedelta(days=1, hours=1),
            )

        with sessions_database.read_session() as session:
            active = PaperSessionRepository(session).list_active_sessions(
                account_id=account_id
            )

            assert len(active) == 1
            assert active[0].session_id == session_id

    def test_status_counts(
        self,
        sessions_database,
        account_id,
        session_id,
    ) -> None:
        with sessions_database.session() as session:
            account = TradingAccountRepository(session).require(account_id)
            second = PaperSessionService(session).start_session(
                account=account,
                session_name="Second run",
                session_type=PaperSessionType.MANUAL_PAPER_SESSION,
                started_at_utc=FIXED_NOW + timedelta(days=1),
            ).session_id
            PaperSessionService(session).complete_session(
                second,
                occurred_at_utc=FIXED_NOW + timedelta(days=2),
            )

        with sessions_database.read_session() as session:
            counts = PaperSessionRepository(session).count_by_status(account_id)

            assert counts == {"completed": 1, "running": 1}


class TestActivityLinking:
    def test_execution_artefacts_are_linked_to_the_session(
        self,
        sessions_database,
        user_id,
        account_id,
        session_id,
    ) -> None:
        with sessions_database.session() as session:
            run_trade(session, user_id, account_id, session_id)

        with sessions_database.read_session() as session:
            assert len(
                PaperOrderRepository(session).list_orders(session_id=session_id)
            ) == 2
            assert len(
                PaperFillRepository(session).list_fills(session_id=session_id)
            ) == 2
            assert len(
                PaperPositionRepository(session).list_positions(
                    session_id=session_id
                )
            ) == 1
            assert len(
                PaperTradeRepository(session).list_trades(session_id=session_id)
            ) == 1
            assert len(
                PaperExecutionDecisionRepository(session).list_decisions(
                    session_id=session_id
                )
            ) == 1

    def test_activity_without_a_session_stays_valid(
        self,
        sessions_database,
        user_id,
        account_id,
    ) -> None:
        """Ungrouped paper activity predates sessions and must keep working."""

        with sessions_database.session() as session:
            run_trade(session, user_id, account_id, session_id=None)

        with sessions_database.read_session() as session:
            trades = PaperTradeRepository(session).list_trades(
                account_id=account_id
            )

            assert len(trades) == 1
            assert trades[0].session_id is None

    def test_two_sessions_keep_their_activity_apart(
        self,
        sessions_database,
        user_id,
        account_id,
        session_id,
    ) -> None:
        with sessions_database.session() as session:
            account = TradingAccountRepository(session).require(account_id)
            second = PaperSessionService(session).start_session(
                account=account,
                session_name="Second run",
                session_type=PaperSessionType.MANUAL_PAPER_SESSION,
                started_at_utc=FIXED_NOW + timedelta(days=1),
            ).session_id

        with sessions_database.session() as session:
            run_trade(session, user_id, account_id, session_id)

        with sessions_database.session() as session:
            run_trade(
                session,
                user_id,
                account_id,
                second,
                symbol="EURUSD",
                open_minutes=2_000,
                close_minutes=2_060,
                exit_price=95.0,
            )

        with sessions_database.read_session() as session:
            trades = PaperTradeRepository(session)

            first_trades = trades.list_trades(session_id=session_id)
            second_trades = trades.list_trades(session_id=second)

            assert len(first_trades) == 1
            assert first_trades[0].symbol == "XAUUSD"
            assert len(second_trades) == 1
            assert second_trades[0].symbol == "EURUSD"


class TestSessionResults:
    def test_a_result_measures_the_sessions_own_activity(
        self,
        sessions_database,
        user_id,
        account_id,
        session_id,
    ) -> None:
        with sessions_database.session() as session:
            run_trade(session, user_id, account_id, session_id)

        with sessions_database.session() as session:
            run_trade(
                session,
                user_id,
                account_id,
                session_id,
                symbol="EURUSD",
                open_minutes=200,
                close_minutes=260,
                exit_price=96.0,
            )

        with sessions_database.read_session() as session:
            result = PaperSessionResultService(session).build_result(
                session_id=session_id,
                calculated_at_utc=FIXED_NOW,
            )

        assert result.total_orders == 4
        assert result.total_fills == 4
        assert result.total_trades == 2
        assert result.winning_trades == 1
        assert result.losing_trades == 1
        assert result.win_rate == pytest.approx(0.5)
        assert result.net_pnl == pytest.approx(6.0)
        assert result.gross_profit == pytest.approx(10.0)
        assert result.gross_loss == pytest.approx(4.0)
        assert result.profit_factor == pytest.approx(2.5)
        assert result.profit_factor_state == PaperProfitFactorState.FINITE
        assert result.ending_balance == pytest.approx(10_006.0)
        assert result.symbols_traded == ("EURUSD", "XAUUSD")
        assert result.decisions_allowed == 2
        assert result.decisions_rejected == 0

    def test_a_session_with_no_activity_reports_unknowns(
        self,
        sessions_database,
        session_id,
    ) -> None:
        """Nothing traded means unknown results, never zeros."""

        with sessions_database.read_session() as session:
            result = PaperSessionResultService(session).build_result(
                session_id=session_id,
                calculated_at_utc=FIXED_NOW,
            )

        assert result.total_orders == 0
        assert result.total_trades == 0
        assert result.has_trades is False
        assert result.win_rate is None
        assert result.net_pnl is None
        assert result.profit_factor is None
        assert result.profit_factor_state == PaperProfitFactorState.UNAVAILABLE
        assert result.max_drawdown is None
        assert result.ending_balance is None
        assert result.rejection_rate is None

    def test_max_drawdown_is_measured_from_the_equity_path(
        self,
        sessions_database,
        user_id,
        account_id,
        session_id,
    ) -> None:
        with sessions_database.session() as session:
            run_trade(session, user_id, account_id, session_id, exit_price=90.0)

        with sessions_database.session() as session:
            run_trade(
                session,
                user_id,
                account_id,
                session_id,
                open_minutes=200,
                close_minutes=260,
                exit_price=105.0,
            )

        with sessions_database.read_session() as session:
            result = PaperSessionResultService(session).build_result(
                session_id=session_id
            )

        # -10 then +5: the trough is 10 below the starting peak.
        assert result.max_drawdown == pytest.approx(10.0)
        assert result.net_pnl == pytest.approx(-5.0)

    def test_a_run_without_losses_has_an_infinite_profit_factor(
        self,
        sessions_database,
        user_id,
        account_id,
        session_id,
    ) -> None:
        """
        Wins and no losses is unbounded, not unmeasured.

        Sprint 046 settled this definition; the session result follows it rather
        than inventing its own.
        """

        with sessions_database.session() as session:
            run_trade(session, user_id, account_id, session_id)

        with sessions_database.read_session() as session:
            result = PaperSessionResultService(session).build_result(
                session_id=session_id
            )

        assert result.gross_loss == pytest.approx(0.0)
        assert math.isinf(result.profit_factor)
        assert result.profit_factor_state == (
            PaperProfitFactorState.INFINITE_NO_LOSSES
        )
        assert result.has_infinite_profit_factor is True
        assert result.win_rate == pytest.approx(1.0)

    def test_a_wins_only_result_persists_as_null_plus_state(
        self,
        sessions_database,
        user_id,
        account_id,
        session_id,
    ) -> None:
        """A DECIMAL column cannot hold infinity, so the state carries it."""

        with sessions_database.session() as session:
            run_trade(session, user_id, account_id, session_id)

        with sessions_database.session() as session:
            PaperSessionResultService(session).build_and_store_result(
                session_id=session_id
            )

        with sessions_database.read_session() as session:
            record = PaperSessionRepository(session).require_session(session_id)

            assert record.profit_factor is None
            assert record.profit_factor_state == (
                PaperProfitFactorState.INFINITE_NO_LOSSES
            )
            assert record.has_infinite_profit_factor is True
            assert record.to_dict()["profit_factor_state"] == (
                "infinite_no_losses"
            )

    def test_a_mixed_run_persists_a_finite_profit_factor(
        self,
        sessions_database,
        user_id,
        account_id,
        session_id,
    ) -> None:
        with sessions_database.session() as session:
            run_trade(session, user_id, account_id, session_id)

        with sessions_database.session() as session:
            run_trade(
                session,
                user_id,
                account_id,
                session_id,
                symbol="EURUSD",
                open_minutes=200,
                close_minutes=260,
                exit_price=96.0,
            )

        with sessions_database.session() as session:
            PaperSessionResultService(session).build_and_store_result(
                session_id=session_id
            )

        with sessions_database.read_session() as session:
            record = PaperSessionRepository(session).require_session(session_id)

            assert float(record.profit_factor) == pytest.approx(2.5)
            assert record.profit_factor_state == PaperProfitFactorState.FINITE

    def test_an_empty_session_persists_an_unavailable_profit_factor(
        self,
        sessions_database,
        session_id,
    ) -> None:
        """Nothing traded is still unknown, and stays distinguishable."""

        with sessions_database.session() as session:
            PaperSessionResultService(session).build_and_store_result(
                session_id=session_id
            )

        with sessions_database.read_session() as session:
            record = PaperSessionRepository(session).require_session(session_id)

            assert record.profit_factor is None
            assert record.profit_factor_state == (
                PaperProfitFactorState.UNAVAILABLE
            )
            assert record.has_infinite_profit_factor is False

    def test_rejected_decisions_are_counted_and_ranked(
        self,
        sessions_database,
        user_id,
        account_id,
        session_id,
    ) -> None:
        with sessions_database.session() as session:
            SymbolPreferenceRepository(session).add_symbol(
                user_id=user_id,
                symbol="GBPUSD",
                kind=SymbolPreferenceKind.BLOCKED,
            )

        with sessions_database.session() as session:
            account = TradingAccountRepository(session).require(account_id)
            service = PaperExecutionService(session, session_id=session_id)

            for offset in (0, 1):
                service.execute(
                    request=PaperExecutionRequest(
                        user_id=user_id,
                        account_id=account_id,
                        symbol="GBPUSD",
                        action=PaperAction.BUY,
                        quantity=1.0,
                        order_type=PaperOrderType.MARKET,
                        submitted_at_utc=FIXED_NOW + timedelta(minutes=offset),
                    ),
                    account=account,
                    bar=build_bar(minutes=offset, symbol="GBPUSD"),
                )

        with sessions_database.session() as session:
            run_trade(
                session,
                user_id,
                account_id,
                session_id,
                open_minutes=100,
                close_minutes=160,
            )

        with sessions_database.read_session() as session:
            result = PaperSessionResultService(session).build_result(
                session_id=session_id
            )

        assert result.decisions_allowed == 1
        assert result.decisions_rejected == 2
        assert result.rejection_rate == pytest.approx(2 / 3)
        assert result.top_rejection_reasons == (("symbol_blocked", 2),)

    def test_storing_a_result_writes_only_measured_values(
        self,
        sessions_database,
        user_id,
        account_id,
        session_id,
    ) -> None:
        with sessions_database.session() as session:
            run_trade(session, user_id, account_id, session_id)

        with sessions_database.session() as session:
            PaperSessionResultService(session).build_and_store_result(
                session_id=session_id,
                calculated_at_utc=FIXED_NOW + timedelta(hours=3),
            )

        with sessions_database.read_session() as session:
            record = PaperSessionRepository(session).require_session(session_id)

            assert record.total_trades == 1
            assert float(record.net_pnl) == pytest.approx(10.0)
            assert float(record.final_balance) == pytest.approx(10_010.0)
            assert float(record.max_drawdown) == pytest.approx(0.0)
            assert record.realized_pnl == pytest.approx(10.0)

    def test_storing_an_empty_result_leaves_pnl_unset(
        self,
        sessions_database,
        session_id,
    ) -> None:
        with sessions_database.session() as session:
            PaperSessionResultService(session).build_and_store_result(
                session_id=session_id
            )

        with sessions_database.read_session() as session:
            record = PaperSessionRepository(session).require_session(session_id)

            assert record.total_trades == 0
            assert record.net_pnl is None
            assert record.final_balance is None
            assert record.realized_pnl is None


class TestStoredProcedures:
    def test_status_counts_procedure(
        self,
        sessions_database,
        account_id,
        session_id,
    ) -> None:
        result = StoredProcedureService(sessions_database).call_read_only(
            "sp_aqos_paper_session_status_counts",
            parameters=(account_id,),
        )

        assert {row["status"]: row["total"] for row in result.rows} == {
            "running": 1
        }

    def test_latest_sessions_procedure(
        self,
        sessions_database,
        account_id,
        session_id,
    ) -> None:
        with sessions_database.session() as session:
            account = TradingAccountRepository(session).require(account_id)
            PaperSessionService(session).start_session(
                account=account,
                session_name="Newer run",
                session_type=PaperSessionType.SIGNAL_REPLAY_SESSION,
                started_at_utc=FIXED_NOW + timedelta(days=1),
            )

        result = StoredProcedureService(sessions_database).call_read_only(
            "sp_aqos_paper_latest_sessions",
            parameters=(account_id, 1),
        )

        assert len(result.rows) == 1
        assert result.rows[0]["session_name"] == "Newer run"

    def test_result_summary_procedure(
        self,
        sessions_database,
        user_id,
        account_id,
        session_id,
    ) -> None:
        with sessions_database.session() as session:
            run_trade(session, user_id, account_id, session_id)

        result = StoredProcedureService(sessions_database).call(
            "sp_aqos_paper_session_result_summary",
            parameters=(session_id,),
            out_parameters=(
                "total_orders",
                "total_fills",
                "total_trades",
                "winning_trades",
                "net_pnl",
            ),
        )

        assert result.out_values["total_orders"] == 2
        assert result.out_values["total_fills"] == 2
        assert result.out_values["total_trades"] == 1
        assert result.out_values["winning_trades"] == 1
        assert float(result.out_values["net_pnl"]) == pytest.approx(10.0)

    def test_result_summary_leaves_pnl_null_without_trades(
        self,
        sessions_database,
        session_id,
    ) -> None:
        """Unknown must not arrive as zero from the database either."""

        result = StoredProcedureService(sessions_database).call(
            "sp_aqos_paper_session_result_summary",
            parameters=(session_id,),
            out_parameters=(
                "total_orders",
                "total_fills",
                "total_trades",
                "winning_trades",
                "net_pnl",
            ),
        )

        assert result.out_values["total_trades"] == 0
        assert result.out_values["net_pnl"] is None

    def test_profit_factor_procedure_reports_the_state(
        self,
        sessions_database,
        user_id,
        account_id,
        session_id,
    ) -> None:
        """The procedure must not hand back a bare NULL for a wins-only run."""

        with sessions_database.session() as session:
            run_trade(session, user_id, account_id, session_id)

        with sessions_database.session() as session:
            PaperSessionResultService(session).build_and_store_result(
                session_id=session_id
            )

        result = StoredProcedureService(sessions_database).call_read_only(
            "sp_aqos_paper_session_profit_factors",
            parameters=(account_id,),
        )

        assert len(result.rows) == 1
        assert result.rows[0]["profit_factor"] is None
        assert result.rows[0]["profit_factor_state"] == "infinite_no_losses"

    def test_decision_breakdown_procedure(
        self,
        sessions_database,
        user_id,
        account_id,
        session_id,
    ) -> None:
        with sessions_database.session() as session:
            run_trade(session, user_id, account_id, session_id)

        result = StoredProcedureService(sessions_database).call_read_only(
            "sp_aqos_paper_session_decision_breakdown",
            parameters=(session_id,),
        )

        assert len(result.rows) == 1
        assert result.rows[0]["is_allowed"] == 1
        assert result.rows[0]["total"] == 1


class TestDatabaseConstraints:
    """Raw SQL bypasses the Python guards, so MySQL must refuse the same rows."""

    def insert_session(self, session, **overrides) -> None:
        payload = {
            "session_id": "session_raw",
            "session_name": "Raw",
            "session_type": "manual_paper_session",
            "status": "running",
            "initial_balance": STARTING_BALANCE,
            "final_balance": None,
            "total_trades": None,
            "net_pnl": None,
            "started_at": FIXED_NOW,
            "ended_at": None,
            "now": FIXED_NOW,
        }
        payload.update(overrides)

        session.execute(
            text(
                "INSERT INTO paper_sessions (session_id, user_id, account_id, "
                "session_name, session_type, status, initial_balance, "
                "final_balance, total_trades, net_pnl, started_at_utc, "
                "ended_at_utc, created_at_utc, updated_at_utc, metadata_json) "
                "VALUES (:session_id, :user_id, :account_id, :session_name, "
                ":session_type, :status, :initial_balance, :final_balance, "
                ":total_trades, :net_pnl, :started_at, :ended_at, :now, :now, "
                "'{}')"
            ),
            payload,
        )

    def test_a_finished_session_without_an_end_time_is_refused(
        self,
        sessions_database,
        user_id,
        account_id,
    ) -> None:
        with pytest.raises(
            DatabaseError,
            match="ck_paper_sessions_terminal_has_end",
        ):
            with sessions_database.session() as session:
                self.insert_session(
                    session,
                    user_id=user_id,
                    account_id=account_id,
                    status="completed",
                    ended_at=None,
                )

    def test_an_open_session_with_an_end_time_is_refused(
        self,
        sessions_database,
        user_id,
        account_id,
    ) -> None:
        with pytest.raises(
            DatabaseError,
            match="ck_paper_sessions_open_has_no_end",
        ):
            with sessions_database.session() as session:
                self.insert_session(
                    session,
                    user_id=user_id,
                    account_id=account_id,
                    status="running",
                    ended_at=FIXED_NOW,
                )

    def test_an_end_before_the_start_is_refused(
        self,
        sessions_database,
        user_id,
        account_id,
    ) -> None:
        with pytest.raises(
            DatabaseError,
            match="ck_paper_sessions_end_after_start",
        ):
            with sessions_database.session() as session:
                self.insert_session(
                    session,
                    user_id=user_id,
                    account_id=account_id,
                    status="completed",
                    started_at=datetime(2026, 2, 1),
                    ended_at=datetime(2026, 1, 1),
                )

    def test_pnl_without_a_trade_count_is_refused(
        self,
        sessions_database,
        user_id,
        account_id,
    ) -> None:
        """A PnL figure with no trade count behind it is unexplainable."""

        with pytest.raises(
            DatabaseError,
            match="ck_paper_sessions_pnl_needs_trade_count",
        ):
            with sessions_database.session() as session:
                self.insert_session(
                    session,
                    user_id=user_id,
                    account_id=account_id,
                    net_pnl=100.0,
                    total_trades=None,
                )

    def test_a_non_positive_initial_balance_is_refused(
        self,
        sessions_database,
        user_id,
        account_id,
    ) -> None:
        with pytest.raises(
            DatabaseError,
            match="ck_paper_sessions_initial_balance_positive",
        ):
            with sessions_database.session() as session:
                self.insert_session(
                    session,
                    user_id=user_id,
                    account_id=account_id,
                    initial_balance=0,
                )

    def test_a_session_for_an_unknown_account_is_refused(
        self,
        sessions_database,
        user_id,
    ) -> None:
        with pytest.raises(IntegrityError):
            with sessions_database.session() as session:
                self.insert_session(
                    session,
                    user_id=user_id,
                    account_id="account_missing",
                )

    def test_an_order_for_an_unknown_session_is_refused(
        self,
        sessions_database,
        user_id,
        account_id,
    ) -> None:
        with pytest.raises(IntegrityError):
            with sessions_database.session() as session:
                session.execute(
                    text(
                        "INSERT INTO paper_orders (order_id, user_id, "
                        "account_id, session_id, symbol, action, order_type, "
                        "status, quantity, created_at_utc, updated_at_utc, "
                        "metadata_json) VALUES ('o_ghost', :user_id, "
                        ":account_id, 'session_missing', 'XAUUSD', 'buy', "
                        "'market', 'accepted', 1, :now, :now, '{}')"
                    ),
                    {
                        "user_id": user_id,
                        "account_id": account_id,
                        "now": FIXED_NOW,
                    },
                )

    def test_a_finite_state_without_a_value_is_refused(
        self,
        sessions_database,
        user_id,
        account_id,
    ) -> None:
        with pytest.raises(
            DatabaseError,
            match="ck_paper_sessions_finite_profit_factor_has_value",
        ):
            with sessions_database.session() as session:
                session.execute(
                    text(
                        "INSERT INTO paper_sessions (session_id, user_id, "
                        "account_id, session_name, session_type, status, "
                        "initial_balance, profit_factor, profit_factor_state, "
                        "started_at_utc, created_at_utc, updated_at_utc, "
                        "metadata_json) VALUES ('session_pf1', :user_id, "
                        ":account_id, 'Raw', 'manual_paper_session', "
                        "'running', 10000, NULL, 'finite', "
                        ":now, :now, :now, '{}')"
                    ),
                    {
                        "user_id": user_id,
                        "account_id": account_id,
                        "now": FIXED_NOW,
                    },
                )

    def test_an_infinite_state_carrying_a_number_is_refused(
        self,
        sessions_database,
        user_id,
        account_id,
    ) -> None:
        """NULL plus a state is the only honest encoding of infinity."""

        with pytest.raises(
            DatabaseError,
            match="ck_paper_sessions_non_finite_profit_factor_is_null",
        ):
            with sessions_database.session() as session:
                session.execute(
                    text(
                        "INSERT INTO paper_sessions (session_id, user_id, "
                        "account_id, session_name, session_type, status, "
                        "initial_balance, profit_factor, profit_factor_state, "
                        "started_at_utc, created_at_utc, updated_at_utc, "
                        "metadata_json) VALUES ('session_pf2', :user_id, "
                        ":account_id, 'Raw', 'manual_paper_session', "
                        "'running', 10000, 2.5, 'infinite_no_losses', "
                        ":now, :now, :now, '{}')"
                    ),
                    {
                        "user_id": user_id,
                        "account_id": account_id,
                        "now": FIXED_NOW,
                    },
                )

    def test_an_unknown_profit_factor_state_is_refused(
        self,
        sessions_database,
        user_id,
        account_id,
    ) -> None:
        with pytest.raises(
            DatabaseError,
            match="ck_paper_sessions_profit_factor_state",
        ):
            with sessions_database.session() as session:
                session.execute(
                    text(
                        "INSERT INTO paper_sessions (session_id, user_id, "
                        "account_id, session_name, session_type, status, "
                        "initial_balance, profit_factor, profit_factor_state, "
                        "started_at_utc, created_at_utc, updated_at_utc, "
                        "metadata_json) VALUES ('session_pf3', :user_id, "
                        ":account_id, 'Raw', 'manual_paper_session', "
                        "'running', 10000, NULL, 'made_up', "
                        ":now, :now, :now, '{}')"
                    ),
                    {
                        "user_id": user_id,
                        "account_id": account_id,
                        "now": FIXED_NOW,
                    },
                )

    def test_deleting_a_session_keeps_its_activity(
        self,
        sessions_database,
        user_id,
        account_id,
        session_id,
    ) -> None:
        """History survives; only the grouping reference is dropped."""

        with sessions_database.session() as session:
            run_trade(session, user_id, account_id, session_id)

        with sessions_database.session() as session:
            PaperSessionRepository(session).delete_session(session_id)

        with sessions_database.read_session() as session:
            trades = PaperTradeRepository(session).list_trades(
                account_id=account_id
            )

            assert len(trades) == 1
            assert trades[0].session_id is None

    def test_deleting_an_account_cascades_to_sessions(
        self,
        sessions_database,
        account_id,
        session_id,
    ) -> None:
        with sessions_database.session() as session:
            TradingAccountRepository(session).delete_account(account_id)

        with sessions_database.read_session() as session:
            assert PaperSessionRepository(session).list_sessions(
                account_id=account_id
            ) == ()
