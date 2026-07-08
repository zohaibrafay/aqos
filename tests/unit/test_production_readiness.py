"""
Unit tests for AQOS production readiness checks.
"""

import pytest

from aqos.production import (
    ProductionCheckResult,
    ProductionSeverity,
    ProductionStatus,
    ReadinessCategory,
    ReadinessReport,
    ReadinessRequirement,
    build_default_readiness_requirements,
    build_production_check_result,
    build_readiness_report,
    build_readiness_requirement,
    check_artifact_availability,
    check_dependency_status,
    check_minimum_test_coverage,
    check_required_settings,
    check_service_health,
    normalize_readiness_category,
    run_readiness_checks,
    validate_readiness_checks,
    validate_readiness_requirements,
    validate_string_list,
)


def test_readiness_category_values():
    assert ReadinessCategory.CONFIGURATION.value == "configuration"
    assert ReadinessCategory.DEPENDENCIES.value == "dependencies"
    assert ReadinessCategory.DATA.value == "data"
    assert ReadinessCategory.MODELS.value == "models"
    assert ReadinessCategory.SECURITY.value == "security"
    assert ReadinessCategory.OBSERVABILITY.value == "observability"
    assert ReadinessCategory.SERVICES.value == "services"


def test_normalize_readiness_category_accepts_enum_and_string():
    assert normalize_readiness_category(ReadinessCategory.CONFIGURATION) == ReadinessCategory.CONFIGURATION
    assert normalize_readiness_category(" CONFIGURATION ") == ReadinessCategory.CONFIGURATION
    assert normalize_readiness_category("models") == ReadinessCategory.MODELS
    assert normalize_readiness_category("SECURITY") == ReadinessCategory.SECURITY


def test_normalize_readiness_category_rejects_invalid_value():
    with pytest.raises(ValueError):
        normalize_readiness_category("bad")

    with pytest.raises(ValueError):
        normalize_readiness_category("")


def test_validate_string_list():
    assert validate_string_list(["A", "B"], "Values") == ["A", "B"]

    with pytest.raises(ValueError):
        validate_string_list("bad", "Values")

    with pytest.raises(ValueError):
        validate_string_list([""], "Values")


def test_readiness_requirement_to_dict():
    requirement = ReadinessRequirement(
        name=" runtime-config ",
        category="CONFIGURATION",
        required=True,
        description=" Required config. ",
        metadata={
            "scope": "api",
        },
    )

    assert requirement.to_dict() == {
        "name": "runtime-config",
        "category": "configuration",
        "required": True,
        "description": "Required config.",
        "metadata": {
            "scope": "api",
        },
    }


def test_readiness_requirement_rejects_invalid_values():
    with pytest.raises(ValueError):
        ReadinessRequirement(name="", category="configuration")

    with pytest.raises(ValueError):
        ReadinessRequirement(name="config", category="bad")

    with pytest.raises(ValueError):
        ReadinessRequirement(name="config", category="configuration", required="yes")

    with pytest.raises(ValueError):
        ReadinessRequirement(name="config", category="configuration", description=123)

    with pytest.raises(ValueError):
        ReadinessRequirement(name="config", category="configuration", metadata=[])


def test_build_readiness_requirement():
    requirement = build_readiness_requirement(
        name="models",
        category="models",
        description="Models ready.",
        metadata={
            "source": "test",
        },
    )

    assert isinstance(requirement, ReadinessRequirement)
    assert requirement.metadata == {
        "source": "test",
    }


def test_validate_readiness_checks_and_requirements():
    check = build_production_check_result(
        name="check",
        status="ready",
    )
    requirement = build_readiness_requirement(
        name="config",
        category="configuration",
    )

    assert validate_readiness_checks([check]) == [check]
    assert validate_readiness_requirements([requirement]) == [requirement]

    with pytest.raises(ValueError):
        validate_readiness_checks("bad")

    with pytest.raises(ValueError):
        validate_readiness_checks(["bad"])

    with pytest.raises(ValueError):
        validate_readiness_requirements("bad")

    with pytest.raises(ValueError):
        validate_readiness_requirements(["bad"])


def test_readiness_report_to_dict_and_gate_result():
    check = build_production_check_result(
        name="readiness",
        status="ready",
        timestamp="2026-01-01T00:00:00+00:00",
    )
    requirement = build_readiness_requirement(
        name="config",
        category="configuration",
    )
    report = ReadinessReport(
        environment=" production ",
        status="READY",
        checks=[check],
        requirements=[requirement],
        generated_at="2026-01-01T00:00:00+00:00",
        metadata={
            "version": "v0.20.0-dev",
        },
    )

    assert report.ready is True
    assert report.blocked is False
    assert report.warning is False

    payload = report.to_dict()

    assert payload["environment"] == "production"
    assert payload["status"] == "ready"
    assert payload["ready"] is True
    assert len(payload["checks"]) == 1
    assert len(payload["requirements"]) == 1

    gate = report.to_gate_result()

    assert gate.gate_name == "production-readiness"
    assert gate.status == "READY"
    assert gate.passed is True


def test_readiness_report_rejects_invalid_values():
    with pytest.raises(ValueError):
        ReadinessReport(environment="", status="ready")

    with pytest.raises(ValueError):
        ReadinessReport(environment="production", status="bad")

    with pytest.raises(ValueError):
        ReadinessReport(environment="production", status="ready", checks=["bad"])

    with pytest.raises(ValueError):
        ReadinessReport(environment="production", status="ready", requirements=["bad"])

    with pytest.raises(ValueError):
        ReadinessReport(environment="production", status="ready", generated_at="")

    with pytest.raises(ValueError):
        ReadinessReport(environment="production", status="ready", metadata=[])


