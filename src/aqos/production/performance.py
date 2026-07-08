"""
AQOS production performance budget validators.

This module provides dependency-free performance budget primitives for latency,
memory, CPU, error-rate, and throughput release-readiness checks.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import Enum
from typing import Any

from aqos.production.base import (
    ProductionCheckResult,
    ProductionGateResult,
    ProductionSeverity,
    ProductionStatus,
    aggregate_production_status,
    build_production_check_result,
    build_production_gate_result,
    normalize_production_severity,
    normalize_production_status,
    validate_details,
    validate_non_empty_string,
    validate_non_negative_float,
    validate_percentage,
    validate_string,
)


class PerformanceMetricType(str, Enum):
    """Supported performance metric types."""

    LATENCY_MS = "latency_ms"
    MEMORY_MB = "memory_mb"
    CPU_PERCENT = "cpu_percent"
    ERROR_RATE_PERCENT = "error_rate_percent"
    THROUGHPUT_RPS = "throughput_rps"


class PerformanceBudgetDirection(str, Enum):
    """Supported performance budget directions."""

    MAX = "max"
    MIN = "min"


@dataclass(frozen=True)
class PerformanceBudget:
    """Single production performance budget."""

    name: str
    metric_type: PerformanceMetricType | str
    threshold: float
    direction: PerformanceBudgetDirection | str = PerformanceBudgetDirection.MAX
    severity_on_fail: ProductionSeverity | str = ProductionSeverity.ERROR
    description: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        validate_non_empty_string(self.name, "Budget name")
        normalize_performance_metric_type(self.metric_type)
        validate_performance_value(
            self.threshold,
            normalize_performance_metric_type(self.metric_type),
            "Threshold",
        )
        normalize_performance_budget_direction(self.direction)
        normalize_production_severity(self.severity_on_fail)
        validate_string(self.description, "Description")
        validate_details(self.metadata)

    @property
    def unit(self) -> str:
        """Return metric unit."""
        return performance_metric_unit(self.metric_type)

    def to_dict(self) -> dict[str, Any]:
        """Convert budget into dictionary."""
        return {
            "name": self.name.strip(),
            "metric_type": normalize_performance_metric_type(self.metric_type).value,
            "threshold": float(self.threshold),
            "direction": normalize_performance_budget_direction(self.direction).value,
            "unit": self.unit,
            "severity_on_fail": normalize_production_severity(self.severity_on_fail).value,
            "description": self.description.strip(),
            "metadata": dict(self.metadata),
        }


@dataclass(frozen=True)
class PerformanceMeasurement:
    """Single production performance measurement."""

    name: str
    metric_type: PerformanceMetricType | str
    value: float
    timestamp: str = field(default_factory=lambda: datetime.now(UTC).isoformat())
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        validate_non_empty_string(self.name, "Measurement name")
        normalize_performance_metric_type(self.metric_type)
        validate_performance_value(
            self.value,
            normalize_performance_metric_type(self.metric_type),
            "Measurement value",
        )
        validate_non_empty_string(self.timestamp, "Timestamp")
        validate_details(self.metadata)

    @property
    def unit(self) -> str:
        """Return measurement unit."""
        return performance_metric_unit(self.metric_type)

    def to_dict(self) -> dict[str, Any]:
        """Convert measurement into dictionary."""
        return {
            "name": self.name.strip(),
            "metric_type": normalize_performance_metric_type(self.metric_type).value,
            "value": float(self.value),
            "unit": self.unit,
            "timestamp": self.timestamp.strip(),
            "metadata": dict(self.metadata),
        }


@dataclass(frozen=True)
class PerformanceBudgetResult:
    """Result of evaluating one performance budget."""

    budget: PerformanceBudget
    measurement: PerformanceMeasurement
    passed: bool
    status: ProductionStatus | str
    message: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not isinstance(self.budget, PerformanceBudget):
            raise ValueError("Budget must be a PerformanceBudget.")

        if not isinstance(self.measurement, PerformanceMeasurement):
            raise ValueError("Measurement must be a PerformanceMeasurement.")

        if not isinstance(self.passed, bool):
            raise ValueError("Passed must be a boolean.")

        normalize_production_status(self.status)
        validate_string(self.message, "Message")
        validate_details(self.metadata)

        if normalize_performance_metric_type(self.budget.metric_type) != normalize_performance_metric_type(
            self.measurement.metric_type,
        ):
            raise ValueError("Budget and measurement metric types must match.")

    @property
    def failed(self) -> bool:
        """Return whether budget failed."""
        return not self.passed

    def to_check_result(self) -> ProductionCheckResult:
        """Convert performance budget result into production check result."""
        severity = ProductionSeverity.INFO if self.passed else self.budget.severity_on_fail

        return build_production_check_result(
            name=self.budget.name,
            status=self.status,
            severity=severity,
            passed=self.passed,
            message=self.message,
            details=self.to_dict(),
        )

    def to_dict(self) -> dict[str, Any]:
        """Convert result into dictionary."""
        return {
            "budget": self.budget.to_dict(),
            "measurement": self.measurement.to_dict(),
            "passed": self.passed,
            "failed": self.failed,
            "status": normalize_production_status(self.status).value,
            "message": self.message.strip(),
            "metadata": dict(self.metadata),
        }


@dataclass(frozen=True)
class PerformanceBudgetReport:
    """Aggregated performance budget report."""

    environment: str
    results: list[PerformanceBudgetResult] = field(default_factory=list)
    generated_at: str = field(default_factory=lambda: datetime.now(UTC).isoformat())
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        validate_non_empty_string(self.environment, "Environment")
        validate_performance_budget_results(self.results)
        validate_non_empty_string(self.generated_at, "Generated at")
        validate_details(self.metadata)

    @property
    def checks(self) -> list[ProductionCheckResult]:
        """Return production checks."""
        return [
            result.to_check_result()
            for result in self.results
        ]

    @property
    def status(self) -> ProductionStatus:
        """Return aggregated production status."""
        return aggregate_production_status(self.checks)

    @property
    def passed(self) -> bool:
        """Return whether all performance budgets passed."""
        return self.status == ProductionStatus.READY

    @property
    def failed(self) -> bool:
        """Return whether performance report failed."""
        return not self.passed

    def to_gate_result(self) -> ProductionGateResult:
        """Convert performance report into production gate result."""
        return build_production_gate_result(
            gate_name="performance-budget",
            status=self.status,
            checks=self.checks,
            message="Performance budgets passed."
            if self.passed
            else "Performance budgets have issues.",
            metadata={
                "environment": self.environment.strip(),
                "results": [
                    result.to_dict()
                    for result in self.results
                ],
                **self.metadata,
            },
            timestamp=self.generated_at,
        )

    def to_dict(self) -> dict[str, Any]:
        """Convert performance report into dictionary."""
        return {
            "environment": self.environment.strip(),
            "status": self.status.value,
            "passed": self.passed,
            "failed": self.failed,
            "results": [
                result.to_dict()
                for result in self.results
            ],
            "checks": [
                check.to_dict()
                for check in self.checks
            ],
            "generated_at": self.generated_at.strip(),
            "metadata": dict(self.metadata),
        }


def normalize_performance_metric_type(
    metric_type: PerformanceMetricType | str,
) -> PerformanceMetricType:
    """Normalize performance metric type."""
    if isinstance(metric_type, PerformanceMetricType):
        return metric_type

    normalized = validate_non_empty_string(metric_type, "Performance metric type").lower()

    try:
        return PerformanceMetricType(normalized)
    except ValueError as exc:
        valid = ", ".join(item.value for item in PerformanceMetricType)
        raise ValueError(
            f"Invalid performance metric type '{metric_type}'. Valid metric types: {valid}.",
        ) from exc


def normalize_performance_budget_direction(
    direction: PerformanceBudgetDirection | str,
) -> PerformanceBudgetDirection:
    """Normalize performance budget direction."""
    if isinstance(direction, PerformanceBudgetDirection):
        return direction

    normalized = validate_non_empty_string(direction, "Performance budget direction").lower()

    try:
        return PerformanceBudgetDirection(normalized)
    except ValueError as exc:
        valid = ", ".join(item.value for item in PerformanceBudgetDirection)
        raise ValueError(
            f"Invalid performance budget direction '{direction}'. Valid directions: {valid}.",
        ) from exc


def performance_metric_unit(metric_type: PerformanceMetricType | str) -> str:
    """Return metric unit."""
    normalized = normalize_performance_metric_type(metric_type)

    units = {
        PerformanceMetricType.LATENCY_MS: "ms",
        PerformanceMetricType.MEMORY_MB: "mb",
        PerformanceMetricType.CPU_PERCENT: "percent",
        PerformanceMetricType.ERROR_RATE_PERCENT: "percent",
        PerformanceMetricType.THROUGHPUT_RPS: "rps",
    }

    return units[normalized]


def validate_performance_value(
    value: float | int,
    metric_type: PerformanceMetricType | str,
    field_name: str,
) -> float:
    """Validate performance value."""
    normalized = normalize_performance_metric_type(metric_type)

    if normalized in {
        PerformanceMetricType.CPU_PERCENT,
        PerformanceMetricType.ERROR_RATE_PERCENT,
    }:
        return validate_percentage(value, field_name)

    return validate_non_negative_float(value, field_name)


def compare_performance_budget(
    *,
    measurement_value: float | int,
    threshold: float | int,
    direction: PerformanceBudgetDirection | str,
) -> bool:
    """Compare measurement against budget."""
    measurement = validate_non_negative_float(measurement_value, "Measurement value")
    limit = validate_non_negative_float(threshold, "Threshold")
    normalized_direction = normalize_performance_budget_direction(direction)

    if normalized_direction == PerformanceBudgetDirection.MAX:
        return measurement <= limit

    if normalized_direction == PerformanceBudgetDirection.MIN:
        return measurement >= limit

    raise ValueError("Unsupported performance budget direction.")


def validate_performance_budgets(
    budgets: list[PerformanceBudget],
) -> list[PerformanceBudget]:
    """Validate performance budget list."""
    if not isinstance(budgets, list):
        raise ValueError("Budgets must be a list.")

    for budget in budgets:
        if not isinstance(budget, PerformanceBudget):
            raise ValueError("Budgets must contain PerformanceBudget objects.")

    return budgets


def validate_performance_measurements(
    measurements: list[PerformanceMeasurement],
) -> list[PerformanceMeasurement]:
    """Validate performance measurement list."""
    if not isinstance(measurements, list):
        raise ValueError("Measurements must be a list.")

    for measurement in measurements:
        if not isinstance(measurement, PerformanceMeasurement):
            raise ValueError("Measurements must contain PerformanceMeasurement objects.")

    return measurements


def validate_performance_budget_results(
    results: list[PerformanceBudgetResult],
) -> list[PerformanceBudgetResult]:
    """Validate performance budget result list."""
    if not isinstance(results, list):
        raise ValueError("Results must be a list.")

    for result in results:
        if not isinstance(result, PerformanceBudgetResult):
            raise ValueError("Results must contain PerformanceBudgetResult objects.")

    return results


def build_performance_budget(
    *,
    name: str,
    metric_type: PerformanceMetricType | str,
    threshold: float,
    direction: PerformanceBudgetDirection | str = PerformanceBudgetDirection.MAX,
    severity_on_fail: ProductionSeverity | str = ProductionSeverity.ERROR,
    description: str = "",
    metadata: dict[str, Any] | None = None,
) -> PerformanceBudget:
    """Build performance budget."""
    return PerformanceBudget(
        name=name,
        metric_type=metric_type,
        threshold=threshold,
        direction=direction,
        severity_on_fail=severity_on_fail,
        description=description,
        metadata=metadata or {},
    )


def build_performance_measurement(
    *,
    name: str,
    metric_type: PerformanceMetricType | str,
    value: float,
    timestamp: str | None = None,
    metadata: dict[str, Any] | None = None,
) -> PerformanceMeasurement:
    """Build performance measurement."""
    measurement_kwargs: dict[str, Any] = {
        "name": name,
        "metric_type": metric_type,
        "value": value,
        "metadata": metadata or {},
    }

    if timestamp is not None:
        measurement_kwargs["timestamp"] = timestamp

    return PerformanceMeasurement(**measurement_kwargs)


def evaluate_performance_budget(
    *,
    budget: PerformanceBudget,
    measurement: PerformanceMeasurement,
    metadata: dict[str, Any] | None = None,
) -> PerformanceBudgetResult:
    """Evaluate one performance budget."""
    if not isinstance(budget, PerformanceBudget):
        raise ValueError("Budget must be a PerformanceBudget.")

    if not isinstance(measurement, PerformanceMeasurement):
        raise ValueError("Measurement must be a PerformanceMeasurement.")

    if metadata is not None:
        validate_details(metadata)

    if normalize_performance_metric_type(budget.metric_type) != normalize_performance_metric_type(
        measurement.metric_type,
    ):
        raise ValueError("Budget and measurement metric types must match.")

    passed = compare_performance_budget(
        measurement_value=measurement.value,
        threshold=budget.threshold,
        direction=budget.direction,
    )

    return PerformanceBudgetResult(
        budget=budget,
        measurement=measurement,
        passed=passed,
        status=ProductionStatus.READY if passed else ProductionStatus.BLOCKED,
        message="Performance budget passed."
        if passed
        else "Performance budget exceeded.",
        metadata=metadata or {},
    )


def evaluate_performance_budgets(
    *,
    budgets: list[PerformanceBudget],
    measurements: list[PerformanceMeasurement],
    environment: str = "production",
    metadata: dict[str, Any] | None = None,
) -> PerformanceBudgetReport:
    """Evaluate multiple performance budgets."""
    validate_performance_budgets(budgets)
    validate_performance_measurements(measurements)
    validate_non_empty_string(environment, "Environment")

    if metadata is not None:
        validate_details(metadata)

    measurement_by_metric = {
        normalize_performance_metric_type(measurement.metric_type): measurement
        for measurement in measurements
    }

    results: list[PerformanceBudgetResult] = []

    for budget in budgets:
        metric = normalize_performance_metric_type(budget.metric_type)
        measurement = measurement_by_metric.get(metric)

        if measurement is None:
            missing_measurement = build_performance_measurement(
                name=f"missing-{metric.value}",
                metric_type=metric,
                value=0,
            )
            results.append(
                PerformanceBudgetResult(
                    budget=budget,
                    measurement=missing_measurement,
                    passed=False,
                    status=ProductionStatus.BLOCKED,
                    message="Performance measurement is missing.",
                    metadata={
                        "missing_metric": metric.value,
                    },
                ),
            )
            continue

        results.append(
            evaluate_performance_budget(
                budget=budget,
                measurement=measurement,
                metadata=metadata or {},
            ),
        )

    return PerformanceBudgetReport(
        environment=environment,
        results=results,
        metadata=metadata or {},
    )


def build_default_performance_budgets() -> list[PerformanceBudget]:
    """Build default AQOS production performance budgets."""
    return [
        build_performance_budget(
            name="api-latency-p95",
            metric_type=PerformanceMetricType.LATENCY_MS,
            threshold=500,
            direction=PerformanceBudgetDirection.MAX,
            description="API p95 latency should stay below 500ms.",
        ),
        build_performance_budget(
            name="memory-usage",
            metric_type=PerformanceMetricType.MEMORY_MB,
            threshold=1024,
            direction=PerformanceBudgetDirection.MAX,
            description="Runtime memory should stay below 1024MB.",
        ),
        build_performance_budget(
            name="cpu-usage",
            metric_type=PerformanceMetricType.CPU_PERCENT,
            threshold=85,
            direction=PerformanceBudgetDirection.MAX,
            description="CPU usage should stay below 85%.",
        ),
        build_performance_budget(
            name="error-rate",
            metric_type=PerformanceMetricType.ERROR_RATE_PERCENT,
            threshold=2,
            direction=PerformanceBudgetDirection.MAX,
            description="Error rate should stay below 2%.",
        ),
        build_performance_budget(
            name="throughput",
            metric_type=PerformanceMetricType.THROUGHPUT_RPS,
            threshold=10,
            direction=PerformanceBudgetDirection.MIN,
            description="Throughput should stay above 10 requests per second.",
        ),
    ]