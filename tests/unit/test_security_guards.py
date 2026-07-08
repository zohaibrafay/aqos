"""
Unit tests for AQOS request guards and input sanitization.
"""

import pytest

from aqos.security import (
    DEFAULT_BLOCKED_PATTERNS,
    GuardAction,
    GuardedRequest,
    RequestGuard,
    RequestGuardConfig,
    RequestGuardResult,
    SanitizationResult,
    SecurityDecision,
    SecurityPrincipal,
    build_default_permission_registry,
    build_guarded_request,
    build_request_guard,
    contains_blocked_pattern,
    deduplicate_violations,
    normalize_guard_action,
    remove_control_characters,
    sanitize_dict,
    sanitize_guarded_request,
    sanitize_list,
    sanitize_string,
    sanitize_value,
    validate_http_method,
    validate_http_method_list,
    validate_max_string_length,
    validate_request_path,
)


def test_guard_action_values():
    assert GuardAction.ALLOW.value == "allow"
    assert GuardAction.DENY.value == "deny"
    assert GuardAction.SANITIZE.value == "sanitize"


def test_normalize_guard_action_accepts_enum_and_string():
    assert normalize_guard_action(GuardAction.ALLOW) == GuardAction.ALLOW
    assert normalize_guard_action(" ALLOW ") == GuardAction.ALLOW
    assert normalize_guard_action("deny") == GuardAction.DENY
    assert normalize_guard_action("SANITIZE") == GuardAction.SANITIZE


def test_normalize_guard_action_rejects_invalid_value():
    with pytest.raises(ValueError):
        normalize_guard_action("bad")

    with pytest.raises(ValueError):
        normalize_guard_action("")


def test_validate_http_method():
    assert validate_http_method(" get ") == "GET"

    with pytest.raises(ValueError):
        validate_http_method("")

    with pytest.raises(ValueError):
        validate_http_method("bad method")


def test_validate_http_method_list():
    assert validate_http_method_list([" get ", "POST"]) == ["GET", "POST"]

    with pytest.raises(ValueError):
        validate_http_method_list("GET")

    with pytest.raises(ValueError):
        validate_http_method_list(["GET", ""])


def test_validate_request_path():
    assert validate_request_path("/api/health") == "/api/health"

    with pytest.raises(ValueError):
        validate_request_path("")

    with pytest.raises(ValueError):
        validate_request_path("api/health")


def test_validate_max_string_length():
    assert validate_max_string_length(100) == 100

    with pytest.raises(ValueError):
        validate_max_string_length(0)

    with pytest.raises(ValueError):
        validate_max_string_length(True)

    with pytest.raises(ValueError):
        validate_max_string_length("100")


def test_sanitization_result_to_dict():
    result = SanitizationResult(
        value="hello",
        changed=True,
        violations=[
            "<script",
        ],
    )

    assert result.to_dict() == {
        "value": "hello",
        "changed": True,
        "violations": [
            "<script",
        ],
    }


def test_sanitization_result_rejects_invalid_values():
    with pytest.raises(ValueError):
        SanitizationResult(value="hello", changed="yes")

    with pytest.raises(ValueError):
        SanitizationResult(value="hello", violations=[""])


def test_remove_control_characters():
    assert remove_control_characters("hello\x00world") == "helloworld"


def test_contains_blocked_pattern():
    violations = contains_blocked_pattern("<script>alert(1)</script>")

    assert "<script" in violations
    assert "</script" in violations

    assert contains_blocked_pattern("safe text") == []


def test_sanitize_string_trims_limits_and_detects_patterns():
    result = sanitize_string(
        "  <script>alert(1)</script>  ",
        max_string_length=30,
    )

    assert result.value == "<script>alert(1)</script>"
    assert result.changed is True
    assert "<script" in result.violations

    limited = sanitize_string(
        "abcdef",
        max_string_length=3,
    )

    assert limited.value == "abc"
    assert limited.changed is True


