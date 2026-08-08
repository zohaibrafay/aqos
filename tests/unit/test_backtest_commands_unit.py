"""
Unit tests for the backtest command boundary and its request schema.

These run real backtests against real CSV files written into ``tmp_path``, so
"the run produced trades" means rows the simulator actually generated. What
they do not need is a database or a network.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from aqos.backtesting.commands import (
    MAX_BACKTEST_DAYS,
    SUPPORTED_STRATEGIES,
    BacktestCommandError,
    BacktestCommandService,
    BacktestDatasetError,
    BacktestRunCommand,
    build_model_identity,
    summarize_failure,
    validate_period,
    validate_strategy,
)
from aqos.http_api.backtest_action_schemas import (
    MAX_INITIAL_BALANCE,
    MAX_OPEN_POSITIONS,
    BacktestRunRequest,
)


def write_dataset(directory: Path, name: str, rows: int = 40) -> Path:
    """A real OHLC CSV with a couple of signals in it."""

    directory.mkdir(parents=True, exist_ok=True)

    lines = ["timestamp,open,high,low,close,volume,signal"]
    price = 100.0

    for index in range(rows):
        price += 1.0 if index % 3 else -0.5
        signal = "buy" if index == 2 else ("close" if index == 12 else "hold")
        day = f"2026-01-{index + 1:02d}"
        lines.append(
            f"{day}T00:00:00,{price},{price + 1},{price - 1},{price},100,{signal}"
        )

    path = directory / f"{name}.csv"
    path.write_text("\n".join(lines), encoding="utf-8")

    return path


@pytest.fixture
def service(tmp_path) -> BacktestCommandService:
    datasets = tmp_path / "datasets"
    write_dataset(datasets, "xauusd_h1")

    return BacktestCommandService(
        dataset_dir=datasets,
        output_dir=tmp_path / "out",
        registry_path=tmp_path / "registry.json",
    )


def build_command(**overrides) -> BacktestRunCommand:
    payload = {
        "user_id": "user_1",
        "strategy_name": "csv_signal_strategy",
        "dataset": "xauusd_h1",
        "symbol": "XAUUSD",
        "timeframe": "H1",
    }
    payload.update(overrides)

    return BacktestRunCommand(**payload)



FLAT_PRICES = [(100, "hold")] * 10

#: One losing round trip then one winning one, so there is a divisor.
MIXED_BARS = [
    (100, "hold"),
    (100, "buy"),
    (95, "hold"),
    (95, "close"),
    (95, "hold"),
    (95, "buy"),
    (100, "hold"),
    (100, "hold"),
    (110, "close"),
    (110, "hold"),
]


def write_bars(directory: Path, name: str, bars) -> None:
    directory.mkdir(parents=True, exist_ok=True)

    rows = ["timestamp,open,high,low,close,volume,signal"]

    for index, (price, signal) in enumerate(bars):
        rows.append(
            f"2026-01-{index + 1:02d}T00:00:00,"
            f"{price},{price + 1},{price - 1},{price},100,{signal}"
        )

    (directory / f"{name}.csv").write_text("\n".join(rows), encoding="utf-8")


def build_service(tmp_path: Path, suffix: str, name: str, bars):
    """A service with its own directories, so runs cannot collide."""

    datasets = tmp_path / f"datasets_{suffix}"
    write_bars(datasets, name, bars)

    return BacktestCommandService(
        dataset_dir=datasets,
        output_dir=tmp_path / f"out_{suffix}",
        registry_path=tmp_path / f"registry_{suffix}.json",
    )


def run_flat(tmp_path: Path, suffix: str):
    """A run that opens nothing, so there is nothing to divide."""

    service = build_service(tmp_path, suffix, "flat", FLAT_PRICES)

    return service.run(build_command(dataset="flat"))


def run_mixed(tmp_path: Path, suffix: str):
    """A run with one loss and one win, so the profit factor is finite."""

    service = build_service(tmp_path, suffix, "mixed", MIXED_BARS)

    return service.run(build_command(dataset="mixed"))


class TestDatasets:
    def test_it_lists_configured_datasets_by_name(self, service) -> None:
        assert [dataset.name for dataset in service.list_datasets()] == [
            "xauusd_h1"
        ]

    def test_an_unconfigured_directory_lists_nothing(self, tmp_path) -> None:
        """Absent is empty here, not an error: there is simply nothing to run."""

        service = BacktestCommandService(
            dataset_dir=tmp_path / "missing",
            output_dir=tmp_path / "out",
            registry_path=tmp_path / "registry.json",
        )

        assert service.list_datasets() == ()

    def test_an_unknown_dataset_is_refused(self, service) -> None:
        with pytest.raises(BacktestDatasetError):
            service.resolve_dataset("does_not_exist")

    @pytest.mark.parametrize(
        "name",
        ["../secrets", "/etc/passwd", "sub/dir", "xauusd_h1.csv", ".."],
    )
    def test_a_path_cannot_be_passed_as_a_name(
        self,
        service,
        name: str,
    ) -> None:
        with pytest.raises(BacktestDatasetError):
            service.resolve_dataset(name)

    def test_a_file_outside_the_directory_is_unreachable(
        self,
        service,
        tmp_path,
    ) -> None:
        """
        Even a real file elsewhere cannot be named.

        The name is checked first, so a caller cannot reach a dataset the
        deployment did not put in the configured directory.
        """

        write_dataset(tmp_path / "elsewhere", "secret")

        with pytest.raises(BacktestDatasetError):
            service.resolve_dataset("../elsewhere/secret")


class TestValidation:
    def test_the_supported_strategies_are_accepted(self) -> None:
        for name in SUPPORTED_STRATEGIES:
            assert validate_strategy(name) == name

    @pytest.mark.parametrize(
        "name",
        ["", "  ", "os.system", "aqos.backtesting.runner", "my_strategy"],
    )
    def test_anything_else_is_refused(self, name: str) -> None:
        with pytest.raises(BacktestCommandError):
            validate_strategy(name)

    def test_a_backwards_period_is_refused(self) -> None:
        with pytest.raises(BacktestCommandError):
            validate_period("2026-06-01T00:00:00", "2026-01-01T00:00:00")

    def test_an_unbounded_period_is_refused(self) -> None:
        with pytest.raises(BacktestCommandError):
            validate_period("1800-01-01T00:00:00", "2026-01-01T00:00:00")

    def test_a_period_at_the_limit_is_accepted(self) -> None:
        validate_period("2026-01-01T00:00:00", "2026-01-31T00:00:00")

    def test_a_malformed_timestamp_is_refused(self) -> None:
        with pytest.raises(BacktestCommandError):
            validate_period("yesterday", "2026-01-01T00:00:00")

    def test_an_open_ended_period_is_allowed(self) -> None:
        """Unset means "all of it", which is a real answer."""

        validate_period(None, None)
        validate_period("2026-01-01T00:00:00", None)

    def test_the_day_limit_is_stated(self) -> None:
        assert MAX_BACKTEST_DAYS > 0


class TestRunning:
    def test_a_valid_run_completes(self, service) -> None:
        result = service.run(build_command())

        assert result.status == "completed"
        assert result.completed is True
        assert result.failure_reason is None
        assert result.completed_at_utc

    def test_the_run_is_attributed_to_the_caller(self, service) -> None:
        result = service.run(build_command(user_id="user_alice"))

        assert result.user_id == "user_alice"

    def test_the_metrics_are_measured(self, service) -> None:
        """
        Real numbers from a real simulation, not placeholders.

        The dataset has one buy and one close, so exactly one trade should come
        out of it.
        """

        result = service.run(build_command())

        assert result.metrics["total_trades"] == 1
        assert isinstance(result.metrics["net_profit"], (int, float))

    def test_two_runs_get_different_ids(self, service) -> None:
        """
        A shared id would make one run overwrite the other in the registry.

        The registry takes its id from the report filename, so the filename has
        to be unique per run.
        """

        first = service.run(build_command())
        second = service.run(build_command())

        assert first.backtest_id != second.backtest_id

    def test_the_run_is_registered(self, service, tmp_path) -> None:
        result = service.run(build_command())
        payload = json.loads(
            (tmp_path / "registry.json").read_text(encoding="utf-8")
        )
        entry = payload["results"][0]

        assert entry["run_id"] == result.backtest_id
        assert entry["metadata"]["user_id"] == "user_1"
        assert entry["symbol"] == "XAUUSD"

    def test_the_registry_accumulates_runs(self, service, tmp_path) -> None:
        service.run(build_command())
        service.run(build_command(user_id="user_2"))

        payload = json.loads(
            (tmp_path / "registry.json").read_text(encoding="utf-8")
        )

        assert len(payload["results"]) == 2

    def test_a_broken_run_is_reported_not_raised(self, service) -> None:
        """
        The attempt is a fact even when the simulation fails.

        A dataset the loader cannot make sense of comes back as a failed run,
        which a caller can act on, rather than as a 500.
        """

        result = service.run(build_command(timeframe=""))

        assert result.status == "failed"
        assert result.failure_reason
        assert result.completed is False
        assert result.metrics == {}

    def test_a_failure_reason_names_nothing_internal(self, service) -> None:
        result = service.run(build_command(timeframe=""))

        for fragment in (
            "Traceback",
            "pandas",
            "ValueError",
            "/",
            "\\",
            ".csv",
        ):
            assert fragment not in result.failure_reason

    def test_the_summary_never_repeats_the_exception(self) -> None:
        summary = summarize_failure(
            RuntimeError("/srv/aqos/datasets/secret.csv is malformed")
        )

        assert "secret.csv" not in summary
        assert "/srv" not in summary
        assert "RuntimeError" not in summary


class TestProfitFactorStaysHonest:
    """
    An infinite profit factor is a result; an absent one is not.

    Both serialize as ``null`` because JSON has no infinity, so the state is
    what keeps "won every trade" from reading like "nothing happened" — and
    neither may ever read as a measured zero.
    """

    def test_a_winning_run_reports_infinite_not_null_alone(
        self,
        service,
    ) -> None:
        result = service.run(build_command())

        assert result.metrics["total_trades"] == 1
        assert result.metrics["net_profit"] > 0
        assert result.profit_factor_state == "infinite_no_losses"

    def test_a_run_with_no_trades_reports_unavailable(
        self,
        tmp_path,
    ) -> None:
        """Nothing to divide is unavailable, which is not the same answer."""

        datasets = tmp_path / "datasets"
        datasets.mkdir()
        (datasets / "flat.csv").write_text(
            "timestamp,open,high,low,close,volume,signal\n"
            + "\n".join(
                f"2026-01-{day:02d}T00:00:00,100,101,99,100,10,hold"
                for day in range(1, 11)
            ),
            encoding="utf-8",
        )

        service = BacktestCommandService(
            dataset_dir=datasets,
            output_dir=tmp_path / "out",
            registry_path=tmp_path / "registry.json",
        )
        result = service.run(build_command(dataset="flat"))

        assert result.metrics["total_trades"] == 0
        assert result.profit_factor_state == "unavailable"

    def test_a_run_with_a_loss_reports_a_finite_value(self, tmp_path) -> None:
        """
        The ordinary case, asserted with real numbers.

        One losing round trip and one winning one, so there is something to
        divide: 15.0 of gross profit against 5.0 of gross loss. Without this
        the state machine would be proven only at its two edges, and the
        middle — the case almost every real run lands in — would be untested.
        """

        datasets = tmp_path / "datasets"
        datasets.mkdir()

        prices = [100, 100, 95, 95, 95, 95, 100, 100, 110, 110]
        signals = [
            "hold",
            "buy",
            "hold",
            "close",
            "hold",
            "buy",
            "hold",
            "hold",
            "close",
            "hold",
        ]
        rows = ["timestamp,open,high,low,close,volume,signal"]

        for index, (price, signal) in enumerate(zip(prices, signals)):
            rows.append(
                f"2026-01-{index + 1:02d}T00:00:00,"
                f"{price},{price + 1},{price - 1},{price},100,{signal}"
            )

        (datasets / "mixed.csv").write_text("\n".join(rows), encoding="utf-8")

        service = BacktestCommandService(
            dataset_dir=datasets,
            output_dir=tmp_path / "out",
            registry_path=tmp_path / "registry.json",
        )
        result = service.run(build_command(dataset="mixed"))

        assert result.status == "completed"
        assert result.metrics["total_trades"] == 2
        assert result.metrics["profit_factor"] == 3.0
        assert result.profit_factor_state == "finite"

        report = next((tmp_path / "out").rglob("*.json"))
        text = report.read_text(encoding="utf-8")
        payload = json.loads(text)

        assert [trade["net_pnl"] for trade in payload["trades"]] == [-5.0, 15.0]
        assert payload["metrics"]["profit_factor"] == 3.0
        assert payload["metrics"]["profit_factor_state"] == "finite"

        for fragment in ("Infinity", "-Infinity", "NaN"):
            assert fragment not in text

    def test_every_state_is_produced_by_a_real_run(
        self,
        service,
        tmp_path,
    ) -> None:
        """
        All three states come out of actual simulations, and all three differ.

        A state nothing can reach is a state nobody has checked, and two states
        that render identically are one state wearing two names.
        """

        states = {
            service.run(build_command()).profit_factor_state,
            run_flat(tmp_path, "a").profit_factor_state,
            run_mixed(tmp_path, "b").profit_factor_state,
        }

        assert states == {"infinite_no_losses", "unavailable", "finite"}

    def test_the_two_states_are_distinguishable(self, service, tmp_path) -> None:
        datasets = tmp_path / "flatset"
        datasets.mkdir()
        (datasets / "flat.csv").write_text(
            "timestamp,open,high,low,close,volume,signal\n"
            + "\n".join(
                f"2026-01-{day:02d}T00:00:00,100,101,99,100,10,hold"
                for day in range(1, 11)
            ),
            encoding="utf-8",
        )
        flat_service = BacktestCommandService(
            dataset_dir=datasets,
            output_dir=tmp_path / "out2",
            registry_path=tmp_path / "registry2.json",
        )

        winning = service.run(build_command())
        empty = flat_service.run(build_command(dataset="flat"))

        assert winning.profit_factor_state != empty.profit_factor_state

    def test_the_report_records_the_state(self, service, tmp_path) -> None:
        """The artifact is self-describing, not only the response."""

        service.run(build_command())
        report = next((tmp_path / "out").rglob("*.json"))
        payload = json.loads(report.read_text(encoding="utf-8"))

        assert payload["metrics"]["profit_factor_state"] == "infinite_no_losses"
        assert payload["metrics"]["profit_factor"] is None

    def test_the_report_is_strict_json(self, service, tmp_path) -> None:
        """
        A wins-only run would otherwise write ``Infinity``.

        Python's own parser accepts that, so the check is on the bytes rather
        than on whether it round-trips.
        """

        service.run(build_command())
        report = next((tmp_path / "out").rglob("*.json"))
        text = report.read_text(encoding="utf-8")

        for fragment in ("Infinity", "-Infinity", "NaN"):
            assert fragment not in text

        json.loads(text)

    def test_no_absolute_path_survives_in_the_report(
        self,
        service,
        tmp_path,
    ) -> None:
        """
        The API serves this file, so it must not say where anything lives.

        Stripping the locations here is what keeps a future section from
        starting to return them.
        """

        service.run(build_command())
        report = next((tmp_path / "out").rglob("*.json"))
        payload = json.loads(report.read_text(encoding="utf-8"))

        assert "report_path" not in payload
        assert "trades_path" not in payload
        assert "data_path" not in payload.get("config", {})
        assert str(tmp_path) not in json.dumps(payload)

    def test_the_report_carries_the_real_rows(self, service, tmp_path) -> None:
        """
        The read endpoints serve these sections, so they have to be populated.

        The runner nests them; promoting them is what makes the run readable
        rather than an empty list pretending to be one.
        """

        service.run(build_command())
        report = next((tmp_path / "out").rglob("*.json"))
        payload = json.loads(report.read_text(encoding="utf-8"))

        assert len(payload["trades"]) == 1
        assert len(payload["orders"]) == 1
        assert len(payload["equity_curve"]) > 1
        assert payload["equity_summary"]["rows"] > 1


class TestModelTraceability:
    def test_no_model_means_no_identity(self) -> None:
        assert build_model_identity(build_command()) == {}

    def test_a_named_model_is_recorded(self) -> None:
        identity = build_model_identity(
            build_command(model_id="model_1", model_version="1.0")
        )

        assert identity["model_id"] == "model_1"
        assert identity["model_version"] == "1.0"

    def test_the_claim_is_marked_as_a_claim(self) -> None:
        """
        A request said this; the promotion registry did not.

        Recording where the attribution came from is what stops a backtest
        result from being read as evidence a model is production ready.
        """

        identity = build_model_identity(build_command(model_id="model_1"))

        assert identity["claimed_by"] == "backtest_request"

    def test_a_request_cannot_claim_promotion(self) -> None:
        identity = build_model_identity(build_command(model_id="model_1"))

        assert "promotion_state" not in identity
        assert "is_promoted" not in identity
        assert "approved" not in identity

    def test_the_identity_survives_into_the_run(self, service) -> None:
        result = service.run(
            build_command(model_id="model_1", model_version="1.0")
        )

        assert result.model_identity["model_id"] == "model_1"


class TestRunRequestSchema:
    def test_a_minimal_request_is_accepted(self) -> None:
        payload = BacktestRunRequest(
            strategy_name="csv_signal_strategy",
            dataset="xauusd_h1",
            symbol="XAUUSD",
            timeframe="H1",
        )

        assert payload.initial_balance == 10_000.0
        assert payload.model_id is None

    @pytest.mark.parametrize(
        "field",
        ["strategy_name", "dataset", "symbol", "timeframe"],
    )
    def test_every_required_field_is_required(self, field: str) -> None:
        """
        The loader needs a symbol and a timeframe when the CSV has no columns
        for them, so both are required rather than defaulted to something the
        run would then misreport.
        """

        payload = {
            "strategy_name": "csv_signal_strategy",
            "dataset": "xauusd_h1",
            "symbol": "XAUUSD",
            "timeframe": "H1",
        }
        payload.pop(field)

        with pytest.raises(ValidationError):
            BacktestRunRequest(**payload)

    @pytest.mark.parametrize(
        "field, value",
        [
            ("data_path", "/etc/passwd"),
            ("output_dir", "/tmp"),
            ("user_id", "user_someone_else"),
            ("strategy_module", "os"),
            ("registry_path", "registry.json"),
            ("metadata", {"anything": True}),
        ],
    )
    def test_smuggling_a_path_or_owner_is_refused(
        self,
        field: str,
        value,
    ) -> None:
        """
        No request may name a file, a module or an owner.

        This is the assertion that would fail first if somebody widened the
        schema to "just pass the path through".
        """

        with pytest.raises(ValidationError):
            BacktestRunRequest(
                strategy_name="csv_signal_strategy",
                dataset="xauusd_h1",
                symbol="XAUUSD",
                timeframe="H1",
                **{field: value},
            )

    @pytest.mark.parametrize(
        "field, value",
        [
            ("initial_balance", 0.0),
            ("initial_balance", -1.0),
            ("initial_balance", MAX_INITIAL_BALANCE * 10),
            ("risk_fraction", 0.0),
            ("risk_fraction", 1.5),
            ("fixed_quantity", 0.0),
            ("spread_points", -1.0),
            ("max_open_positions", 0),
            ("max_open_positions", MAX_OPEN_POSITIONS + 1),
        ],
    )
    def test_an_out_of_range_parameter_is_refused(
        self,
        field: str,
        value,
    ) -> None:
        with pytest.raises(ValidationError):
            BacktestRunRequest(
                strategy_name="csv_signal_strategy",
                dataset="xauusd_h1",
                symbol="XAUUSD",
                timeframe="H1",
                **{field: value},
            )
