"""
Unit tests for AQOS secure runtime context.
"""

import pytest

from aqos.security import (
    RuntimeEnvironment,
    SecurityContextManager,
    SecurityContextState,
    SecurityDecision,
    SecurityPrincipal,
    SecurityRuntimeContext,
    TokenValidationResult,
    build_anonymous_context,
    build_authenticated_context,
    build_context_from_token_validation,
    build_context_id,
    build_security_runtime_context,
    context_has_permission,
    context_has_role,
    context_has_scope,
    merge_context_attributes,
    normalize_context_state,
    normalize_runtime_environment,
    validate_context_id,
)


def test_runtime_environment_values():
    assert RuntimeEnvironment.LOCAL.value == "local"
    assert RuntimeEnvironment.DEVELOPMENT.value == "development"
    assert RuntimeEnvironment.TEST.value == "test"
    assert RuntimeEnvironment.STAGING.value == "staging"
    assert RuntimeEnvironment.PRODUCTION.value == "production"


def test_security_context_state_values():
    assert SecurityContextState.ANONYMOUS.value == "anonymous"
    assert SecurityContextState.AUTHENTICATED.value == "authenticated"
    assert SecurityContextState.DENIED.value == "denied"


def test_normalize_runtime_environment_accepts_enum_and_string():
    assert normalize_runtime_environment(RuntimeEnvironment.LOCAL) == RuntimeEnvironment.LOCAL
    assert normalize_runtime_environment(" LOCAL ") == RuntimeEnvironment.LOCAL
    assert normalize_runtime_environment("production") == RuntimeEnvironment.PRODUCTION


def test_normalize_runtime_environment_rejects_invalid_value():
    with pytest.raises(ValueError):
        normalize_runtime_environment("bad")

    with pytest.raises(ValueError):
        normalize_runtime_environment("")


def test_normalize_context_state_accepts_enum_and_string():
    assert normalize_context_state(SecurityContextState.AUTHENTICATED) == SecurityContextState.AUTHENTICATED
    assert normalize_context_state(" AUTHENTICATED ") == SecurityContextState.AUTHENTICATED
    assert normalize_context_state("denied") == SecurityContextState.DENIED


def test_normalize_context_state_rejects_invalid_value():
    with pytest.raises(ValueError):
        normalize_context_state("bad")

    with pytest.raises(ValueError):
        normalize_context_state("")


def test_validate_context_id():
    assert validate_context_id("ctx-1") == "ctx-1"

    with pytest.raises(ValueError):
        validate_context_id("")

    with pytest.raises(ValueError):
        validate_context_id("bad ctx")


def test_build_context_id():
    context_id = build_context_id()

    assert context_id.startswith("ctx-")
    assert len(context_id) > len("ctx-")

    with pytest.raises(ValueError):
        build_context_id("")

    with pytest.raises(ValueError):
        build_context_id("bad prefix")


def test_merge_context_attributes():
    assert merge_context_attributes(
        {
            "a": 1,
        },
        {
            "b": 2,
        },
    ) == {
        "a": 1,
        "b": 2,
    }

    assert merge_context_attributes(
        {
            "a": 1,
        },
        {
            "a": 2,
        },
    ) == {
        "a": 2,
    }

    with pytest.raises(ValueError):
        merge_context_attributes([], {})

    with pytest.raises(ValueError):
        merge_context_attributes({}, [])


def test_security_runtime_context_to_dict_and_helpers():
    principal = SecurityPrincipal(
        principal_id="user-1",
        roles=[
            "trader",
        ],
    )

    context = SecurityRuntimeContext(
        context_id="ctx-1",
        principal=principal,
        environment="PRODUCTION",
        state="AUTHENTICATED",
        request_id="req-1",
        source_ip="127.0.0.1",
        scopes=[
            "trade.execute",
        ],
        permissions=[
            "trade.execute",
        ],
        created_at="2026-01-01T00:00:00+00:00",
        attributes={
            "source": "api",
        },
    )

    assert context.authenticated is True
    assert context.anonymous is False
    assert context.denied is False
    assert context.principal_id == "user-1"
    assert context.has_role("trader") is True
    assert context.has_scope("trade.execute") is True
    assert context.has_permission("trade.execute") is True

    assert context.to_dict() == {
        "context_id": "ctx-1",
        "principal": principal.to_dict(),
        "principal_id": "user-1",
        "environment": "production",
        "state": "authenticated",
        "authenticated": True,
        "anonymous": False,
        "denied": False,
        "request_id": "req-1",
        "source_ip": "127.0.0.1",
        "scopes": [
            "trade.execute",
        ],
        "permissions": [
            "trade.execute",
        ],
        "created_at": "2026-01-01T00:00:00+00:00",
        "attributes": {
            "source": "api",
        },
    }


