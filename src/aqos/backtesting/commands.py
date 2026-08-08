"""
The approved way to start a backtest from outside the package.

A backtest reads a file, writes several more and runs a simulation. Every one
of those is a place a request could reach further than it should, so none of
them is a parameter a caller controls:

* bars come from a **named dataset** inside one configured directory, never
  from a path in a request;
* artifacts are written under one configured output directory, and their
  locations are never returned;
* the strategy is chosen from a fixed list of built-in names, never imported,
  evaluated or fetched.

Callers outside :mod:`aqos.backtesting` use this module and nothing else. The
runner, the simulator, the data loader and the adapters stay private, and a
guard test proves the API cannot reach them.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field as dataclass_field
from datetime import datetime
from pathlib import Path
from typing import Any

from aqos.account_analytics.metrics import resolve_profit_factor_state
from aqos.backtesting.contracts import backtesting_utc_now_iso
from aqos.backtesting.registry import (
    BacktestResultEntry,
    register_backtest_report,
)
from aqos.backtesting.runner import BacktestRunnerConfig, run_backtest_from_csv
from aqos.users.repositories import build_entity_id


AQOS_BACKTEST_COMMANDS_VERSION = "1.0"

#: What a dataset may be called.
#:
#: No separators, no dots, no anything that could climb out of the configured
#: directory. A name is a name, not a path fragment.
DATASET_NAME_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_-]{0,63}$")

DATASET_SUFFIX = ".csv"

#: The strategies a request may ask for.
#:
#: A fixed list, resolved by name. Nothing here imports a module named by a
#: client, evaluates submitted code or downloads anything: the only way to add
#: a strategy is to add it to the codebase.
SUPPORTED_STRATEGIES = ("csv_signal_strategy",)

#: The widest window one run may cover.
#:
#: A backtest holds its bars in memory and writes a row per trade; an unbounded
#: range is a way to exhaust the process. Deployments with more data can raise
#: this deliberately rather than by accident.
MAX_BACKTEST_DAYS = 3_660

#: The most rows one run may load.
MAX_BACKTEST_ROWS = 500_000


class BacktestCommandError(ValueError):
    """A backtest that cannot be run as asked."""


class BacktestDatasetError(BacktestCommandError):
    """A dataset that is not one of the configured ones."""


@dataclass(frozen=True)
class BacktestDataset:
    """One dataset a run may be executed against."""

    name: str
    rows: int | None = None

    def to_dict(self) -> dict[str, Any]:
        return {"name": self.name, "rows": self.rows}


@dataclass(frozen=True)
class BacktestRunCommand:
    """One request to run a historical backtest."""

    user_id: str
    strategy_name: str
    dataset: str
    symbol: str | None = None
    timeframe: str | None = None
    period_start: str | None = None
    period_end: str | None = None
    initial_balance: float = 10_000.0
    risk_fraction: float = 0.01
    fixed_quantity: float | None = 1.0
    spread_points: float = 0.0
    slippage_points: float = 0.0
    commission_per_trade: float = 0.0
    allow_short: bool = True
    max_open_positions: int = 1
    model_id: str | None = None
    model_version: str | None = None


@dataclass(frozen=True)
class BacktestCommandResult:
    """
    What one run produced.

    ``status`` is ``completed`` or ``failed`` and nothing else: the run happens
    inside the request, so there is no queue to report and claiming one would
    be a lie about how the system works.
    """

    status: str
    backtest_id: str
    user_id: str
    strategy_name: str
    dataset: str
    symbol: str | None = None
    timeframe: str | None = None
    period_start: str | None = None
    period_end: str | None = None
    created_at_utc: str = ""
    completed_at_utc: str | None = None
    metrics: dict[str, Any] = dataclass_field(default_factory=dict)
    model_identity: dict[str, Any] = dataclass_field(default_factory=dict)
    rows_loaded: int | None = None
    #: Whether ``metrics['profit_factor']`` is measured, infinite or absent.
    #:
    #: A null profit factor is ambiguous on its own: a run that never lost
    #: and a run with nothing to divide both serialize the same way.
    profit_factor_state: str | None = None
    failure_reason: str | None = None

    @property
    def completed(self) -> bool:
        return self.status == "completed"


def normalize_dataset_name(value: str) -> str:
    """
    Check a dataset name, or refuse it.

    The pattern is the whole defence: anything that is not a bare name cannot
    become a path, so ``../``, an absolute path and a symlinked name all fail
    here rather than being resolved and then checked.
    """

    name = (value or "").strip()

    if not DATASET_NAME_PATTERN.match(name):
        raise BacktestDatasetError(
            "A dataset is named, not located. Use one of the configured "
            "dataset names."
        )

    return name


def validate_period(period_start: str | None, period_end: str | None) -> None:
    """A window that runs backwards, or forever, is refused."""

    if period_start is None or period_end is None:
        return

    try:
        start = datetime.fromisoformat(period_start)
        end = datetime.fromisoformat(period_end)
    except ValueError as error:
        raise BacktestCommandError(
            "period_start and period_end must be ISO timestamps."
        ) from error

    if end < start:
        raise BacktestCommandError("period_end cannot be before period_start.")

    if (end - start).days > MAX_BACKTEST_DAYS:
        raise BacktestCommandError(
            f"A backtest may cover at most {MAX_BACKTEST_DAYS} days."
        )


def validate_strategy(strategy_name: str) -> str:
    name = (strategy_name or "").strip()

    if name not in SUPPORTED_STRATEGIES:
        raise BacktestCommandError(
            f"Unsupported strategy: {name!r}. Supported strategies are: "
            f"{', '.join(SUPPORTED_STRATEGIES)}."
        )

    return name


class BacktestCommandService:
    """
    Runs backtests inside configured boundaries.

    Holds the three directories a deployment configured and refuses to work
    without them, rather than falling back to a default that would put a
    client's data somewhere nobody chose.
    """

    def __init__(
        self,
        dataset_dir: str | Path,
        output_dir: str | Path,
        registry_path: str | Path,
    ) -> None:
        self.dataset_dir = Path(dataset_dir).resolve()
        self.output_dir = Path(output_dir).resolve()
        self.registry_path = Path(registry_path)

    # -- datasets ---------------------------------------------------------

    def list_datasets(self) -> tuple[BacktestDataset, ...]:
        """
        Every dataset a caller may run against, by name.

        Names only. A client that knew where these lived would know where the
        process can read, which is not something a backtest API should teach.
        """

        if not self.dataset_dir.is_dir():
            return ()

        return tuple(
            BacktestDataset(name=path.stem)
            for path in sorted(self.dataset_dir.glob(f"*{DATASET_SUFFIX}"))
            if DATASET_NAME_PATTERN.match(path.stem)
        )

    def resolve_dataset(self, name: str) -> Path:
        """
        Turn a dataset name into a file inside the configured directory.

        Checked twice: the name cannot express a path, and the resolved file
        must still sit under the configured root. The second check is what
        catches a symlink pointing somewhere else.
        """

        resolved_name = normalize_dataset_name(name)
        candidate = (self.dataset_dir / f"{resolved_name}{DATASET_SUFFIX}").resolve()

        if not candidate.is_file():
            raise BacktestDatasetError(f"Unknown dataset: {resolved_name}.")

        if self.dataset_dir not in candidate.parents:
            raise BacktestDatasetError(f"Unknown dataset: {resolved_name}.")

        return candidate

    # -- runs -------------------------------------------------------------

    def run(self, command: BacktestRunCommand) -> BacktestCommandResult:
        """
        Run one backtest and register its result.

        The run is synchronous: by the time this returns the artifacts are on
        disk and the registry names them, so the read endpoints can serve the
        run immediately. A failure inside the simulation is reported as a
        failed result rather than raised, because the attempt is still a fact
        worth reporting; a refused *request* is raised before anything runs.
        """

        strategy_name = validate_strategy(command.strategy_name)
        dataset_path = self.resolve_dataset(command.dataset)

        validate_period(command.period_start, command.period_end)

        backtest_id = build_entity_id("backtest")
        created_at_utc = backtesting_utc_now_iso()
        model_identity = build_model_identity(command)

        try:
            output = run_backtest_from_csv(
                BacktestRunnerConfig(
                    data_path=dataset_path,
                    output_dir=self.output_dir / backtest_id,
                    symbol=command.symbol,
                    timeframe=command.timeframe,
                    strategy_name=strategy_name,
                    initial_balance=command.initial_balance,
                    risk_fraction=command.risk_fraction,
                    fixed_quantity=command.fixed_quantity,
                    spread_points=command.spread_points,
                    slippage_points=command.slippage_points,
                    commission_per_trade=command.commission_per_trade,
                    allow_short=command.allow_short,
                    max_open_positions=command.max_open_positions,
                    start_timestamp=command.period_start,
                    end_timestamp=command.period_end,
                    # The registry takes a run's id from its report filename,
                    # so naming the report after the run is what keeps two
                    # runs from registering as one.
                    report_filename=f"{backtest_id}.json",
                    metadata={
                        "backtest_id": backtest_id,
                        "user_id": command.user_id,
                        "dataset": command.dataset,
                    },
                )
            )
        except Exception as error:  # noqa: BLE001 - reported, never re-raised
            return BacktestCommandResult(
                status="failed",
                backtest_id=backtest_id,
                user_id=command.user_id,
                strategy_name=strategy_name,
                dataset=command.dataset,
                symbol=command.symbol,
                timeframe=command.timeframe,
                period_start=command.period_start,
                period_end=command.period_end,
                created_at_utc=created_at_utc,
                model_identity=model_identity,
                failure_reason=summarize_failure(error),
            )

        rows_loaded = output.data_load_result.loaded_rows

        if rows_loaded is not None and rows_loaded > MAX_BACKTEST_ROWS:
            return BacktestCommandResult(
                status="failed",
                backtest_id=backtest_id,
                user_id=command.user_id,
                strategy_name=strategy_name,
                dataset=command.dataset,
                symbol=command.symbol,
                timeframe=command.timeframe,
                period_start=command.period_start,
                period_end=command.period_end,
                created_at_utc=created_at_utc,
                model_identity=model_identity,
                rows_loaded=rows_loaded,
                failure_reason=(
                    f"This run loaded more than {MAX_BACKTEST_ROWS} rows. "
                    "Narrow the period."
                ),
            )

        profit_factor_state = resolve_profit_factor_state(
            output.metrics.profit_factor
        ).value

        finalize_report(output.report_path)

        entry = self.register(
            output=output,
            backtest_id=backtest_id,
            command=command,
            created_at_utc=created_at_utc,
            model_identity=model_identity,
        )

        return BacktestCommandResult(
            status="completed",
            backtest_id=entry.run_id,
            user_id=command.user_id,
            strategy_name=strategy_name,
            dataset=command.dataset,
            symbol=entry.symbol,
            timeframe=entry.timeframe,
            period_start=command.period_start,
            period_end=command.period_end,
            created_at_utc=created_at_utc,
            completed_at_utc=backtesting_utc_now_iso(),
            metrics=dict(entry.metrics),
            model_identity=model_identity,
            rows_loaded=rows_loaded,
            profit_factor_state=profit_factor_state,
        )

    def register(
        self,
        output: Any,
        backtest_id: str,
        command: BacktestRunCommand,
        created_at_utc: str,
        model_identity: dict[str, Any],
    ) -> BacktestResultEntry:
        """
        Record the run so the read endpoints can find it.

        The owning user goes into the entry's metadata: it is what lets a read
        endpoint tell whose run this was, and runs made outside the API simply
        do not carry one.
        """

        entry = register_backtest_report(
            registry_path=self.registry_path,
            report_path=output.report_path,
            metadata={
                "user_id": command.user_id,
                "dataset": command.dataset,
                "run_id": backtest_id,
                "period_start": command.period_start,
                "period_end": command.period_end,
                "rows_loaded": output.data_load_result.loaded_rows,
            },
            created_at_utc=created_at_utc,
        )

        if not model_identity:
            return entry

        # The report's own identity wins where it has one; a request may only
        # add traceability, never claim a model was something it was not.
        merged = {**model_identity, **entry.model_identity}

        return BacktestResultEntry(
            run_id=entry.run_id,
            created_at_utc=entry.created_at_utc,
            kind=entry.kind,
            strategy_name=entry.strategy_name,
            report_path=entry.report_path,
            symbol=entry.symbol,
            timeframe=entry.timeframe,
            manifest_path=entry.manifest_path,
            analytics_path=entry.analytics_path,
            metrics=entry.metrics,
            model_identity=merged,
            tags=entry.tags,
            metadata=entry.metadata,
        )


#: Report keys that name a location on disk.
#:
#: Useful to whoever ran the backtest from a shell, and to nobody reading it
#: over HTTP. They are removed from a report the API will serve so that no
#: future section can accidentally start returning them.
REPORT_PATH_KEYS = (
    "report_path",
    "trades_path",
    "orders_path",
    "equity_curve_path",
)

#: Config keys inside a report that name a location on disk.
REPORT_CONFIG_PATH_KEYS = ("data_path", "output_dir")


def strip_non_finite(value: Any) -> Any:
    """
    Replace values JSON cannot represent, without inventing a number.

    ``Infinity`` is not JSON, so it becomes ``None`` rather than a large number
    that would read as measured. On its own that would lose the difference
    between "won every trade" and "nothing to divide", which is why
    :func:`finalize_report` records ``profit_factor_state`` before this runs.
    """

    if isinstance(value, float):
        return value if value == value and value not in (
            float("inf"),
            float("-inf"),
        ) else None

    if isinstance(value, dict):
        return {key: strip_non_finite(item) for key, item in value.items()}

    if isinstance(value, list):
        return [strip_non_finite(item) for item in value]

    return value


def finalize_report(report_path: Path) -> None:
    """
    Rewrite a run's report into the shape the read endpoints serve.

    The runner nests trades and orders inside its final state and writes the
    equity curve as a summary object. The read endpoints serve flat sections,
    so those rows are promoted to the top level here — the same rows, not a
    copy or a summary of them.

    Locations are removed and non-finite numbers are replaced while this file
    is being rewritten, because this is the report an HTTP client will read.
    """

    payload = json.loads(report_path.read_text(encoding="utf-8"))

    final_state = payload.get("final_state") or {}
    equity_curve = payload.get("equity_curve") or {}

    payload["trades"] = list(final_state.get("trades") or ())
    payload["orders"] = list(final_state.get("orders") or ())
    payload["equity_curve"] = list(equity_curve.get("points") or ())
    payload["equity_summary"] = {
        key: value
        for key, value in equity_curve.items()
        if key != "points"
    }

    # Recorded before the non-finite values are replaced, so a reader can tell
    # an infinite profit factor from one that could not be calculated. Both
    # serialize as null; only the state says which happened.
    metrics = payload.get("metrics")

    if isinstance(metrics, dict):
        metrics["profit_factor_state"] = resolve_profit_factor_state(
            metrics.get("profit_factor")
        ).value

    for key in REPORT_PATH_KEYS:
        payload.pop(key, None)

    config = payload.get("config")

    if isinstance(config, dict):
        for key in REPORT_CONFIG_PATH_KEYS:
            config.pop(key, None)

    report_path.write_text(
        json.dumps(
            strip_non_finite(payload),
            indent=2,
            sort_keys=True,
            allow_nan=False,
        ),
        encoding="utf-8",
    )


def build_model_identity(command: BacktestRunCommand) -> dict[str, Any]:
    """
    Traceability for a run a caller attributed to a model.

    ``promotion_state`` is deliberately absent: whether a model is promoted is
    the promotion registry's answer, not a request's, and this run says nothing
    about production readiness either way.
    """

    if not (command.model_id or command.model_version):
        return {}

    return {
        "model_id": command.model_id,
        "model_version": command.model_version,
        "claimed_by": "backtest_request",
    }


def summarize_failure(error: Exception) -> str:
    """
    What a caller is told about a run that broke.

    Never the exception text: a loader failure can carry the path it tried to
    read, and a pandas error can carry a column of somebody's data.
    """

    return (
        "The backtest could not be completed. Check the dataset, the period "
        "and the run parameters."
    )


__all__ = [
    "AQOS_BACKTEST_COMMANDS_VERSION",
    "BacktestCommandError",
    "BacktestCommandResult",
    "BacktestCommandService",
    "BacktestDataset",
    "BacktestDatasetError",
    "BacktestRunCommand",
    "DATASET_NAME_PATTERN",
    "DATASET_SUFFIX",
    "MAX_BACKTEST_DAYS",
    "MAX_BACKTEST_ROWS",
    "REPORT_CONFIG_PATH_KEYS",
    "REPORT_PATH_KEYS",
    "SUPPORTED_STRATEGIES",
    "build_model_identity",
    "finalize_report",
    "normalize_dataset_name",
    "strip_non_finite",
    "summarize_failure",
    "validate_period",
    "validate_strategy",
]