def test_build_readiness_report_aggregates_status():
    ready = build_production_check_result(name="ready", status="ready")
    blocked = build_production_check_result(
        name="blocked",
        status="blocked",
        passed=False,
    )

    ready_report = build_readiness_report(
        environment="production",
        checks=[ready],
        generated_at="2026-01-01T00:00:00+00:00",
    )

    blocked_report = build_readiness_report(
        environment="production",
        checks=[ready, blocked],
        generated_at="2026-01-01T00:00:00+00:00",
    )

    assert ready_report.status == ProductionStatus.READY
    assert blocked_report.status == ProductionStatus.BLOCKED


def test_check_required_settings_ready_and_blocked():
    ready = check_required_settings(
        {
            "DATABASE_URL": "postgres://example",
            "SECRET_KEY": "secret",
        },
        ["DATABASE_URL", "SECRET_KEY"],
    )

    blocked = check_required_settings(
        {
            "DATABASE_URL": "",
        },
        ["DATABASE_URL", "SECRET_KEY"],
    )

    assert ready.passed is True
    assert ready.status == ProductionStatus.READY
    assert blocked.passed is False
    assert blocked.status == ProductionStatus.BLOCKED
    assert blocked.details["missing"] == ["DATABASE_URL", "SECRET_KEY"]


def test_check_dependency_status_ready_and_blocked():
    ready = check_dependency_status(
        {
            "postgres": True,
            "redis": True,
        },
    )

    blocked = check_dependency_status(
        {
            "postgres": True,
            "redis": False,
        },
    )

    assert ready.status == ProductionStatus.READY
    assert blocked.status == ProductionStatus.BLOCKED
    assert blocked.details["unavailable"] == ["redis"]


def test_check_service_health_ready_warning_and_blocked():
    ready = check_service_health(
        {
            "api": "ready",
            "worker": True,
        },
    )

    warning = check_service_health(
        {
            "api": "ready",
            "worker": "warning",
        },
    )

    blocked = check_service_health(
        {
            "api": "ready",
            "worker": False,
        },
    )

    assert ready.status == ProductionStatus.READY
    assert warning.status == ProductionStatus.WARNING
    assert warning.severity == ProductionSeverity.WARNING
    assert blocked.status == ProductionStatus.BLOCKED
    assert blocked.details["blocked"] == ["worker"]


def test_check_artifact_availability_ready_and_blocked():
    ready = check_artifact_availability(
        {
            "model.pkl": True,
            "features.json": True,
        },
    )

    blocked = check_artifact_availability(
        {
            "model.pkl": True,
            "features.json": False,
        },
    )

    assert ready.status == ProductionStatus.READY
    assert blocked.status == ProductionStatus.BLOCKED
    assert blocked.details["missing"] == ["features.json"]


def test_check_minimum_test_coverage_ready_and_blocked():
    ready = check_minimum_test_coverage(
        90,
        minimum_percent=80,
    )

    blocked = check_minimum_test_coverage(
        70,
        minimum_percent=80,
    )

    assert ready.status == ProductionStatus.READY
    assert blocked.status == ProductionStatus.BLOCKED
    assert blocked.details == {
        "coverage_percent": 70.0,
        "minimum_percent": 80.0,
    }


def test_run_readiness_checks():
    report = run_readiness_checks(
        [
            lambda: check_required_settings({"A": "1"}, ["A"]),
            lambda: check_dependency_status({"postgres": True}),
        ],
        environment="production",
        requirements=build_default_readiness_requirements(),
        metadata={
            "source": "test",
        },
    )

    assert isinstance(report, ReadinessReport)
    assert report.ready is True
    assert len(report.checks) == 2
    assert len(report.requirements) == 5
    assert report.metadata == {
        "source": "test",
    }


def test_run_readiness_checks_catches_failed_check():
    def fail():
        raise RuntimeError("boom")

    report = run_readiness_checks(
        [fail],
        environment="production",
    )

    assert report.blocked is True
    assert report.checks[0].passed is False
    assert report.checks[0].details["error"] == "boom"


def test_run_readiness_checks_rejects_invalid_values():
    with pytest.raises(ValueError):
        run_readiness_checks("bad")

    with pytest.raises(ValueError):
        run_readiness_checks([lambda: check_dependency_status({})], environment="")

    with pytest.raises(ValueError):
        run_readiness_checks(["bad"])

    with pytest.raises(ValueError):
        run_readiness_checks([], requirements=["bad"])

    with pytest.raises(ValueError):
        run_readiness_checks([], metadata=[])


def test_build_default_readiness_requirements():
    requirements = build_default_readiness_requirements()

    assert len(requirements) == 5
    assert all(isinstance(requirement, ReadinessRequirement) for requirement in requirements)
    assert {
        requirement.category
        for requirement in requirements
    } == {
        ReadinessCategory.CONFIGURATION,
        ReadinessCategory.DEPENDENCIES,
        ReadinessCategory.MODELS,
        ReadinessCategory.SECURITY,
        ReadinessCategory.OBSERVABILITY,
    }


def test_production_readiness_exports_exist():
    import aqos.production as production

    expected_exports = [
        "ReadinessCategory",
        "ReadinessReport",
        "ReadinessRequirement",
        "build_default_readiness_requirements",
        "build_readiness_report",
        "build_readiness_requirement",
        "check_artifact_availability",
        "check_dependency_status",
        "check_minimum_test_coverage",
        "check_required_settings",
        "check_service_health",
        "normalize_readiness_category",
        "run_readiness_checks",
        "validate_readiness_checks",
        "validate_readiness_requirements",
        "validate_string_list",
    ]

    for export_name in expected_exports:
        assert hasattr(production, export_name), export_name