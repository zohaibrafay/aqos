"""
Unit tests for AQOS role-based permissions.
"""

import pytest

from aqos.security import (
    Permission,
    PermissionCheck,
    PermissionCheckResult,
    PermissionEffect,
    PermissionRegistry,
    Role,
    SecurityDecision,
    SecurityPrincipal,
    build_default_permission_registry,
    build_permission,
    build_permission_check,
    build_role,
    evaluate_permission_check,
    normalize_permission_effect,
    require_permission,
    validate_permission_list,
    validate_permission_name,
    validate_role_name,
)


def test_permission_effect_values():
    assert PermissionEffect.ALLOW.value == "allow"
    assert PermissionEffect.DENY.value == "deny"


def test_normalize_permission_effect_accepts_enum_and_string():
    assert normalize_permission_effect(PermissionEffect.ALLOW) == PermissionEffect.ALLOW
    assert normalize_permission_effect(" ALLOW ") == PermissionEffect.ALLOW
    assert normalize_permission_effect("deny") == PermissionEffect.DENY


def test_normalize_permission_effect_rejects_invalid_value():
    with pytest.raises(ValueError):
        normalize_permission_effect("bad")

    with pytest.raises(ValueError):
        normalize_permission_effect("")


def test_validate_permission_name():
    assert validate_permission_name("trade.execute") == "trade.execute"

    with pytest.raises(ValueError):
        validate_permission_name("")

    with pytest.raises(ValueError):
        validate_permission_name("trade execute")


def test_validate_role_name():
    assert validate_role_name("admin") == "admin"

    with pytest.raises(ValueError):
        validate_role_name("")

    with pytest.raises(ValueError):
        validate_role_name("bad role")


def test_validate_permission_list():
    assert validate_permission_list(
        [
            " market.read ",
            "trade.execute",
        ],
    ) == [
        "market.read",
        "trade.execute",
    ]

    with pytest.raises(ValueError):
        validate_permission_list("market.read")

    with pytest.raises(ValueError):
        validate_permission_list(["market.read", ""])


def test_permission_to_dict_and_matches():
    permission = Permission(
        name=" trade.execute ",
        description=" Execute trades. ",
        attributes={
            "risk": "high",
        },
    )

    assert permission.to_dict() == {
        "name": "trade.execute",
        "description": "Execute trades.",
        "attributes": {
            "risk": "high",
        },
    }

    assert permission.matches("trade.execute") is True
    assert permission.matches("market.read") is False


def test_wildcard_permission_matches_any_permission():
    permission = Permission(name="*")

    assert permission.matches("trade.execute") is True
    assert permission.matches("market.read") is True


def test_permission_rejects_invalid_values():
    with pytest.raises(ValueError):
        Permission(name="")

    with pytest.raises(ValueError):
        Permission(name="trade execute")

    with pytest.raises(ValueError):
        Permission(name="trade.execute", description=123)

    with pytest.raises(ValueError):
        Permission(name="trade.execute", attributes=[])


def test_build_permission():
    permission = build_permission(
        name="trade.execute",
        description="Execute trades.",
        attributes={
            "risk": "high",
        },
    )

    assert isinstance(permission, Permission)
    assert permission.to_dict() == {
        "name": "trade.execute",
        "description": "Execute trades.",
        "attributes": {
            "risk": "high",
        },
    }


def test_role_to_dict_and_has_permission():
    role = Role(
        name=" trader ",
        permissions=[
            " market.read ",
            " trade.execute ",
        ],
        description=" Trading role. ",
        attributes={
            "risk": "high",
        },
    )

    assert role.to_dict() == {
        "name": "trader",
        "permissions": [
            "market.read",
            "trade.execute",
        ],
        "description": "Trading role.",
        "attributes": {
            "risk": "high",
        },
    }

    assert role.has_permission("trade.execute") is True
    assert role.has_permission("admin.manage") is False


def test_admin_role_with_wildcard_permission():
    role = Role(
        name="admin",
        permissions=[
            "*",
        ],
    )

    assert role.has_permission("trade.execute") is True
    assert role.has_permission("admin.manage") is True


def test_role_rejects_invalid_values():
    with pytest.raises(ValueError):
        Role(name="")

    with pytest.raises(ValueError):
        Role(name="bad role")

    with pytest.raises(ValueError):
        Role(
            name="trader",
            permissions="trade.execute",
        )

    with pytest.raises(ValueError):
        Role(
            name="trader",
            permissions=[""],
        )

    with pytest.raises(ValueError):
        Role(
            name="trader",
            description=123,
        )

    with pytest.raises(ValueError):
        Role(
            name="trader",
            attributes=[],
        )


def test_build_role():
    role = build_role(
        name="trader",
        permissions=[
            "market.read",
            "trade.execute",
        ],
        description="Trading role.",
    )

    assert isinstance(role, Role)
    assert role.has_permission("trade.execute") is True