def test_sanitize_value_dict_and_list():
    result = sanitize_value(
        {
            " name ": " Zohaib ",
            "items": [
                " safe ",
                "<script>alert(1)</script>",
            ],
        },
    )

    assert result.value == {
        "name": "Zohaib",
        "items": [
            "safe",
            "<script>alert(1)</script>",
        ],
    }
    assert result.changed is True
    assert "<script" in result.violations


def test_sanitize_list_rejects_invalid_value():
    with pytest.raises(ValueError):
        sanitize_list("bad")


def test_sanitize_dict_rejects_invalid_value():
    with pytest.raises(ValueError):
        sanitize_dict("bad")


def test_deduplicate_violations():
    assert deduplicate_violations(
        [
            "<script",
            "<script",
            "drop\\s+table",
        ],
    ) == [
        "<script",
        "drop\\s+table",
    ]


def test_guarded_request_to_dict():
    principal = SecurityPrincipal(
        principal_id="user-1",
        roles=[
            "trader",
        ],
    )

    request = GuardedRequest(
        request_id="req-1",
        method="post",
        path="/api/trade",
        principal=principal,
        headers={
            "Authorization": "Bearer token",
        },
        query_params={
            "symbol": "XAUUSD",
        },
        body={
            "side": "buy",
        },
        source_ip="127.0.0.1",
        metadata={
            "source": "test",
        },
    )

    assert request.to_dict() == {
        "request_id": "req-1",
        "method": "POST",
        "path": "/api/trade",
        "principal": principal.to_dict(),
        "headers": {
            "Authorization": "Bearer token",
        },
        "query_params": {
            "symbol": "XAUUSD",
        },
        "body": {
            "side": "buy",
        },
        "source_ip": "127.0.0.1",
        "metadata": {
            "source": "test",
        },
    }


def test_guarded_request_rejects_invalid_values():
    with pytest.raises(ValueError):
        GuardedRequest(request_id="", method="GET", path="/api")

    with pytest.raises(ValueError):
        GuardedRequest(request_id="req-1", method="", path="/api")

    with pytest.raises(ValueError):
        GuardedRequest(request_id="req-1", method="GET", path="api")

    with pytest.raises(ValueError):
        GuardedRequest(request_id="req-1", method="GET", path="/api", principal="bad")

    with pytest.raises(ValueError):
        GuardedRequest(request_id="req-1", method="GET", path="/api", headers=[])

    with pytest.raises(ValueError):
        GuardedRequest(request_id="req-1", method="GET", path="/api", query_params=[])

    with pytest.raises(ValueError):
        GuardedRequest(request_id="req-1", method="GET", path="/api", body=[])

    with pytest.raises(ValueError):
        GuardedRequest(request_id="req-1", method="GET", path="/api", source_ip=123)

    with pytest.raises(ValueError):
        GuardedRequest(request_id="req-1", method="GET", path="/api", metadata=[])


def test_build_guarded_request():
    request = build_guarded_request(
        request_id="req-1",
        method="GET",
        path="/api/health",
    )

    assert isinstance(request, GuardedRequest)
    assert request.request_id == "req-1"
    assert request.method == "GET"
    assert request.path == "/api/health"


def test_request_guard_config_defaults():
    config = RequestGuardConfig()

    assert config.allowed_methods == [
        "GET",
        "POST",
    ]
    assert config.require_principal is False
    assert config.required_permission is None
    assert config.sanitize_inputs is True
    assert config.deny_on_violation is True
    assert config.max_string_length == 5000
    assert config.blocked_patterns == DEFAULT_BLOCKED_PATTERNS


