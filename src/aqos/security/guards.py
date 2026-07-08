"""
AQOS request guard and input sanitization primitives.

This module provides dependency-free request validation, payload sanitization,
blocked-pattern detection, and optional permission enforcement.
"""

from __future__ import annotations

import re
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
from aqos.security.permissions import (
    PermissionRegistry,
    require_permission,
)


class GuardAction(str, Enum):
    """Supported guard actions."""

    ALLOW = "allow"
    DENY = "deny"
    SANITIZE = "sanitize"


DEFAULT_BLOCKED_PATTERNS = [
    r"<script",
    r"</script",
    r"javascript:",
    r"onerror\s*=",
    r"onload\s*=",
    r"drop\s+table",
    r"delete\s+from",
    r"insert\s+into",
    r"update\s+\w+\s+set",
    r"union\s+select",
    r"--",
]


@dataclass(frozen=True)
class SanitizationResult:
    """Result of sanitizing an input value."""

    value: Any
    changed: bool = False
    violations: list[str] = field(default_factory=list)

    def __post_init__(self) -> None:
        if not isinstance(self.changed, bool):
            raise ValueError("Changed must be a boolean.")

        validate_string_list(self.violations, "Violations")

    def to_dict(self) -> dict[str, Any]:
        """Convert sanitization result into dictionary."""
        return {
            "value": self.value,
            "changed": self.changed,
            "violations": [
                violation.strip()
                for violation in self.violations
            ],
        }


@dataclass(frozen=True)
class GuardedRequest:
    """Request object used by security guards."""

    request_id: str
    method: str
    path: str
    principal: SecurityPrincipal | None = None
    headers: dict[str, Any] = field(default_factory=dict)
    query_params: dict[str, Any] = field(default_factory=dict)
    body: dict[str, Any] = field(default_factory=dict)
    source_ip: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        validate_non_empty_string(self.request_id, "Request ID")
        validate_http_method(self.method)
        validate_request_path(self.path)
        validate_attributes(self.headers)
        validate_attributes(self.query_params)
        validate_attributes(self.body)
        validate_string(self.source_ip, "Source IP")
        validate_attributes(self.metadata)

        if self.principal is not None and not isinstance(self.principal, SecurityPrincipal):
            raise ValueError("Principal must be a SecurityPrincipal.")

    def to_dict(self) -> dict[str, Any]:
        """Convert guarded request into dictionary."""
        return {
            "request_id": self.request_id.strip(),
            "method": self.method.strip().upper(),
            "path": self.path.strip(),
            "principal": self.principal.to_dict() if self.principal else None,
            "headers": dict(self.headers),
            "query_params": dict(self.query_params),
            "body": dict(self.body),
            "source_ip": self.source_ip.strip(),
            "metadata": dict(self.metadata),
        }


@dataclass(frozen=True)
class RequestGuardConfig:
    """Request guard configuration."""

    allowed_methods: list[str] = field(default_factory=lambda: ["GET", "POST"])
    require_principal: bool = False
    required_permission: str | None = None
    sanitize_inputs: bool = True
    deny_on_violation: bool = True
    max_string_length: int = 5000
    blocked_patterns: list[str] = field(default_factory=lambda: list(DEFAULT_BLOCKED_PATTERNS))
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        validate_http_method_list(self.allowed_methods)

        if not isinstance(self.require_principal, bool):
            raise ValueError("Require principal must be a boolean.")

        if self.required_permission is not None:
            validate_non_empty_string(self.required_permission, "Required permission")

        if not isinstance(self.sanitize_inputs, bool):
            raise ValueError("Sanitize inputs must be a boolean.")

        if not isinstance(self.deny_on_violation, bool):
            raise ValueError("Deny on violation must be a boolean.")

        validate_max_string_length(self.max_string_length)
        validate_string_list(self.blocked_patterns, "Blocked patterns")
        validate_attributes(self.metadata)