def test_permission_check_to_dict():
    principal = SecurityPrincipal(
        principal_id="user-1",
        roles=[
            "trader",
        ],
    )

    check = PermissionCheck(
        principal=principal,
        permission="trade.execute",
        resource="XAUUSD",
        context={
            "timeframe": "H1",
        },
    )

    assert check.to_dict() == {
        "principal": principal.to_dict(),
        "permission": "trade.execute",
        "resource": "XAUUSD",
        "context": {
            "timeframe": "H1",
        },
    }


def test_permission_check_rejects_invalid_values():
    principal = SecurityPrincipal(principal_id="user-1")

    with pytest.raises(ValueError):
        PermissionCheck(
            principal="bad",
            permission="trade.execute",
        )

    with pytest.raises(ValueError):
        PermissionCheck(
            principal=principal,
            permission="",
        )

    with pytest.raises(ValueError):
        PermissionCheck(
            principal=principal,
            permission="trade.execute",
            resource=123,
        )

    with pytest.raises(ValueError):
        PermissionCheck(
            principal=principal,
            permission="trade.execute",
            context=[],
        )


def test_build_permission_check():
    principal = SecurityPrincipal(
        principal_id="user-1",
        roles=[
            "trader",
        ],
    )

    check = build_permission_check(
        principal=principal,
        permission="trade.execute",
        resource="XAUUSD",
        context={
            "timeframe": "H1",
        },
    )

    assert isinstance(check, PermissionCheck)
    assert check.permission == "trade.execute"


def test_permission_check_result_to_dict_and_security_result():
    result = PermissionCheckResult(
        allowed=True,
        permission="trade.execute",
        principal_id="user-1",
        reason="Permission granted.",
        matched_roles=[
            "trader",
        ],
        missing_roles=[
            "ghost",
        ],
        metadata={
            "resource": "XAUUSD",
        },
    )

    assert result.denied is False
    assert result.to_dict() == {
        "allowed": True,
        "denied": False,
        "permission": "trade.execute",
        "principal_id": "user-1",
        "reason": "Permission granted.",
        "matched_roles": [
            "trader",
        ],
        "missing_roles": [
            "ghost",
        ],
        "metadata": {
            "resource": "XAUUSD",
        },
    }

    security_result = result.to_security_result()

    assert security_result.decision == SecurityDecision.ALLOW
    assert security_result.allowed is True
    assert security_result.principal_id == "user-1"


def test_permission_check_result_denied_security_result():
    result = PermissionCheckResult(
        allowed=False,
        permission="trade.execute",
        principal_id="user-1",
        reason="Permission denied.",
    )

    security_result = result.to_security_result()

    assert security_result.decision == SecurityDecision.DENY
    assert security_result.denied is True
    assert security_result.to_dict()["risk_level"] == "medium"


def test_permission_check_result_rejects_invalid_values():
    with pytest.raises(ValueError):
        PermissionCheckResult(
            allowed="yes",
            permission="trade.execute",
            principal_id="user-1",
        )

    with pytest.raises(ValueError):
        PermissionCheckResult(
            allowed=True,
            permission="",
            principal_id="user-1",
        )

    with pytest.raises(ValueError):
        PermissionCheckResult(
            allowed=True,
            permission="trade.execute",
            principal_id="",
        )

    with pytest.raises(ValueError):
        PermissionCheckResult(
            allowed=True,
            permission="trade.execute",
            principal_id="user-1",
            reason=123,
        )

    with pytest.raises(ValueError):
        PermissionCheckResult(
            allowed=True,
            permission="trade.execute",
            principal_id="user-1",
            matched_roles=[""],
        )

    with pytest.raises(ValueError):
        PermissionCheckResult(
            allowed=True,
            permission="trade.execute",
            principal_id="user-1",
            missing_roles=[""],
        )

    with pytest.raises(ValueError):
        PermissionCheckResult(
            allowed=True,
            permission="trade.execute",
            principal_id="user-1",
            metadata=[],
        )


def test_permission_registry_register_get_and_summary():
    registry = PermissionRegistry()

    permission = build_permission(name="trade.execute")
    role = build_role(
        name="trader",
        permissions=[
            "trade.execute",
        ],
    )

    assert registry.register_permission(permission) is permission
    assert registry.register_role(role) is role

    assert registry.get_permission("trade.execute") is permission
    assert registry.get_role("trader") is role
    assert registry.get_required_permission("trade.execute") is permission
    assert registry.get_required_role("trader") is role
    assert registry.list_permissions() == [
        permission,
    ]
    assert registry.list_roles() == [
        role,
    ]

    assert registry.summary() == {
        "permissions": 1,
        "roles": 1,
        "permission_names": [
            "trade.execute",
        ],
        "role_names": [
            "trader",
        ],
    }


def test_permission_registry_upsert_replaces_existing_values():
    registry = PermissionRegistry()

    permission = build_permission(name="trade.execute", description="Old.")
    replacement_permission = build_permission(name="trade.execute", description="New.")

    role = build_role(name="trader", permissions=["market.read"])
    replacement_role = build_role(name="trader", permissions=["trade.execute"])

    registry.upsert_permission(permission)
    registry.upsert_permission(replacement_permission)
    registry.upsert_role(role)
    registry.upsert_role(replacement_role)

    assert registry.get_required_permission("trade.execute") is replacement_permission
    assert registry.get_required_role("trader") is replacement_role