def test_request_guard_config_rejects_invalid_values():
    with pytest.raises(ValueError):
        RequestGuardConfig(allowed_methods="GET")

    with pytest.raises(ValueError):
        RequestGuardConfig(require_principal="yes")

    with pytest.raises(ValueError):
        RequestGuardConfig(required_permission="")

    with pytest.raises(ValueError):
        RequestGuardConfig(sanitize_inputs="yes")

    with pytest.raises(ValueError):
        RequestGuardConfig(deny_on_violation="yes")

    with pytest.raises(ValueError):
        RequestGuardConfig(max_string_length=0)

    with pytest.raises(ValueError):
        RequestGuardConfig(blocked_patterns=[""])

    with pytest.raises(ValueError):
        RequestGuardConfig(metadata=[])


def test_request_guard_result_to_dict_and_security_result():
    request = build_guarded_request(
        request_id="req-1",
        method="GET",
        path="/api/health",
    )

    result = RequestGuardResult(
        allowed=True,
        request_id="req-1",
        reason="Request allowed.",
        sanitized_request=request,
        violations=[],
        metadata={
            "changed": False,
        },
    )

    assert result.denied is False
    assert result.to_dict()["allowed"] is True
    assert result.to_dict()["sanitized_request"] == request.to_dict()

    security_result = result.to_security_result()

    assert security_result.decision == SecurityDecision.ALLOW
    assert security_result.allowed is True
    assert security_result.metadata["request_id"] == "req-1"


def test_request_guard_result_denied_security_result():
    result = RequestGuardResult(
        allowed=False,
        request_id="req-1",
        reason="Denied.",
        violations=[
            "blocked_input",
        ],
    )

    security_result = result.to_security_result()

    assert security_result.decision == SecurityDecision.DENY
    assert security_result.denied is True
    assert security_result.to_dict()["risk_level"] == "high"


def test_request_guard_result_rejects_invalid_values():
    with pytest.raises(ValueError):
        RequestGuardResult(allowed="yes", request_id="req-1")

    with pytest.raises(ValueError):
        RequestGuardResult(allowed=True, request_id="")

    with pytest.raises(ValueError):
        RequestGuardResult(allowed=True, request_id="req-1", reason=123)

    with pytest.raises(ValueError):
        RequestGuardResult(allowed=True, request_id="req-1", sanitized_request="bad")

    with pytest.raises(ValueError):
        RequestGuardResult(allowed=True, request_id="req-1", violations=[""])

    with pytest.raises(ValueError):
        RequestGuardResult(allowed=True, request_id="req-1", metadata=[])


def test_sanitize_guarded_request():
    request = build_guarded_request(
        request_id="req-1",
        method="POST",
        path="/api/trade",
        headers={
            " X-Test ": " value ",
        },
        body={
            "symbol": " XAUUSD ",
        },
        source_ip=" 127.0.0.1 ",
    )

    sanitized, violations, changed = sanitize_guarded_request(request)

    assert sanitized.headers == {
        "X-Test": "value",
    }
    assert sanitized.body == {
        "symbol": "XAUUSD",
    }
    assert sanitized.source_ip == "127.0.0.1"
    assert violations == []
    assert changed is True


def test_request_guard_allows_safe_request():
    guard = build_request_guard()
    request = build_guarded_request(
        request_id="req-1",
        method="GET",
        path="/api/health",
    )

    result = guard.guard(request)

    assert result.allowed is True
    assert result.reason == "Request allowed."
    assert result.violations == []
    assert result.metadata["changed"] is False


def test_request_guard_denies_method_not_allowed():
    guard = build_request_guard(
        config=RequestGuardConfig(
            allowed_methods=[
                "GET",
            ],
        ),
    )
    request = build_guarded_request(
        request_id="req-1",
        method="POST",
        path="/api/trade",
    )

    result = guard.guard(request)

    assert result.allowed is False
    assert result.reason == "HTTP method is not allowed."
    assert result.violations == [
        "method_not_allowed",
    ]


def test_request_guard_denies_missing_principal():
    guard = build_request_guard(
        config=RequestGuardConfig(
            require_principal=True,
        ),
    )
    request = build_guarded_request(
        request_id="req-1",
        method="GET",
        path="/api/health",
    )

    result = guard.guard(request)

    assert result.allowed is False
    assert result.reason == "Principal is required."
    assert result.violations == [
        "principal_required",
    ]


