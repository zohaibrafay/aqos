from __future__ import annotations

import json
import math
from dataclasses import dataclass, field as dataclass_field
from enum import Enum
from pathlib import Path
from typing import Any

import pandas as pd

from aqos.backtesting.contracts import backtesting_utc_now_iso


BACKTEST_COMPARISON_VERSION = "1.0"


class BacktestComparisonMetric(str, Enum):
    NET_PROFIT = "net_profit"
    RETURN_FRACTION = "return_fraction"
    PROFIT_FACTOR = "profit_factor"
    WIN_RATE = "win_rate"
    TOTAL_TRADES = "total_trades"
    MAX_DRAWDOWN = "max_drawdown"
    EXPECTANCY = "expectancy"
    SHARPE_LIKE_RATIO = "sharpe_like_ratio"


LOWER_IS_BETTER_METRICS = (BacktestComparisonMetric.MAX_DRAWDOWN,)


@dataclass(frozen=True)
class BacktestComparisonEntry:
    label: str
    metrics: dict[str, Any] = dataclass_field(default_factory=dict)
    source_path: str | None = None
    metadata: dict[str, Any] = dataclass_field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.label.strip():
            raise ValueError("label cannot be empty.")

    def metric_value(self, metric: BacktestComparisonMetric) -> float | None:
        value = self.metrics.get(metric.value)

        if value is None or isinstance(value, bool):
            return None

        if not isinstance(value, (int, float)):
            return None

        return float(value)

    def to_dict(self) -> dict[str, Any]:
        return {
            "label": self.label,
            "metrics": self.metrics,
            "source_path": self.source_path,
            "metadata": self.metadata,
        }


@dataclass(frozen=True)
class BacktestComparisonRanking:
    rank: int
    label: str
    value: float | None

    def to_dict(self) -> dict[str, Any]:
        return {
            "rank": self.rank,
            "label": self.label,
            "value": self.value,
        }


@dataclass(frozen=True)
class BacktestComparisonResult:
    metric: BacktestComparisonMetric
    higher_is_better: bool
    entries: tuple[BacktestComparisonEntry, ...]
    rankings: tuple[BacktestComparisonRanking, ...]
    comparison_version: str = BACKTEST_COMPARISON_VERSION
    created_at_utc: str = dataclass_field(default_factory=backtesting_utc_now_iso)
    metadata: dict[str, Any] = dataclass_field(default_factory=dict)

    @property
    def best(self) -> BacktestComparisonRanking | None:
        ranked = [ranking for ranking in self.rankings if ranking.value is not None]
        return ranked[0] if ranked else None

    @property
    def worst(self) -> BacktestComparisonRanking | None:
        ranked = [ranking for ranking in self.rankings if ranking.value is not None]
        return ranked[-1] if ranked else None

    def to_dict(self) -> dict[str, Any]:
        return {
            "comparison_version": self.comparison_version,
            "created_at_utc": self.created_at_utc,
            "metric": self.metric.value,
            "higher_is_better": self.higher_is_better,
            "entry_count": len(self.entries),
            "best": self.best.to_dict() if self.best is not None else None,
            "worst": self.worst.to_dict() if self.worst is not None else None,
            "rankings": [ranking.to_dict() for ranking in self.rankings],
            "entries": [entry.to_dict() for entry in self.entries],
            "metadata": self.metadata,
        }


def metric_defaults_to_higher_is_better(metric: BacktestComparisonMetric) -> bool:
    return metric not in LOWER_IS_BETTER_METRICS


def flatten_backtest_report_metrics(payload: dict[str, Any]) -> dict[str, Any]:
    """
    Pull comparable metrics out of any AQOS backtest report payload.

    CSV-signal, strategy and model backtest reports nest their metrics
    differently, so each known shape is unwrapped here.
    """

    if "strategy_backtest" in payload:
        return flatten_backtest_report_metrics(payload["strategy_backtest"])

    metrics = dict(payload.get("metrics", {}))

    analytics = payload.get("analytics", {})
    risk = analytics.get("risk", {}) if isinstance(analytics, dict) else {}

    for key in ("expectancy", "sharpe_like_ratio", "recovery_factor", "payoff_ratio"):
        if key in risk:
            metrics[key] = risk[key]

    return metrics


def resolve_backtest_report_label(
    payload: dict[str, Any],
    fallback: str,
) -> str:
    source = payload.get("strategy_backtest", payload)

    run_config = source.get("run_config", {})

    if isinstance(run_config, dict):
        strategy_name = run_config.get("strategy_name")

        if isinstance(strategy_name, str) and strategy_name.strip():
            return strategy_name

    return fallback


