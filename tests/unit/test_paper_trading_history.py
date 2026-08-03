"""Unit tests for paper history contracts and the analytics trade source."""

from __future__ import annotations

from datetime import date, datetime

import pytest

from aqos.account_analytics.metrics import (
    AccountTradeRecord,
    TradeMetricsAvailability,
    calculate_trade_metrics,
)
from aqos.account_analytics.trade_source import (
    AQOS_ACCOUNT_TRADE_SOURCE_VERSION,
    AccountTradeSource,
    is_trade_source,
    resolve_trades,
)
from aqos.paper_trading.contracts import PaperSide, PaperTradingError
from aqos.paper_trading.history import (
    AQOS_PAPER_HISTORY_VERSION,
    DailyPnlPoint,
    EquityPoint,
    OpenRisk,
    PaperHistoryService,
    PaperTradeSource,
    SignalExecutionHistory,
    validate_period,
)
from aqos.paper_trading.models import PaperTradeRecord
from aqos.paper_trading.simulator import PaperExitReason


FIXED_NOW = datetime(2026, 1, 1, 0, 0, 0)


def build_trade_record(
    trade_id: str = "trade_1",
    net_pnl: float = 10.0,
    closed_at_utc: datetime = FIXED_NOW,
) -> PaperTradeRecord:
    return PaperTradeRecord(
        trade_id=trade_id,
        account_id="account_1",
        symbol="XAUUSD",
        side=PaperSide.LONG,
        quantity=1.0,
        entry_price=100.0,
        exit_price=110.0,
        gross_pnl=net_pnl,
        commission=0.0,
        net_pnl=net_pnl,
        exit_reason=PaperExitReason.TAKE_PROFIT,
        opened_at_utc=FIXED_NOW,
        closed_at_utc=closed_at_utc,
    )


class FakeTradeSource:
    """A minimal object satisfying the analytics source protocol."""

    def __init__(self, records: tuple[AccountTradeRecord, ...] = ()) -> None:
        self.records = records
        self.calls: list[dict] = []

    def list_account_trades(
        self,
        user_id=None,
        account_id=None,
        period_start_utc=None,
        period_end_utc=None,
    ):
        self.calls.append(
            {
                "user_id": user_id,
                "account_id": account_id,
                "period_start_utc": period_start_utc,
                "period_end_utc": period_end_utc,
            }
        )

        return self.records


def test_module_versions_are_declared() -> None:
    assert AQOS_PAPER_HISTORY_VERSION == "1.0"
    assert AQOS_ACCOUNT_TRADE_SOURCE_VERSION == "1.0"


class TestValidatePeriod:
    def test_an_ordered_period_is_accepted(self) -> None:
        validate_period(FIXED_NOW, datetime(2026, 2, 1))

    def test_open_ended_periods_are_accepted(self) -> None:
        validate_period(None, None)
        validate_period(FIXED_NOW, None)
        validate_period(None, FIXED_NOW)

    def test_a_reversed_period_is_rejected(self) -> None:
        with pytest.raises(PaperTradingError, match="cannot be before"):
            validate_period(datetime(2026, 2, 1), FIXED_NOW)

    def test_an_equal_period_is_accepted(self) -> None:
        validate_period(FIXED_NOW, FIXED_NOW)


class TestTradeSourceProtocol:
    def test_an_object_with_the_method_is_a_source(self) -> None:
        assert is_trade_source(FakeTradeSource()) is True

    def test_a_list_of_records_is_not_a_source(self) -> None:
        """A fixed sequence cannot answer a scoped query, so it is used as-is."""

        assert is_trade_source([]) is False
        assert is_trade_source(()) is False

    def test_an_unrelated_object_is_not_a_source(self) -> None:
        assert is_trade_source(object()) is False

    def test_the_protocol_is_runtime_checkable(self) -> None:
        assert isinstance(FakeTradeSource(), AccountTradeSource)

    def test_resolve_trades_passes_the_scope_to_a_source(self) -> None:
        source = FakeTradeSource()

        resolve_trades(
            source,
            user_id="user_1",
            account_id="account_1",
            period_start_utc=FIXED_NOW,
            period_end_utc=datetime(2026, 2, 1),
        )

        assert source.calls == [
            {
                "user_id": "user_1",
                "account_id": "account_1",
                "period_start_utc": FIXED_NOW,
                "period_end_utc": datetime(2026, 2, 1),
            }
        ]

    def test_resolve_trades_returns_a_sequence_untouched(self) -> None:
        records = (
            AccountTradeRecord(
                trade_id="t1",
                net_pnl=5.0,
                closed_at_utc=FIXED_NOW,
            ),
        )

        assert resolve_trades(records, account_id="account_1") is records