@dataclass(frozen=True)
class RequestGuardResult:
    """Result of guarding a request."""

    allowed: bool
    request_id: str
    reason: str = ""
    sanitized_request: GuardedRequest | None = None
    violations: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not isinstance(self.allowed, bool):
            raise ValueError("Allowed must be a boolean.")

        validate_non_empty_string(self.request_id, "Request ID")
        validate_string(self.reason, "Reason")
        validate_string_list(self.violations, "Violations")
        validate_attributes(self.metadata)

        if self.sanitized_request is not None and not isinstance(self.sanitized_request, GuardedRequest):
            raise ValueError("Sanitized request must be a GuardedRequest.")

    @property
    def denied(self) -> bool:
        """Return whether request was denied."""
        return not self.allowed

    def to_security_result(self) -> SecurityResult:
        """Convert guard result into security result."""
        return build_security_result(
            decision=SecurityDecision.ALLOW if self.allowed else SecurityDecision.DENY,
            reason=self.reason,
            risk_level="low" if self.allowed else "high",
            principal_id=self.sanitized_request.principal.principal_id
            if self.sanitized_request and self.sanitized_request.principal
            else None,
            metadata={
                "request_id": self.request_id,
                "violations": [
                    violation.strip()
                    for violation in self.violations
                ],
                **self.metadata,
            },
        )

    def to_dict(self) -> dict[str, Any]:
        """Convert guard result into dictionary."""
        return {
            "allowed": self.allowed,
            "denied": self.denied,
            "request_id": self.request_id.strip(),
            "reason": self.reason.strip(),
            "sanitized_request": self.sanitized_request.to_dict()
            if self.sanitized_request
            else None,
            "violations": [
                violation.strip()
                for violation in self.violations
            ],
            "metadata": dict(self.metadata),
        }


@dataclass
class RequestGuard:
    """Dependency-free request guard."""

    config: RequestGuardConfig = field(default_factory=RequestGuardConfig)
    permission_registry: PermissionRegistry | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.config, RequestGuardConfig):
            raise ValueError("Config must be a RequestGuardConfig.")

        if self.permission_registry is not None and not isinstance(self.permission_registry, PermissionRegistry):
            raise ValueError("Permission registry must be a PermissionRegistry.")

    def guard(self, request: GuardedRequest) -> RequestGuardResult:
        """Guard a request."""
        if not isinstance(request, GuardedRequest):
            raise ValueError("Request must be a GuardedRequest.")

        method = request.method.strip().upper()

        if method not in [
            item.strip().upper()
            for item in self.config.allowed_methods
        ]:
            return RequestGuardResult(
                allowed=False,
                request_id=request.request_id,
                reason="HTTP method is not allowed.",
                sanitized_request=request,
                violations=[
                    "method_not_allowed",
                ],
            )

        if self.config.require_principal and request.principal is None:
            return RequestGuardResult(
                allowed=False,
                request_id=request.request_id,
                reason="Principal is required.",
                sanitized_request=request,
                violations=[
                    "principal_required",
                ],
            )

        sanitized_request, violations, changed = sanitize_guarded_request(
            request,
            max_string_length=self.config.max_string_length,
            blocked_patterns=self.config.blocked_patterns,
        )

        if violations and self.config.deny_on_violation:
            return RequestGuardResult(
                allowed=False,
                request_id=request.request_id,
                reason="Request contains blocked input.",
                sanitized_request=sanitized_request,
                violations=violations,
                metadata={
                    "changed": changed,
                },
            )

        if self.config.required_permission is not None:
            if sanitized_request.principal is None:
                return RequestGuardResult(
                    allowed=False,
                    request_id=request.request_id,
                    reason="Principal is required for permission check.",
                    sanitized_request=sanitized_request,
                    violations=[
                        "principal_required",
                    ],
                    metadata={
                        "changed": changed,
                    },
                )

            if self.permission_registry is None:
                return RequestGuardResult(
                    allowed=False,
                    request_id=request.request_id,
                    reason="Permission registry is required.",
                    sanitized_request=sanitized_request,
                    violations=[
                        "permission_registry_required",
                    ],
                    metadata={
                        "changed": changed,
                    },
                )

            permission_result = require_permission(
                sanitized_request.principal,
                self.config.required_permission,
                self.permission_registry,
                resource=sanitized_request.path,
                context={
                    "method": sanitized_request.method,
                    "source_ip": sanitized_request.source_ip,
                },
            )

            if permission_result.denied:
                return RequestGuardResult(
                    allowed=False,
                    request_id=request.request_id,
                    reason=permission_result.reason,
                    sanitized_request=sanitized_request,
                    violations=[
                        "permission_denied",
                    ],
                    metadata={
                        "changed": changed,
                        "permission": self.config.required_permission,
                    },
                )

        return RequestGuardResult(
            allowed=True,
            request_id=request.request_id,
            reason="Request allowed.",
            sanitized_request=sanitized_request,
            violations=violations,
            metadata={
                "changed": changed,
            },
        )