def test_permission_registry_rejects_invalid_values():
    registry = PermissionRegistry()

    with pytest.raises(ValueError):
        registry.register_permission("bad")

    with pytest.raises(ValueError):
        registry.upsert_permission("bad")

    with pytest.raises(ValueError):
        registry.register_role("bad")

    with pytest.raises(ValueError):
        registry.upsert_role("bad")

    permission = build_permission(name="trade.execute")
    role = build_role(name="trader")

    registry.register_permission(permission)
    registry.register_role(role)

    with pytest.raises(ValueError):
        registry.register_permission(permission)

    with pytest.raises(ValueError):
        registry.register_role(role)

    with pytest.raises(ValueError):
        registry.get_required_permission("missing.permission")

    with pytest.raises(ValueError):
        registry.get_required_role("missing-role")


def test_evaluate_permission_check_allows_matching_role():
    registry = PermissionRegistry()
    registry.register_role(
        build_role(
            name="trader",
            permissions=[
                "trade.execute",
            ],
        ),
    )

    principal = SecurityPrincipal(
        principal_id="user-1",
        roles=[
            "trader",
        ],
    )

    check = build_permission_check(
        principal=principal,
        permission="trade.execute",
        resource="XAUUSD",
    )

    result = evaluate_permission_check(check, registry)

    assert result.allowed is True
    assert result.reason == "Permission granted."
    assert result.matched_roles == [
        "trader",
    ]
    assert result.metadata["resource"] == "XAUUSD"


def test_evaluate_permission_check_denies_missing_permission():
    registry = PermissionRegistry()
    registry.register_role(
        build_role(
            name="viewer",
            permissions=[
                "market.read",
            ],
        ),
    )

    principal = SecurityPrincipal(
        principal_id="user-1",
        roles=[
            "viewer",
        ],
    )

    result = registry.check_permission(
        principal,
        "trade.execute",
    )

    assert result.allowed is False
    assert result.reason == "Permission denied."
    assert result.matched_roles == []


def test_evaluate_permission_check_tracks_missing_roles():
    registry = PermissionRegistry()

    principal = SecurityPrincipal(
        principal_id="user-1",
        roles=[
            "ghost",
        ],
    )

    result = registry.check_permission(
        principal,
        "trade.execute",
    )

    assert result.allowed is False
    assert result.missing_roles == [
        "ghost",
    ]


def test_evaluate_permission_check_rejects_invalid_values():
    registry = PermissionRegistry()
    principal = SecurityPrincipal(principal_id="user-1")
    check = build_permission_check(
        principal=principal,
        permission="market.read",
    )

    with pytest.raises(ValueError):
        evaluate_permission_check("bad", registry)

    with pytest.raises(ValueError):
        evaluate_permission_check(check, "bad")


def test_require_permission():
    registry = PermissionRegistry()
    registry.register_role(
        build_role(
            name="trader",
            permissions=[
                "trade.execute",
            ],
        ),
    )

    principal = SecurityPrincipal(
        principal_id="user-1",
        roles=[
            "trader",
        ],
    )

    result = require_permission(
        principal,
        "trade.execute",
        registry,
        resource="XAUUSD",
    )

    assert result.allowed is True
    assert result.reason == "Permission granted."
    assert result.metadata["permission"] == "trade.execute"


def test_build_default_permission_registry():
    registry = build_default_permission_registry()

    viewer = registry.get_required_role("viewer")
    trader = registry.get_required_role("trader")
    researcher = registry.get_required_role("researcher")
    admin = registry.get_required_role("admin")

    assert viewer.has_permission("market.read") is True
    assert viewer.has_permission("trade.execute") is False

    assert trader.has_permission("trade.execute") is True
    assert researcher.has_permission("research.write") is True
    assert admin.has_permission("admin.manage") is True

    assert registry.summary()["permissions"] == 8
    assert registry.summary()["roles"] == 4


def test_permission_registry_clear():
    registry = build_default_permission_registry()

    assert registry.summary()["permissions"] == 8

    registry.clear()

    assert registry.summary() == {
        "permissions": 0,
        "roles": 0,
        "permission_names": [],
        "role_names": [],
    }


def test_security_permission_exports_exist():
    import aqos.security as security

    expected_exports = [
        "Permission",
        "PermissionCheck",
        "PermissionCheckResult",
        "PermissionEffect",
        "PermissionRegistry",
        "Role",
        "build_default_permission_registry",
        "build_permission",
        "build_permission_check",
        "build_role",
        "evaluate_permission_check",
        "normalize_permission_effect",
        "require_permission",
        "validate_permission_list",
        "validate_permission_name",
        "validate_role_name",
    ]

    for export_name in expected_exports:
        assert hasattr(security, export_name), export_name