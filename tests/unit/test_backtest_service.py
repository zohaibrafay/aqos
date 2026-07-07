"""
Unit tests for BacktestService.
"""

import pytest

from aqos.evaluation import BacktestResult, EvaluationReport
from aqos.services import BacktestRun, BacktestService


def test_run_backtest():
    service = BacktestService()

    run = service.run(
        name="xauusd-test",
        profits=[100.0, -50.0, 25.0],
        initial_balance=10_000.0,
        metadata={"symbol": "XAUUSD"},
    )

    assert isinstance(run, BacktestRun)
    assert run.name == "xauusd-test"
    assert isinstance(run.result, BacktestResult)
    assert run.result.final_balance == 10_075.0
    assert run.result.total_profit == 75.0
    assert run.metadata["symbol"] == "XAUUSD"
    assert service.count() == 1


def test_get_backtest_run():
    service = BacktestService()

    service.run(
        name="run-1",
        profits=[100.0],
        initial_balance=10_000.0,
    )

    run = service.get("run-1")

    assert run is not None
    assert run.name == "run-1"


def test_get_missing_backtest_run():
    service = BacktestService()

    run = service.get("missing")

    assert run is None


def test_get_backtest_result():
    service = BacktestService()

    service.run(
        name="run-1",
        profits=[100.0],
        initial_balance=10_000.0,
    )

    result = service.get_result("run-1")

    assert isinstance(result, BacktestResult)
    assert result.total_profit == 100.0


def test_get_missing_backtest_result():
    service = BacktestService()

    with pytest.raises(ValueError):
        service.get_result("missing")


def test_exists_true():
    service = BacktestService()

    service.run(
        name="run-1",
        profits=[100.0],
        initial_balance=10_000.0,
    )

    assert service.exists("run-1") is True


def test_exists_false():
    service = BacktestService()

    assert service.exists("run-1") is False


def test_list_backtest_runs():
    service = BacktestService()

    service.run("run-b", [100.0], 10_000.0)
    service.run("run-a", [50.0], 10_000.0)

    runs = service.list()

    assert len(runs) == 2


def test_list_names():
    service = BacktestService()

    service.run("run-b", [100.0], 10_000.0)
    service.run("run-a", [50.0], 10_000.0)

    assert service.list_names() == [
        "run-a",
        "run-b",
    ]


def test_remove_backtest_run():
    service = BacktestService()

    service.run("run-1", [100.0], 10_000.0)

    service.remove("run-1")

    assert service.exists("run-1") is False
    assert service.count() == 0


def test_clear_backtest_runs():
    service = BacktestService()

    service.run("run-1", [100.0], 10_000.0)
    service.run("run-2", [50.0], 10_000.0)

    service.clear()

    assert service.count() == 0


def test_generate_report():
    service = BacktestService()

    service.run(
        name="run-1",
        profits=[100.0, -50.0, 25.0],
        initial_balance=10_000.0,
    )

    report = service.generate_report(
        name="run-1",
        title="AQOS Report",
    )

    assert isinstance(report, EvaluationReport)
    assert report.title == "AQOS Report"
    assert report.summary["total_profit"] == 75.0
    assert report.summary["total_trades"] == 3


def test_generate_text_summary():
    service = BacktestService()

    service.run(
        name="run-1",
        profits=[100.0, -50.0, 25.0],
        initial_balance=10_000.0,
    )

    summary = service.generate_text_summary(
        name="run-1",
        title="AQOS Report",
    )

    assert "AQOS Report" in summary
    assert "Total Profit: 75.0" in summary


def test_best_run_by_profit():
    service = BacktestService()

    service.run("run-low", [50.0], 10_000.0)
    service.run("run-high", [100.0], 10_000.0)

    best = service.best_run_by_profit()

    assert best.name == "run-high"
    assert best.result.total_profit == 100.0


def test_best_run_without_runs():
    service = BacktestService()

    with pytest.raises(ValueError):
        service.best_run_by_profit()


def test_empty_name():
    service = BacktestService()

    with pytest.raises(ValueError):
        service.run(
            name="",
            profits=[100.0],
            initial_balance=10_000.0,
        )


def test_empty_profits():
    service = BacktestService()

    with pytest.raises(ValueError):
        service.run(
            name="run-1",
            profits=[],
            initial_balance=10_000.0,
        )


def test_invalid_initial_balance():
    service = BacktestService()

    with pytest.raises(ValueError):
        service.run(
            name="run-1",
            profits=[100.0],
            initial_balance=0,
        )