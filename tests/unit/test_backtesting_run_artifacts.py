from __future__ import annotations

import json

import pandas as pd
import pytest

from aqos.backtesting.artifacts import (
    BacktestArtifactKind,
    read_backtest_artifact_manifest,
    verify_backtest_artifact_manifest,
)
from aqos.backtesting.builtin_strategies import build_builtin_rule_strategy
from aqos.backtesting.cli import run_backtesting_cli
from aqos.backtesting.rule_based_adapter import RuleBasedBacktestSignalAdapter
from aqos.backtesting.strategy_runner import (
    StrategyBacktestRunnerConfig,
    run_backtest_with_signal_adapter,
)


def build_close_momentum_adapter() -> RuleBasedBacktestSignalAdapter:
    return RuleBasedBacktestSignalAdapter(
        strategy=build_builtin_rule_strategy(
            "close_momentum",
            lookback_bars=1,
            min_return_fraction=0.0005,
            stop_loss_points=4.0,
            take_profit_points=6.0,
        )
    )


def run_strategy_backtest(
    data_path,
    output_dir,
    strategy_name: str = "close_momentum_artifacts",
    **overrides,
):
    config = StrategyBacktestRunnerConfig(
        data_path=data_path,
        output_dir=output_dir,
        symbol="XAUUSD",
        timeframe="H1",
        strategy_name=strategy_name,
        fixed_quantity=1.0,
        **overrides,
    )

    return run_backtest_with_signal_adapter(config, build_close_momentum_adapter())


def test_reporting_symbols_are_re_exported() -> None:
    import aqos.backtesting as backtesting

    expected = (
        "BACKTEST_ANALYTICS_VERSION",
        "BACKTEST_ARTIFACTS_VERSION",
        "BACKTEST_COMPARISON_VERSION",
        "BacktestAdvancedReport",
        "BacktestArtifactKind",
        "BacktestArtifactManifest",
        "BacktestComparisonMetric",
        "BacktestComparisonResult",
        "build_backtest_advanced_report",
        "build_backtest_artifact_manifest",
        "build_backtest_run_id",
        "build_model_backtest_manifest",
        "build_strategy_backtest_manifest",
        "compare_backtest_runs",
        "load_backtest_comparison_entries",
        "read_backtest_artifact_manifest",
        "verify_backtest_artifact_manifest",
        "write_backtest_comparison_report",
    )

    for name in expected:
        assert name in backtesting.__all__
        assert hasattr(backtesting, name)


def test_strategy_backtest_writes_analytics_and_manifest(
    backtest_model_data_path,
    tmp_path,
) -> None:
    output_dir = tmp_path / "strategy_artifacts"

    output = run_strategy_backtest(backtest_model_data_path, output_dir)

    assert output.analytics is not None
    assert output.analytics_path is not None
    assert output.analytics_path.exists()
    assert output.manifest is not None
    assert output.manifest_path is not None
    assert output.manifest_path.exists()
    assert output.run_id.startswith("close_momentum_artifacts_xauusd_h1_")

    analytics = json.loads(output.analytics_path.read_text(encoding="utf-8"))

    assert analytics["metrics"]["total_trades"] == output.metrics.total_trades
    assert len(analytics["side_breakdowns"]) == 2
    assert analytics["metadata"]["adapter_type"] == "rule_based"


def test_strategy_backtest_manifest_covers_every_artifact(
    backtest_model_data_path,
    tmp_path,
) -> None:
    output = run_strategy_backtest(
        backtest_model_data_path,
        tmp_path / "strategy_artifacts",
    )

    manifest = read_backtest_artifact_manifest(output.manifest_path)
    kinds = {artifact.kind for artifact in manifest.artifacts}

    assert kinds == {
        BacktestArtifactKind.REPORT,
        BacktestArtifactKind.ANALYTICS,
        BacktestArtifactKind.TRADES,
        BacktestArtifactKind.ORDERS,
        BacktestArtifactKind.EQUITY_CURVE,
        BacktestArtifactKind.SIGNALS,
        BacktestArtifactKind.ADAPTER_RESULTS,
    }
    assert manifest.missing_artifacts == ()
    assert verify_backtest_artifact_manifest(manifest) == ()
    assert manifest.metadata["strategy_name"] == "close_momentum_artifacts"


def test_strategy_backtest_report_embeds_analytics(
    backtest_model_data_path,
    tmp_path,
) -> None:
    output = run_strategy_backtest(
        backtest_model_data_path,
        tmp_path / "strategy_artifacts",
    )

    report = json.loads(output.report_path.read_text(encoding="utf-8"))

    assert report["run_id"] == output.run_id
    assert report["analytics"]["metrics"]["total_trades"] >= 0
    assert report["analytics_path"].endswith("strategy_backtest_analytics.json")
    assert report["manifest_path"].endswith("strategy_backtest_manifest.json")


