from __future__ import annotations

import json

import pytest

from aqos.backtesting.cli import run_backtesting_cli
from aqos.backtesting.registry import (
    BACKTEST_REGISTRY_VERSION,
    BacktestKind,
    BacktestResultEntry,
    BacktestResultRegistry,
    append_backtest_result_to_registry,
    build_backtest_result_entry_from_report,
    find_best_backtest_result,
    find_latest_backtest_result,
    list_backtest_results,
    read_backtest_result_registry,
    register_backtest_report,
    resolve_backtest_kind,
    select_registered_metrics,
    write_backtest_result_registry,
)


def write_report(path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")


def build_strategy_report_payload(
    strategy_name: str = "close_momentum",
    net_profit: float = 120.0,
    adapter_type: str = "rule_based",
) -> dict:
    return {
        "run_id": f"{strategy_name}_run",
        "manifest_path": "tmp/manifest.json",
        "analytics_path": "tmp/analytics.json",
        "run_config": {
            "strategy_name": strategy_name,
            "symbol": "XAUUSD",
            "timeframe": "H1",
        },
        "metrics": {
            "net_profit": net_profit,
            "return_fraction": net_profit / 10_000.0,
            "total_trades": 4,
            "win_rate": 0.75,
            "profit_factor": 3.0,
            "max_drawdown": 0.02,
            "metadata": {"adapter_type": adapter_type},
        },
        "analytics": {"risk": {"expectancy": 30.0}},
    }


def build_entry(run_id: str, **overrides) -> BacktestResultEntry:
    payload = {
        "run_id": run_id,
        "created_at_utc": "2026-01-01T00:00:00+00:00",
        "kind": BacktestKind.RULE_STRATEGY,
        "strategy_name": "close_momentum",
        "report_path": "tmp/report.json",
    }
    payload.update(overrides)

    return BacktestResultEntry(**payload)


def test_registry_version_is_exposed() -> None:
    assert BACKTEST_REGISTRY_VERSION == "1.0"


def test_entry_validation() -> None:
    with pytest.raises(ValueError, match="run_id cannot be empty"):
        build_entry("  ")

    with pytest.raises(ValueError, match="created_at_utc cannot be empty"):
        build_entry("run", created_at_utc=" ")

    with pytest.raises(ValueError, match="strategy_name cannot be empty"):
        build_entry("run", strategy_name="")

    with pytest.raises(ValueError, match="report_path cannot be empty"):
        build_entry("run", report_path=" ")


def test_entry_net_profit_property() -> None:
    assert build_entry("run", metrics={"net_profit": 12.5}).net_profit == 12.5
    assert build_entry("run").net_profit is None
    assert build_entry("run", metrics={"net_profit": "n/a"}).net_profit is None


def test_select_registered_metrics_filters_unknown_and_non_numeric() -> None:
    metrics = select_registered_metrics(
        {
            "net_profit": 10.0,
            "win_rate": 0.5,
            "metadata": {"a": 1},
            "unknown_metric": 4,
            "profit_factor": "inf",
        }
    )

    assert metrics == {"net_profit": 10.0, "win_rate": 0.5}


def test_resolve_backtest_kind() -> None:
    assert resolve_backtest_kind({"model_identity": {}}) == BacktestKind.ML_MODEL
    assert resolve_backtest_kind(build_strategy_report_payload()) == (
        BacktestKind.RULE_STRATEGY
    )
    assert resolve_backtest_kind(
        build_strategy_report_payload(adapter_type="ml_model")
    ) == BacktestKind.ML_MODEL
    assert resolve_backtest_kind({"metrics": {"metadata": {}}}) == (
        BacktestKind.CSV_SIGNAL
    )


def test_build_entry_from_report(tmp_path) -> None:
    report_path = tmp_path / "report.json"
    write_report(report_path, build_strategy_report_payload())

    entry = build_backtest_result_entry_from_report(
        report_path,
        tags=("nightly",),
        created_at_utc="2026-01-01T00:00:00+00:00",
    )

    assert entry.run_id == "close_momentum_run"
    assert entry.kind == BacktestKind.RULE_STRATEGY
    assert entry.strategy_name == "close_momentum"
    assert entry.symbol == "XAUUSD"
    assert entry.timeframe == "H1"
    assert entry.metrics["net_profit"] == 120.0
    assert entry.metrics["expectancy"] == 30.0
    assert entry.manifest_path == "tmp/manifest.json"
    assert entry.analytics_path == "tmp/analytics.json"
    assert entry.tags == ("nightly",)


def test_build_entry_from_model_report(tmp_path) -> None:
    report_path = tmp_path / "model_report.json"
    write_report(
        report_path,
        {
            "run_id": "model_run",
            "model_identity": {"model_id": "model_abc", "promotion_stage": "demo"},
            "gate_decision": {"status": "approved"},
            "strategy_backtest": build_strategy_report_payload(
                strategy_name="model_strategy",
                net_profit=45.0,
                adapter_type="ml_model",
            ),
        },
    )

    entry = build_backtest_result_entry_from_report(report_path)

    assert entry.kind == BacktestKind.ML_MODEL
    assert entry.strategy_name == "model_strategy"
    assert entry.model_identity["model_id"] == "model_abc"
    assert entry.metrics["net_profit"] == 45.0


def test_build_entry_rejects_missing_report(tmp_path) -> None:
    with pytest.raises(FileNotFoundError, match="does not exist"):
        build_backtest_result_entry_from_report(tmp_path / "missing.json")


def test_build_entry_rejects_non_object_report(tmp_path) -> None:
    report_path = tmp_path / "list.json"
    report_path.write_text("[]", encoding="utf-8")

    with pytest.raises(ValueError, match="must be a JSON object"):
        build_backtest_result_entry_from_report(report_path)


def test_read_missing_registry_returns_empty(tmp_path) -> None:
    registry = read_backtest_result_registry(tmp_path / "missing.json")

    assert registry.result_count == 0
    assert registry.results == ()


def test_registry_round_trip(tmp_path) -> None:
    registry = BacktestResultRegistry(results=(build_entry("run_1"),))

    path = write_backtest_result_registry(tmp_path / "registry.json", registry)
    loaded = read_backtest_result_registry(path)

    assert loaded.to_dict() == registry.to_dict()


def test_append_sorts_and_replaces_by_run_id(tmp_path) -> None:
    path = tmp_path / "registry.json"

    append_backtest_result_to_registry(
        path,
        build_entry("run_b", created_at_utc="2026-01-02T00:00:00+00:00"),
    )
    append_backtest_result_to_registry(
        path,
        build_entry("run_a", created_at_utc="2026-01-01T00:00:00+00:00"),
    )
    registry = append_backtest_result_to_registry(
        path,
        build_entry(
            "run_b",
            created_at_utc="2026-01-02T00:00:00+00:00",
            strategy_name="updated",
        ),
    )

    assert [result.run_id for result in registry.results] == ["run_a", "run_b"]
    assert registry.results[1].strategy_name == "updated"


def test_register_backtest_report_appends(tmp_path) -> None:
    report_path = tmp_path / "report.json"
    write_report(report_path, build_strategy_report_payload())

    entry = register_backtest_report(
        registry_path=tmp_path / "registry.json",
        report_path=report_path,
        tags=("ci",),
    )

    registry = read_backtest_result_registry(tmp_path / "registry.json")

    assert registry.result_count == 1
    assert registry.results[0].run_id == entry.run_id
    assert registry.results[0].tags == ("ci",)


def test_list_backtest_results_filters() -> None:
    registry = BacktestResultRegistry(
        results=(
            build_entry("a", symbol="XAUUSD", tags=("nightly",)),
            build_entry("b", symbol="EURUSD", kind=BacktestKind.ML_MODEL),
            build_entry("c", symbol="XAUUSD", strategy_name="other"),
        )
    )

    assert len(list_backtest_results(registry, symbol="XAUUSD")) == 2
    assert len(list_backtest_results(registry, kind=BacktestKind.ML_MODEL)) == 1
    assert len(list_backtest_results(registry, strategy_name="other")) == 1
    assert len(list_backtest_results(registry, tag="nightly")) == 1
    assert len(list_backtest_results(registry)) == 3


def test_find_latest_backtest_result() -> None:
    registry = BacktestResultRegistry(
        results=(
            build_entry("a", created_at_utc="2026-01-01T00:00:00+00:00"),
            build_entry("b", created_at_utc="2026-03-01T00:00:00+00:00"),
        )
    )

    latest = find_latest_backtest_result(registry)

    assert latest is not None and latest.run_id == "b"
    assert find_latest_backtest_result(BacktestResultRegistry()) is None


def test_find_best_backtest_result() -> None:
    registry = BacktestResultRegistry(
        results=(
            build_entry("a", metrics={"net_profit": 10.0}),
            build_entry("b", metrics={"net_profit": 90.0}),
            build_entry("c"),
        )
    )

    best = find_best_backtest_result(registry)

    assert best is not None and best.run_id == "b"
    assert find_best_backtest_result(registry, metric_key="win_rate") is None


def test_strategy_backtest_cli_registers_result(
    backtest_model_data_path,
    tmp_path,
    capsys,
) -> None:
    registry_path = tmp_path / "registry" / "backtest_results.json"

    exit_code = run_backtesting_cli(
        [
            "strategy-backtest",
            "--data-path",
            str(backtest_model_data_path),
            "--output-dir",
            str(tmp_path / "run_output"),
            "--symbol",
            "XAUUSD",
            "--timeframe",
            "H1",
            "--strategy-name",
            "registered_momentum",
            "--result-registry-path",
            str(registry_path),
        ]
    )

    capsys.readouterr()
    registry = read_backtest_result_registry(registry_path)

    assert exit_code == 0
    assert registry.result_count == 1
    assert registry.results[0].kind == BacktestKind.RULE_STRATEGY
    assert registry.results[0].strategy_name == "registered_momentum"
    assert registry.results[0].symbol == "XAUUSD"
    assert registry.results[0].metrics["net_profit"] is not None


def test_model_backtest_cli_registers_result(
    promoted_backtest_model_files,
    backtest_model_data_path,
    tmp_path,
    capsys,
) -> None:
    registry_path = tmp_path / "registry" / "backtest_results.json"

    exit_code = run_backtesting_cli(
        [
            "model-backtest",
            "--data-path",
            str(backtest_model_data_path),
            "--output-dir",
            str(tmp_path / "model_output"),
            "--model-path",
            str(promoted_backtest_model_files["model_path"]),
            "--model-metadata-path",
            str(promoted_backtest_model_files["metadata_path"]),
            "--promotion-registry-path",
            str(promoted_backtest_model_files["registry_path"]),
            "--symbol",
            "XAUUSD",
            "--timeframe",
            "H1",
            "--warmup-bars",
            "5",
            "--result-registry-path",
            str(registry_path),
        ]
    )

    capsys.readouterr()
    registry = read_backtest_result_registry(registry_path)

    assert exit_code == 0
    assert registry.result_count == 1
    assert registry.results[0].kind == BacktestKind.ML_MODEL
    assert registry.results[0].model_identity["model_id"] == (
        promoted_backtest_model_files["model_id"]
    )
