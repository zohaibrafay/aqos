"""
Unit tests for AQOS reliability integration helpers.
"""

import pytest

from aqos.reliability import (
    ProtectedOperationResult,
    ReliabilityProfile,
    ReliabilityResult,
    ReliabilityStatus,
    ReliabilityToolkit,
    RuntimeSupervisor,
    build_protected_operation_result,
    build_rate_limit_config,
    build_reliability_profile,
    build_reliability_result,
    build_reliability_toolkit,
    build_retry_policy,
    build_runtime_supervisor_config,
    compose_reliability_metadata,
    protect_operation,
    reliability_result_from_exception,
    validate_string_list,
)


def test_validate_string_list():
    assert validate_string_list(
        [
            "retry",
            "deadline",
        ],
        "Controls",
    ) == [
        "retry",
        "deadline",
    ]

    with pytest.raises(ValueError):
        validate_string_list("bad", "Controls")

    with pytest.raises(ValueError):
        validate_string_list([""], "Controls")


def test_reliability_profile_to_dict_and_builders():
    profile = ReliabilityProfile(
        name=" trading ",
        component=" strategy-service ",
        retry_policy=build_retry_policy(max_attempts=2),
        rate_limit_config=build_rate_limit_config(max_requests=5),
        supervisor_config=build_runtime_supervisor_config(
            default_component="strategy-service",
        ),
        metadata={
            "symbol": "XAUUSD",
        },
    )

    payload = profile.to_dict()

    assert payload["name"] == "trading"
    assert payload["component"] == "strategy-service"
    assert payload["retry_policy"]["max_attempts"] == 2
    assert payload["rate_limit_config"]["max_requests"] == 5
    assert payload["metadata"] == {
        "symbol": "XAUUSD",
    }

    rate_limiter = profile.build_rate_limiter()
    breaker = profile.build_circuit_breaker("generate-signal")
    deadline = profile.build_deadline(
        "generate-signal",
        started_at="2026-01-01T00:00:00+00:00",
    )
    supervisor = profile.build_supervisor()

    assert rate_limiter.metadata["profile"] == "trading"
    assert breaker.name == "generate-signal"
    assert deadline.operation == "generate-signal"
    assert isinstance(supervisor, RuntimeSupervisor)


def test_reliability_profile_rejects_invalid_values():
    with pytest.raises(ValueError):
        ReliabilityProfile(name="", component="service")

    with pytest.raises(ValueError):
        ReliabilityProfile(name="profile", component="")

    with pytest.raises(ValueError):
        ReliabilityProfile(name="profile", component="service", retry_policy="bad")

    with pytest.raises(ValueError):
        ReliabilityProfile(
            name="profile",
            component="service",
            circuit_breaker_config="bad",
        )

    with pytest.raises(ValueError):
        ReliabilityProfile(name="profile", component="service", rate_limit_config="bad")

    with pytest.raises(ValueError):
        ReliabilityProfile(name="profile", component="service", timeout_config="bad")

    with pytest.raises(ValueError):
        ReliabilityProfile(name="profile", component="service", supervisor_config="bad")

    with pytest.raises(ValueError):
        ReliabilityProfile(name="profile", component="service", metadata=[])


def test_build_reliability_profile():
    profile = build_reliability_profile(
        name="api-profile",
        component="api",
        metadata={
            "source": "test",
        },
    )

    assert isinstance(profile, ReliabilityProfile)
    assert profile.name == "api-profile"
    assert profile.component == "api"
    assert profile.metadata == {
        "source": "test",
    }


def test_protected_operation_result_to_dict():
    reliability_result = build_reliability_result(
        success=True,
        operation="calculate",
        component="math",
        value=10,
    )

    result = ProtectedOperationResult(
        success=True,
        operation=" calculate ",
        component=" math ",
        reliability_result=reliability_result,
        controls=[
            "retry",
            "deadline",
        ],
        value=10,
        metadata={
            "source": "test",
        },
    )

    assert result.failed is False

    payload = result.to_dict()

    assert payload["success"] is True
    assert payload["operation"] == "calculate"
    assert payload["component"] == "math"
    assert payload["controls"] == [
        "retry",
        "deadline",
    ]
    assert payload["value"] == 10


