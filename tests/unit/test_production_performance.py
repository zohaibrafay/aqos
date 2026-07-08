"""
Unit tests for AQOS production performance budget validators.
"""

import pytest

from aqos.production import (
    PerformanceBudget,
    PerformanceBudgetDirection,
    PerformanceBudgetReport,
    PerformanceBudgetResult,
    PerformanceMeasurement,
    PerformanceMetricType,
    ProductionStatus,
    build_default_performance_budgets,
    build_performance_budget,
    build_performance_measurement,
    compare_performance_budget,
    evaluate_performance_budget,
    evaluate_performance_budgets,
    normalize_performance_budget_direction,
    normalize_performance_metric_type,
    performance_metric_unit,
    validate_performance_budget_results,
    validate_performance_budgets,
    validate_performance_measurements,
    validate_performance_value,
)


def test_performance_metric_type_values():
    assert PerformanceMetricType.LATENCY_MS.value == "latency_ms"
    assert PerformanceMetricType.MEMORY_MB.value == "memory_mb"
    assert PerformanceMetricType.CPU_PERCENT.value == "cpu_percent"
    assert PerformanceMetricType.ERROR_RATE_PERCENT.value == "error_rate_percent"
    assert PerformanceMetricType.THROUGHPUT_RPS.value == "throughput_rps"


def test_performance_budget_direction_values():
    assert PerformanceBudgetDirection.MAX.value == "max"
    assert PerformanceBudgetDirection.MIN.value == "min"


def test_normalize_performance_metric_type_accepts_enum_and_string():
    assert normalize_performance_metric_type(PerformanceMetricType.LATENCY_MS) == PerformanceMetricType.LATENCY_MS
    assert normalize_performance_metric_type(" LATENCY_MS ") == PerformanceMetricType.LATENCY_MS
    assert normalize_performance_metric_type("memory_mb") == PerformanceMetricType.MEMORY_MB
    assert normalize_performance_metric_type("CPU_PERCENT") == PerformanceMetricType.CPU_PERCENT


def test_normalize_performance_metric_type_rejects_invalid_value():
    with pytest.raises(ValueError):
        normalize_performance_metric_type("bad")

    with pytest.raises(ValueError):
        normalize_performance_metric_type("")


def test_normalize_performance_budget_direction_accepts_enum_and_string():
    assert normalize_performance_budget_direction(PerformanceBudgetDirection.MAX) == PerformanceBudgetDirection.MAX
    assert normalize_performance_budget_direction(" MAX ") == PerformanceBudgetDirection.MAX
    assert normalize_performance_budget_direction("min") == PerformanceBudgetDirection.MIN


def test_normalize_performance_budget_direction_rejects_invalid_value():
    with pytest.raises(ValueError):
        normalize_performance_budget_direction("bad")

    with pytest.raises(ValueError):
        normalize_performance_budget_direction("")


def test_performance_metric_unit():
    assert performance_metric_unit("latency_ms") == "ms"
    assert performance_metric_unit("memory_mb") == "mb"
    assert performance_metric_unit("cpu_percent") == "percent"
    assert performance_metric_unit("error_rate_percent") == "percent"
    assert performance_metric_unit("throughput_rps") == "rps"


def test_validate_performance_value():
    assert validate_performance_value(10, "latency_ms", "Value") == 10.0
    assert validate_performance_value(50, "cpu_percent", "Value") == 50.0

    with pytest.raises(ValueError):
        validate_performance_value(-1, "latency_ms", "Value")

    with pytest.raises(ValueError):
        validate_performance_value(101, "cpu_percent", "Value")


def test_compare_performance_budget():
    assert compare_performance_budget(
        measurement_value=100,
        threshold=200,
        direction="max",
    ) is True

    assert compare_performance_budget(
        measurement_value=300,
        threshold=200,
        direction="max",
    ) is False

    assert compare_performance_budget(
        measurement_value=20,
        threshold=10,
        direction="min",
    ) is True

    assert compare_performance_budget(
        measurement_value=5,
        threshold=10,
        direction="min",
    ) is False


def test_performance_budget_to_dict():
    budget = PerformanceBudget(
        name=" api-latency ",
        metric_type="LATENCY_MS",
        threshold=500,
        direction="MAX",
        severity_on_fail="ERROR",
        description=" API latency budget. ",
        metadata={
            "scope": "api",
        },
    )

    assert budget.unit == "ms"

    assert budget.to_dict() == {
        "name": "api-latency",
        "metric_type": "latency_ms",
        "threshold": 500.0,
        "direction": "max",
        "unit": "ms",
        "severity_on_fail": "error",
        "description": "API latency budget.",
        "metadata": {
            "scope": "api",
        },
    }


