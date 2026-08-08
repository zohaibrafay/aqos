"""
Read-only backtest APIs against real registry and report files.

The backtest registry is a JSON file rather than a MySQL table, so these tests
write real ones with the production writer and read them back through the API.
"""

from __future__ import annotations

import json

import pytest
from fastapi.testclient import TestClient

from aqos.backtesting.registry import (
    BacktestKind,
    BacktestResultEntry,
    BacktestResultRegistry,
    write_backtest_result_registry,
)
from aqos.http_api.app import create_aqos_api_app
from aqos.http_api.config import API_V1_PREFIX, ApiConfig, ApiEnvironment
from datetime import datetime, timedelta

from aqos.http_api.auth import AuthenticatedCaller
from aqos.http_api.authz import get_read_only_caller
from aqos.users.models import UserProfile, UserRole, UserSession, UserStatus



def build_stub_caller() -> AuthenticatedCaller:
    """
    A caller for tests that have no database.

    These suites exercise route behaviour, not authentication. The real token
    path is covered end to end by the MySQL protection tests; overriding the
    dependency here keeps these fast without pretending auth does not exist.
    """

    now = datetime(2026, 1, 1, 0, 0, 0)
    profile = UserProfile(
        user_id="user_stub",
        email="stub@example.com",
        display_name="Stub",
        role=UserRole.TRADER,
        status=UserStatus.ACTIVE,
        created_at_utc=now,
        updated_at_utc=now,
    )
    user_session = UserSession(
        session_id="session_stub",
        user_id="user_stub",
        token_hash="a" * 64,
        created_at_utc=now,
        expires_at_utc=now + timedelta(hours=1),
    )

    return AuthenticatedCaller(user=profile, session=user_session)


def authenticate(app) -> None:
    app.dependency_overrides[get_read_only_caller] = build_stub_caller


SECRET_DIR = "/srv/aqos/backtests"


def build_client(**overrides) -> TestClient:
    payload = {"environment": ApiEnvironment.TEST}
    payload.update(overrides)

    app = create_aqos_api_app(ApiConfig(**payload))
    authenticate(app)

    return TestClient(app)


@pytest.fixture
def report_file(tmp_path):
    path = tmp_path / "report.json"

    path.write_text(
        json.dumps(
            {
                "strategy_name": "Breakout",
                "trades": [
                    {"trade_id": "t1", "net_profit": 12.5, "symbol": "XAUUSD"},
                    {"trade_id": "t2", "net_profit": -4.0, "symbol": "XAUUSD"},
                ],
                "orders": [{"order_id": "o1", "side": "buy"}],
                "equity_curve": [
                    {"index": 0, "equity": 10_000.0},
                    {"index": 1, "equity": 10_012.5},
                ],
                # Present in the file, never served: it is a server-side path.
                "artifact_path": f"{SECRET_DIR}/run/report.json",
            }
        ),
        encoding="utf-8",
    )

    return path


@pytest.fixture
def registry_file(tmp_path, report_file):
    path = tmp_path / "backtest_results.json"

    write_backtest_result_registry(
        path,
        BacktestResultRegistry(
            results=(
                BacktestResultEntry(
                    run_id="run_1",
                    created_at_utc="2026-01-01T00:00:00",
                    kind=BacktestKind.RULE_STRATEGY,
                    strategy_name="Breakout",
                    report_path=str(report_file),
                    symbol="XAUUSD",
                    timeframe="H1",
                    manifest_path=f"{SECRET_DIR}/run/manifest.json",
                    analytics_path=f"{SECRET_DIR}/run/analytics.json",
                    metrics={"net_profit": 8.5, "win_rate": 0.5},
                    model_identity={
                        "model_id": "model_1",
                        "model_version": "1.0",
                    },
                    tags=("baseline",),
                ),
                BacktestResultEntry(
                    run_id="run_2",
                    created_at_utc="2026-02-01T00:00:00",
                    kind=BacktestKind.ML_MODEL,
                    strategy_name="Momentum",
                    report_path=f"{SECRET_DIR}/missing/report.json",
                    symbol="EURUSD",
                    metrics={"net_profit": -3.0},
                ),
            )
        ),
    )

    return path