def test_protected_operation_result_rejects_invalid_values():
    reliability_result = build_reliability_result(
        success=True,
        operation="operation",
        component="service",
    )

    with pytest.raises(ValueError):
        ProtectedOperationResult(
            success="yes",
            operation="operation",
            component="service",
            reliability_result=reliability_result,
        )

    with pytest.raises(ValueError):
        ProtectedOperationResult(
            success=True,
            operation="",
            component="service",
            reliability_result=reliability_result,
        )

    with pytest.raises(ValueError):
        ProtectedOperationResult(
            success=True,
            operation="operation",
            component="",
            reliability_result=reliability_result,
        )

    with pytest.raises(ValueError):
        ProtectedOperationResult(
            success=True,
            operation="operation",
            component="service",
            reliability_result="bad",
        )

    with pytest.raises(ValueError):
        ProtectedOperationResult(
            success=True,
            operation="operation",
            component="service",
            reliability_result=reliability_result,
            controls=[""],
        )

    with pytest.raises(ValueError):
        ProtectedOperationResult(
            success=False,
            operation="operation",
            component="service",
            reliability_result=reliability_result,
            error="",
        )

    with pytest.raises(ValueError):
        ProtectedOperationResult(
            success=True,
            operation="operation",
            component="service",
            reliability_result=reliability_result,
            metadata=[],
        )


def test_build_protected_operation_result():
    reliability_result = build_reliability_result(
        success=True,
        operation="operation",
        component="service",
    )

    result = build_protected_operation_result(
        success=True,
        operation="operation",
        component="service",
        reliability_result=reliability_result,
        controls=[
            "safe_execute",
        ],
    )

    assert isinstance(result, ProtectedOperationResult)
    assert result.controls == [
        "safe_execute",
    ]


def test_reliability_toolkit_run_basic_success_and_failure():
    toolkit = build_reliability_toolkit(
        profile=build_reliability_profile(
            component="math",
        ),
        metadata={
            "source": "test",
        },
    )

    success = toolkit.run_basic(
        lambda: 10,
        operation_name="calculate",
        metadata={
            "request_id": "req-1",
        },
    )

    assert success.success is True
    assert success.value == 10
    assert success.controls == [
        "safe_execute",
    ]
    assert success.metadata == {
        "source": "test",
        "request_id": "req-1",
    }

    def fail():
        raise RuntimeError("boom")

    failure = toolkit.run_basic(
        fail,
        operation_name="fail-op",
    )

    assert failure.success is False
    assert failure.error == "boom"


def test_reliability_toolkit_run_with_retry():
    calls = {
        "count": 0,
    }

    def flaky():
        calls["count"] += 1

        if calls["count"] < 2:
            raise RuntimeError("temporary")

        return "ok"

    toolkit = build_reliability_toolkit(
        profile=build_reliability_profile(
            component="worker",
            retry_policy=build_retry_policy(
                max_attempts=2,
                retry_on_exceptions=(RuntimeError,),
            ),
        ),
    )

    result = toolkit.run_with_retry(
        flaky,
        operation_name="flaky-op",
    )

    assert result.success is True
    assert result.value == "ok"
    assert result.controls == [
        "retry",
    ]


def test_reliability_toolkit_run_supervised():
    toolkit = build_reliability_toolkit(
        profile=build_reliability_profile(
            component="api",
            rate_limit_config=build_rate_limit_config(
                max_requests=2,
                window_seconds=60,
            ),
        ),
    )

    result = toolkit.run_supervised(
        lambda: 10,
        operation_name="calculate",
        rate_limit_key="user-1",
        now="2026-01-01T00:00:00+00:00",
    )

    assert result.success is True
    assert result.value == 10
    assert "rate_limiter" in result.controls
    assert toolkit.summary()["has_supervisor"] is True