def test_performance_budget_rejects_invalid_values():
    with pytest.raises(ValueError):
        PerformanceBudget(name="", metric_type="latency_ms", threshold=100)

    with pytest.raises(ValueError):
        PerformanceBudget(name="budget", metric_type="bad", threshold=100)

    with pytest.raises(ValueError):
        PerformanceBudget(name="budget", metric_type="latency_ms", threshold=-1)

    with pytest.raises(ValueError):
        PerformanceBudget(name="budget", metric_type="latency_ms", threshold=100, direction="bad")

    with pytest.raises(ValueError):
        PerformanceBudget(name="budget", metric_type="latency_ms", threshold=100, severity_on_fail="bad")

    with pytest.raises(ValueError):
        PerformanceBudget(name="budget", metric_type="latency_ms", threshold=100, description=123)

    with pytest.raises(ValueError):
        PerformanceBudget(name="budget", metric_type="latency_ms", threshold=100, metadata=[])


def test_build_performance_budget():
    budget = build_performance_budget(
        name="memory",
        metric_type="memory_mb",
        threshold=1024,
        metadata={
            "source": "test",
        },
    )

    assert isinstance(budget, PerformanceBudget)
    assert budget.metadata == {
        "source": "test",
    }


def test_performance_measurement_to_dict():
    measurement = PerformanceMeasurement(
        name=" latency ",
        metric_type="LATENCY_MS",
        value=250,
        timestamp="2026-01-01T00:00:00+00:00",
        metadata={
            "p": "p95",
        },
    )

    assert measurement.unit == "ms"

    assert measurement.to_dict() == {
        "name": "latency",
        "metric_type": "latency_ms",
        "value": 250.0,
        "unit": "ms",
        "timestamp": "2026-01-01T00:00:00+00:00",
        "metadata": {
            "p": "p95",
        },
    }


def test_performance_measurement_rejects_invalid_values():
    with pytest.raises(ValueError):
        PerformanceMeasurement(name="", metric_type="latency_ms", value=100)

    with pytest.raises(ValueError):
        PerformanceMeasurement(name="metric", metric_type="bad", value=100)

    with pytest.raises(ValueError):
        PerformanceMeasurement(name="metric", metric_type="latency_ms", value=-1)

    with pytest.raises(ValueError):
        PerformanceMeasurement(name="metric", metric_type="latency_ms", value=100, timestamp="")

    with pytest.raises(ValueError):
        PerformanceMeasurement(name="metric", metric_type="latency_ms", value=100, metadata=[])


def test_build_performance_measurement():
    measurement = build_performance_measurement(
        name="latency",
        metric_type="latency_ms",
        value=100,
        timestamp="2026-01-01T00:00:00+00:00",
    )

    assert isinstance(measurement, PerformanceMeasurement)
    assert measurement.value == 100


def test_validate_performance_lists():
    budget = build_performance_budget(
        name="latency",
        metric_type="latency_ms",
        threshold=500,
    )
    measurement = build_performance_measurement(
        name="latency",
        metric_type="latency_ms",
        value=100,
    )

    result = evaluate_performance_budget(
        budget=budget,
        measurement=measurement,
    )

    assert validate_performance_budgets([budget]) == [budget]
    assert validate_performance_measurements([measurement]) == [measurement]
    assert validate_performance_budget_results([result]) == [result]

    with pytest.raises(ValueError):
        validate_performance_budgets("bad")

    with pytest.raises(ValueError):
        validate_performance_budgets(["bad"])

    with pytest.raises(ValueError):
        validate_performance_measurements("bad")

    with pytest.raises(ValueError):
        validate_performance_measurements(["bad"])

    with pytest.raises(ValueError):
        validate_performance_budget_results("bad")

    with pytest.raises(ValueError):
        validate_performance_budget_results(["bad"])


def test_evaluate_performance_budget_pass_and_fail():
    budget = build_performance_budget(
        name="latency",
        metric_type="latency_ms",
        threshold=500,
        direction="max",
    )

    passed = evaluate_performance_budget(
        budget=budget,
        measurement=build_performance_measurement(
            name="latency",
            metric_type="latency_ms",
            value=250,
        ),
    )

    failed = evaluate_performance_budget(
        budget=budget,
        measurement=build_performance_measurement(
            name="latency",
            metric_type="latency_ms",
            value=700,
        ),
    )

    assert isinstance(passed, PerformanceBudgetResult)
    assert passed.passed is True
    assert passed.status == ProductionStatus.READY
    assert passed.to_check_result().passed is True

    assert failed.failed is True
    assert failed.status == ProductionStatus.BLOCKED
    assert failed.to_check_result().passed is False


def test_evaluate_performance_budget_rejects_invalid_values():
    budget = build_performance_budget(
        name="latency",
        metric_type="latency_ms",
        threshold=500,
    )
    measurement = build_performance_measurement(
        name="memory",
        metric_type="memory_mb",
        value=256,
    )

    with pytest.raises(ValueError):
        evaluate_performance_budget(
            budget="bad",
            measurement=measurement,
        )

    with pytest.raises(ValueError):
        evaluate_performance_budget(
            budget=budget,
            measurement="bad",
        )

    with pytest.raises(ValueError):
        evaluate_performance_budget(
            budget=budget,
            measurement=measurement,
        )

    with pytest.raises(ValueError):
        evaluate_performance_budget(
            budget=budget,
            measurement=build_performance_measurement(
                name="latency",
                metric_type="latency_ms",
                value=100,
            ),
            metadata=[],
        )