class TestUnavailableRegistry:
    def test_unconfigured_is_not_ready(self) -> None:
        """Unavailable is not the same as no backtests having been run."""

        response = build_client().get(f"{API_V1_PREFIX}/backtests")

        assert response.status_code == 503
        assert response.json()["error"]["code"] == "not_ready"
        assert response.json()["error"]["details"]["configured"] is False

    def test_a_missing_registry_file_is_not_ready(self, tmp_path) -> None:
        client = build_client(
            backtest_registry_path=str(tmp_path / "absent.json")
        )
        response = client.get(f"{API_V1_PREFIX}/backtests")

        assert response.status_code == 503
        assert response.json()["error"]["details"]["configured"] is True

    def test_an_empty_registry_is_a_valid_empty_list(self, tmp_path) -> None:
        """Configured with no runs is a real answer, unlike unavailable."""

        path = tmp_path / "empty.json"
        write_backtest_result_registry(path, BacktestResultRegistry())

        payload = build_client(backtest_registry_path=str(path)).get(
            f"{API_V1_PREFIX}/backtests"
        ).json()

        assert payload["items"] == []
        assert payload["total"] == 0

    def test_detail_is_also_unavailable_when_unconfigured(self) -> None:
        assert build_client().get(
            f"{API_V1_PREFIX}/backtests/run_1"
        ).status_code == 503


class TestBacktestList:
    def test_it_lists_registered_runs(self, registry_file) -> None:
        payload = build_client(
            backtest_registry_path=str(registry_file)
        ).get(f"{API_V1_PREFIX}/backtests").json()

        assert payload["total"] == 2
        assert {item["backtest_id"] for item in payload["items"]} == {
            "run_1",
            "run_2",
        }

    def test_it_filters_by_kind(self, registry_file) -> None:
        payload = build_client(
            backtest_registry_path=str(registry_file)
        ).get(f"{API_V1_PREFIX}/backtests?kind=ml_model").json()

        assert payload["total"] == 1
        assert payload["items"][0]["backtest_id"] == "run_2"

    def test_it_filters_by_symbol_and_strategy(self, registry_file) -> None:
        client = build_client(backtest_registry_path=str(registry_file))

        assert client.get(
            f"{API_V1_PREFIX}/backtests?symbol=XAUUSD"
        ).json()["total"] == 1
        assert client.get(
            f"{API_V1_PREFIX}/backtests?strategy_name=Momentum"
        ).json()["total"] == 1

    def test_an_unknown_kind_is_refused(self, registry_file) -> None:
        response = build_client(
            backtest_registry_path=str(registry_file)
        ).get(f"{API_V1_PREFIX}/backtests?kind=telepathy")

        assert response.status_code == 422
        assert response.json()["error"]["details"]["field"] == "kind"

    def test_an_invalid_limit_is_refused(self, registry_file) -> None:
        assert build_client(
            backtest_registry_path=str(registry_file)
        ).get(f"{API_V1_PREFIX}/backtests?limit=0").status_code == 422

    def test_no_filesystem_path_is_exposed(self, registry_file) -> None:
        """Report, manifest and analytics paths all stay server-side."""

        body = build_client(
            backtest_registry_path=str(registry_file)
        ).get(f"{API_V1_PREFIX}/backtests").text

        assert SECRET_DIR not in body
        assert str(registry_file) not in body
        assert "report_path" not in body
        assert "manifest_path" not in body
        assert "analytics_path" not in body

    def test_metrics_and_model_identity_are_served(
        self,
        registry_file,
    ) -> None:
        item = build_client(
            backtest_registry_path=str(registry_file)
        ).get(f"{API_V1_PREFIX}/backtests?symbol=XAUUSD").json()["items"][0]

        assert item["metrics"]["net_profit"] == pytest.approx(8.5)
        assert item["model_id"] == "model_1"
        assert item["model_version"] == "1.0"
        assert item["tags"] == ["baseline"]