def test_reliability_toolkit_rejects_invalid_values():
    with pytest.raises(ValueError):
        ReliabilityToolkit(profile="bad")

    with pytest.raises(ValueError):
        ReliabilityToolkit(supervisor="bad")

    with pytest.raises(ValueError):
        ReliabilityToolkit(metadata=[])

    toolkit = build_reliability_toolkit()

    with pytest.raises(ValueError):
        toolkit.run_basic(
            lambda: None,
            operation_name="operation",
            metadata=[],
        )

    with pytest.raises(ValueError):
        toolkit.run_with_retry(
            lambda: None,
            operation_name="operation",
            metadata=[],
        )

    with pytest.raises(ValueError):
        toolkit.run_supervised(
            lambda: None,
            operation_name="operation",
            metadata=[],
        )


def test_build_reliability_toolkit():
    toolkit = build_reliability_toolkit(
        metadata={
            "source": "test",
        },
    )

    assert isinstance(toolkit, ReliabilityToolkit)
    assert toolkit.metadata == {
        "source": "test",
    }


def test_protect_operation_success_and_failure():
    profile = build_reliability_profile(
        component="api",
        rate_limit_config=build_rate_limit_config(
            max_requests=1,
            window_seconds=60,
        ),
    )

    success = protect_operation(
        lambda: 10,
        operation_name="calculate",
        profile=profile,
        rate_limit_key="user-1",
        now="2026-01-01T00:00:00+00:00",
        metadata={
            "source": "test",
        },
    )

    assert success.success is True
    assert success.value == 10

    failure = protect_operation(
        lambda: (_ for _ in ()).throw(RuntimeError("boom")),
        operation_name="fail-op",
        profile=profile,
        rate_limit_key="user-2",
        now="2026-01-01T00:00:00+00:00",
    )

    assert failure.success is False
    assert failure.error is not None


def test_compose_reliability_metadata():
    profile = build_reliability_profile(
        name="profile-1",
        component="api",
        metadata={
            "env": "test",
        },
    )

    metadata = compose_reliability_metadata(
        profile=profile,
        operation="calculate",
        extra={
            "request_id": "req-1",
        },
    )

    assert metadata == {
        "profile": "profile-1",
        "component": "api",
        "operation": "calculate",
        "env": "test",
        "request_id": "req-1",
    }

    with pytest.raises(ValueError):
        compose_reliability_metadata(
            profile="bad",
            operation="calculate",
        )

    with pytest.raises(ValueError):
        compose_reliability_metadata(
            profile=profile,
            operation="",
        )

    with pytest.raises(ValueError):
        compose_reliability_metadata(
            profile=profile,
            operation="calculate",
            extra=[],
        )


def test_reliability_result_from_exception():
    error = RuntimeError("boom")

    result = reliability_result_from_exception(
        error,
        operation="calculate",
        component="math",
        metadata={
            "source": "test",
        },
    )

    assert isinstance(result, ReliabilityResult)
    assert result.success is False
    assert result.status == ReliabilityStatus.FAILED
    assert result.error == "boom"
    assert result.metadata == {
        "error_type": "RuntimeError",
        "source": "test",
    }

    with pytest.raises(ValueError):
        reliability_result_from_exception(
            "bad",
            operation="calculate",
            component="math",
        )

    with pytest.raises(ValueError):
        reliability_result_from_exception(
            error,
            operation="calculate",
            component="math",
            metadata=[],
        )


def test_reliability_integration_exports_exist():
    import aqos.reliability as reliability

    expected_exports = [
        "ProtectedOperationResult",
        "ReliabilityProfile",
        "ReliabilityToolkit",
        "build_protected_operation_result",
        "build_reliability_profile",
        "build_reliability_toolkit",
        "compose_reliability_metadata",
        "protect_operation",
        "reliability_result_from_exception",
        "validate_string_list",
    ]

    for export_name in expected_exports:
        assert hasattr(reliability, export_name), export_name