def test_strategy_backtest_can_disable_reporting_artifacts(
    backtest_model_data_path,
    tmp_path,
) -> None:
    output = run_strategy_backtest(
        backtest_model_data_path,
        tmp_path / "strategy_artifacts_disabled",
        enable_analytics_report=False,
        enable_artifact_manifest=False,
    )

    assert output.analytics is None
    assert output.analytics_path is None
    assert output.manifest is None
    assert output.manifest_path is None
    assert not (
        tmp_path / "strategy_artifacts_disabled" / "strategy_backtest_analytics.json"
    ).exists()


def test_model_backtest_manifest_includes_predictions(
    promoted_backtest_model_files,
    backtest_model_data_path,
    tmp_path,
    capsys,
) -> None:
    output_dir = tmp_path / "model_artifacts"

    exit_code = run_backtesting_cli(
        [
            "model-backtest",
            "--data-path",
            str(backtest_model_data_path),
            "--output-dir",
            str(output_dir),
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
            "--model-stop-loss-points",
            "4",
            "--model-take-profit-points",
            "6",
        ]
    )

    payload = json.loads(capsys.readouterr().out)
    manifest_path = output_dir / "model_backtest_manifest.json"

    assert exit_code == 0
    assert manifest_path.exists()
    assert payload["manifest_path"].endswith("model_backtest_manifest.json")
    assert payload["run_id"].startswith("model_strategy_xauusd_h1_")

    manifest = read_backtest_artifact_manifest(manifest_path)
    kinds = {artifact.kind for artifact in manifest.artifacts}

    assert BacktestArtifactKind.PREDICTIONS in kinds
    assert BacktestArtifactKind.ANALYTICS in kinds
    assert verify_backtest_artifact_manifest(manifest) == ()
    assert manifest.metadata["model_id"] == promoted_backtest_model_files["model_id"]


def test_compare_backtests_cli_ranks_runs(
    backtest_model_data_path,
    tmp_path,
    capsys,
) -> None:
    first = run_strategy_backtest(
        backtest_model_data_path,
        tmp_path / "run_a",
        strategy_name="run_a",
    )
    second = run_strategy_backtest(
        backtest_model_data_path,
        tmp_path / "run_b",
        strategy_name="run_b",
        commission_per_trade=1.0,
    )

    comparison_dir = tmp_path / "comparison"

    exit_code = run_backtesting_cli(
        [
            "compare-backtests",
            "--report",
            str(first.report_path),
            "--report",
            str(second.report_path),
            "--metric",
            "net_profit",
            "--output-dir",
            str(comparison_dir),
        ]
    )

    payload = json.loads(capsys.readouterr().out)
    comparison_csv = comparison_dir / "backtest_comparison.csv"

    assert exit_code == 0
    assert (comparison_dir / "backtest_comparison.json").exists()
    assert comparison_csv.exists()

    assert payload["metric"] == "net_profit"
    assert payload["entry_count"] == 2
    assert {ranking["label"] for ranking in payload["rankings"]} == {"run_a", "run_b"}
    assert payload["best"]["label"] == "run_a"

    frame = pd.read_csv(comparison_csv)

    assert list(frame["rank"]) == [1, 2]
    assert frame.iloc[0]["label"] == "run_a"


def test_compare_backtests_cli_supports_labels_and_direction(
    backtest_model_data_path,
    tmp_path,
    capsys,
) -> None:
    first = run_strategy_backtest(
        backtest_model_data_path,
        tmp_path / "run_a",
        strategy_name="run_a",
    )
    second = run_strategy_backtest(
        backtest_model_data_path,
        tmp_path / "run_b",
        strategy_name="run_b",
        commission_per_trade=1.0,
    )

    exit_code = run_backtesting_cli(
        [
            "compare-backtests",
            "--report",
            str(first.report_path),
            "--label",
            "baseline",
            "--report",
            str(second.report_path),
            "--label",
            "with_costs",
            "--metric",
            "net_profit",
            "--lower-is-better",
            "--output-dir",
            str(tmp_path / "comparison_labels"),
        ]
    )

    payload = json.loads(capsys.readouterr().out)

    assert exit_code == 0
    assert payload["higher_is_better"] is False
    assert payload["best"]["label"] == "with_costs"
    assert [entry["label"] for entry in payload["entries"]] == [
        "baseline",
        "with_costs",
    ]
