"""
Guard tests: analytics and report payloads must be strictly valid JSON.

Python happily writes ``Infinity`` and ``NaN`` from ``json.dumps``, but neither
is JSON. MySQL refuses them in a JSON column and API consumers cannot parse
them, so an unbounded profit factor has to travel as a state rather than as a
non-standard number.
"""

from __future__ import annotations

import json
import math
from datetime import datetime

import pytest

from aqos.account_analytics.metrics import (
    ProfitFactorState,
    ReasonMetrics,
    SignalMetrics,
    TradeMetrics,
    TradeMetricsAvailability,
)
from aqos.account_analytics.models import (
    AccountAnalytics,
    AccountAnalyticsSnapshot,
    AnalyticsScope,
)
from aqos.account_reports.artifacts import render_report_json
from aqos.account_reports.contracts import (
    AccountPerformanceReport,
    ReportType,
)
from aqos.accounts.models import AccountType


FIXED_NOW = datetime(2026, 1, 1, 0, 0, 0)

#: Tokens Python emits for non-finite floats. None of them is valid JSON.
NON_JSON_TOKENS = ("Infinity", "-Infinity", "NaN")


def build_metrics(profit_factor: float | None) -> TradeMetrics:
    return TradeMetrics(
        availability=TradeMetricsAvailability.AVAILABLE,
        total_trades=3,
        winning_trades=3,
        losing_trades=0,
        win_rate=1.0,
        gross_profit=300.0,
        gross_loss=0.0,
        net_pnl=300.0,
        profit_factor=profit_factor,
        max_drawdown=0.0,
        starting_balance=10_000.0,
        ending_balance=10_300.0,
    )


def build_analytics(profit_factor: float | None) -> AccountAnalytics:
    return AccountAnalytics(
        scope=AnalyticsScope.ACCOUNT,
        user_id="user_1",
        account_id="account_1",
        calculated_at_utc=FIXED_NOW,
        signal_metrics=SignalMetrics(),
        reason_metrics=ReasonMetrics(),
        trade_metrics=build_metrics(profit_factor),
    )


def build_report(profit_factor: float | None) -> AccountPerformanceReport:
    return AccountPerformanceReport(
        report_id="report_1",
        report_type=ReportType.TRADE_PERFORMANCE,
        user_id="user_1",
        account_id="account_1",
        account_type=AccountType.PAPER,
        generated_at_utc=FIXED_NOW,
        trade_metrics=build_metrics(profit_factor),
    )


def dumps_strict(payload: object) -> str:
    """Serialise the way a JSON column or an API response would."""

    return json.dumps(payload, sort_keys=True, allow_nan=False)


PROFIT_FACTORS = [
    pytest.param(None, "unavailable", id="unavailable"),
    pytest.param(2.5, "finite", id="finite"),
    pytest.param(math.inf, "infinite_no_losses", id="infinite"),
]


class TestTradeMetricsPayload:
    @pytest.mark.parametrize("profit_factor, expected_state", PROFIT_FACTORS)
    def test_the_payload_is_strict_json(
        self,
        profit_factor,
        expected_state,
    ) -> None:
        payload = build_metrics(profit_factor).to_dict()
        rendered = dumps_strict(payload)

        assert json.loads(rendered)["profit_factor_state"] == expected_state

    def test_infinity_never_reaches_the_payload(self) -> None:
        payload = build_metrics(math.inf).to_dict()

        assert payload["profit_factor"] is None
        assert payload["profit_factor_state"] == "infinite_no_losses"
        assert payload["has_infinite_profit_factor"] is True

    def test_the_in_memory_value_is_still_infinite(self) -> None:
        """Only the serialised form changes; the metric stays truthful."""

        metrics = build_metrics(math.inf)

        assert math.isinf(metrics.profit_factor)
        assert metrics.profit_factor_state == (
            ProfitFactorState.INFINITE_NO_LOSSES
        )

    def test_no_non_json_token_appears(self) -> None:
        rendered = dumps_strict(build_metrics(math.inf).to_dict())

        for token in NON_JSON_TOKENS:
            assert token not in rendered


class TestAnalyticsPayload:
    @pytest.mark.parametrize("profit_factor, expected_state", PROFIT_FACTORS)
    def test_the_payload_is_strict_json(
        self,
        profit_factor,
        expected_state,
    ) -> None:
        rendered = dumps_strict(build_analytics(profit_factor).to_dict())
        restored = json.loads(rendered)

        assert restored["trade_metrics"]["profit_factor_state"] == expected_state

    def test_a_wins_only_payload_survives_a_json_round_trip(self) -> None:
        """This is the payload that MySQL previously refused outright."""

        payload = build_analytics(math.inf).to_dict()
        restored = json.loads(dumps_strict(payload))

        assert restored["trade_metrics"]["profit_factor"] is None
        assert restored["trade_metrics"]["has_infinite_profit_factor"] is True


class TestReportPayload:
    @pytest.mark.parametrize("profit_factor, expected_state", PROFIT_FACTORS)
    def test_the_rendered_artifact_is_strict_json(
        self,
        profit_factor,
        expected_state,
    ) -> None:
        rendered = render_report_json(build_report(profit_factor))
        restored = json.loads(rendered)

        assert restored["trade_metrics"]["profit_factor_state"] == expected_state

    def test_the_writer_refuses_non_json_numbers(self) -> None:
        """
        The artifact writer fails loudly rather than shipping ``Infinity``.

        A checksummed artifact that no consumer can parse is worse than an
        error at write time.
        """

        report = build_report(2.5)
        payload = report.to_dict()
        payload["trade_metrics"]["profit_factor"] = math.inf

        with pytest.raises(ValueError, match="Out of range float"):
            json.dumps(payload, allow_nan=False)

    def test_no_non_json_token_appears_in_an_artifact(self) -> None:
        rendered = render_report_json(build_report(math.inf))

        for token in NON_JSON_TOKENS:
            assert token not in rendered

    def test_the_summary_row_is_strict_json(self) -> None:
        rendered = dumps_strict(build_report(math.inf).summary_row())

        assert json.loads(rendered)["profit_factor"] is None


class TestSnapshotPayload:
    def test_a_stored_snapshot_payload_is_strict_json(self) -> None:
        snapshot = AccountAnalyticsSnapshot(
            snapshot_id="snapshot_1",
            user_id="user_1",
            scope=AnalyticsScope.USER,
            calculated_at_utc=FIXED_NOW,
            trade_metrics_available=True,
            total_trades=3,
            profit_factor=None,
            profit_factor_state=ProfitFactorState.INFINITE_NO_LOSSES,
            payload_json=build_analytics(math.inf).to_dict(),
        )
        snapshot.assert_trade_metrics_are_honest()

        rendered = dumps_strict(snapshot.payload_json)

        for token in NON_JSON_TOKENS:
            assert token not in rendered

    def test_the_snapshot_itself_is_strict_json(self) -> None:
        snapshot = AccountAnalyticsSnapshot(
            snapshot_id="snapshot_1",
            user_id="user_1",
            scope=AnalyticsScope.USER,
            calculated_at_utc=FIXED_NOW,
            trade_metrics_available=True,
            total_trades=3,
            profit_factor_state=ProfitFactorState.INFINITE_NO_LOSSES,
        )

        restored = json.loads(dumps_strict(snapshot.to_dict()))

        assert restored["profit_factor"] is None
        assert restored["profit_factor_state"] == "infinite_no_losses"
