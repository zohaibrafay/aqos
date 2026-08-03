"""
Paper trading history and analytics against real MySQL 8.

Run with::

    AQOS_TEST_DB_URL=mysql+pymysql://user:password@localhost:3306/aqos_test \\
        pytest -m mysql
"""

from __future__ import annotations

import os
from datetime import date, datetime, timedelta

import pytest
from sqlalchemy import text

from aqos.account_analytics.service import (
    AccountAnalyticsService,
    AccountAnalyticsSnapshotRepository,
)
from aqos.account_reports.builder import (
    available_report_types,
    build_account_performance_report,
)
from aqos.account_reports.contracts import ReportType
from aqos.accounts.models import AccountType, BrokerKind
from aqos.accounts.repositories import TradingAccountRepository
from aqos.database.config import parse_database_url
from aqos.database.engine import AqosDatabase
from aqos.database.migration_runner import apply_migrations
from aqos.database.procedures import StoredProcedureService
from aqos.execution_policy.modes import ExecutionMode
from aqos.paper_trading.contracts import (
    PaperAction,
    PaperExecutionRequest,
    PaperOrderStatus,
    PaperOrderType,
    PaperPositionStatus,
    PaperSide,
    PaperTradingError,
)
from aqos.paper_trading.execution_service import PaperExecutionService
from aqos.paper_trading.history import PaperHistoryService, PaperTradeSource
from aqos.paper_trading.simulator import PaperExitReason, PaperMarketBar
from aqos.signals.models import SignalAction, SignalSource
from aqos.signals.repositories import TradingSignalRepository
from aqos.trading_settings.repositories import TradingSettingsRepository
from aqos.users.repositories import UserProfileRepository


ENV_TEST_DB_URL = "AQOS_TEST_DB_URL"

FIXED_NOW = datetime(2026, 1, 1, 0, 0, 0)
STARTING_BALANCE = 10_000.0

pytestmark = pytest.mark.mysql


