"""
AQOS role-based permission primitives.

This module provides dependency-free RBAC helpers for roles, permissions,
permission checks, and in-memory permission registry management.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any

from aqos.security.base import (
    SecurityDecision,
    SecurityPrincipal,
    SecurityResult,
    build_security_result,
    validate_attributes,
    validate_non_empty_string,
    validate_string,
    validate_string_list,
)


class PermissionEffect(str, Enum):
    """Supported permission effects."""

    ALLOW = "allow"
    DENY = "deny"


@dataclass(frozen=True)
class Permission:
    """Single permission definition."""

    name: str
    description: str = ""
    attributes: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        validate_permission_name(self.name)
        validate_string(self.description, "Description")
        validate_attributes(self.attributes)

    def matches(self, permission_name: str) -> bool:
        """Return whether this permission matches a requested permission."""
        requested = validate_permission_name(permission_name)
        current = self.name.strip()

        return current == "*" or current == requested

    def to_dict(self) -> dict[str, Any]:
        """Convert permission into a serializable dictionary."""
        return {
            "name": self.name.strip(),
            "description": self.description.strip(),
            "attributes": dict(self.attributes),
        }


@dataclass(frozen=True)
class Role:
    """Role with assigned permissions."""

    name: str
    permissions: list[str] = field(default_factory=list)
    description: str = ""
    attributes: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        validate_role_name(self.name)
        validate_permission_list(self.permissions)
        validate_string(self.description, "Description")
        validate_attributes(self.attributes)

    def has_permission(self, permission_name: str) -> bool:
        """Return whether role has permission."""
        requested = validate_permission_name(permission_name)

        return "*" in self.permissions or requested in [
            permission.strip()
            for permission in self.permissions
        ]

    def to_dict(self) -> dict[str, Any]:
        """Convert role into a serializable dictionary."""
        return {
            "name": self.name.strip(),
            "permissions": [
                permission.strip()
                for permission in self.permissions
            ],
            "description": self.description.strip(),
            "attributes": dict(self.attributes),
        }


@dataclass(frozen=True)
class PermissionCheck:
    """Permission check request."""

    principal: SecurityPrincipal
    permission: str
    resource: str = ""
    context: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not isinstance(self.principal, SecurityPrincipal):
            raise ValueError("Principal must be a SecurityPrincipal.")

        validate_permission_name(self.permission)
        validate_string(self.resource, "Resource")
        validate_attributes(self.context)

    def to_dict(self) -> dict[str, Any]:
        """Convert check into a serializable dictionary."""
        return {
            "principal": self.principal.to_dict(),
            "permission": self.permission.strip(),
            "resource": self.resource.strip(),
            "context": dict(self.context),
        }


@dataclass(frozen=True)
class PermissionCheckResult:
    """Permission check result."""

    allowed: bool
    permission: str
    principal_id: str
    reason: str = ""
    matched_roles: list[str] = field(default_factory=list)
    missing_roles: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not isinstance(self.allowed, bool):
            raise ValueError("Allowed must be a boolean.")

        validate_permission_name(self.permission)
        validate_non_empty_string(self.principal_id, "Principal ID")
        validate_string(self.reason, "Reason")
        validate_string_list(self.matched_roles, "Matched roles")
        validate_string_list(self.missing_roles, "Missing roles")
        validate_attributes(self.metadata)

    @property
    def denied(self) -> bool:
        """Return whether permission was denied."""
        return not self.allowed

    def to_security_result(self) -> SecurityResult:
        """Convert permission result into a security result."""
        return build_security_result(
            decision=SecurityDecision.ALLOW if self.allowed else SecurityDecision.DENY,
            reason=self.reason,
            risk_level="low" if self.allowed else "medium",
            principal_id=self.principal_id,
            metadata={
                "permission": self.permission,
                "matched_roles": [
                    role.strip()
                    for role in self.matched_roles
                ],
                "missing_roles": [
                    role.strip()
                    for role in self.missing_roles
                ],
                **self.metadata,
            },
        )

    def to_dict(self) -> dict[str, Any]:
        """Convert permission result into a serializable dictionary."""
        return {
            "allowed": self.allowed,
            "denied": self.denied,
            "permission": self.permission.strip(),
            "principal_id": self.principal_id.strip(),
            "reason": self.reason.strip(),
            "matched_roles": [
                role.strip()
                for role in self.matched_roles
            ],
            "missing_roles": [
                role.strip()
                for role in self.missing_roles
            ],
            "metadata": dict(self.metadata),
        }


@dataclass
class PermissionRegistry:
    """In-memory role and permission registry."""

    permissions: dict[str, Permission] = field(default_factory=dict)
    roles: dict[str, Role] = field(default_factory=dict)

    def register_permission(self, permission: Permission) -> Permission:
        """Register a permission."""
        if not isinstance(permission, Permission):
            raise ValueError("Permission must be a Permission.")

        if permission.name in self.permissions:
            raise ValueError("Permission already exists.")

        self.permissions[permission.name] = permission
        return permission

    def upsert_permission(self, permission: Permission) -> Permission:
        """Create or replace a permission."""
        if not isinstance(permission, Permission):
            raise ValueError("Permission must be a Permission.")

        self.permissions[permission.name] = permission
        return permission

    def register_role(self, role: Role) -> Role:
        """Register a role."""
        if not isinstance(role, Role):
            raise ValueError("Role must be a Role.")

        if role.name in self.roles:
            raise ValueError("Role already exists.")

        self.roles[role.name] = role
        return role

    def upsert_role(self, role: Role) -> Role:
        """Create or replace a role."""
        if not isinstance(role, Role):
            raise ValueError("Role must be a Role.")

        self.roles[role.name] = role
        return role

    def get_permission(self, name: str) -> Permission | None:
        """Get permission by name."""
        normalized = validate_permission_name(name)

        return self.permissions.get(normalized)

    def get_role(self, name: str) -> Role | None:
        """Get role by name."""
        normalized = validate_role_name(name)

        return self.roles.get(normalized)

    def get_required_permission(self, name: str) -> Permission:
        """Get permission or raise."""
        permission = self.get_permission(name)

        if permission is None:
            raise ValueError("Permission not found.")

        return permission

    def get_required_role(self, name: str) -> Role:
        """Get role or raise."""
        role = self.get_role(name)

        if role is None:
            raise ValueError("Role not found.")

        return role

    def list_permissions(self) -> list[Permission]:
        """List permissions."""
        return list(self.permissions.values())

    def list_roles(self) -> list[Role]:
        """List roles."""
        return list(self.roles.values())

    def check_permission(
        self,
        principal: SecurityPrincipal,
        permission: str,
        *,
        resource: str = "",
        context: dict[str, Any] | None = None,
    ) -> PermissionCheckResult:
        """Check whether principal has permission."""
        check = PermissionCheck(
            principal=principal,
            permission=permission,
            resource=resource,
            context=context or {},
        )

        return evaluate_permission_check(check, self)

    def summary(self) -> dict[str, Any]:
        """Return registry summary."""
        return {
            "permissions": len(self.permissions),
            "roles": len(self.roles),
            "permission_names": list(self.permissions.keys()),
            "role_names": list(self.roles.keys()),
        }

    def clear(self) -> None:
        """Clear registry."""
        self.permissions.clear()
        self.roles.clear()


def normalize_permission_effect(effect: PermissionEffect | str) -> PermissionEffect:
    """Normalize permission effect."""
    if isinstance(effect, PermissionEffect):
        return effect

    normalized = validate_non_empty_string(effect, "Permission effect").lower()

    try:
        return PermissionEffect(normalized)
    except ValueError as exc:
        valid = ", ".join(item.value for item in PermissionEffect)
        raise ValueError(
            f"Invalid permission effect '{effect}'. Valid effects: {valid}.",
        ) from exc


def validate_permission_name(permission_name: str) -> str:
    """Validate permission name."""
    normalized = validate_non_empty_string(permission_name, "Permission name")

    if " " in normalized:
        raise ValueError("Permission name cannot contain spaces.")

    return normalized


def validate_role_name(role_name: str) -> str:
    """Validate role name."""
    normalized = validate_non_empty_string(role_name, "Role name")

    if " " in normalized:
        raise ValueError("Role name cannot contain spaces.")

    return normalized


def validate_permission_list(permissions: list[str]) -> list[str]:
    """Validate list of permission names."""
    if not isinstance(permissions, list):
        raise ValueError("Permissions must be a list.")

    return [
        validate_permission_name(permission)
        for permission in permissions
    ]


def build_permission(
    *,
    name: str,
    description: str = "",
    attributes: dict[str, Any] | None = None,
) -> Permission:
    """Build permission."""
    return Permission(
        name=name,
        description=description,
        attributes=attributes or {},
    )


def build_role(
    *,
    name: str,
    permissions: list[str] | None = None,
    description: str = "",
    attributes: dict[str, Any] | None = None,
) -> Role:
    """Build role."""
    return Role(
        name=name,
        permissions=permissions or [],
        description=description,
        attributes=attributes or {},
    )


def build_permission_check(
    *,
    principal: SecurityPrincipal,
    permission: str,
    resource: str = "",
    context: dict[str, Any] | None = None,
) -> PermissionCheck:
    """Build permission check."""
    return PermissionCheck(
        principal=principal,
        permission=permission,
        resource=resource,
        context=context or {},
    )


def evaluate_permission_check(
    check: PermissionCheck,
    registry: PermissionRegistry,
) -> PermissionCheckResult:
    """Evaluate a permission check against registry roles."""
    if not isinstance(check, PermissionCheck):
        raise ValueError("Check must be a PermissionCheck.")

    if not isinstance(registry, PermissionRegistry):
        raise ValueError("Registry must be a PermissionRegistry.")

    matched_roles: list[str] = []
    missing_roles: list[str] = []

    for role_name in check.principal.roles:
        role = registry.get_role(role_name)

        if role is None:
            missing_roles.append(role_name)
            continue

        if role.has_permission(check.permission):
            matched_roles.append(role.name)

    if matched_roles:
        return PermissionCheckResult(
            allowed=True,
            permission=check.permission,
            principal_id=check.principal.principal_id,
            reason="Permission granted.",
            matched_roles=matched_roles,
            missing_roles=missing_roles,
            metadata={
                "resource": check.resource,
                "context": dict(check.context),
            },
        )

    return PermissionCheckResult(
        allowed=False,
        permission=check.permission,
        principal_id=check.principal.principal_id,
        reason="Permission denied.",
        matched_roles=matched_roles,
        missing_roles=missing_roles,
        metadata={
            "resource": check.resource,
            "context": dict(check.context),
        },
    )


def require_permission(
    principal: SecurityPrincipal,
    permission: str,
    registry: PermissionRegistry,
    *,
    resource: str = "",
    context: dict[str, Any] | None = None,
) -> SecurityResult:
    """Return security result for required permission."""
    result = registry.check_permission(
        principal,
        permission,
        resource=resource,
        context=context or {},
    )

    return result.to_security_result()


def build_default_permission_registry() -> PermissionRegistry:
    """Build default AQOS permission registry."""
    registry = PermissionRegistry()

    default_permissions = [
        build_permission(name="market.read", description="Read market state."),
        build_permission(name="strategy.read", description="Read strategy signals."),
        build_permission(name="risk.read", description="Read risk analysis."),
        build_permission(name="trade.execute", description="Execute trades."),
        build_permission(name="research.write", description="Write research records."),
        build_permission(name="memory.write", description="Write memory records."),
        build_permission(name="admin.manage", description="Manage system resources."),
        build_permission(name="*", description="Wildcard permission."),
    ]

    for permission in default_permissions:
        registry.register_permission(permission)

    default_roles = [
        build_role(
            name="viewer",
            permissions=[
                "market.read",
                "strategy.read",
                "risk.read",
            ],
            description="Read-only role.",
        ),
        build_role(
            name="trader",
            permissions=[
                "market.read",
                "strategy.read",
                "risk.read",
                "trade.execute",
            ],
            description="Trading role.",
        ),
        build_role(
            name="researcher",
            permissions=[
                "market.read",
                "strategy.read",
                "research.write",
                "memory.write",
            ],
            description="Research role.",
        ),
        build_role(
            name="admin",
            permissions=[
                "*",
            ],
            description="Administrator role.",
        ),
    ]

    for role in default_roles:
        registry.register_role(role)

    return registry