def test_performance_budget_result_rejects_metric_mismatch():
    budget = build_performance_budget(
        name="latency",
        metric_type="latency_ms",
        threshold=500,
    )
    measurement = build_performance_measurement(
        name="memory",
        metric_type="memory_mb",
        value=256,
    )

    with pytest.raises(ValueError):
        PerformanceBudgetResult(
            budget=budget,
            measurement=measurement,
            passed=True,
            status="ready",
        )


def test_evaluate_performance_budgets_report_ready_blocked_and_missing():
    budgets = [
        build_performance_budget(
            name="latency",
            metric_type="latency_ms",
            threshold=500,
        ),
        build_performance_budget(
            name="throughput",
            metric_type="throughput_rps",
            threshold=10,
            direction="min",
        ),
    ]
    measurements = [
        build_performance_measurement(
            name="latency",
            metric_type="latency_ms",
            value=250,
        ),
        build_performance_measurement(
            name="throughput",
            metric_type="throughput_rps",
            value=20,
        ),
    ]

    report = evaluate_performance_budgets(
        budgets=budgets,
        measurements=measurements,
        environment="production",
        metadata={
            "source": "test",
        },
    )

    assert isinstance(report, PerformanceBudgetReport)
    assert report.passed is True
    assert report.status == ProductionStatus.READY
    assert report.to_gate_result().passed is True
    assert report.metadata == {
        "source": "test",
    }

    missing_report = evaluate_performance_budgets(
        budgets=budgets,
        measurements=[
            measurements[0],
        ],
        environment="production",
    )

    assert missing_report.failed is True
    assert missing_report.status == ProductionStatus.BLOCKED
    assert missing_report.results[1].message == "Performance measurement is missing."


def test_performance_budget_report_to_dict():
    budget = build_performance_budget(
        name="latency",
        metric_type="latency_ms",
        threshold=500,
    )
    measurement = build_performance_measurement(
        name="latency",
        metric_type="latency_ms",
        value=250,
        timestamp="2026-01-01T00:00:00+00:00",
    )
    result = evaluate_performance_budget(
        budget=budget,
        measurement=measurement,
    )

    report = PerformanceBudgetReport(
        environment=" production ",
        results=[result],
        generated_at="2026-01-01T00:00:00+00:00",
        metadata={
            "version": "v0.20.0-dev",
        },
    )

    payload = report.to_dict()

    assert payload["environment"] == "production"
    assert payload["status"] == "ready"
    assert payload["passed"] is True
    assert len(payload["results"]) == 1
    assert len(payload["checks"]) == 1
    assert payload["metadata"] == {
        "version": "v0.20.0-dev",
    }


def test_performance_budget_report_rejects_invalid_values():
    with pytest.raises(ValueError):
        PerformanceBudgetReport(environment="", results=[])

    with pytest.raises(ValueError):
        PerformanceBudgetReport(environment="production", results=["bad"])

    with pytest.raises(ValueError):
        PerformanceBudgetReport(environment="production", generated_at="")

    with pytest.raises(ValueError):
        PerformanceBudgetReport(environment="production", metadata=[])


def test_build_default_performance_budgets():
    budgets = build_default_performance_budgets()

    assert len(budgets) == 5
    assert all(isinstance(budget, PerformanceBudget) for budget in budgets)
    assert {
        budget.metric_type
        for budget in budgets
    } == {
        PerformanceMetricType.LATENCY_MS,
        PerformanceMetricType.MEMORY_MB,
        PerformanceMetricType.CPU_PERCENT,
        PerformanceMetricType.ERROR_RATE_PERCENT,
        PerformanceMetricType.THROUGHPUT_RPS,
    }


def test_production_performance_exports_exist():
    import aqos.production as production

    expected_exports = [
        "PerformanceBudget",
        "PerformanceBudgetDirection",
        "PerformanceBudgetReport",
        "PerformanceBudgetResult",
        "PerformanceMeasurement",
        "PerformanceMetricType",
        "build_default_performance_budgets",
        "build_performance_budget",
        "build_performance_measurement",
        "compare_performance_budget",
        "evaluate_performance_budget",
        "evaluate_performance_budgets",
        "normalize_performance_budget_direction",
        "normalize_performance_metric_type",
        "performance_metric_unit",
        "validate_performance_budget_results",
        "validate_performance_budgets",
        "validate_performance_measurements",
        "validate_performance_value",
    ]

    for export_name in expected_exports:
        assert hasattr(production, export_name), export_name