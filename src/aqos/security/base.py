"""
AQOS security base primitives.

This module contains dependency-free security building blocks used by API
guards, CLI guards, permission checks, audit logs, and governance policies.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class SecurityDecision(str, Enum):
    """Supported security decisions."""

    ALLOW = "allow"
    DENY = "deny"


class SecurityRiskLevel(str, Enum):
    """Supported security risk levels."""

    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


@dataclass(frozen=True)
class SecurityPrincipal:
    """Authenticated or anonymous security principal."""

    principal_id: str
    principal_type: str = "user"
    roles: list[str] = field(default_factory=list)
    attributes: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        validate_non_empty_string(self.principal_id, "Principal ID")
        validate_non_empty_string(self.principal_type, "Principal type")
        validate_string_list(self.roles, "Roles")
        validate_attributes(self.attributes)

    def has_role(self, role: str) -> bool:
        """Return whether principal has a role."""
        normalized_role = validate_non_empty_string(role, "Role")

        return normalized_role in [
            item.strip()
            for item in self.roles
        ]

    def to_dict(self) -> dict[str, Any]:
        """Convert principal into a serializable dictionary."""
        return {
            "principal_id": self.principal_id.strip(),
            "principal_type": self.principal_type.strip(),
            "roles": [
                role.strip()
                for role in self.roles
            ],
            "attributes": dict(self.attributes),
        }


@dataclass(frozen=True)
class SecurityResult:
    """Result of a security decision."""

    decision: SecurityDecision | str
    reason: str = ""
    risk_level: SecurityRiskLevel | str = SecurityRiskLevel.LOW
    principal_id: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        normalize_security_decision(self.decision)
        validate_string(self.reason, "Reason")
        normalize_risk_level(self.risk_level)
        validate_attributes(self.metadata)

        if self.principal_id is not None:
            validate_non_empty_string(self.principal_id, "Principal ID")

    @property
    def allowed(self) -> bool:
        """Return whether result allows access."""
        return normalize_security_decision(self.decision) == SecurityDecision.ALLOW

    @property
    def denied(self) -> bool:
        """Return whether result denies access."""
        return normalize_security_decision(self.decision) == SecurityDecision.DENY

    def to_dict(self) -> dict[str, Any]:
        """Convert result into a serializable dictionary."""
        payload = {
            "decision": normalize_security_decision(self.decision).value,
            "allowed": self.allowed,
            "denied": self.denied,
            "reason": self.reason.strip(),
            "risk_level": normalize_risk_level(self.risk_level).value,
            "principal_id": self.principal_id.strip() if self.principal_id else None,
            "metadata": dict(self.metadata),
        }

        return {
            key: value
            for key, value in payload.items()
            if value is not None
        }


def validate_string(value: str, field_name: str) -> str:
    """Validate a string value."""
    if not isinstance(value, str):
        raise ValueError(f"{field_name} must be a string.")

    return value


def validate_non_empty_string(value: str, field_name: str) -> str:
    """Validate a non-empty string value."""
    validate_string(value, field_name)

    if not value.strip():
        raise ValueError(f"{field_name} must be a non-empty string.")

    return value.strip()


def validate_attributes(attributes: dict[str, Any]) -> dict[str, Any]:
    """Validate attributes dictionary."""
    if not isinstance(attributes, dict):
        raise ValueError("Attributes must be a dictionary.")

    return attributes


def validate_string_list(values: list[str], field_name: str) -> list[str]:
    """Validate a list of strings."""
    if not isinstance(values, list):
        raise ValueError(f"{field_name} must be a list.")

    for value in values:
        validate_non_empty_string(value, field_name)

    return [
        value.strip()
        for value in values
    ]


def normalize_security_decision(decision: SecurityDecision | str) -> SecurityDecision:
    """Normalize security decision."""
    if isinstance(decision, SecurityDecision):
        return decision

    normalized = validate_non_empty_string(decision, "Security decision").lower()

    try:
        return SecurityDecision(normalized)
    except ValueError as exc:
        valid = ", ".join(item.value for item in SecurityDecision)
        raise ValueError(
            f"Invalid security decision '{decision}'. Valid decisions: {valid}.",
        ) from exc


def normalize_risk_level(risk_level: SecurityRiskLevel | str) -> SecurityRiskLevel:
    """Normalize security risk level."""
    if isinstance(risk_level, SecurityRiskLevel):
        return risk_level

    normalized = validate_non_empty_string(risk_level, "Risk level").lower()

    try:
        return SecurityRiskLevel(normalized)
    except ValueError as exc:
        valid = ", ".join(item.value for item in SecurityRiskLevel)
        raise ValueError(
            f"Invalid risk level '{risk_level}'. Valid risk levels: {valid}.",
        ) from exc


def build_security_principal(
    *,
    principal_id: str,
    principal_type: str = "user",
    roles: list[str] | None = None,
    attributes: dict[str, Any] | None = None,
) -> SecurityPrincipal:
    """Build a security principal."""
    return SecurityPrincipal(
        principal_id=principal_id,
        principal_type=principal_type,
        roles=roles or [],
        attributes=attributes or {},
    )


def build_security_result(
    *,
    decision: SecurityDecision | str,
    reason: str = "",
    risk_level: SecurityRiskLevel | str = SecurityRiskLevel.LOW,
    principal_id: str | None = None,
    metadata: dict[str, Any] | None = None,
) -> SecurityResult:
    """Build a security result."""
    return SecurityResult(
        decision=decision,
        reason=reason,
        risk_level=risk_level,
        principal_id=principal_id,
        metadata=metadata or {},
    )