def validate_http_method(method: str) -> str:
    """Validate HTTP method."""
    normalized = validate_non_empty_string(method, "HTTP method").upper()

    if " " in normalized:
        raise ValueError("HTTP method cannot contain spaces.")

    return normalized


def validate_http_method_list(methods: list[str]) -> list[str]:
    """Validate allowed HTTP method list."""
    if not isinstance(methods, list):
        raise ValueError("Allowed methods must be a list.")

    return [
        validate_http_method(method)
        for method in methods
    ]


def validate_request_path(path: str) -> str:
    """Validate request path."""
    normalized = validate_non_empty_string(path, "Request path")

    if not normalized.startswith("/"):
        raise ValueError("Request path must start with '/'.")

    return normalized


def validate_max_string_length(max_string_length: int) -> int:
    """Validate max string length."""
    if (
        isinstance(max_string_length, bool)
        or not isinstance(max_string_length, int)
        or max_string_length <= 0
    ):
        raise ValueError("Max string length must be a positive integer.")

    return max_string_length


def normalize_guard_action(action: GuardAction | str) -> GuardAction:
    """Normalize guard action."""
    if isinstance(action, GuardAction):
        return action

    normalized = validate_non_empty_string(action, "Guard action").lower()

    try:
        return GuardAction(normalized)
    except ValueError as exc:
        valid = ", ".join(item.value for item in GuardAction)
        raise ValueError(f"Invalid guard action '{action}'. Valid actions: {valid}.") from exc


def contains_blocked_pattern(
    value: str,
    blocked_patterns: list[str] | None = None,
) -> list[str]:
    """Return blocked patterns found in a string."""
    validate_string(value, "Value")
    patterns = blocked_patterns or DEFAULT_BLOCKED_PATTERNS
    validate_string_list(patterns, "Blocked patterns")

    violations: list[str] = []

    for pattern in patterns:
        if re.search(pattern, value, flags=re.IGNORECASE):
            violations.append(pattern)

    return violations


def sanitize_string(
    value: str,
    *,
    max_string_length: int = 5000,
    blocked_patterns: list[str] | None = None,
) -> SanitizationResult:
    """Sanitize a string value."""
    validate_string(value, "Value")
    validate_max_string_length(max_string_length)

    patterns = blocked_patterns or DEFAULT_BLOCKED_PATTERNS
    validate_string_list(patterns, "Blocked patterns")

    original = value
    sanitized = remove_control_characters(value).strip()

    if len(sanitized) > max_string_length:
        sanitized = sanitized[:max_string_length]

    violations = contains_blocked_pattern(sanitized, patterns)

    return SanitizationResult(
        value=sanitized,
        changed=sanitized != original,
        violations=violations,
    )


def sanitize_value(
    value: Any,
    *,
    max_string_length: int = 5000,
    blocked_patterns: list[str] | None = None,
) -> SanitizationResult:
    """Sanitize a scalar, list, or dictionary value."""
    if isinstance(value, str):
        return sanitize_string(
            value,
            max_string_length=max_string_length,
            blocked_patterns=blocked_patterns,
        )

    if isinstance(value, dict):
        return sanitize_dict(
            value,
            max_string_length=max_string_length,
            blocked_patterns=blocked_patterns,
        )

    if isinstance(value, list):
        return sanitize_list(
            value,
            max_string_length=max_string_length,
            blocked_patterns=blocked_patterns,
        )

    return SanitizationResult(
        value=value,
        changed=False,
        violations=[],
    )


def sanitize_list(
    values: list[Any],
    *,
    max_string_length: int = 5000,
    blocked_patterns: list[str] | None = None,
) -> SanitizationResult:
    """Sanitize list values."""
    if not isinstance(values, list):
        raise ValueError("Values must be a list.")

    sanitized_values: list[Any] = []
    changed = False
    violations: list[str] = []

    for value in values:
        result = sanitize_value(
            value,
            max_string_length=max_string_length,
            blocked_patterns=blocked_patterns,
        )
        sanitized_values.append(result.value)
        changed = changed or result.changed
        violations.extend(result.violations)

    return SanitizationResult(
        value=sanitized_values,
        changed=changed,
        violations=deduplicate_violations(violations),
    )


