from __future__ import annotations

import json
from dataclasses import dataclass, field as dataclass_field
from enum import Enum
from pathlib import Path
from typing import Any

from aqos.backtesting.comparison import flatten_backtest_report_metrics
from aqos.backtesting.contracts import backtesting_utc_now_iso


BACKTEST_REGISTRY_VERSION = "1.0"

REGISTERED_METRIC_KEYS = (
    "net_profit",
    "return_fraction",
    "total_trades",
    "win_rate",
    "profit_factor",
    "max_drawdown",
    "expectancy",
    "sharpe_like_ratio",
)


class BacktestKind(str, Enum):
    CSV_SIGNAL = "csv_signal"
    RULE_STRATEGY = "rule_strategy"
    ML_MODEL = "ml_model"


@dataclass(frozen=True)
class BacktestResultEntry:
    run_id: str
    created_at_utc: str
    kind: BacktestKind
    strategy_name: str
    report_path: str
    symbol: str | None = None
    timeframe: str | None = None
    manifest_path: str | None = None
    analytics_path: str | None = None
    metrics: dict[str, Any] = dataclass_field(default_factory=dict)
    model_identity: dict[str, Any] = dataclass_field(default_factory=dict)
    tags: tuple[str, ...] = ()
    metadata: dict[str, Any] = dataclass_field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.run_id.strip():
            raise ValueError("run_id cannot be empty.")

        if not self.created_at_utc.strip():
            raise ValueError("created_at_utc cannot be empty.")

        if not self.strategy_name.strip():
            raise ValueError("strategy_name cannot be empty.")

        if not self.report_path.strip():
            raise ValueError("report_path cannot be empty.")

    @property
    def net_profit(self) -> float | None:
        value = self.metrics.get("net_profit")

        return float(value) if isinstance(value, (int, float)) else None

    def to_dict(self) -> dict[str, Any]:
        return {
            "run_id": self.run_id,
            "created_at_utc": self.created_at_utc,
            "kind": self.kind.value,
            "strategy_name": self.strategy_name,
            "symbol": self.symbol,
            "timeframe": self.timeframe,
            "report_path": self.report_path,
            "manifest_path": self.manifest_path,
            "analytics_path": self.analytics_path,
            "metrics": self.metrics,
            "model_identity": self.model_identity,
            "tags": list(self.tags),
            "metadata": self.metadata,
        }


@dataclass(frozen=True)
class BacktestResultRegistry:
    results: tuple[BacktestResultEntry, ...] = ()
    registry_version: str = BACKTEST_REGISTRY_VERSION

    @property
    def result_count(self) -> int:
        return len(self.results)

    def to_dict(self) -> dict[str, Any]:
        return {
            "registry_version": self.registry_version,
            "result_count": self.result_count,
            "results": [result.to_dict() for result in self.results],
        }


def select_registered_metrics(metrics: dict[str, Any]) -> dict[str, Any]:
    return {
        key: metrics[key]
        for key in REGISTERED_METRIC_KEYS
        if key in metrics and isinstance(metrics[key], (int, float))
    }


def resolve_backtest_kind(payload: dict[str, Any]) -> BacktestKind:
    if "gate_decision" in payload or "model_identity" in payload:
        return BacktestKind.ML_MODEL

    source = payload.get("strategy_backtest", payload)
    metrics_metadata = source.get("metrics", {}).get("metadata", {})

    adapter_type = metrics_metadata.get("adapter_type")

    if adapter_type == BacktestKind.ML_MODEL.value:
        return BacktestKind.ML_MODEL

    if adapter_type is not None:
        return BacktestKind.RULE_STRATEGY

    return BacktestKind.CSV_SIGNAL


def build_backtest_result_entry_from_report(
    report_path: str | Path,
    tags: tuple[str, ...] = (),
    metadata: dict[str, Any] | None = None,
    created_at_utc: str | None = None,
) -> BacktestResultEntry:
    path = Path(report_path)

    if not path.exists():
        raise FileNotFoundError(f"Backtest report does not exist: {path}")

    payload = json.loads(path.read_text(encoding="utf-8"))

    if not isinstance(payload, dict):
        raise ValueError(f"Backtest report must be a JSON object: {path}")

    source = payload.get("strategy_backtest", payload)
    run_config = source.get("run_config", {})

    model_identity = payload.get("model_identity")

    return BacktestResultEntry(
        run_id=str(payload.get("run_id") or source.get("run_id") or path.stem),
        created_at_utc=created_at_utc or backtesting_utc_now_iso(),
        kind=resolve_backtest_kind(payload),
        strategy_name=str(run_config.get("strategy_name") or path.stem),
        report_path=path.as_posix(),
        symbol=run_config.get("symbol"),
        timeframe=run_config.get("timeframe"),
        manifest_path=payload.get("manifest_path") or source.get("manifest_path"),
        analytics_path=source.get("analytics_path"),
        metrics=select_registered_metrics(flatten_backtest_report_metrics(payload)),
        model_identity=model_identity if isinstance(model_identity, dict) else {},
        tags=tags,
        metadata=metadata or {},
    )


