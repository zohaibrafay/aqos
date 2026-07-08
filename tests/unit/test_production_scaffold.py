"""
Unit tests for AQOS production scaffold.
"""

import pytest

from aqos.production import (
    ProductionCheckResult,
    ProductionGateResult,
    ProductionSeverity,
    ProductionStatus,
    aggregate_production_status,
    build_production_check_result,
    build_production_gate_result,
    normalize_production_severity,
    normalize_production_status,
    safe_production_check,
    validate_boolean,
    validate_check_results,
    validate_details,
    validate_non_empty_string,
    validate_non_negative_float,
    validate_non_negative_integer,
    validate_percentage,
    validate_positive_integer,
    validate_string,
)


def test_production_status_values():
    assert ProductionStatus.READY.value == "ready"
    assert ProductionStatus.WARNING.value == "warning"
    assert ProductionStatus.BLOCKED.value == "blocked"
    assert ProductionStatus.UNKNOWN.value == "unknown"


def test_production_severity_values():
    assert ProductionSeverity.INFO.value == "info"
    assert ProductionSeverity.WARNING.value == "warning"
    assert ProductionSeverity.ERROR.value == "error"
    assert ProductionSeverity.CRITICAL.value == "critical"


def test_normalize_production_status_accepts_enum_and_string():
    assert normalize_production_status(ProductionStatus.READY) == ProductionStatus.READY
    assert normalize_production_status(" READY ") == ProductionStatus.READY
    assert normalize_production_status("warning") == ProductionStatus.WARNING
    assert normalize_production_status("BLOCKED") == ProductionStatus.BLOCKED


def test_normalize_production_status_rejects_invalid_value():
    with pytest.raises(ValueError):
        normalize_production_status("bad")

    with pytest.raises(ValueError):
        normalize_production_status("")


def test_normalize_production_severity_accepts_enum_and_string():
    assert normalize_production_severity(ProductionSeverity.INFO) == ProductionSeverity.INFO
    assert normalize_production_severity(" INFO ") == ProductionSeverity.INFO
    assert normalize_production_severity("warning") == ProductionSeverity.WARNING
    assert normalize_production_severity("ERROR") == ProductionSeverity.ERROR


def test_normalize_production_severity_rejects_invalid_value():
    with pytest.raises(ValueError):
        normalize_production_severity("bad")

    with pytest.raises(ValueError):
        normalize_production_severity("")


def test_validate_string_accepts_string():
    assert validate_string("", "Field") == ""
    assert validate_string("value", "Field") == "value"


def test_validate_string_rejects_non_string():
    with pytest.raises(ValueError):
        validate_string(123, "Field")


def test_validate_non_empty_string_accepts_trimmed_value():
    assert validate_non_empty_string(" value ", "Field") == "value"


def test_validate_non_empty_string_rejects_empty_value():
    with pytest.raises(ValueError):
        validate_non_empty_string("", "Field")

    with pytest.raises(ValueError):
        validate_non_empty_string("   ", "Field")


def test_validate_boolean():
    assert validate_boolean(True, "Enabled") is True
    assert validate_boolean(False, "Enabled") is False

    with pytest.raises(ValueError):
        validate_boolean("yes", "Enabled")


def test_validate_details_accepts_dictionary():
    details = {
        "env": "production",
    }

    assert validate_details(details) == details


def test_validate_details_rejects_non_dictionary():
    with pytest.raises(ValueError):
        validate_details([])


def test_validate_positive_integer():
    assert validate_positive_integer(1, "Value") == 1

    with pytest.raises(ValueError):
        validate_positive_integer(0, "Value")

    with pytest.raises(ValueError):
        validate_positive_integer(True, "Value")

    with pytest.raises(ValueError):
        validate_positive_integer("1", "Value")


def test_validate_non_negative_integer():
    assert validate_non_negative_integer(0, "Value") == 0
    assert validate_non_negative_integer(1, "Value") == 1

    with pytest.raises(ValueError):
        validate_non_negative_integer(-1, "Value")

    with pytest.raises(ValueError):
        validate_non_negative_integer(True, "Value")

    with pytest.raises(ValueError):
        validate_non_negative_integer("1", "Value")


def test_validate_non_negative_float():
    assert validate_non_negative_float(0, "Value") == 0.0
    assert validate_non_negative_float(1.5, "Value") == 1.5

    with pytest.raises(ValueError):
        validate_non_negative_float(-0.1, "Value")

    with pytest.raises(ValueError):
        validate_non_negative_float(True, "Value")

    with pytest.raises(ValueError):
        validate_non_negative_float("1", "Value")


def test_validate_percentage():
    assert validate_percentage(0, "Coverage") == 0.0
    assert validate_percentage(99.5, "Coverage") == 99.5
    assert validate_percentage(100, "Coverage") == 100.0

    with pytest.raises(ValueError):
        validate_percentage(-1, "Coverage")

    with pytest.raises(ValueError):
        validate_percentage(101, "Coverage")


def test_production_check_result_to_dict():
    result = ProductionCheckResult(
        name=" readiness ",
        status="READY",
        severity="INFO",
        passed=True,
        message=" Ready. ",
        details={
            "checks": 10,
        },
        timestamp="2026-01-01T00:00:00+00:00",
    )

    assert result.failed is False
    assert result.blocking is False

    assert result.to_dict() == {
        "name": "readiness",
        "status": "ready",
        "severity": "info",
        "passed": True,
        "failed": False,
        "blocking": False,
        "message": "Ready.",
        "details": {
            "checks": 10,
        },
        "timestamp": "2026-01-01T00:00:00+00:00",
    }


def test_production_check_result_blocking():
    result = ProductionCheckResult(
        name="security",
        status="blocked",
        severity="critical",
        passed=False,
    )

    assert result.failed is True
    assert result.blocking is True