def test_security_runtime_context_security_result():
    principal = SecurityPrincipal(principal_id="user-1")

    authenticated = SecurityRuntimeContext(
        context_id="ctx-1",
        principal=principal,
        state="authenticated",
    )
    anonymous = SecurityRuntimeContext(
        context_id="ctx-2",
        state="anonymous",
    )
    denied = SecurityRuntimeContext(
        context_id="ctx-3",
        principal=principal,
        state="denied",
    )

    assert authenticated.to_security_result().decision == SecurityDecision.ALLOW
    assert authenticated.to_security_result().reason == "Security context authenticated."

    assert anonymous.to_security_result().decision == SecurityDecision.ALLOW
    assert anonymous.to_security_result().reason == "Security context anonymous."

    assert denied.to_security_result().decision == SecurityDecision.DENY
    assert denied.to_security_result().reason == "Security context denied."


def test_security_runtime_context_with_state():
    context = SecurityRuntimeContext(
        context_id="ctx-1",
        state="authenticated",
        attributes={
            "source": "api",
        },
    )

    denied = context.with_state(
        "denied",
        attributes={
            "reason": "blocked",
        },
    )

    assert denied.context_id == "ctx-1"
    assert denied.denied is True
    assert denied.attributes == {
        "source": "api",
        "reason": "blocked",
    }


def test_security_runtime_context_rejects_invalid_values():
    principal = SecurityPrincipal(principal_id="user-1")

    with pytest.raises(ValueError):
        SecurityRuntimeContext(context_id="")

    with pytest.raises(ValueError):
        SecurityRuntimeContext(context_id="ctx-1", principal="bad")

    with pytest.raises(ValueError):
        SecurityRuntimeContext(context_id="ctx-1", environment="bad")

    with pytest.raises(ValueError):
        SecurityRuntimeContext(context_id="ctx-1", state="bad")

    with pytest.raises(ValueError):
        SecurityRuntimeContext(context_id="ctx-1", request_id=123)

    with pytest.raises(ValueError):
        SecurityRuntimeContext(context_id="ctx-1", source_ip=123)

    with pytest.raises(ValueError):
        SecurityRuntimeContext(context_id="ctx-1", scopes=[""])

    with pytest.raises(ValueError):
        SecurityRuntimeContext(context_id="ctx-1", permissions=[""])

    with pytest.raises(ValueError):
        SecurityRuntimeContext(context_id="ctx-1", created_at="")

    with pytest.raises(ValueError):
        SecurityRuntimeContext(context_id="ctx-1", attributes=[])

    context = SecurityRuntimeContext(context_id="ctx-1", principal=principal)

    with pytest.raises(ValueError):
        context.has_role("")

    with pytest.raises(ValueError):
        context.has_scope("")

    with pytest.raises(ValueError):
        context.has_permission("")


def test_context_has_helpers():
    principal = SecurityPrincipal(
        principal_id="user-1",
        roles=[
            "admin",
        ],
    )

    context = SecurityRuntimeContext(
        context_id="ctx-1",
        principal=principal,
        scopes=[
            "*",
        ],
        permissions=[
            "*",
        ],
    )

    assert context_has_role(context, "admin") is True
    assert context_has_scope(context, "trade.execute") is True
    assert context_has_permission(context, "trade.execute") is True

    anonymous = SecurityRuntimeContext(context_id="ctx-2")

    assert context_has_role(anonymous, "admin") is False

    with pytest.raises(ValueError):
        context_has_role("bad", "admin")

    with pytest.raises(ValueError):
        context_has_scope("bad", "scope")

    with pytest.raises(ValueError):
        context_has_permission("bad", "permission")


def test_build_security_runtime_context():
    principal = SecurityPrincipal(principal_id="user-1")

    context = build_security_runtime_context(
        context_id="ctx-1",
        principal=principal,
        environment="test",
        state="authenticated",
        request_id="req-1",
        source_ip="127.0.0.1",
        scopes=[
            "market.read",
        ],
        permissions=[
            "market.read",
        ],
        created_at="2026-01-01T00:00:00+00:00",
        attributes={
            "source": "test",
        },
    )

    assert isinstance(context, SecurityRuntimeContext)
    assert context.authenticated is True
    assert context.to_dict()["environment"] == "test"


def test_build_anonymous_context():
    context = build_anonymous_context(
        context_id="ctx-1",
        environment="local",
        request_id="req-1",
        source_ip="127.0.0.1",
        attributes={
            "source": "api",
        },
    )

    assert context.anonymous is True
    assert context.authenticated is False
    assert context.principal is None
    assert context.attributes == {
        "source": "api",
    }


def test_build_authenticated_context():
    principal = SecurityPrincipal(
        principal_id="user-1",
        roles=[
            "trader",
        ],
    )

    context = build_authenticated_context(
        context_id="ctx-1",
        principal=principal,
        environment="production",
        scopes=[
            "trade.execute",
        ],
        permissions=[
            "trade.execute",
        ],
    )

    assert context.authenticated is True
    assert context.principal_id == "user-1"
    assert context.has_role("trader") is True

    with pytest.raises(ValueError):
        build_authenticated_context(
            context_id="ctx-1",
            principal="bad",
        )