class TestBacktestDetail:
    def test_it_returns_one_run(self, registry_file) -> None:
        payload = build_client(
            backtest_registry_path=str(registry_file)
        ).get(f"{API_V1_PREFIX}/backtests/run_1").json()

        assert payload["backtest_id"] == "run_1"
        assert payload["strategy_name"] == "Breakout"
        assert payload["timeframe"] == "H1"

    def test_an_unknown_run_is_not_found(self, registry_file) -> None:
        response = build_client(
            backtest_registry_path=str(registry_file)
        ).get(f"{API_V1_PREFIX}/backtests/run_missing")

        assert response.status_code == 404
        assert response.json()["error"]["code"] == "not_found"


class TestBacktestSections:
    def test_trades_are_served_from_the_report(self, registry_file) -> None:
        payload = build_client(
            backtest_registry_path=str(registry_file)
        ).get(f"{API_V1_PREFIX}/backtests/run_1/trades").json()

        assert payload["backtest_id"] == "run_1"
        assert payload["total"] == 2
        assert payload["items"][0]["trade_id"] == "t1"

    def test_orders_are_served(self, registry_file) -> None:
        payload = build_client(
            backtest_registry_path=str(registry_file)
        ).get(f"{API_V1_PREFIX}/backtests/run_1/orders").json()

        assert payload["total"] == 1

    def test_equity_is_served(self, registry_file) -> None:
        payload = build_client(
            backtest_registry_path=str(registry_file)
        ).get(f"{API_V1_PREFIX}/backtests/run_1/equity").json()

        assert payload["total"] == 2
        assert payload["items"][1]["equity"] == pytest.approx(10_012.5)

    def test_sections_paginate(self, registry_file) -> None:
        payload = build_client(
            backtest_registry_path=str(registry_file)
        ).get(f"{API_V1_PREFIX}/backtests/run_1/trades?limit=1").json()

        assert payload["count"] == 1
        assert payload["total"] == 2

    def test_a_registered_run_with_no_report_file_is_unavailable(
        self,
        registry_file,
    ) -> None:
        """
        Registered but absent is unavailable, not empty.

        An empty list would claim the run produced no trades, which is a
        different and false statement.
        """

        response = build_client(
            backtest_registry_path=str(registry_file)
        ).get(f"{API_V1_PREFIX}/backtests/run_2/trades")

        assert response.status_code == 503
        assert response.json()["error"]["code"] == "not_ready"

    def test_no_report_path_leaks_through_a_section(
        self,
        registry_file,
    ) -> None:
        body = build_client(
            backtest_registry_path=str(registry_file)
        ).get(f"{API_V1_PREFIX}/backtests/run_1/trades").text

        assert SECRET_DIR not in body

    def test_sections_are_strict_json(self, registry_file) -> None:
        client = build_client(backtest_registry_path=str(registry_file))

        for path in (
            f"{API_V1_PREFIX}/backtests",
            f"{API_V1_PREFIX}/backtests/run_1",
            f"{API_V1_PREFIX}/backtests/run_1/trades",
            f"{API_V1_PREFIX}/backtests/run_1/orders",
            f"{API_V1_PREFIX}/backtests/run_1/equity",
        ):
            body = client.get(path).text

            for token in ("Infinity", "-Infinity", "NaN"):
                assert token not in body

            json.loads(body)


class TestSystemInfoReporting:
    def test_it_reports_configuration_without_the_path(
        self,
        registry_file,
    ) -> None:
        payload = build_client(
            backtest_registry_path=str(registry_file)
        ).get(f"{API_V1_PREFIX}/system/info").json()

        assert payload["api"]["has_backtest_registry"] is True
        assert str(registry_file) not in json.dumps(payload)