def test_production_check_result_rejects_invalid_values():
    with pytest.raises(ValueError):
        ProductionCheckResult(name="", status="ready")

    with pytest.raises(ValueError):
        ProductionCheckResult(name="check", status="bad")

    with pytest.raises(ValueError):
        ProductionCheckResult(name="check", status="ready", severity="bad")

    with pytest.raises(ValueError):
        ProductionCheckResult(name="check", status="ready", passed="yes")

    with pytest.raises(ValueError):
        ProductionCheckResult(name="check", status="ready", message=123)

    with pytest.raises(ValueError):
        ProductionCheckResult(name="check", status="ready", details=[])

    with pytest.raises(ValueError):
        ProductionCheckResult(name="check", status="ready", timestamp="")


def test_build_production_check_result():
    result = build_production_check_result(
        name="readiness",
        status="ready",
        severity="info",
        passed=True,
        message="OK.",
        details={
            "source": "test",
        },
        timestamp="2026-01-01T00:00:00+00:00",
    )

    assert isinstance(result, ProductionCheckResult)
    assert result.to_dict()["details"] == {
        "source": "test",
    }


def test_validate_check_results():
    result = build_production_check_result(
        name="readiness",
        status="ready",
    )

    assert validate_check_results([result]) == [
        result,
    ]

    with pytest.raises(ValueError):
        validate_check_results("bad")

    with pytest.raises(ValueError):
        validate_check_results(["bad"])


def test_aggregate_production_status():
    ready = build_production_check_result(
        name="ready",
        status="ready",
        passed=True,
    )
    warning = build_production_check_result(
        name="warning",
        status="warning",
        severity="warning",
        passed=True,
    )
    blocked = build_production_check_result(
        name="blocked",
        status="blocked",
        severity="critical",
        passed=False,
    )

    assert aggregate_production_status([]) == ProductionStatus.UNKNOWN
    assert aggregate_production_status([ready]) == ProductionStatus.READY
    assert aggregate_production_status([warning]) == ProductionStatus.WARNING
    assert aggregate_production_status([ready, warning]) == ProductionStatus.WARNING
    assert aggregate_production_status([ready, blocked]) == ProductionStatus.BLOCKED


def test_production_gate_result_to_dict():
    ready = build_production_check_result(
        name="readiness",
        status="ready",
        passed=True,
        timestamp="2026-01-01T00:00:00+00:00",
    )
    warning = build_production_check_result(
        name="budget",
        status="warning",
        severity="warning",
        passed=True,
        timestamp="2026-01-01T00:00:00+00:00",
    )

    result = ProductionGateResult(
        gate_name=" release ",
        status="WARNING",
        checks=[
            ready,
            warning,
        ],
        message=" Has warnings. ",
        metadata={
            "version": "v0.20.0-dev",
        },
        timestamp="2026-01-01T00:00:00+00:00",
    )

    assert result.passed is False
    assert result.failed is True
    assert len(result.warning_checks) == 1

    payload = result.to_dict()

    assert payload["gate_name"] == "release"
    assert payload["status"] == "warning"
    assert payload["passed"] is False
    assert payload["failed"] is True
    assert payload["blocking_checks"] == 0
    assert payload["warning_checks"] == 1
    assert payload["metadata"] == {
        "version": "v0.20.0-dev",
    }


def test_production_gate_result_rejects_invalid_values():
    with pytest.raises(ValueError):
        ProductionGateResult(gate_name="", status="ready")

    with pytest.raises(ValueError):
        ProductionGateResult(gate_name="gate", status="bad")

    with pytest.raises(ValueError):
        ProductionGateResult(gate_name="gate", status="ready", checks=["bad"])

    with pytest.raises(ValueError):
        ProductionGateResult(gate_name="gate", status="ready", message=123)

    with pytest.raises(ValueError):
        ProductionGateResult(gate_name="gate", status="ready", metadata=[])

    with pytest.raises(ValueError):
        ProductionGateResult(gate_name="gate", status="ready", timestamp="")


def test_build_production_gate_result():
    check = build_production_check_result(
        name="readiness",
        status="ready",
    )

    result = build_production_gate_result(
        gate_name="release",
        status="ready",
        checks=[
            check,
        ],
        metadata={
            "source": "test",
        },
        timestamp="2026-01-01T00:00:00+00:00",
    )

    assert isinstance(result, ProductionGateResult)
    assert result.metadata == {
        "source": "test",
    }


def test_safe_production_check_success():
    expected = build_production_check_result(
        name="readiness",
        status="ready",
        passed=True,
    )

    result = safe_production_check(
        lambda: expected,
        name="readiness",
    )

    assert result is expected


def test_safe_production_check_failure():
    def fail():
        raise RuntimeError("boom")

    result = safe_production_check(
        fail,
        name="readiness",
    )

    assert result.passed is False
    assert result.status == ProductionStatus.BLOCKED
    assert result.details == {
        "error": "boom",
        "error_type": "RuntimeError",
    }


def test_safe_production_check_rejects_invalid_values():
    with pytest.raises(ValueError):
        safe_production_check(
            "bad",
            name="readiness",
        )

    with pytest.raises(ValueError):
        safe_production_check(
            lambda: None,
            name="",
        )

    result = safe_production_check(
        lambda: "bad",
        name="readiness",
    )

    assert result.passed is False
    assert result.status == ProductionStatus.BLOCKED
    assert result.details["error_type"] == "ValueError"


def test_production_exports_are_sorted():
    import aqos.production as production

    assert production.__all__ == sorted(production.__all__)


def test_production_exports_exist():
    import aqos.production as production

    for export_name in production.__all__:
        assert hasattr(production, export_name), export_name