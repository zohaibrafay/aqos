from __future__ import annotations

import json

import pandas as pd
import pytest

from aqos.backtesting.comparison import (
    BACKTEST_COMPARISON_VERSION,
    BacktestComparisonEntry,
    BacktestComparisonMetric,
    build_backtest_comparison_dataframe,
    build_backtest_comparison_entry_from_report,
    compare_backtest_runs,
    flatten_backtest_report_metrics,
    load_backtest_comparison_entries,
    metric_defaults_to_higher_is_better,
    rank_backtest_entries,
    resolve_backtest_report_label,
    write_backtest_comparison_csv,
    write_backtest_comparison_report,
)


def build_entry(label: str, **metrics) -> BacktestComparisonEntry:
    return BacktestComparisonEntry(label=label, metrics=dict(metrics))


def write_strategy_report(path, strategy_name: str, net_profit: float, **extra):
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "run_config": {"strategy_name": strategy_name},
        "metrics": {
            "net_profit": net_profit,
            "win_rate": 0.5,
            "max_drawdown": 0.1,
            **extra,
        },
        "analytics": {"risk": {"expectancy": net_profit / 10.0}},
    }
    path.write_text(json.dumps(payload), encoding="utf-8")
    return path


def test_comparison_version_is_exposed() -> None:
    assert BACKTEST_COMPARISON_VERSION == "1.0"


def test_entry_requires_label() -> None:
    with pytest.raises(ValueError, match="label cannot be empty"):
        BacktestComparisonEntry(label="   ")


def test_entry_metric_value_handles_non_numeric() -> None:
    entry = build_entry(
        "run",
        net_profit=120.0,
        profit_factor=None,
        win_rate=True,
        strategy="text",
    )

    assert entry.metric_value(BacktestComparisonMetric.NET_PROFIT) == 120.0
    assert entry.metric_value(BacktestComparisonMetric.PROFIT_FACTOR) is None
    assert entry.metric_value(BacktestComparisonMetric.WIN_RATE) is None
    assert entry.metric_value(BacktestComparisonMetric.EXPECTANCY) is None


def test_metric_direction_defaults() -> None:
    assert metric_defaults_to_higher_is_better(BacktestComparisonMetric.NET_PROFIT)
    assert not metric_defaults_to_higher_is_better(
        BacktestComparisonMetric.MAX_DRAWDOWN
    )


def test_rank_entries_descending() -> None:
    rankings = rank_backtest_entries(
        (
            build_entry("a", net_profit=10.0),
            build_entry("b", net_profit=50.0),
            build_entry("c", net_profit=30.0),
        ),
        BacktestComparisonMetric.NET_PROFIT,
        higher_is_better=True,
    )

    assert [ranking.label for ranking in rankings] == ["b", "c", "a"]
    assert [ranking.rank for ranking in rankings] == [1, 2, 3]


def test_rank_entries_ascending() -> None:
    rankings = rank_backtest_entries(
        (
            build_entry("a", max_drawdown=0.3),
            build_entry("b", max_drawdown=0.1),
        ),
        BacktestComparisonMetric.MAX_DRAWDOWN,
        higher_is_better=False,
    )

    assert [ranking.label for ranking in rankings] == ["b", "a"]


def test_rank_entries_break_ties_by_label() -> None:
    rankings = rank_backtest_entries(
        (
            build_entry("zulu", net_profit=10.0),
            build_entry("alpha", net_profit=10.0),
        ),
        BacktestComparisonMetric.NET_PROFIT,
        higher_is_better=True,
    )

    assert [ranking.label for ranking in rankings] == ["alpha", "zulu"]


def test_rank_entries_place_missing_metrics_last() -> None:
    rankings = rank_backtest_entries(
        (
            build_entry("missing"),
            build_entry("present", net_profit=10.0),
        ),
        BacktestComparisonMetric.NET_PROFIT,
        higher_is_better=True,
    )

    assert rankings[0].label == "present"
    assert rankings[1].label == "missing"
    assert rankings[1].value is None


def test_compare_backtest_runs_result() -> None:
    result = compare_backtest_runs(
        entries=(
            build_entry("slow", net_profit=10.0),
            build_entry("fast", net_profit=90.0),
        ),
        metric=BacktestComparisonMetric.NET_PROFIT,
    )

    assert result.higher_is_better is True
    assert result.best is not None and result.best.label == "fast"
    assert result.worst is not None and result.worst.label == "slow"

    payload = result.to_dict()

    assert payload["metric"] == "net_profit"
    assert payload["entry_count"] == 2
    assert payload["best"]["value"] == 90.0
    assert len(payload["rankings"]) == 2


def test_compare_backtest_runs_respects_explicit_direction() -> None:
    result = compare_backtest_runs(
        entries=(
            build_entry("a", net_profit=10.0),
            build_entry("b", net_profit=90.0),
        ),
        metric=BacktestComparisonMetric.NET_PROFIT,
        higher_is_better=False,
    )

    assert result.best is not None and result.best.label == "a"


def test_compare_backtest_runs_rejects_empty_entries() -> None:
    with pytest.raises(ValueError, match="entries cannot be empty"):
        compare_backtest_runs(entries=())


