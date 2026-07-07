"""
Unit tests for ExperimentService.
"""

import pytest

from aqos.services import ExperimentRun, ExperimentService


def test_create_experiment():
    service = ExperimentService()

    experiment = service.create(
        name="experiment-1",
        description="Baseline experiment",
        metadata={"symbol": "XAUUSD"},
    )

    assert isinstance(experiment, ExperimentRun)
    assert experiment.name == "experiment-1"
    assert experiment.status == "created"
    assert experiment.description == "Baseline experiment"
    assert experiment.metadata["symbol"] == "XAUUSD"
    assert experiment.results == {}
    assert service.count() == 1


def test_create_duplicate_experiment():
    service = ExperimentService()

    service.create("experiment-1")

    with pytest.raises(ValueError):
        service.create("experiment-1")


def test_get_experiment():
    service = ExperimentService()

    service.create("experiment-1")

    experiment = service.get("experiment-1")

    assert experiment is not None
    assert experiment.name == "experiment-1"


def test_get_missing_experiment():
    service = ExperimentService()

    experiment = service.get("missing")

    assert experiment is None


def test_get_required_missing_experiment():
    service = ExperimentService()

    with pytest.raises(ValueError):
        service.get_required("missing")


def test_exists_true():
    service = ExperimentService()

    service.create("experiment-1")

    assert service.exists("experiment-1") is True


def test_exists_false():
    service = ExperimentService()

    assert service.exists("experiment-1") is False


def test_list_experiments():
    service = ExperimentService()

    service.create("experiment-b")
    service.create("experiment-a")

    experiments = service.list()

    assert len(experiments) == 2


def test_list_names():
    service = ExperimentService()

    service.create("experiment-b")
    service.create("experiment-a")

    assert service.list_names() == [
        "experiment-a",
        "experiment-b",
    ]


def test_start_experiment():
    service = ExperimentService()

    service.create("experiment-1")

    experiment = service.start("experiment-1")

    assert experiment.status == "running"


def test_complete_experiment():
    service = ExperimentService()

    service.create("experiment-1")
    service.start("experiment-1")

    experiment = service.complete("experiment-1")

    assert experiment.status == "completed"


def test_fail_experiment():
    service = ExperimentService()

    service.create("experiment-1")

    experiment = service.fail(
        name="experiment-1",
        reason="Backtest failed.",
    )

    assert experiment.status == "failed"
    assert experiment.results["failure_reason"] == "Backtest failed."


def test_fail_experiment_empty_reason():
    service = ExperimentService()

    service.create("experiment-1")

    with pytest.raises(ValueError):
        service.fail(
            name="experiment-1",
            reason="",
        )


def test_add_result():
    service = ExperimentService()

    service.create("experiment-1")

    experiment = service.add_result(
        name="experiment-1",
        key="total_profit",
        value=125.0,
    )

    assert experiment.results["total_profit"] == 125.0


def test_add_result_updates_existing_result():
    service = ExperimentService()

    service.create("experiment-1")

    service.add_result("experiment-1", "total_profit", 100.0)
    experiment = service.add_result("experiment-1", "total_profit", 125.0)

    assert experiment.results["total_profit"] == 125.0


def test_best_by_metric_higher_is_better():
    service = ExperimentService()

    service.create("experiment-low")
    service.create("experiment-high")

    service.add_result("experiment-low", "total_profit", 50.0)
    service.add_result("experiment-high", "total_profit", 150.0)

    best = service.best_by_metric(
        metric="total_profit",
        higher_is_better=True,
    )

    assert best.name == "experiment-high"


def test_best_by_metric_lower_is_better():
    service = ExperimentService()

    service.create("experiment-low-dd")
    service.create("experiment-high-dd")

    service.add_result("experiment-low-dd", "max_drawdown", 0.05)
    service.add_result("experiment-high-dd", "max_drawdown", 0.2)

    best = service.best_by_metric(
        metric="max_drawdown",
        higher_is_better=False,
    )

    assert best.name == "experiment-low-dd"


def test_best_by_metric_without_experiments():
    service = ExperimentService()

    with pytest.raises(ValueError):
        service.best_by_metric("total_profit")


def test_best_by_metric_missing_metric():
    service = ExperimentService()

    service.create("experiment-1")

    with pytest.raises(ValueError):
        service.best_by_metric("total_profit")


def test_remove_experiment():
    service = ExperimentService()

    service.create("experiment-1")

    service.remove("experiment-1")

    assert service.exists("experiment-1") is False
    assert service.count() == 0


def test_clear_experiments():
    service = ExperimentService()

    service.create("experiment-1")
    service.create("experiment-2")

    service.clear()

    assert service.count() == 0


def test_empty_experiment_name():
    service = ExperimentService()

    with pytest.raises(ValueError):
        service.create("")


def test_invalid_status():
    service = ExperimentService()

    service.create("experiment-1")

    with pytest.raises(ValueError):
        service.update_status(
            name="experiment-1",
            status="invalid",
        )


def test_empty_result_key():
    service = ExperimentService()

    service.create("experiment-1")

    with pytest.raises(ValueError):
        service.add_result(
            name="experiment-1",
            key="",
            value=100.0,
        )