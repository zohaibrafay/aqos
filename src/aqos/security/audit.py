"""
AQOS security audit log primitives.

This module provides dependency-free audit records, audit querying, and an
in-memory audit logger/store for security and governance events.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import Enum
from typing import Any
from uuid import uuid4

from aqos.security.base import (
    SecurityDecision,
    SecurityResult,
    SecurityRiskLevel,
    build_security_result,
    normalize_risk_level,
    validate_attributes,
    validate_non_empty_string,
    validate_string,
)


class AuditAction(str, Enum):
    """Supported audit actions."""

    AUTHENTICATE = "authenticate"
    AUTHORIZE = "authorize"
    GUARD_REQUEST = "guard_request"
    TOKEN_VALIDATE = "token_validate"
    PERMISSION_CHECK = "permission_check"
    POLICY_EVALUATE = "policy_evaluate"
    CUSTOM = "custom"


class AuditOutcome(str, Enum):
    """Supported audit outcomes."""

    SUCCESS = "success"
    FAILURE = "failure"
    DENIED = "denied"


@dataclass(frozen=True)
class AuditLogRecord:
    """Single security audit log record."""

    audit_id: str
    action: AuditAction | str
    outcome: AuditOutcome | str
    actor_id: str | None = None
    resource: str = ""
    message: str = ""
    timestamp: str = field(default_factory=lambda: datetime.now(UTC).isoformat())
    risk_level: SecurityRiskLevel | str = SecurityRiskLevel.LOW
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        validate_non_empty_string(self.audit_id, "Audit ID")
        normalize_audit_action(self.action)
        normalize_audit_outcome(self.outcome)
        validate_audit_resource(self.resource)
        validate_audit_message(self.message)
        validate_non_empty_string(self.timestamp, "Timestamp")
        normalize_risk_level(self.risk_level)
        validate_audit_metadata(self.metadata)

        if self.actor_id is not None:
            validate_non_empty_string(self.actor_id, "Actor ID")

    @property
    def allowed(self) -> bool:
        """Return whether audit outcome represents allowed/successful access."""
        return normalize_audit_outcome(self.outcome) == AuditOutcome.SUCCESS

    @property
    def denied(self) -> bool:
        """Return whether audit outcome represents denied access."""
        return normalize_audit_outcome(self.outcome) == AuditOutcome.DENIED

    def to_security_result(self) -> SecurityResult:
        """Convert audit record into a security result."""
        decision = SecurityDecision.ALLOW if self.allowed else SecurityDecision.DENY

        return build_security_result(
            decision=decision,
            reason=self.message,
            risk_level=self.risk_level,
            principal_id=self.actor_id,
            metadata={
                "audit_id": self.audit_id,
                "action": normalize_audit_action(self.action).value,
                "outcome": normalize_audit_outcome(self.outcome).value,
                "resource": self.resource.strip(),
                **self.metadata,
            },
        )

    def to_dict(self) -> dict[str, Any]:
        """Convert audit record into a serializable dictionary."""
        payload = {
            "audit_id": self.audit_id.strip(),
            "action": normalize_audit_action(self.action).value,
            "outcome": normalize_audit_outcome(self.outcome).value,
            "allowed": self.allowed,
            "denied": self.denied,
            "actor_id": self.actor_id.strip() if self.actor_id else None,
            "resource": self.resource.strip(),
            "message": self.message.strip(),
            "timestamp": self.timestamp.strip(),
            "risk_level": normalize_risk_level(self.risk_level).value,
            "metadata": dict(self.metadata),
        }

        return {
            key: value
            for key, value in payload.items()
            if value is not None
        }


@dataclass(frozen=True)
class AuditQuery:
    """Query object for filtering audit records."""

    actor_id: str | None = None
    action: AuditAction | str | None = None
    outcome: AuditOutcome | str | None = None
    resource: str | None = None
    limit: int | None = None

    def __post_init__(self) -> None:
        if self.actor_id is not None:
            validate_non_empty_string(self.actor_id, "Actor ID")

        if self.action is not None:
            normalize_audit_action(self.action)

        if self.outcome is not None:
            normalize_audit_outcome(self.outcome)

        if self.resource is not None:
            validate_audit_resource(self.resource)

        if self.limit is not None:
            validate_audit_limit(self.limit)

    def matches(self, record: AuditLogRecord) -> bool:
        """Return whether a record matches this query."""
        if not isinstance(record, AuditLogRecord):
            raise ValueError("Record must be an AuditLogRecord.")

        if self.actor_id is not None and record.actor_id != self.actor_id.strip():
            return False

        if self.action is not None and normalize_audit_action(record.action) != normalize_audit_action(self.action):
            return False

        if self.outcome is not None and normalize_audit_outcome(record.outcome) != normalize_audit_outcome(self.outcome):
            return False

        if self.resource is not None and record.resource.strip() != self.resource.strip():
            return False

        return True

    def to_dict(self) -> dict[str, Any]:
        """Convert query into dictionary."""
        payload = {
            "actor_id": self.actor_id.strip() if self.actor_id else None,
            "action": normalize_audit_action(self.action).value if self.action else None,
            "outcome": normalize_audit_outcome(self.outcome).value if self.outcome else None,
            "resource": self.resource.strip() if self.resource is not None else None,
            "limit": self.limit,
        }

        return {
            key: value
            for key, value in payload.items()
            if value is not None
        }


@dataclass
class AuditStore:
    """In-memory audit log store."""

    records: list[AuditLogRecord] = field(default_factory=list)

    def append(self, record: AuditLogRecord) -> AuditLogRecord:
        """Append an audit log record."""
        if not isinstance(record, AuditLogRecord):
            raise ValueError("Record must be an AuditLogRecord.")

        self.records.append(record)
        return record

    def record(
        self,
        *,
        action: AuditAction | str,
        outcome: AuditOutcome | str,
        actor_id: str | None = None,
        resource: str = "",
        message: str = "",
        risk_level: SecurityRiskLevel | str = SecurityRiskLevel.LOW,
        metadata: dict[str, Any] | None = None,
        audit_id: str | None = None,
        timestamp: str | None = None,
    ) -> AuditLogRecord:
        """Build and append an audit record."""
        record = build_audit_log_record(
            action=action,
            outcome=outcome,
            actor_id=actor_id,
            resource=resource,
            message=message,
            risk_level=risk_level,
            metadata=metadata or {},
            audit_id=audit_id,
            timestamp=timestamp,
        )

        return self.append(record)

    def latest(self, limit: int | None = None) -> list[AuditLogRecord]:
        """Return latest audit records."""
        if limit is None:
            return list(self.records)

        validate_audit_limit(limit)

        return self.records[-limit:]

    def query(self, query: AuditQuery) -> list[AuditLogRecord]:
        """Query audit records."""
        if not isinstance(query, AuditQuery):
            raise ValueError("Query must be an AuditQuery.")

        matched = [
            record
            for record in self.records
            if query.matches(record)
        ]

        if query.limit is not None:
            return matched[-query.limit:]

        return matched

    def filter_by_actor(self, actor_id: str) -> list[AuditLogRecord]:
        """Return records for actor."""
        return self.query(
            AuditQuery(
                actor_id=actor_id,
            ),
        )

    def filter_by_action(self, action: AuditAction | str) -> list[AuditLogRecord]:
        """Return records matching action."""
        return self.query(
            AuditQuery(
                action=action,
            ),
        )

    def filter_by_outcome(self, outcome: AuditOutcome | str) -> list[AuditLogRecord]:
        """Return records matching outcome."""
        return self.query(
            AuditQuery(
                outcome=outcome,
            ),
        )

    def filter_by_resource(self, resource: str) -> list[AuditLogRecord]:
        """Return records matching resource."""
        return self.query(
            AuditQuery(
                resource=resource,
            ),
        )

    def count(self) -> int:
        """Return audit record count."""
        return len(self.records)

    def to_dicts(self) -> list[dict[str, Any]]:
        """Return all records as dictionaries."""
        return [
            record.to_dict()
            for record in self.records
        ]

    def summary(self) -> dict[str, Any]:
        """Return audit store summary."""
        actions: dict[str, int] = {}
        outcomes: dict[str, int] = {}
        actors: dict[str, int] = {}

        for record in self.records:
            action = normalize_audit_action(record.action).value
            outcome = normalize_audit_outcome(record.outcome).value

            actions[action] = actions.get(action, 0) + 1
            outcomes[outcome] = outcomes.get(outcome, 0) + 1

            if record.actor_id:
                actors[record.actor_id] = actors.get(record.actor_id, 0) + 1

        return {
            "records": len(self.records),
            "actions": actions,
            "outcomes": outcomes,
            "actors": actors,
        }

    def clear(self) -> None:
        """Clear audit records."""
        self.records.clear()


@dataclass
class AuditLogger:
    """Audit logger backed by an audit store."""

    store: AuditStore = field(default_factory=AuditStore)
    component: str = "security"
    default_metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not isinstance(self.store, AuditStore):
            raise ValueError("Store must be an AuditStore.")

        validate_non_empty_string(self.component, "Component")
        validate_audit_metadata(self.default_metadata)

    def record(
        self,
        *,
        action: AuditAction | str,
        outcome: AuditOutcome | str,
        actor_id: str | None = None,
        resource: str = "",
        message: str = "",
        risk_level: SecurityRiskLevel | str = SecurityRiskLevel.LOW,
        metadata: dict[str, Any] | None = None,
        audit_id: str | None = None,
        timestamp: str | None = None,
    ) -> AuditLogRecord:
        """Record an audit event."""
        merged_metadata = {
            "component": self.component,
            **self.default_metadata,
            **(metadata or {}),
        }

        return self.store.record(
            action=action,
            outcome=outcome,
            actor_id=actor_id,
            resource=resource,
            message=message,
            risk_level=risk_level,
            metadata=merged_metadata,
            audit_id=audit_id,
            timestamp=timestamp,
        )

    def success(
        self,
        *,
        action: AuditAction | str,
        actor_id: str | None = None,
        resource: str = "",
        message: str = "",
        metadata: dict[str, Any] | None = None,
    ) -> AuditLogRecord:
        """Record successful audit event."""
        return self.record(
            action=action,
            outcome=AuditOutcome.SUCCESS,
            actor_id=actor_id,
            resource=resource,
            message=message,
            risk_level=SecurityRiskLevel.LOW,
            metadata=metadata or {},
        )

    def failure(
        self,
        *,
        action: AuditAction | str,
        actor_id: str | None = None,
        resource: str = "",
        message: str = "",
        metadata: dict[str, Any] | None = None,
    ) -> AuditLogRecord:
        """Record failed audit event."""
        return self.record(
            action=action,
            outcome=AuditOutcome.FAILURE,
            actor_id=actor_id,
            resource=resource,
            message=message,
            risk_level=SecurityRiskLevel.HIGH,
            metadata=metadata or {},
        )

    def denied(
        self,
        *,
        action: AuditAction | str,
        actor_id: str | None = None,
        resource: str = "",
        message: str = "",
        metadata: dict[str, Any] | None = None,
    ) -> AuditLogRecord:
        """Record denied audit event."""
        return self.record(
            action=action,
            outcome=AuditOutcome.DENIED,
            actor_id=actor_id,
            resource=resource,
            message=message,
            risk_level=SecurityRiskLevel.HIGH,
            metadata=metadata or {},
        )


def normalize_audit_action(action: AuditAction | str) -> AuditAction:
    """Normalize audit action."""
    if isinstance(action, AuditAction):
        return action

    normalized = validate_non_empty_string(action, "Audit action").lower()

    try:
        return AuditAction(normalized)
    except ValueError as exc:
        valid = ", ".join(item.value for item in AuditAction)
        raise ValueError(f"Invalid audit action '{action}'. Valid actions: {valid}.") from exc


def normalize_audit_outcome(outcome: AuditOutcome | str) -> AuditOutcome:
    """Normalize audit outcome."""
    if isinstance(outcome, AuditOutcome):
        return outcome

    normalized = validate_non_empty_string(outcome, "Audit outcome").lower()

    try:
        return AuditOutcome(normalized)
    except ValueError as exc:
        valid = ", ".join(item.value for item in AuditOutcome)
        raise ValueError(f"Invalid audit outcome '{outcome}'. Valid outcomes: {valid}.") from exc


def validate_audit_message(message: str) -> str:
    """Validate audit message."""
    validate_string(message, "Message")

    return message.strip()


def validate_audit_resource(resource: str) -> str:
    """Validate audit resource."""
    validate_string(resource, "Resource")

    return resource.strip()


def validate_audit_metadata(metadata: dict[str, Any]) -> dict[str, Any]:
    """Validate audit metadata."""
    return validate_attributes(metadata)


def validate_audit_limit(limit: int) -> int:
    """Validate audit query limit."""
    if isinstance(limit, bool) or not isinstance(limit, int) or limit <= 0:
        raise ValueError("Limit must be a positive integer.")

    return limit


def build_audit_id(prefix: str = "audit") -> str:
    """Build audit ID."""
    normalized_prefix = validate_non_empty_string(prefix, "Audit ID prefix")

    if " " in normalized_prefix:
        raise ValueError("Audit ID prefix cannot contain spaces.")

    return f"{normalized_prefix}-{uuid4().hex}"


def build_audit_log_record(
    *,
    action: AuditAction | str,
    outcome: AuditOutcome | str,
    actor_id: str | None = None,
    resource: str = "",
    message: str = "",
    risk_level: SecurityRiskLevel | str = SecurityRiskLevel.LOW,
    metadata: dict[str, Any] | None = None,
    audit_id: str | None = None,
    timestamp: str | None = None,
) -> AuditLogRecord:
    """Build an audit log record."""
    record_kwargs: dict[str, Any] = {
        "audit_id": audit_id or build_audit_id(),
        "action": action,
        "outcome": outcome,
        "actor_id": actor_id,
        "resource": resource,
        "message": message,
        "risk_level": risk_level,
        "metadata": metadata or {},
    }

    if timestamp is not None:
        record_kwargs["timestamp"] = timestamp

    return AuditLogRecord(**record_kwargs)


def build_audit_query(
    *,
    actor_id: str | None = None,
    action: AuditAction | str | None = None,
    outcome: AuditOutcome | str | None = None,
    resource: str | None = None,
    limit: int | None = None,
) -> AuditQuery:
    """Build audit query."""
    return AuditQuery(
        actor_id=actor_id,
        action=action,
        outcome=outcome,
        resource=resource,
        limit=limit,
    )


def build_audit_logger(
    *,
    store: AuditStore | None = None,
    component: str = "security",
    default_metadata: dict[str, Any] | None = None,
) -> AuditLogger:
    """Build audit logger."""
    return AuditLogger(
        store=store or AuditStore(),
        component=component,
        default_metadata=default_metadata or {},
    )