def sanitize_dict(
    values: dict[str, Any],
    *,
    max_string_length: int = 5000,
    blocked_patterns: list[str] | None = None,
) -> SanitizationResult:
    """Sanitize dictionary keys and values."""
    validate_attributes(values)

    sanitized_values: dict[str, Any] = {}
    changed = False
    violations: list[str] = []

    for key, value in values.items():
        key_result = sanitize_string(
            str(key),
            max_string_length=max_string_length,
            blocked_patterns=blocked_patterns,
        )
        value_result = sanitize_value(
            value,
            max_string_length=max_string_length,
            blocked_patterns=blocked_patterns,
        )

        sanitized_values[key_result.value] = value_result.value
        changed = changed or key_result.changed or value_result.changed
        violations.extend(key_result.violations)
        violations.extend(value_result.violations)

    return SanitizationResult(
        value=sanitized_values,
        changed=changed,
        violations=deduplicate_violations(violations),
    )


def sanitize_guarded_request(
    request: GuardedRequest,
    *,
    max_string_length: int = 5000,
    blocked_patterns: list[str] | None = None,
) -> tuple[GuardedRequest, list[str], bool]:
    """Sanitize request headers, query params, body, source IP, and metadata."""
    if not isinstance(request, GuardedRequest):
        raise ValueError("Request must be a GuardedRequest.")

    headers = sanitize_dict(
        request.headers,
        max_string_length=max_string_length,
        blocked_patterns=blocked_patterns,
    )
    query_params = sanitize_dict(
        request.query_params,
        max_string_length=max_string_length,
        blocked_patterns=blocked_patterns,
    )
    body = sanitize_dict(
        request.body,
        max_string_length=max_string_length,
        blocked_patterns=blocked_patterns,
    )
    source_ip = sanitize_string(
        request.source_ip,
        max_string_length=max_string_length,
        blocked_patterns=blocked_patterns,
    )
    metadata = sanitize_dict(
        request.metadata,
        max_string_length=max_string_length,
        blocked_patterns=blocked_patterns,
    )

    violations = deduplicate_violations(
        [
            *headers.violations,
            *query_params.violations,
            *body.violations,
            *source_ip.violations,
            *metadata.violations,
        ],
    )

    changed = (
        headers.changed
        or query_params.changed
        or body.changed
        or source_ip.changed
        or metadata.changed
    )

    sanitized_request = GuardedRequest(
        request_id=request.request_id,
        method=request.method,
        path=request.path,
        principal=request.principal,
        headers=headers.value,
        query_params=query_params.value,
        body=body.value,
        source_ip=source_ip.value,
        metadata=metadata.value,
    )

    return sanitized_request, violations, changed


def remove_control_characters(value: str) -> str:
    """Remove non-printable control characters except common whitespace."""
    validate_string(value, "Value")

    return "".join(
        character
        for character in value
        if character.isprintable() or character in "\n\t\r"
    )


def deduplicate_violations(violations: list[str]) -> list[str]:
    """Deduplicate violations while keeping order."""
    validate_string_list(violations, "Violations")

    seen: set[str] = set()
    unique: list[str] = []

    for violation in violations:
        normalized = violation.strip()

        if normalized not in seen:
            seen.add(normalized)
            unique.append(normalized)

    return unique


def build_guarded_request(
    *,
    request_id: str,
    method: str,
    path: str,
    principal: SecurityPrincipal | None = None,
    headers: dict[str, Any] | None = None,
    query_params: dict[str, Any] | None = None,
    body: dict[str, Any] | None = None,
    source_ip: str = "",
    metadata: dict[str, Any] | None = None,
) -> GuardedRequest:
    """Build a guarded request."""
    return GuardedRequest(
        request_id=request_id,
        method=method,
        path=path,
        principal=principal,
        headers=headers or {},
        query_params=query_params or {},
        body=body or {},
        source_ip=source_ip,
        metadata=metadata or {},
    )


def build_request_guard(
    *,
    config: RequestGuardConfig | None = None,
    permission_registry: PermissionRegistry | None = None,
) -> RequestGuard:
    """Build request guard."""
    return RequestGuard(
        config=config or RequestGuardConfig(),
        permission_registry=permission_registry,
    )