def test_compare_backtest_runs_rejects_duplicate_labels() -> None:
    with pytest.raises(ValueError, match="labels must be unique"):
        compare_backtest_runs(
            entries=(build_entry("same", net_profit=1.0), build_entry("same"))
        )


def test_best_and_worst_are_none_without_values() -> None:
    result = compare_backtest_runs(entries=(build_entry("only"),))

    assert result.best is None
    assert result.worst is None
    assert result.to_dict()["best"] is None


def test_flatten_report_metrics_from_strategy_report() -> None:
    metrics = flatten_backtest_report_metrics(
        {
            "metrics": {"net_profit": 20.0},
            "analytics": {"risk": {"expectancy": 4.0, "sharpe_like_ratio": 1.2}},
        }
    )

    assert metrics["net_profit"] == 20.0
    assert metrics["expectancy"] == 4.0
    assert metrics["sharpe_like_ratio"] == 1.2


def test_flatten_report_metrics_from_model_report() -> None:
    metrics = flatten_backtest_report_metrics(
        {
            "strategy_backtest": {
                "metrics": {"net_profit": 55.0},
                "analytics": {"risk": {"expectancy": 5.0}},
            }
        }
    )

    assert metrics["net_profit"] == 55.0
    assert metrics["expectancy"] == 5.0


def test_resolve_report_label_prefers_strategy_name() -> None:
    assert (
        resolve_backtest_report_label(
            {"run_config": {"strategy_name": "momentum"}},
            "fallback",
        )
        == "momentum"
    )
    assert resolve_backtest_report_label({}, "fallback") == "fallback"


def test_build_entry_from_report(tmp_path) -> None:
    path = write_strategy_report(tmp_path / "report.json", "momentum", 120.0)

    entry = build_backtest_comparison_entry_from_report(path)

    assert entry.label == "momentum"
    assert entry.metrics["net_profit"] == 120.0
    assert entry.metrics["expectancy"] == 12.0
    assert entry.source_path == path.as_posix()


def test_build_entry_from_report_keeps_model_identity(tmp_path) -> None:
    path = tmp_path / "model_report.json"
    path.write_text(
        json.dumps(
            {
                "model_identity": {"model_id": "model_abc"},
                "strategy_backtest": {
                    "run_config": {"strategy_name": "model_strategy"},
                    "metrics": {"net_profit": 10.0},
                },
            }
        ),
        encoding="utf-8",
    )

    entry = build_backtest_comparison_entry_from_report(path)

    assert entry.label == "model_strategy"
    assert entry.metadata["model_identity"]["model_id"] == "model_abc"


def test_build_entry_from_report_rejects_missing_file(tmp_path) -> None:
    with pytest.raises(FileNotFoundError, match="does not exist"):
        build_backtest_comparison_entry_from_report(tmp_path / "missing.json")


def test_build_entry_from_report_rejects_non_object(tmp_path) -> None:
    path = tmp_path / "list_report.json"
    path.write_text("[1, 2, 3]", encoding="utf-8")

    with pytest.raises(ValueError, match="must be a JSON object"):
        build_backtest_comparison_entry_from_report(path)


def test_load_entries_with_labels(tmp_path) -> None:
    first = write_strategy_report(tmp_path / "a.json", "alpha", 10.0)
    second = write_strategy_report(tmp_path / "b.json", "beta", 20.0)

    entries = load_backtest_comparison_entries(
        report_paths=(first, second),
        labels=("run_a", "run_b"),
    )

    assert [entry.label for entry in entries] == ["run_a", "run_b"]


def test_load_entries_rejects_empty_paths() -> None:
    with pytest.raises(ValueError, match="report_paths cannot be empty"):
        load_backtest_comparison_entries(report_paths=())


def test_load_entries_rejects_label_length_mismatch(tmp_path) -> None:
    path = write_strategy_report(tmp_path / "a.json", "alpha", 10.0)

    with pytest.raises(ValueError, match="same length"):
        load_backtest_comparison_entries(report_paths=(path,), labels=("a", "b"))


def test_comparison_dataframe_is_ranked() -> None:
    result = compare_backtest_runs(
        entries=(
            build_entry("slow", net_profit=10.0, win_rate=0.4),
            build_entry("fast", net_profit=90.0, win_rate=0.7),
        )
    )

    frame = build_backtest_comparison_dataframe(result)

    assert list(frame["label"]) == ["fast", "slow"]
    assert list(frame["rank"]) == [1, 2]
    assert frame.iloc[0]["net_profit"] == 90.0
    assert "max_drawdown" in frame.columns


def test_write_comparison_artifacts(tmp_path) -> None:
    result = compare_backtest_runs(
        entries=(
            build_entry("a", net_profit=10.0),
            build_entry("b", net_profit=20.0),
        )
    )

    report_path = write_backtest_comparison_report(
        tmp_path / "nested" / "comparison.json",
        result,
    )
    csv_path = write_backtest_comparison_csv(
        tmp_path / "nested" / "comparison.csv",
        result,
    )

    payload = json.loads(report_path.read_text(encoding="utf-8"))
    frame = pd.read_csv(csv_path)

    assert payload["best"]["label"] == "b"
    assert len(frame) == 2
    assert frame.iloc[0]["label"] == "b"
