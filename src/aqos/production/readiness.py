"""
AQOS production readiness checks.

This module provides dependency-free readiness checks for configuration,
dependencies, services, artifacts, security, observability, and test coverage.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import Enum
from typing import Any, Callable

from aqos.production.base import (
    ProductionCheckResult,
    ProductionGateResult,
    ProductionSeverity,
    ProductionStatus,
    aggregate_production_status,
    build_production_check_result,
    build_production_gate_result,
    normalize_production_status,
    safe_production_check,
    validate_details,
    validate_non_empty_string,
    validate_percentage,
    validate_string,
)


class ReadinessCategory(str, Enum):
    """Supported production readiness categories."""

    CONFIGURATION = "configuration"
    DEPENDENCIES = "dependencies"
    DATA = "data"
    MODELS = "models"
    SECURITY = "security"
    OBSERVABILITY = "observability"
    SERVICES = "services"


@dataclass(frozen=True)
class ReadinessRequirement:
    """Single production readiness requirement."""

    name: str
    category: ReadinessCategory | str
    required: bool = True
    description: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        validate_non_empty_string(self.name, "Requirement name")
        normalize_readiness_category(self.category)

        if not isinstance(self.required, bool):
            raise ValueError("Required must be a boolean.")

        validate_string(self.description, "Description")
        validate_details(self.metadata)

    def to_dict(self) -> dict[str, Any]:
        """Convert readiness requirement into dictionary."""
        return {
            "name": self.name.strip(),
            "category": normalize_readiness_category(self.category).value,
            "required": self.required,
            "description": self.description.strip(),
            "metadata": dict(self.metadata),
        }


@dataclass(frozen=True)
class ReadinessReport:
    """Aggregated production readiness report."""

    environment: str
    status: ProductionStatus | str
    checks: list[ProductionCheckResult] = field(default_factory=list)
    requirements: list[ReadinessRequirement] = field(default_factory=list)
    generated_at: str = field(default_factory=lambda: datetime.now(UTC).isoformat())
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        validate_non_empty_string(self.environment, "Environment")
        normalize_production_status(self.status)
        validate_readiness_checks(self.checks)
        validate_readiness_requirements(self.requirements)
        validate_non_empty_string(self.generated_at, "Generated at")
        validate_details(self.metadata)

    @property
    def ready(self) -> bool:
        """Return whether report is production ready."""
        return normalize_production_status(self.status) == ProductionStatus.READY

    @property
    def blocked(self) -> bool:
        """Return whether report is blocked."""
        return normalize_production_status(self.status) == ProductionStatus.BLOCKED

    @property
    def warning(self) -> bool:
        """Return whether report has warnings."""
        return normalize_production_status(self.status) == ProductionStatus.WARNING

    def to_gate_result(self) -> ProductionGateResult:
        """Convert readiness report into production gate result."""
        return build_production_gate_result(
            gate_name="production-readiness",
            status=self.status,
            checks=self.checks,
            message="Production readiness passed."
            if self.ready
            else "Production readiness has issues.",
            metadata={
                "environment": self.environment.strip(),
                "requirements": [
                    requirement.to_dict()
                    for requirement in self.requirements
                ],
                **self.metadata,
            },
            timestamp=self.generated_at,
        )

    def to_dict(self) -> dict[str, Any]:
        """Convert readiness report into dictionary."""
        return {
            "environment": self.environment.strip(),
            "status": normalize_production_status(self.status).value,
            "ready": self.ready,
            "blocked": self.blocked,
            "warning": self.warning,
            "checks": [
                check.to_dict()
                for check in self.checks
            ],
            "requirements": [
                requirement.to_dict()
                for requirement in self.requirements
            ],
            "generated_at": self.generated_at.strip(),
            "metadata": dict(self.metadata),
        }


def normalize_readiness_category(
    category: ReadinessCategory | str,
) -> ReadinessCategory:
    """Normalize readiness category."""
    if isinstance(category, ReadinessCategory):
        return category

    normalized = validate_non_empty_string(category, "Readiness category").lower()

    try:
        return ReadinessCategory(normalized)
    except ValueError as exc:
        valid = ", ".join(item.value for item in ReadinessCategory)
        raise ValueError(
            f"Invalid readiness category '{category}'. Valid categories: {valid}.",
        ) from exc


def validate_string_list(values: list[str], field_name: str) -> list[str]:
    """Validate a non-empty string list."""
    if not isinstance(values, list):
        raise ValueError(f"{field_name} must be a list.")

    for value in values:
        validate_non_empty_string(value, field_name)

    return values


def validate_readiness_checks(
    checks: list[ProductionCheckResult],
) -> list[ProductionCheckResult]:
    """Validate readiness check list."""
    if not isinstance(checks, list):
        raise ValueError("Checks must be a list.")

    for check in checks:
        if not isinstance(check, ProductionCheckResult):
            raise ValueError("Checks must contain ProductionCheckResult objects.")

    return checks


def validate_readiness_requirements(
    requirements: list[ReadinessRequirement],
) -> list[ReadinessRequirement]:
    """Validate readiness requirements."""
    if not isinstance(requirements, list):
        raise ValueError("Requirements must be a list.")

    for requirement in requirements:
        if not isinstance(requirement, ReadinessRequirement):
            raise ValueError("Requirements must contain ReadinessRequirement objects.")

    return requirements


def build_readiness_requirement(
    *,
    name: str,
    category: ReadinessCategory | str,
    required: bool = True,
    description: str = "",
    metadata: dict[str, Any] | None = None,
) -> ReadinessRequirement:
    """Build readiness requirement."""
    return ReadinessRequirement(
        name=name,
        category=category,
        required=required,
        description=description,
        metadata=metadata or {},
    )


def build_readiness_report(
    *,
    environment: str,
    checks: list[ProductionCheckResult] | None = None,
    requirements: list[ReadinessRequirement] | None = None,
    status: ProductionStatus | str | None = None,
    generated_at: str | None = None,
    metadata: dict[str, Any] | None = None,
) -> ReadinessReport:
    """Build readiness report."""
    normalized_checks = checks or []
    resolved_status = status or aggregate_production_status(normalized_checks)

    report_kwargs: dict[str, Any] = {
        "environment": environment,
        "status": resolved_status,
        "checks": normalized_checks,
        "requirements": requirements or [],
        "metadata": metadata or {},
    }

    if generated_at is not None:
        report_kwargs["generated_at"] = generated_at

    return ReadinessReport(**report_kwargs)


def check_required_settings(
    settings: dict[str, Any],
    required_keys: list[str],
    *,
    name: str = "required-settings",
) -> ProductionCheckResult:
    """Check required runtime settings exist and are non-empty."""
    validate_details(settings)
    validate_string_list(required_keys, "Required keys")
    validate_non_empty_string(name, "Check name")

    missing = [
        key
        for key in required_keys
        if key not in settings or settings[key] in (None, "")
    ]

    if missing:
        return build_production_check_result(
            name=name,
            status=ProductionStatus.BLOCKED,
            severity=ProductionSeverity.CRITICAL,
            passed=False,
            message="Required settings are missing.",
            details={
                "required_keys": list(required_keys),
                "missing": missing,
            },
        )

    return build_production_check_result(
        name=name,
        status=ProductionStatus.READY,
        severity=ProductionSeverity.INFO,
        passed=True,
        message="Required settings are present.",
        details={
            "required_keys": list(required_keys),
        },
    )


def check_dependency_status(
    dependencies: dict[str, bool],
    *,
    name: str = "dependencies",
) -> ProductionCheckResult:
    """Check dependency availability."""
    validate_details(dependencies)
    validate_non_empty_string(name, "Check name")

    unavailable = [
        dependency_name
        for dependency_name, available in dependencies.items()
        if available is not True
    ]

    if unavailable:
        return build_production_check_result(
            name=name,
            status=ProductionStatus.BLOCKED,
            severity=ProductionSeverity.ERROR,
            passed=False,
            message="One or more dependencies are unavailable.",
            details={
                "dependencies": dict(dependencies),
                "unavailable": unavailable,
            },
        )

    return build_production_check_result(
        name=name,
        status=ProductionStatus.READY,
        severity=ProductionSeverity.INFO,
        passed=True,
        message="All dependencies are available.",
        details={
            "dependencies": dict(dependencies),
        },
    )


def check_service_health(
    services: dict[str, ProductionStatus | str | bool],
    *,
    name: str = "service-health",
) -> ProductionCheckResult:
    """Check service health statuses."""
    validate_details(services)
    validate_non_empty_string(name, "Check name")

    blocked: list[str] = []
    warnings: list[str] = []

    for service_name, service_status in services.items():
        validate_non_empty_string(service_name, "Service name")

        if isinstance(service_status, bool):
            if not service_status:
                blocked.append(service_name)
            continue

        normalized = normalize_production_status(service_status)

        if normalized == ProductionStatus.BLOCKED:
            blocked.append(service_name)
        elif normalized == ProductionStatus.WARNING:
            warnings.append(service_name)

    if blocked:
        return build_production_check_result(
            name=name,
            status=ProductionStatus.BLOCKED,
            severity=ProductionSeverity.ERROR,
            passed=False,
            message="One or more services are blocked.",
            details={
                "services": dict(services),
                "blocked": blocked,
                "warnings": warnings,
            },
        )

    if warnings:
        return build_production_check_result(
            name=name,
            status=ProductionStatus.WARNING,
            severity=ProductionSeverity.WARNING,
            passed=True,
            message="One or more services have warnings.",
            details={
                "services": dict(services),
                "warnings": warnings,
            },
        )

    return build_production_check_result(
        name=name,
        status=ProductionStatus.READY,
        severity=ProductionSeverity.INFO,
        passed=True,
        message="All services are healthy.",
        details={
            "services": dict(services),
        },
    )


def check_artifact_availability(
    artifacts: dict[str, bool],
    *,
    name: str = "artifact-availability",
) -> ProductionCheckResult:
    """Check required artifacts are available."""
    validate_details(artifacts)
    validate_non_empty_string(name, "Check name")

    missing = [
        artifact_name
        for artifact_name, available in artifacts.items()
        if available is not True
    ]

    if missing:
        return build_production_check_result(
            name=name,
            status=ProductionStatus.BLOCKED,
            severity=ProductionSeverity.ERROR,
            passed=False,
            message="Required artifacts are missing.",
            details={
                "artifacts": dict(artifacts),
                "missing": missing,
            },
        )

    return build_production_check_result(
        name=name,
        status=ProductionStatus.READY,
        severity=ProductionSeverity.INFO,
        passed=True,
        message="All required artifacts are available.",
        details={
            "artifacts": dict(artifacts),
        },
    )


def check_minimum_test_coverage(
    coverage_percent: float | int,
    *,
    minimum_percent: float | int = 80.0,
    name: str = "test-coverage",
) -> ProductionCheckResult:
    """Check minimum test coverage."""
    coverage = validate_percentage(coverage_percent, "Coverage percent")
    minimum = validate_percentage(minimum_percent, "Minimum percent")
    validate_non_empty_string(name, "Check name")

    if coverage < minimum:
        return build_production_check_result(
            name=name,
            status=ProductionStatus.BLOCKED,
            severity=ProductionSeverity.ERROR,
            passed=False,
            message="Test coverage is below production threshold.",
            details={
                "coverage_percent": coverage,
                "minimum_percent": minimum,
            },
        )

    return build_production_check_result(
        name=name,
        status=ProductionStatus.READY,
        severity=ProductionSeverity.INFO,
        passed=True,
        message="Test coverage meets production threshold.",
        details={
            "coverage_percent": coverage,
            "minimum_percent": minimum,
        },
    )


def run_readiness_checks(
    checks: list[Callable[[], ProductionCheckResult]],
    *,
    environment: str = "production",
    requirements: list[ReadinessRequirement] | None = None,
    metadata: dict[str, Any] | None = None,
) -> ReadinessReport:
    """Run production readiness checks safely."""
    if not isinstance(checks, list):
        raise ValueError("Checks must be a list.")

    validate_non_empty_string(environment, "Environment")

    if requirements is not None:
        validate_readiness_requirements(requirements)

    if metadata is not None:
        validate_details(metadata)

    results: list[ProductionCheckResult] = []

    for index, check in enumerate(checks):
        if not callable(check):
            raise ValueError("Checks must contain callables.")

        results.append(
            safe_production_check(
                check,
                name=f"readiness-check-{index + 1}",
            ),
        )

    return build_readiness_report(
        environment=environment,
        checks=results,
        requirements=requirements or [],
        metadata=metadata or {},
    )


def build_default_readiness_requirements() -> list[ReadinessRequirement]:
    """Build default AQOS production readiness requirements."""
    return [
        build_readiness_requirement(
            name="runtime-configuration",
            category=ReadinessCategory.CONFIGURATION,
            description="Required runtime configuration must be present.",
        ),
        build_readiness_requirement(
            name="external-dependencies",
            category=ReadinessCategory.DEPENDENCIES,
            description="Required external dependencies must be available.",
        ),
        build_readiness_requirement(
            name="model-artifacts",
            category=ReadinessCategory.MODELS,
            description="Required model artifacts must be available.",
        ),
        build_readiness_requirement(
            name="security-controls",
            category=ReadinessCategory.SECURITY,
            description="Security controls must be enabled.",
        ),
        build_readiness_requirement(
            name="observability-controls",
            category=ReadinessCategory.OBSERVABILITY,
            description="Logging, metrics, and tracing must be enabled.",
        ),
    ]