def requires_mysql() -> str:
    url = os.environ.get(ENV_TEST_DB_URL, "").strip()

    if not url:
        pytest.skip(
            f"{ENV_TEST_DB_URL} is not set, so paper history and analytics are "
            "NOT verified against MySQL by this run. Run them with:\n"
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
def history_database() -> AqosDatabase:
    url = requires_mysql()
    database = AqosDatabase(config=parse_database_url(url))

    if not database.ping():
        database.dispose()
        pytest.skip("MySQL server is not reachable; paper history NOT verified.")

    apply_migrations(database)
    reset_tables(database)

    yield database

    reset_tables(database)
    database.dispose()


@pytest.fixture
def user_id(history_database) -> str:
    with history_database.session() as session:
        user_id = UserProfileRepository(session).create_user(
            email="history@example.com",
            display_name="History Trader",
            created_at_utc=FIXED_NOW,
        ).user_id

        TradingSettingsRepository(session).create_for_user(
            user_id=user_id,
            execution_mode=ExecutionMode.AUTO_TRADE,
            created_at_utc=FIXED_NOW,
        )

        return user_id


@pytest.fixture
def account_id(history_database, user_id: str) -> str:
    with history_database.session() as session:
        return TradingAccountRepository(session).create_account(
            user_id=user_id,
            name="Paper History",
            account_type=AccountType.PAPER,
            broker=BrokerKind.INTERNAL_PAPER,
            initial_balance=STARTING_BALANCE,
            execution_mode=ExecutionMode.AUTO_TRADE,
            auto_trade_enabled=True,
            created_at_utc=FIXED_NOW,
        ).account_id


def build_bar(
    minutes: int = 0,
    symbol: str = "XAUUSD",
    open_price: float = 100.0,
    high: float = 105.0,
    low: float = 95.0,
    close: float = 102.0,
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


def open_and_close(
    session,
    user_id: str,
    account_id: str,
    symbol: str = "XAUUSD",
    open_minutes: int = 0,
    close_minutes: int = 60,
    entry: float = 100.0,
    exit_price: float = 110.0,
    action: PaperAction = PaperAction.BUY,
    signal_id: str | None = None,
):
    """Run one full paper trade and return its close outcome."""

    account = TradingAccountRepository(session).require(account_id)
    service = PaperExecutionService(session)

    result = service.execute(
        request=PaperExecutionRequest(
            user_id=user_id,
            account_id=account_id,
            symbol=symbol,
            action=action,
            quantity=1.0,
            order_type=PaperOrderType.MARKET,
            submitted_at_utc=FIXED_NOW + timedelta(minutes=open_minutes),
            signal_id=signal_id,
        ),
        account=account,
        bar=build_bar(
            minutes=open_minutes,
            symbol=symbol,
            open_price=entry,
            high=entry + 5,
            low=entry - 5,
            close=entry,
        ),
    )
    result.raise_if_rejected()

    outcomes = service.close_all_positions(
        account,
        build_bar(
            minutes=close_minutes,
            symbol=symbol,
            open_price=exit_price,
            high=exit_price + 1,
            low=exit_price - 1,
            close=exit_price,
        ),
    )

    return outcomes[0]


def seed_two_trades(history_database, user_id: str, account_id: str) -> None:
    """One winner on XAUUSD, one loser on EURUSD, on different days."""

    with history_database.session() as session:
        open_and_close(
            session,
            user_id,
            account_id,
            symbol="XAUUSD",
            open_minutes=0,
            close_minutes=60,
            entry=100.0,
            exit_price=110.0,
        )

    with history_database.session() as session:
        open_and_close(
            session,
            user_id,
            account_id,
            symbol="EURUSD",
            open_minutes=1_500,
            close_minutes=1_560,
            entry=100.0,
            exit_price=96.0,
        )


class TestHistoryQueries:
    def test_order_history_filters_by_symbol_and_status(
        self,
        history_database,
        user_id,
        account_id,
    ) -> None:
        seed_two_trades(history_database, user_id, account_id)

        with history_database.read_session() as session:
            history = PaperHistoryService(session)

            assert len(history.order_history(account_id=account_id)) == 4
            assert len(
                history.order_history(account_id=account_id, symbol="XAUUSD")
            ) == 2
            assert len(
                history.order_history(
                    account_id=account_id,
                    status=PaperOrderStatus.FILLED,
                )
            ) == 4
            assert history.order_history(
                account_id=account_id,
                status=PaperOrderStatus.REJECTED,
            ) == ()

    def test_history_filters_by_period(
        self,
        history_database,
        user_id,
        account_id,
    ) -> None:
        seed_two_trades(history_database, user_id, account_id)

        with history_database.read_session() as session:
            history = PaperHistoryService(session)

            first_day_only = history.trade_history(
                account_id=account_id,
                period_end_utc=FIXED_NOW + timedelta(hours=12),
            )
            second_day_only = history.trade_history(
                account_id=account_id,
                period_start_utc=FIXED_NOW + timedelta(hours=12),
            )

            assert len(first_day_only) == 1
            assert first_day_only[0].symbol == "XAUUSD"
            assert len(second_day_only) == 1
            assert second_day_only[0].symbol == "EURUSD"

    def test_a_reversed_period_is_refused(
        self,
        history_database,
        account_id,
    ) -> None:
        with history_database.read_session() as session:
            with pytest.raises(PaperTradingError, match="cannot be before"):
                PaperHistoryService(session).trade_history(
                    account_id=account_id,
                    period_start_utc=datetime(2026, 2, 1),
                    period_end_utc=FIXED_NOW,
                )

    def test_trade_history_filters_by_side_and_exit_reason(
        self,
        history_database,
        user_id,
        account_id,
    ) -> None:
        seed_two_trades(history_database, user_id, account_id)

        with history_database.read_session() as session:
            history = PaperHistoryService(session)

            assert len(
                history.trade_history(account_id=account_id, side=PaperSide.LONG)
            ) == 2
            assert history.trade_history(
                account_id=account_id,
                side=PaperSide.SHORT,
            ) == ()
            assert len(
                history.trade_history(
                    account_id=account_id,
                    exit_reason=PaperExitReason.END_OF_DATA,
                )
            ) == 2

    def test_fill_and_position_history(
        self,
        history_database,
        user_id,
        account_id,
    ) -> None:
        seed_two_trades(history_database, user_id, account_id)

        with history_database.read_session() as session:
            history = PaperHistoryService(session)

            assert len(history.fill_history(account_id=account_id)) == 4
            assert len(history.position_history(account_id=account_id)) == 2
            assert history.position_history(
                account_id=account_id,
                status=PaperPositionStatus.OPEN,
            ) == ()
            assert len(
                history.position_history(
                    account_id=account_id,
                    status=PaperPositionStatus.CLOSED,
                )
            ) == 2

    def test_signal_execution_history_gathers_everything(
        self,
        history_database,
        user_id,
        account_id,
    ) -> None:
        with history_database.session() as session:
            signals = TradingSignalRepository(session)
            signal = signals.create_signal(
                user_id=user_id,
                account_id=account_id,
                symbol="XAUUSD",
                timeframe="H1",
                action=SignalAction.BUY,
                source=SignalSource.MANUAL,
                generated_at_utc=FIXED_NOW,
            )
            signals.approve_signal(signal.signal_id, occurred_at_utc=FIXED_NOW)
            signal_id = signal.signal_id

        with history_database.session() as session:
            open_and_close(
                session,
                user_id,
                account_id,
                open_minutes=5,
                close_minutes=60,
                signal_id=signal_id,
            )

        with history_database.read_session() as session:
            history = PaperHistoryService(session).signal_execution_history(
                signal_id=signal_id,
                account_id=account_id,
            )

            assert history.was_executed is True
            assert len(history.orders) == 2
            assert len(history.trades) == 1
            assert len(history.decisions) == 1
            assert history.net_pnl == pytest.approx(10.0)

    def test_a_signal_that_never_executed_has_unknown_pnl(
        self,
        history_database,
        account_id,
    ) -> None:
        """No trade means unknown, not zero."""

        with history_database.read_session() as session:
            history = PaperHistoryService(session).signal_execution_history(
                signal_id="signal_missing",
                account_id=account_id,
            )

            assert history.was_executed is False
            assert history.net_pnl is None


class TestBalanceAndEquity:
    def test_the_equity_curve_follows_closed_trades(
        self,
        history_database,
        user_id,
        account_id,
    ) -> None:
        seed_two_trades(history_database, user_id, account_id)

        with history_database.read_session() as session:
            curve = PaperHistoryService(session).equity_curve(
                account_id=account_id,
                starting_balance=STARTING_BALANCE,
            )

            assert len(curve) == 2
            assert curve[0].equity == pytest.approx(10_010.0)
            assert curve[1].equity == pytest.approx(10_006.0)
            assert curve[0].at_utc < curve[1].at_utc

    def test_an_account_with_no_trades_has_an_empty_curve(
        self,
        history_database,
        account_id,
    ) -> None:
        with history_database.read_session() as session:
            assert PaperHistoryService(session).equity_curve(
                account_id=account_id,
                starting_balance=STARTING_BALANCE,
            ) == ()

    def test_a_non_positive_starting_balance_is_refused(
        self,
        history_database,
        account_id,
    ) -> None:
        with history_database.read_session() as session:
            with pytest.raises(PaperTradingError, match="must be positive"):
                PaperHistoryService(session).equity_curve(
                    account_id=account_id,
                    starting_balance=0.0,
                )

    def test_daily_pnl_groups_by_close_date(
        self,
        history_database,
        user_id,
        account_id,
    ) -> None:
        seed_two_trades(history_database, user_id, account_id)

        with history_database.read_session() as session:
            days = PaperHistoryService(session).daily_pnl(account_id=account_id)

            assert len(days) == 2
            assert days[0].day == date(2026, 1, 1)
            assert days[0].net_pnl == pytest.approx(10.0)
            assert days[0].winning_trades == 1
            assert days[1].day == date(2026, 1, 2)
            assert days[1].net_pnl == pytest.approx(-4.0)
            assert days[1].losing_trades == 1

    def test_days_without_trades_are_absent_rather_than_zero(
        self,
        history_database,
        user_id,
        account_id,
    ) -> None:
        """A flat zero would imply the account traded and broke even."""

        seed_two_trades(history_database, user_id, account_id)

        with history_database.read_session() as session:
            days = PaperHistoryService(session).daily_pnl(account_id=account_id)

            assert [day.day for day in days] == [
                date(2026, 1, 1),
                date(2026, 1, 2),
            ]

    def test_realized_pnl_is_none_without_trades(
        self,
        history_database,
        account_id,
    ) -> None:
        with history_database.read_session() as session:
            assert PaperHistoryService(session).realized_pnl(
                account_id=account_id
            ) is None

    def test_realized_pnl_sums_closed_trades(
        self,
        history_database,
        user_id,
        account_id,
    ) -> None:
        seed_two_trades(history_database, user_id, account_id)

        with history_database.read_session() as session:
            assert PaperHistoryService(session).realized_pnl(
                account_id=account_id
            ) == pytest.approx(6.0)

    def test_open_risk_reports_positions_without_a_stop(
        self,
        history_database,
        user_id,
        account_id,
    ) -> None:
        with history_database.session() as session:
            account = TradingAccountRepository(session).require(account_id)
            service = PaperExecutionService(session)

            service.execute(
                request=PaperExecutionRequest(
                    user_id=user_id,
                    account_id=account_id,
                    symbol="XAUUSD",
                    action=PaperAction.BUY,
                    quantity=2.0,
                    order_type=PaperOrderType.MARKET,
                    submitted_at_utc=FIXED_NOW,
                    stop_loss=96.0,
                ),
                account=account,
                bar=build_bar(),
            ).raise_if_rejected()

            service.execute(
                request=PaperExecutionRequest(
                    user_id=user_id,
                    account_id=account_id,
                    symbol="EURUSD",
                    action=PaperAction.BUY,
                    quantity=1.0,
                    order_type=PaperOrderType.MARKET,
                    submitted_at_utc=FIXED_NOW + timedelta(minutes=1),
                ),
                account=account,
                bar=build_bar(minutes=1, symbol="EURUSD"),
            ).raise_if_rejected()

        with history_database.read_session() as session:
            risk = PaperHistoryService(session).open_risk(
                account_id=account_id,
                measured_at_utc=FIXED_NOW,
            )

            assert risk.open_position_count == 2
            assert risk.measured_risk == pytest.approx(8.0)
            assert risk.positions_without_stop == 1
            assert risk.is_fully_measured is False

    def test_snapshot_history_is_exposed(
        self,
        history_database,
        user_id,
        account_id,
    ) -> None:
        with history_database.session() as session:
            account = TradingAccountRepository(session).require(account_id)
            PaperExecutionService(session).capture_snapshot(
                account,
                captured_at_utc=FIXED_NOW,
            )

        with history_database.read_session() as session:
            snapshots = PaperHistoryService(session).snapshot_history(account_id)

            assert len(snapshots) == 1
            assert float(snapshots[0].starting_balance) == pytest.approx(
                STARTING_BALANCE
            )


class TestAnalyticsFromPersistedTrades:
    def test_analytics_consume_persisted_paper_trades(
        self,
        history_database,
        user_id,
        account_id,
    ) -> None:
        """Sprint 046 metrics now read real rows, not a hand-built list."""

        seed_two_trades(history_database, user_id, account_id)

        with history_database.read_session() as session:
            analytics = AccountAnalyticsService(
                session,
                trade_source=PaperTradeSource(session),
            ).build_account_analytics(
                user_id=user_id,
                account_id=account_id,
                starting_balance=STARTING_BALANCE,
                calculated_at_utc=FIXED_NOW,
            )

        metrics = analytics.trade_metrics

        assert analytics.has_trade_metrics is True
        assert metrics.total_trades == 2
        assert metrics.winning_trades == 1
        assert metrics.losing_trades == 1
        assert metrics.net_pnl == pytest.approx(6.0)
        assert metrics.win_rate == pytest.approx(0.5)
        assert metrics.profit_factor == pytest.approx(2.5)
        assert metrics.ending_balance == pytest.approx(10_006.0)

    def test_a_connected_source_with_no_trades_is_available_with_zero(
        self,
        history_database,
        user_id,
        account_id,
    ) -> None:
        """Connected but empty is a measured zero, not unknown."""

        with history_database.read_session() as session:
            analytics = AccountAnalyticsService(
                session,
                trade_source=PaperTradeSource(session),
            ).build_account_analytics(
                user_id=user_id,
                account_id=account_id,
                starting_balance=STARTING_BALANCE,
                calculated_at_utc=FIXED_NOW,
            )

        metrics = analytics.trade_metrics

        assert analytics.has_trade_metrics is True
        assert metrics.total_trades == 0
        assert metrics.net_pnl == pytest.approx(0.0)
        assert metrics.win_rate is None
        assert metrics.unavailable_reason is None

    def test_no_source_stays_unavailable(
        self,
        history_database,
        user_id,
        account_id,
    ) -> None:
        """Unknown must never collapse into zero."""

        with history_database.read_session() as session:
            analytics = AccountAnalyticsService(session).build_account_analytics(
                user_id=user_id,
                account_id=account_id,
                calculated_at_utc=FIXED_NOW,
            )

        metrics = analytics.trade_metrics

        assert analytics.has_trade_metrics is False
        assert metrics.total_trades is None
        assert metrics.net_pnl is None
        assert metrics.unavailable_reason

    def test_the_source_respects_the_requested_period(
        self,
        history_database,
        user_id,
        account_id,
    ) -> None:
        seed_two_trades(history_database, user_id, account_id)

        with history_database.read_session() as session:
            analytics = AccountAnalyticsService(
                session,
                trade_source=PaperTradeSource(session),
            ).build_account_analytics(
                user_id=user_id,
                account_id=account_id,
                period_end_utc=FIXED_NOW + timedelta(hours=12),
                starting_balance=STARTING_BALANCE,
                calculated_at_utc=FIXED_NOW,
            )

        assert analytics.trade_metrics.total_trades == 1
        assert analytics.trade_metrics.net_pnl == pytest.approx(10.0)

    def test_user_scoped_analytics_span_the_users_paper_accounts(
        self,
        history_database,
        user_id,
        account_id,
    ) -> None:
        seed_two_trades(history_database, user_id, account_id)

        with history_database.session() as session:
            second = TradingAccountRepository(session).create_account(
                user_id=user_id,
                name="Paper Two",
                account_type=AccountType.PAPER,
                broker=BrokerKind.INTERNAL_PAPER,
                initial_balance=STARTING_BALANCE,
                execution_mode=ExecutionMode.AUTO_TRADE,
                auto_trade_enabled=True,
                created_at_utc=FIXED_NOW,
            ).account_id

        with history_database.session() as session:
            open_and_close(
                session,
                user_id,
                second,
                open_minutes=3_000,
                close_minutes=3_060,
                entry=100.0,
                exit_price=105.0,
            )

        with history_database.read_session() as session:
            analytics = AccountAnalyticsService(
                session,
                trade_source=PaperTradeSource(session),
            ).build_user_analytics(
                user_id=user_id,
                starting_balance=STARTING_BALANCE,
                calculated_at_utc=FIXED_NOW,
            )

        assert analytics.trade_metrics.total_trades == 3
        assert analytics.trade_metrics.net_pnl == pytest.approx(11.0)

    def test_a_snapshot_stores_the_real_trade_metrics(
        self,
        history_database,
        user_id,
        account_id,
    ) -> None:
        seed_two_trades(history_database, user_id, account_id)

        with history_database.session() as session:
            analytics = AccountAnalyticsService(
                session,
                trade_source=PaperTradeSource(session),
            ).build_account_analytics(
                user_id=user_id,
                account_id=account_id,
                starting_balance=STARTING_BALANCE,
                calculated_at_utc=FIXED_NOW,
            )
            snapshot_id = AccountAnalyticsSnapshotRepository(session).save_snapshot(
                analytics
            ).snapshot_id

        with history_database.read_session() as session:
            stored = AccountAnalyticsSnapshotRepository(session).require(snapshot_id)

            assert stored.trade_metrics_available is True
            assert stored.total_trades == 2
            assert float(stored.net_pnl) == pytest.approx(6.0)
            assert float(stored.win_rate) == pytest.approx(0.5)


class TestReportIntegration:
    def test_trade_performance_becomes_available_with_paper_trades(
        self,
        history_database,
        user_id,
        account_id,
    ) -> None:
        """Sprint 047 can now honestly produce a trade report for paper."""

        seed_two_trades(history_database, user_id, account_id)

        with history_database.read_session() as session:
            analytics = AccountAnalyticsService(
                session,
                trade_source=PaperTradeSource(session),
            ).build_account_analytics(
                user_id=user_id,
                account_id=account_id,
                starting_balance=STARTING_BALANCE,
                calculated_at_utc=FIXED_NOW,
            )

        assert ReportType.TRADE_PERFORMANCE in available_report_types(analytics)

    def test_trade_performance_stays_unavailable_without_a_source(
        self,
        history_database,
        user_id,
        account_id,
    ) -> None:
        with history_database.read_session() as session:
            analytics = AccountAnalyticsService(session).build_account_analytics(
                user_id=user_id,
                account_id=account_id,
                calculated_at_utc=FIXED_NOW,
            )

        assert ReportType.TRADE_PERFORMANCE not in available_report_types(analytics)

    def test_trade_performance_is_available_with_zero_paper_trades(
        self,
        history_database,
        user_id,
        account_id,
    ) -> None:
        """A connected repository reporting no trades is still a source."""

        with history_database.read_session() as session:
            analytics = AccountAnalyticsService(
                session,
                trade_source=PaperTradeSource(session),
            ).build_account_analytics(
                user_id=user_id,
                account_id=account_id,
                starting_balance=STARTING_BALANCE,
                calculated_at_utc=FIXED_NOW,
            )

        assert ReportType.TRADE_PERFORMANCE in available_report_types(analytics)

    def test_a_full_report_carries_the_paper_trade_metrics(
        self,
        history_database,
        user_id,
        account_id,
    ) -> None:
        seed_two_trades(history_database, user_id, account_id)

        with history_database.read_session() as session:
            analytics = AccountAnalyticsService(
                session,
                trade_source=PaperTradeSource(session),
            ).build_account_analytics(
                user_id=user_id,
                account_id=account_id,
                starting_balance=STARTING_BALANCE,
                calculated_at_utc=FIXED_NOW,
            )
            account = TradingAccountRepository(session).require(account_id)

            report = build_account_performance_report(
                analytics=analytics,
                account=account,
                report_type=ReportType.TRADE_PERFORMANCE,
                generated_at_utc=FIXED_NOW,
            )

        payload = report.to_dict()

        assert report.report_type == ReportType.TRADE_PERFORMANCE
        assert payload["trade_metrics_available"] is True
        assert payload["trade_metrics"]["total_trades"] == 2
        assert payload["trade_metrics"]["net_pnl"] == pytest.approx(6.0)
        assert payload["trade_metrics"]["win_rate"] == pytest.approx(0.5)


class TestStoredProcedures:
    def test_daily_pnl_procedure(
        self,
        history_database,
        user_id,
        account_id,
    ) -> None:
        seed_two_trades(history_database, user_id, account_id)

        result = StoredProcedureService(history_database).call_read_only(
            "sp_aqos_paper_daily_pnl",
            parameters=(account_id,),
        )

        rows = {str(row["trade_day"]): row for row in result.rows}

        assert set(rows) == {"2026-01-01", "2026-01-02"}
        assert float(rows["2026-01-01"]["net_pnl"]) == pytest.approx(10.0)
        assert rows["2026-01-01"]["winning_trades"] == 1
        assert float(rows["2026-01-02"]["net_pnl"]) == pytest.approx(-4.0)

    def test_equity_curve_procedure_matches_the_service(
        self,
        history_database,
        user_id,
        account_id,
    ) -> None:
        seed_two_trades(history_database, user_id, account_id)

        result = StoredProcedureService(history_database).call_read_only(
            "sp_aqos_paper_equity_curve",
            parameters=(account_id, STARTING_BALANCE),
        )

        with history_database.read_session() as session:
            curve = PaperHistoryService(session).equity_curve(
                account_id=account_id,
                starting_balance=STARTING_BALANCE,
            )

        assert [float(row["equity"]) for row in result.rows] == [
            pytest.approx(point.equity) for point in curve
        ]

    def test_symbol_performance_procedure(
        self,
        history_database,
        user_id,
        account_id,
    ) -> None:
        seed_two_trades(history_database, user_id, account_id)

        result = StoredProcedureService(history_database).call_read_only(
            "sp_aqos_paper_symbol_performance",
            parameters=(account_id,),
        )

        rows = {row["symbol"]: row for row in result.rows}

        assert set(rows) == {"XAUUSD", "EURUSD"}
        assert float(rows["XAUUSD"]["net_pnl"]) == pytest.approx(10.0)
        assert rows["EURUSD"]["winning_trades"] == 0

    def test_order_fill_summary_procedure(
        self,
        history_database,
        user_id,
        account_id,
    ) -> None:
        seed_two_trades(history_database, user_id, account_id)

        result = StoredProcedureService(history_database).call(
            "sp_aqos_paper_order_fill_summary",
            parameters=(account_id,),
            out_parameters=(
                "order_count",
                "filled_order_count",
                "rejected_order_count",
                "fill_count",
            ),
        )

        assert result.out_values["order_count"] == 4
        assert result.out_values["filled_order_count"] == 4
        assert result.out_values["rejected_order_count"] == 0
        assert result.out_values["fill_count"] == 4

    def test_order_fill_summary_on_an_empty_account(
        self,
        history_database,
        account_id,
    ) -> None:
        """No orders means zero, not NULL."""

        result = StoredProcedureService(history_database).call(
            "sp_aqos_paper_order_fill_summary",
            parameters=(account_id,),
            out_parameters=(
                "order_count",
                "filled_order_count",
                "rejected_order_count",
                "fill_count",
            ),
        )

        assert result.out_values["order_count"] == 0
        assert result.out_values["fill_count"] == 0

    def test_latest_account_state_procedure(
        self,
        history_database,
        user_id,
        account_id,
    ) -> None:
        with history_database.session() as session:
            account = TradingAccountRepository(session).require(account_id)
            service = PaperExecutionService(session)

            service.capture_snapshot(account, captured_at_utc=FIXED_NOW)
            service.capture_snapshot(
                account,
                captured_at_utc=FIXED_NOW + timedelta(hours=1),
            )

        result = StoredProcedureService(history_database).call_read_only(
            "sp_aqos_paper_latest_account_state",
            parameters=(account_id,),
        )

        assert len(result.rows) == 1
        assert result.rows[0]["captured_at_utc"] == FIXED_NOW + timedelta(hours=1)

    def test_latest_account_state_on_an_account_without_snapshots(
        self,
        history_database,
        account_id,
    ) -> None:
        result = StoredProcedureService(history_database).call_read_only(
            "sp_aqos_paper_latest_account_state",
            parameters=(account_id,),
        )

        assert result.rows == ()


class TestTradeSourceScoping:
    def test_the_source_only_reads_paper_accounts(
        self,
        history_database,
        user_id,
        account_id,
    ) -> None:
        """A live account's trades must never enter paper analytics."""

        seed_two_trades(history_database, user_id, account_id)

        with history_database.session() as session:
            live = TradingAccountRepository(session).create_account(
                user_id=user_id,
                name="Live One",
                account_type=AccountType.LIVE,
                broker=BrokerKind.MT5,
                initial_balance=STARTING_BALANCE,
                created_at_utc=FIXED_NOW,
            ).account_id

        with history_database.read_session() as session:
            source = PaperTradeSource(session)

            assert live not in source.paper_account_ids(user_id)
            assert account_id in source.paper_account_ids(user_id)
            assert len(source.list_account_trades(user_id=user_id)) == 2

    def test_a_user_with_no_paper_accounts_yields_no_trades(
        self,
        history_database,
        user_id,
    ) -> None:
        with history_database.read_session() as session:
            assert PaperTradeSource(session).list_account_trades(
                user_id="user_missing"
            ) == ()

    def test_a_reversed_period_is_refused_by_the_source(
        self,
        history_database,
        account_id,
    ) -> None:
        with history_database.read_session() as session:
            with pytest.raises(PaperTradingError, match="cannot be before"):
                PaperTradeSource(session).list_account_trades(
                    account_id=account_id,
                    period_start_utc=datetime(2026, 2, 1),
                    period_end_utc=FIXED_NOW,
                )