class TestAvailabilityRules:
    def test_a_connected_source_with_no_trades_is_available(self) -> None:
        """Zero trades is a measured result, not a missing source."""

        metrics = calculate_trade_metrics(
            resolve_trades(FakeTradeSource(records=()))
        )

        assert metrics.availability == TradeMetricsAvailability.AVAILABLE
        assert metrics.is_available is True
        assert metrics.total_trades == 0
        assert metrics.net_pnl == 0.0
        # Ratios stay unknown: there were no trades to measure them over.
        assert metrics.win_rate is None
        assert metrics.profit_factor is None

    def test_a_connected_source_with_trades_measures_them(self) -> None:
        source = FakeTradeSource(
            records=(
                AccountTradeRecord("t1", 100.0, datetime(2026, 1, 2)),
                AccountTradeRecord("t2", -40.0, datetime(2026, 1, 3)),
            )
        )

        metrics = calculate_trade_metrics(
            resolve_trades(source),
            starting_balance=10_000.0,
        )

        assert metrics.is_available is True
        assert metrics.total_trades == 2
        assert metrics.net_pnl == pytest.approx(60.0)
        assert metrics.win_rate == pytest.approx(0.5)
        assert metrics.ending_balance == pytest.approx(10_060.0)


class TestEquityPoint:
    def test_to_dict(self) -> None:
        payload = EquityPoint(
            at_utc=FIXED_NOW,
            trade_id="trade_1",
            net_pnl=12.5,
            equity=10_012.5,
        ).to_dict()

        assert payload == {
            "at_utc": FIXED_NOW.isoformat(),
            "trade_id": "trade_1",
            "net_pnl": 12.5,
            "equity": 10_012.5,
        }


class TestDailyPnlPoint:
    def test_to_dict(self) -> None:
        payload = DailyPnlPoint(
            day=date(2026, 1, 1),
            net_pnl=-5.0,
            trade_count=3,
            winning_trades=1,
            losing_trades=2,
        ).to_dict()

        assert payload["day"] == "2026-01-01"
        assert payload["net_pnl"] == -5.0
        assert payload["trade_count"] == 3


class TestOpenRisk:
    def test_a_fully_measured_risk(self) -> None:
        risk = OpenRisk(
            account_id="account_1",
            open_position_count=2,
            measured_risk=150.0,
            positions_without_stop=0,
            measured_at_utc=FIXED_NOW,
        )

        assert risk.is_fully_measured is True
        assert risk.to_dict()["measured_risk"] == 150.0

    def test_positions_without_a_stop_are_reported_separately(self) -> None:
        """Unmeasurable risk must not be folded in as zero."""

        risk = OpenRisk(
            account_id="account_1",
            open_position_count=3,
            measured_risk=150.0,
            positions_without_stop=1,
            measured_at_utc=FIXED_NOW,
        )

        assert risk.is_fully_measured is False
        assert risk.to_dict()["positions_without_stop"] == 1


class TestSignalExecutionHistory:
    def test_an_unexecuted_signal_has_no_pnl(self) -> None:
        """No closed trade means unknown PnL, not zero."""

        history = SignalExecutionHistory(signal_id="signal_1")

        assert history.was_executed is False
        assert history.net_pnl is None
        assert history.to_dict()["net_pnl"] is None

    def test_an_executed_signal_sums_its_trades(self) -> None:
        history = SignalExecutionHistory(
            signal_id="signal_1",
            trades=(
                build_trade_record("t1", 10.0),
                build_trade_record("t2", -4.0),
            ),
        )

        assert history.net_pnl == pytest.approx(6.0)

    def test_to_dict_counts_each_artefact(self) -> None:
        payload = SignalExecutionHistory(
            signal_id="signal_1",
            trades=(build_trade_record(),),
        ).to_dict()

        assert payload["signal_id"] == "signal_1"
        assert payload["trade_count"] == 1
        assert payload["order_count"] == 0


class TestServiceConstruction:
    def test_the_history_service_requires_a_session(self) -> None:
        with pytest.raises(ValueError, match="session is required"):
            PaperHistoryService(None)

    def test_the_trade_source_requires_a_session(self) -> None:
        with pytest.raises(ValueError, match="session is required"):
            PaperTradeSource(None)