def test_build_context_from_valid_token_validation():
    validation = TokenValidationResult(
        valid=True,
        status="active",
        reason="Access token is valid.",
        principal_id="user-1",
        token_id="token-1",
        scopes=[
            "trade.execute",
        ],
        metadata={
            "source": "token-store",
        },
    )

    context = build_context_from_token_validation(
        context_id="ctx-1",
        validation_result=validation,
        environment="production",
        request_id="req-1",
        source_ip="127.0.0.1",
        permissions=[
            "trade.execute",
        ],
    )

    assert context.authenticated is True
    assert context.principal_id == "user-1"
    assert context.principal.principal_type == "token"
    assert context.scopes == [
        "trade.execute",
    ]
    assert context.attributes == {
        "token_id": "token-1",
        "token_status": "active",
        "token_reason": "Access token is valid.",
        "source": "token-store",
    }


def test_build_context_from_invalid_token_validation():
    validation = TokenValidationResult(
        valid=False,
        status="revoked",
        reason="Access token is revoked.",
        token_id="token-1",
    )

    context = build_context_from_token_validation(
        context_id="ctx-1",
        validation_result=validation,
    )

    assert context.denied is True
    assert context.principal is None
    assert context.attributes["token_status"] == "revoked"

    with pytest.raises(ValueError):
        build_context_from_token_validation(
            context_id="ctx-1",
            validation_result="bad",
        )


def test_security_context_manager_register_get_and_summary():
    manager = SecurityContextManager()
    principal = SecurityPrincipal(principal_id="user-1")

    context = build_authenticated_context(
        context_id="ctx-1",
        principal=principal,
        environment="production",
    )

    assert manager.register_context(context) is context
    assert manager.get_context("ctx-1") is context
    assert manager.get_required_context("ctx-1") is context
    assert manager.list_contexts() == [
        context,
    ]
    assert manager.filter_by_principal("user-1") == [
        context,
    ]

    assert manager.summary() == {
        "contexts": 1,
        "states": {
            "authenticated": 1,
        },
        "environments": {
            "production": 1,
        },
        "context_ids": [
            "ctx-1",
        ],
    }


def test_security_context_manager_create_context():
    manager = SecurityContextManager()
    principal = SecurityPrincipal(principal_id="user-1")

    context = manager.create_context(
        context_id="ctx-1",
        principal=principal,
        environment="test",
        scopes=[
            "market.read",
        ],
        permissions=[
            "market.read",
        ],
    )

    assert context.context_id == "ctx-1"
    assert context.authenticated is True
    assert manager.get_context("ctx-1") is context

    anonymous = manager.create_context(
        context_id="ctx-2",
    )

    assert anonymous.anonymous is True


def test_security_context_manager_upsert_and_state_change():
    manager = SecurityContextManager()

    context = build_anonymous_context(context_id="ctx-1")
    replacement = build_security_runtime_context(
        context_id="ctx-1",
        state="authenticated",
    )

    manager.upsert_context(context)
    manager.upsert_context(replacement)

    assert manager.get_context("ctx-1") is replacement

    denied = manager.deny_context(
        "ctx-1",
        reason="Blocked.",
    )

    assert denied.denied is True
    assert denied.attributes == {
        "deny_reason": "Blocked.",
    }


def test_security_context_manager_clear():
    manager = SecurityContextManager()
    manager.create_context(context_id="ctx-1")

    assert manager.summary()["contexts"] == 1

    manager.clear()

    assert manager.summary() == {
        "contexts": 0,
        "states": {},
        "environments": {},
        "context_ids": [],
    }


def test_security_context_manager_rejects_invalid_values():
    manager = SecurityContextManager()

    with pytest.raises(ValueError):
        manager.register_context("bad")

    with pytest.raises(ValueError):
        manager.upsert_context("bad")

    context = build_anonymous_context(context_id="ctx-1")
    manager.register_context(context)

    with pytest.raises(ValueError):
        manager.register_context(context)

    with pytest.raises(ValueError):
        manager.get_required_context("missing")

    with pytest.raises(ValueError):
        manager.deny_context("ctx-1", reason="")

    with pytest.raises(ValueError):
        manager.filter_by_principal("")


def test_security_context_exports_exist():
    import aqos.security as security

    expected_exports = [
        "RuntimeEnvironment",
        "SecurityContextManager",
        "SecurityContextState",
        "SecurityRuntimeContext",
        "build_anonymous_context",
        "build_authenticated_context",
        "build_context_from_token_validation",
        "build_context_id",
        "build_security_runtime_context",
        "context_has_permission",
        "context_has_role",
        "context_has_scope",
        "merge_context_attributes",
        "normalize_context_state",
        "normalize_runtime_environment",
        "validate_context_id",
    ]

    for export_name in expected_exports:
        assert hasattr(security, export_name), export_name