"""
AQOS secure runtime context primitives.

This module provides dependency-free runtime context objects for carrying
authenticated principal, scopes, permissions, request metadata, environment,
and security state across API, CLI, agents, and services.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import Enum
from typing import Any
from uuid import uuid4

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
from aqos.security.tokens import TokenValidationResult, normalize_token_status


class RuntimeEnvironment(str, Enum):
    """Supported runtime environments."""

    LOCAL = "local"
    DEVELOPMENT = "development"
    TEST = "test"
    STAGING = "staging"
    PRODUCTION = "production"


class SecurityContextState(str, Enum):
    """Supported security context states."""

    ANONYMOUS = "anonymous"
    AUTHENTICATED = "authenticated"
    DENIED = "denied"


@dataclass(frozen=True)
class SecurityRuntimeContext:
    """Secure runtime context."""

    context_id: str
    principal: SecurityPrincipal | None = None
    environment: RuntimeEnvironment | str = RuntimeEnvironment.LOCAL
    state: SecurityContextState | str = SecurityContextState.ANONYMOUS
    request_id: str = ""
    source_ip: str = ""
    scopes: list[str] = field(default_factory=list)
    permissions: list[str] = field(default_factory=list)
    created_at: str = field(default_factory=lambda: datetime.now(UTC).isoformat())
    attributes: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        validate_context_id(self.context_id)
        normalize_runtime_environment(self.environment)
        normalize_context_state(self.state)
        validate_string(self.request_id, "Request ID")
        validate_string(self.source_ip, "Source IP")
        validate_string_list(self.scopes, "Scopes")
        validate_string_list(self.permissions, "Permissions")
        validate_non_empty_string(self.created_at, "Created at")
        validate_attributes(self.attributes)

        if self.principal is not None and not isinstance(self.principal, SecurityPrincipal):
            raise ValueError("Principal must be a SecurityPrincipal.")

    @property
    def authenticated(self) -> bool:
        """Return whether context is authenticated."""
        return (
            self.principal is not None
            and normalize_context_state(self.state) == SecurityContextState.AUTHENTICATED
        )

    @property
    def anonymous(self) -> bool:
        """Return whether context is anonymous."""
        return normalize_context_state(self.state) == SecurityContextState.ANONYMOUS

    @property
    def denied(self) -> bool:
        """Return whether context is denied."""
        return normalize_context_state(self.state) == SecurityContextState.DENIED

    @property
    def principal_id(self) -> str | None:
        """Return principal ID if available."""
        if self.principal is None:
            return None

        return self.principal.principal_id.strip()

    def has_role(self, role: str) -> bool:
        """Return whether context principal has role."""
        return context_has_role(self, role)

    def has_scope(self, scope: str) -> bool:
        """Return whether context has scope."""
        return context_has_scope(self, scope)

    def has_permission(self, permission: str) -> bool:
        """Return whether context has permission."""
        return context_has_permission(self, permission)

    def with_state(
        self,
        state: SecurityContextState | str,
        *,
        attributes: dict[str, Any] | None = None,
    ) -> "SecurityRuntimeContext":
        """Return copy of context with a new state."""
        merged_attributes = merge_context_attributes(
            self.attributes,
            attributes or {},
        )

        return SecurityRuntimeContext(
            context_id=self.context_id,
            principal=self.principal,
            environment=self.environment,
            state=state,
            request_id=self.request_id,
            source_ip=self.source_ip,
            scopes=self.scopes,
            permissions=self.permissions,
            created_at=self.created_at,
            attributes=merged_attributes,
        )

    def to_security_result(self) -> SecurityResult:
        """Convert context into a security result."""
        if self.denied:
            return build_security_result(
                decision=SecurityDecision.DENY,
                reason="Security context denied.",
                risk_level="high",
                principal_id=self.principal_id,
                metadata=self.to_dict(),
            )

        return build_security_result(
            decision=SecurityDecision.ALLOW,
            reason="Security context authenticated."
            if self.authenticated
            else "Security context anonymous.",
            risk_level="low",
            principal_id=self.principal_id,
            metadata=self.to_dict(),
        )

    def to_dict(self) -> dict[str, Any]:
        """Convert context into a serializable dictionary."""
        return {
            "context_id": self.context_id.strip(),
            "principal": self.principal.to_dict() if self.principal else None,
            "principal_id": self.principal_id,
            "environment": normalize_runtime_environment(self.environment).value,
            "state": normalize_context_state(self.state).value,
            "authenticated": self.authenticated,
            "anonymous": self.anonymous,
            "denied": self.denied,
            "request_id": self.request_id.strip(),
            "source_ip": self.source_ip.strip(),
            "scopes": [
                scope.strip()
                for scope in self.scopes
            ],
            "permissions": [
                permission.strip()
                for permission in self.permissions
            ],
            "created_at": self.created_at.strip(),
            "attributes": dict(self.attributes),
        }


@dataclass
class SecurityContextManager:
    """In-memory security runtime context manager."""

    contexts: dict[str, SecurityRuntimeContext] = field(default_factory=dict)

    def register_context(self, context: SecurityRuntimeContext) -> SecurityRuntimeContext:
        """Register a security context."""
        if not isinstance(context, SecurityRuntimeContext):
            raise ValueError("Context must be a SecurityRuntimeContext.")

        if context.context_id in self.contexts:
            raise ValueError("Security context already exists.")

        self.contexts[context.context_id] = context
        return context

    def upsert_context(self, context: SecurityRuntimeContext) -> SecurityRuntimeContext:
        """Create or replace a security context."""
        if not isinstance(context, SecurityRuntimeContext):
            raise ValueError("Context must be a SecurityRuntimeContext.")

        self.contexts[context.context_id] = context
        return context

    def create_context(
        self,
        *,
        context_id: str | None = None,
        principal: SecurityPrincipal | None = None,
        environment: RuntimeEnvironment | str = RuntimeEnvironment.LOCAL,
        state: SecurityContextState | str | None = None,
        request_id: str = "",
        source_ip: str = "",
        scopes: list[str] | None = None,
        permissions: list[str] | None = None,
        attributes: dict[str, Any] | None = None,
    ) -> SecurityRuntimeContext:
        """Create and register a security context."""
        context = build_security_runtime_context(
            context_id=context_id or build_context_id(),
            principal=principal,
            environment=environment,
            state=state
            or (
                SecurityContextState.AUTHENTICATED
                if principal is not None
                else SecurityContextState.ANONYMOUS
            ),
            request_id=request_id,
            source_ip=source_ip,
            scopes=scopes or [],
            permissions=permissions or [],
            attributes=attributes or {},
        )

        return self.register_context(context)

    def get_context(self, context_id: str) -> SecurityRuntimeContext | None:
        """Get context by ID."""
        normalized = validate_context_id(context_id)

        return self.contexts.get(normalized)

    def get_required_context(self, context_id: str) -> SecurityRuntimeContext:
        """Get context by ID or raise."""
        context = self.get_context(context_id)

        if context is None:
            raise ValueError("Security context not found.")

        return context

    def set_context_state(
        self,
        context_id: str,
        state: SecurityContextState | str,
        *,
        attributes: dict[str, Any] | None = None,
    ) -> SecurityRuntimeContext:
        """Update context state."""
        context = self.get_required_context(context_id)
        updated = context.with_state(
            state,
            attributes=attributes or {},
        )

        self.contexts[context.context_id] = updated
        return updated

    def deny_context(
        self,
        context_id: str,
        *,
        reason: str | None = None,
    ) -> SecurityRuntimeContext:
        """Mark context as denied."""
        attributes = {}

        if reason is not None:
            attributes["deny_reason"] = validate_non_empty_string(reason, "Reason")

        return self.set_context_state(
            context_id,
            SecurityContextState.DENIED,
            attributes=attributes,
    )

    def list_contexts(self) -> list[SecurityRuntimeContext]:
        """List contexts."""
        return list(self.contexts.values())

    def filter_by_principal(self, principal_id: str) -> list[SecurityRuntimeContext]:
        """Return contexts for a principal."""
        normalized = validate_non_empty_string(principal_id, "Principal ID")

        return [
            context
            for context in self.contexts.values()
            if context.principal_id == normalized
        ]

    def summary(self) -> dict[str, Any]:
        """Return context manager summary."""
        states: dict[str, int] = {}
        environments: dict[str, int] = {}

        for context in self.contexts.values():
            state = normalize_context_state(context.state).value
            environment = normalize_runtime_environment(context.environment).value

            states[state] = states.get(state, 0) + 1
            environments[environment] = environments.get(environment, 0) + 1

        return {
            "contexts": len(self.contexts),
            "states": states,
            "environments": environments,
            "context_ids": list(self.contexts.keys()),
        }

    def clear(self) -> None:
        """Clear all contexts."""
        self.contexts.clear()


def normalize_runtime_environment(
    environment: RuntimeEnvironment | str,
) -> RuntimeEnvironment:
    """Normalize runtime environment."""
    if isinstance(environment, RuntimeEnvironment):
        return environment

    normalized = validate_non_empty_string(environment, "Runtime environment").lower()

    try:
        return RuntimeEnvironment(normalized)
    except ValueError as exc:
        valid = ", ".join(item.value for item in RuntimeEnvironment)
        raise ValueError(
            f"Invalid runtime environment '{environment}'. Valid environments: {valid}.",
        ) from exc


def normalize_context_state(
    state: SecurityContextState | str,
) -> SecurityContextState:
    """Normalize security context state."""
    if isinstance(state, SecurityContextState):
        return state

    normalized = validate_non_empty_string(state, "Security context state").lower()

    try:
        return SecurityContextState(normalized)
    except ValueError as exc:
        valid = ", ".join(item.value for item in SecurityContextState)
        raise ValueError(
            f"Invalid security context state '{state}'. Valid states: {valid}.",
        ) from exc


def validate_context_id(context_id: str) -> str:
    """Validate security context ID."""
    normalized = validate_non_empty_string(context_id, "Context ID")

    if " " in normalized:
        raise ValueError("Context ID cannot contain spaces.")

    return normalized


def build_context_id(prefix: str = "ctx") -> str:
    """Build security context ID."""
    normalized_prefix = validate_non_empty_string(prefix, "Context ID prefix")

    if " " in normalized_prefix:
        raise ValueError("Context ID prefix cannot contain spaces.")

    return f"{normalized_prefix}-{uuid4().hex}"


def merge_context_attributes(
    base_attributes: dict[str, Any],
    extra_attributes: dict[str, Any],
) -> dict[str, Any]:
    """Merge security context attributes."""
    validate_attributes(base_attributes)
    validate_attributes(extra_attributes)

    return {
        **base_attributes,
        **extra_attributes,
    }


def context_has_role(
    context: SecurityRuntimeContext,
    role: str,
) -> bool:
    """Return whether context principal has role."""
    if not isinstance(context, SecurityRuntimeContext):
        raise ValueError("Context must be a SecurityRuntimeContext.")

    if context.principal is None:
        return False

    return context.principal.has_role(role)


def context_has_scope(
    context: SecurityRuntimeContext,
    scope: str,
) -> bool:
    """Return whether context has scope."""
    if not isinstance(context, SecurityRuntimeContext):
        raise ValueError("Context must be a SecurityRuntimeContext.")

    normalized_scope = validate_non_empty_string(scope, "Scope")

    return "*" in context.scopes or normalized_scope in [
        item.strip()
        for item in context.scopes
    ]


def context_has_permission(
    context: SecurityRuntimeContext,
    permission: str,
) -> bool:
    """Return whether context has permission."""
    if not isinstance(context, SecurityRuntimeContext):
        raise ValueError("Context must be a SecurityRuntimeContext.")

    normalized_permission = validate_non_empty_string(permission, "Permission")

    return "*" in context.permissions or normalized_permission in [
        item.strip()
        for item in context.permissions
    ]


def build_security_runtime_context(
    *,
    context_id: str,
    principal: SecurityPrincipal | None = None,
    environment: RuntimeEnvironment | str = RuntimeEnvironment.LOCAL,
    state: SecurityContextState | str = SecurityContextState.ANONYMOUS,
    request_id: str = "",
    source_ip: str = "",
    scopes: list[str] | None = None,
    permissions: list[str] | None = None,
    created_at: str | None = None,
    attributes: dict[str, Any] | None = None,
) -> SecurityRuntimeContext:
    """Build security runtime context."""
    context_kwargs: dict[str, Any] = {
        "context_id": context_id,
        "principal": principal,
        "environment": environment,
        "state": state,
        "request_id": request_id,
        "source_ip": source_ip,
        "scopes": scopes or [],
        "permissions": permissions or [],
        "attributes": attributes or {},
    }

    if created_at is not None:
        context_kwargs["created_at"] = created_at

    return SecurityRuntimeContext(**context_kwargs)


def build_anonymous_context(
    *,
    context_id: str,
    environment: RuntimeEnvironment | str = RuntimeEnvironment.LOCAL,
    request_id: str = "",
    source_ip: str = "",
    attributes: dict[str, Any] | None = None,
) -> SecurityRuntimeContext:
    """Build anonymous security context."""
    return build_security_runtime_context(
        context_id=context_id,
        principal=None,
        environment=environment,
        state=SecurityContextState.ANONYMOUS,
        request_id=request_id,
        source_ip=source_ip,
        attributes=attributes or {},
    )


def build_authenticated_context(
    *,
    context_id: str,
    principal: SecurityPrincipal,
    environment: RuntimeEnvironment | str = RuntimeEnvironment.LOCAL,
    request_id: str = "",
    source_ip: str = "",
    scopes: list[str] | None = None,
    permissions: list[str] | None = None,
    attributes: dict[str, Any] | None = None,
) -> SecurityRuntimeContext:
    """Build authenticated security context."""
    if not isinstance(principal, SecurityPrincipal):
        raise ValueError("Principal must be a SecurityPrincipal.")

    return build_security_runtime_context(
        context_id=context_id,
        principal=principal,
        environment=environment,
        state=SecurityContextState.AUTHENTICATED,
        request_id=request_id,
        source_ip=source_ip,
        scopes=scopes or [],
        permissions=permissions or [],
        attributes=attributes or {},
    )


def build_context_from_token_validation(
    *,
    context_id: str,
    validation_result: TokenValidationResult,
    environment: RuntimeEnvironment | str = RuntimeEnvironment.LOCAL,
    request_id: str = "",
    source_ip: str = "",
    permissions: list[str] | None = None,
) -> SecurityRuntimeContext:
    """Build security context from token validation result."""
    if not isinstance(validation_result, TokenValidationResult):
        raise ValueError("Validation result must be a TokenValidationResult.")

    token_status = normalize_token_status(validation_result.status).value

    principal = None

    if validation_result.valid and validation_result.principal_id:
        principal = SecurityPrincipal(
            principal_id=validation_result.principal_id,
            principal_type="token",
            attributes={
                "token_id": validation_result.token_id,
                "token_status": token_status,
            },
        )

    return build_security_runtime_context(
        context_id=context_id,
        principal=principal,
        environment=environment,
        state=SecurityContextState.AUTHENTICATED
        if validation_result.valid
        else SecurityContextState.DENIED,
        request_id=request_id,
        source_ip=source_ip,
        scopes=validation_result.scopes,
        permissions=permissions or [],
        attributes={
            "token_id": validation_result.token_id,
            "token_status": token_status,
            "token_reason": validation_result.reason,
            **validation_result.metadata,
        },
    )