def test_request_guard_denies_blocked_input():
    guard = build_request_guard()
    request = build_guarded_request(
        request_id="req-1",
        method="POST",
        path="/api/trade",
        body={
            "comment": "<script>alert(1)</script>",
        },
    )

    result = guard.guard(request)

    assert result.allowed is False
    assert result.reason == "Request contains blocked input."
    assert "<script" in result.violations


def test_request_guard_allows_sanitized_violation_when_not_denied():
    guard = build_request_guard(
        config=RequestGuardConfig(
            deny_on_violation=False,
        ),
    )
    request = build_guarded_request(
        request_id="req-1",
        method="POST",
        path="/api/trade",
        body={
            "comment": "<script>alert(1)</script>",
        },
    )

    result = guard.guard(request)

    assert result.allowed is True
    assert "<script" in result.violations


def test_request_guard_permission_allowed():
    registry = build_default_permission_registry()
    principal = SecurityPrincipal(
        principal_id="user-1",
        roles=[
            "trader",
        ],
    )

    guard = build_request_guard(
        config=RequestGuardConfig(
            require_principal=True,
            required_permission="trade.execute",
        ),
        permission_registry=registry,
    )

    request = build_guarded_request(
        request_id="req-1",
        method="POST",
        path="/api/trade",
        principal=principal,
    )

    result = guard.guard(request)

    assert result.allowed is True
    assert result.reason == "Request allowed."


def test_request_guard_permission_denied():
    registry = build_default_permission_registry()
    principal = SecurityPrincipal(
        principal_id="user-1",
        roles=[
            "viewer",
        ],
    )

    guard = build_request_guard(
        config=RequestGuardConfig(
            require_principal=True,
            required_permission="trade.execute",
        ),
        permission_registry=registry,
    )

    request = build_guarded_request(
        request_id="req-1",
        method="POST",
        path="/api/trade",
        principal=principal,
    )

    result = guard.guard(request)

    assert result.allowed is False
    assert result.reason == "Permission denied."
    assert result.violations == [
        "permission_denied",
    ]


def test_request_guard_requires_permission_registry():
    principal = SecurityPrincipal(
        principal_id="user-1",
        roles=[
            "trader",
        ],
    )

    guard = build_request_guard(
        config=RequestGuardConfig(
            require_principal=True,
            required_permission="trade.execute",
        ),
    )

    request = build_guarded_request(
        request_id="req-1",
        method="POST",
        path="/api/trade",
        principal=principal,
    )

    result = guard.guard(request)

    assert result.allowed is False
    assert result.reason == "Permission registry is required."
    assert result.violations == [
        "permission_registry_required",
    ]


def test_request_guard_rejects_invalid_values():
    with pytest.raises(ValueError):
        RequestGuard(config="bad")

    with pytest.raises(ValueError):
        RequestGuard(permission_registry="bad")

    guard = build_request_guard()

    with pytest.raises(ValueError):
        guard.guard("bad")


def test_security_guard_exports_exist():
    import aqos.security as security

    expected_exports = [
        "DEFAULT_BLOCKED_PATTERNS",
        "GuardAction",
        "GuardedRequest",
        "RequestGuard",
        "RequestGuardConfig",
        "RequestGuardResult",
        "SanitizationResult",
        "build_guarded_request",
        "build_request_guard",
        "contains_blocked_pattern",
        "deduplicate_violations",
        "normalize_guard_action",
        "remove_control_characters",
        "sanitize_dict",
        "sanitize_guarded_request",
        "sanitize_list",
        "sanitize_string",
        "sanitize_value",
        "validate_http_method",
        "validate_http_method_list",
        "validate_max_string_length",
        "validate_request_path",
    ]

    for export_name in expected_exports:
        assert hasattr(security, export_name), export_name