def build_backtest_comparison_entry_from_report(
    report_path: str | Path,
    label: str | None = None,
) -> BacktestComparisonEntry:
    path = Path(report_path)

    if not path.exists():
        raise FileNotFoundError(f"Backtest report does not exist: {path}")

    payload = json.loads(path.read_text(encoding="utf-8"))

    if not isinstance(payload, dict):
        raise ValueError(f"Backtest report must be a JSON object: {path}")

    metadata: dict[str, Any] = {}
    model_identity = payload.get("model_identity")

    if isinstance(model_identity, dict):
        metadata["model_identity"] = model_identity

    return BacktestComparisonEntry(
        label=label or resolve_backtest_report_label(payload, path.stem),
        metrics=flatten_backtest_report_metrics(payload),
        source_path=path.as_posix(),
        metadata=metadata,
    )


def load_backtest_comparison_entries(
    report_paths: tuple[str | Path, ...],
    labels: tuple[str, ...] | None = None,
) -> tuple[BacktestComparisonEntry, ...]:
    if not report_paths:
        raise ValueError("report_paths cannot be empty.")

    if labels is not None and len(labels) != len(report_paths):
        raise ValueError("labels must have the same length as report_paths.")

    return tuple(
        build_backtest_comparison_entry_from_report(
            report_path=report_path,
            label=labels[index] if labels is not None else None,
        )
        for index, report_path in enumerate(report_paths)
    )


def rank_backtest_entries(
    entries: tuple[BacktestComparisonEntry, ...],
    metric: BacktestComparisonMetric,
    higher_is_better: bool,
) -> tuple[BacktestComparisonRanking, ...]:
    ranked: list[tuple[BacktestComparisonEntry, float]] = []
    unranked: list[BacktestComparisonEntry] = []

    for entry in entries:
        value = entry.metric_value(metric)

        if value is None or math.isnan(value):
            unranked.append(entry)
        else:
            ranked.append((entry, value))

    ranked.sort(key=lambda item: item[0].label)
    ranked.sort(key=lambda item: item[1], reverse=higher_is_better)
    unranked.sort(key=lambda entry: entry.label)

    rankings = [
        BacktestComparisonRanking(rank=index + 1, label=entry.label, value=value)
        for index, (entry, value) in enumerate(ranked)
    ]

    rankings.extend(
        BacktestComparisonRanking(
            rank=len(ranked) + offset + 1,
            label=entry.label,
            value=None,
        )
        for offset, entry in enumerate(unranked)
    )

    return tuple(rankings)


def compare_backtest_runs(
    entries: tuple[BacktestComparisonEntry, ...],
    metric: BacktestComparisonMetric = BacktestComparisonMetric.NET_PROFIT,
    higher_is_better: bool | None = None,
    metadata: dict[str, Any] | None = None,
    created_at_utc: str | None = None,
) -> BacktestComparisonResult:
    if not entries:
        raise ValueError("entries cannot be empty.")

    labels = [entry.label for entry in entries]

    if len(set(labels)) != len(labels):
        raise ValueError("Backtest comparison entry labels must be unique.")

    resolved_direction = (
        metric_defaults_to_higher_is_better(metric)
        if higher_is_better is None
        else higher_is_better
    )

    return BacktestComparisonResult(
        metric=metric,
        higher_is_better=resolved_direction,
        entries=entries,
        rankings=rank_backtest_entries(entries, metric, resolved_direction),
        created_at_utc=created_at_utc or backtesting_utc_now_iso(),
        metadata=metadata or {},
    )


def build_backtest_comparison_dataframe(
    result: BacktestComparisonResult,
) -> pd.DataFrame:
    rank_by_label = {ranking.label: ranking.rank for ranking in result.rankings}

    rows = []

    for entry in result.entries:
        row: dict[str, Any] = {
            "rank": rank_by_label.get(entry.label),
            "label": entry.label,
            "source_path": entry.source_path,
        }

        for comparison_metric in BacktestComparisonMetric:
            row[comparison_metric.value] = entry.metric_value(comparison_metric)

        rows.append(row)

    frame = pd.DataFrame(rows)

    return frame.sort_values("rank", kind="stable").reset_index(drop=True)


def write_backtest_comparison_report(
    path: str | Path,
    result: BacktestComparisonResult,
) -> Path:
    output_path = Path(path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(result.to_dict(), indent=2, sort_keys=True),
        encoding="utf-8",
    )

    return output_path


def write_backtest_comparison_csv(
    path: str | Path,
    result: BacktestComparisonResult,
) -> Path:
    output_path = Path(path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    build_backtest_comparison_dataframe(result).to_csv(output_path, index=False)

    return output_path


__all__ = [
    "BACKTEST_COMPARISON_VERSION",
    "BacktestComparisonEntry",
    "BacktestComparisonMetric",
    "BacktestComparisonRanking",
    "BacktestComparisonResult",
    "LOWER_IS_BETTER_METRICS",
    "build_backtest_comparison_dataframe",
    "build_backtest_comparison_entry_from_report",
    "compare_backtest_runs",
    "flatten_backtest_report_metrics",
    "load_backtest_comparison_entries",
    "metric_defaults_to_higher_is_better",
    "rank_backtest_entries",
    "resolve_backtest_report_label",
    "write_backtest_comparison_csv",
    "write_backtest_comparison_report",
]