def parse_backtest_result_entry(payload: dict[str, Any]) -> BacktestResultEntry:
    return BacktestResultEntry(
        run_id=str(payload["run_id"]),
        created_at_utc=str(payload["created_at_utc"]),
        kind=BacktestKind(str(payload["kind"])),
        strategy_name=str(payload["strategy_name"]),
        report_path=str(payload["report_path"]),
        symbol=payload.get("symbol"),
        timeframe=payload.get("timeframe"),
        manifest_path=payload.get("manifest_path"),
        analytics_path=payload.get("analytics_path"),
        metrics=payload.get("metrics", {}),
        model_identity=payload.get("model_identity", {}),
        tags=tuple(str(tag) for tag in payload.get("tags", ())),
        metadata=payload.get("metadata", {}),
    )


def read_backtest_result_registry(path: str | Path) -> BacktestResultRegistry:
    registry_path = Path(path)

    if not registry_path.exists():
        return BacktestResultRegistry()

    payload = json.loads(registry_path.read_text(encoding="utf-8"))

    return BacktestResultRegistry(
        results=tuple(
            parse_backtest_result_entry(item)
            for item in payload.get("results", ())
        ),
        registry_version=str(
            payload.get("registry_version", BACKTEST_REGISTRY_VERSION)
        ),
    )


def write_backtest_result_registry(
    path: str | Path,
    registry: BacktestResultRegistry,
) -> Path:
    output_path = Path(path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(registry.to_dict(), indent=2, sort_keys=True),
        encoding="utf-8",
    )

    return output_path


def append_backtest_result_to_registry(
    path: str | Path,
    entry: BacktestResultEntry,
) -> BacktestResultRegistry:
    """Insert or replace ``entry`` by run id and persist the registry."""

    registry = read_backtest_result_registry(path)

    existing = {result.run_id: result for result in registry.results}
    existing[entry.run_id] = entry

    updated = BacktestResultRegistry(
        results=tuple(
            sorted(
                existing.values(),
                key=lambda result: (result.created_at_utc, result.run_id),
            )
        )
    )

    write_backtest_result_registry(path, updated)

    return updated


def register_backtest_report(
    registry_path: str | Path,
    report_path: str | Path,
    tags: tuple[str, ...] = (),
    metadata: dict[str, Any] | None = None,
    created_at_utc: str | None = None,
) -> BacktestResultEntry:
    entry = build_backtest_result_entry_from_report(
        report_path=report_path,
        tags=tags,
        metadata=metadata,
        created_at_utc=created_at_utc,
    )
    append_backtest_result_to_registry(registry_path, entry)

    return entry


def list_backtest_results(
    registry: BacktestResultRegistry,
    kind: BacktestKind | None = None,
    symbol: str | None = None,
    strategy_name: str | None = None,
    tag: str | None = None,
) -> tuple[BacktestResultEntry, ...]:
    results = registry.results

    if kind is not None:
        results = tuple(result for result in results if result.kind == kind)

    if symbol is not None:
        results = tuple(result for result in results if result.symbol == symbol)

    if strategy_name is not None:
        results = tuple(
            result for result in results if result.strategy_name == strategy_name
        )

    if tag is not None:
        results = tuple(result for result in results if tag in result.tags)

    return results


def find_latest_backtest_result(
    registry: BacktestResultRegistry,
    kind: BacktestKind | None = None,
    symbol: str | None = None,
    strategy_name: str | None = None,
) -> BacktestResultEntry | None:
    results = list_backtest_results(
        registry=registry,
        kind=kind,
        symbol=symbol,
        strategy_name=strategy_name,
    )

    if not results:
        return None

    return max(results, key=lambda result: (result.created_at_utc, result.run_id))


def find_best_backtest_result(
    registry: BacktestResultRegistry,
    metric_key: str = "net_profit",
    kind: BacktestKind | None = None,
    symbol: str | None = None,
) -> BacktestResultEntry | None:
    candidates = [
        result
        for result in list_backtest_results(registry, kind=kind, symbol=symbol)
        if isinstance(result.metrics.get(metric_key), (int, float))
    ]

    if not candidates:
        return None

    return max(candidates, key=lambda result: float(result.metrics[metric_key]))


__all__ = [
    "BACKTEST_REGISTRY_VERSION",
    "BacktestKind",
    "BacktestResultEntry",
    "BacktestResultRegistry",
    "REGISTERED_METRIC_KEYS",
    "append_backtest_result_to_registry",
    "build_backtest_result_entry_from_report",
    "find_best_backtest_result",
    "find_latest_backtest_result",
    "list_backtest_results",
    "parse_backtest_result_entry",
    "read_backtest_result_registry",
    "register_backtest_report",
    "resolve_backtest_kind",
    "select_registered_metrics",
    "write_backtest_result_registry",
]
