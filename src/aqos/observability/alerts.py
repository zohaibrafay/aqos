"""
AQOS observability alerting primitives.

This module provides dependency-free alert rules, alert records, and an
in-memory alert manager for evaluating metric points.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import Enum
from typing import Any
from uuid import uuid4

from aqos.observability.base import (
    ObservabilityEvent,
    ObservabilitySeverity,
    build_observability_event,
    normalize_severity,
    validate_attributes,
    validate_non_empty_string,
)
from aqos.observability.metrics import (
    MetricPoint,
    validate_metric_value,
)


class AlertState(str, Enum):
    """Supported alert lifecycle states."""

    ACTIVE = "active"
    RESOLVED = "resolved"
    SUPPRESSED = "suppressed"


class AlertOperator(str, Enum):
    """Supported alert comparison operators."""

    GT = ">"
    GTE = ">="
    LT = "<"
    LTE = "<="
    EQ = "=="
    NE = "!="


@dataclass(frozen=True)
class AlertRule:
    """Metric alert rule."""

    name: str
    metric_name: str
    component: str
    operator: AlertOperator | str
    threshold: float
    severity: ObservabilitySeverity | str = ObservabilitySeverity.WARNING
    message: str = ""
    enabled: bool = True
    attributes: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        validate_non_empty_string(self.name, "Alert rule name")
        validate_non_empty_string(self.metric_name, "Metric name")
        validate_non_empty_string(self.component, "Component")
        normalize_alert_operator(self.operator)
        validate_metric_value(self.threshold)
        normalize_severity(self.severity)
        validate_alert_message(self.message)

        if not isinstance(self.enabled, bool):
            raise ValueError("Enabled must be a boolean.")

        validate_attributes(self.attributes)

    def matches(self, point: MetricPoint) -> bool:
        """Return whether this rule matches a metric point."""
        if not isinstance(point, MetricPoint):
            raise ValueError("Point must be a MetricPoint.")

        if not self.enabled:
            return False

        payload = point.to_dict()

        if payload["name"] != self.metric_name.strip():
            return False

        if payload["component"] != self.component.strip():
            return False

        return compare_alert_values(
            payload["value"],
            self.operator,
            self.threshold,
        )

    def to_dict(self) -> dict[str, Any]:
        """Convert alert rule into serializable dictionary."""
        return {
            "name": self.name.strip(),
            "metric_name": self.metric_name.strip(),
            "component": self.component.strip(),
            "operator": normalize_alert_operator(self.operator).value,
            "threshold": float(self.threshold),
            "severity": normalize_severity(self.severity).value,
            "message": self.message.strip(),
            "enabled": self.enabled,
            "attributes": dict(self.attributes),
        }


@dataclass
class AlertRecord:
    """Concrete alert emitted from an alert rule."""

    alert_id: str
    rule_name: str
    metric_name: str
    component: str
    severity: ObservabilitySeverity | str
    state: AlertState | str
    message: str
    value: float
    threshold: float
    timestamp: str = field(default_factory=lambda: datetime.now(UTC).isoformat())
    attributes: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        validate_non_empty_string(self.alert_id, "Alert ID")
        validate_non_empty_string(self.rule_name, "Rule name")
        validate_non_empty_string(self.metric_name, "Metric name")
        validate_non_empty_string(self.component, "Component")
        normalize_severity(self.severity)
        normalize_alert_state(self.state)
        validate_non_empty_string(self.message, "Message")
        validate_metric_value(self.value)
        validate_metric_value(self.threshold)
        validate_non_empty_string(self.timestamp, "Timestamp")
        validate_attributes(self.attributes)

    def resolve(self, message: str | None = None) -> "AlertRecord":
        """Mark alert as resolved."""
        self.state = AlertState.RESOLVED

        if message is not None:
            self.message = validate_non_empty_string(message, "Message")

        return self

    def suppress(self, message: str | None = None) -> "AlertRecord":
        """Mark alert as suppressed."""
        self.state = AlertState.SUPPRESSED

        if message is not None:
            self.message = validate_non_empty_string(message, "Message")

        return self

    def to_dict(self) -> dict[str, Any]:
        """Convert alert record into serializable dictionary."""
        return {
            "alert_id": self.alert_id.strip(),
            "rule_name": self.rule_name.strip(),
            "metric_name": self.metric_name.strip(),
            "component": self.component.strip(),
            "severity": normalize_severity(self.severity).value,
            "state": normalize_alert_state(self.state).value,
            "message": self.message.strip(),
            "value": float(self.value),
            "threshold": float(self.threshold),
            "timestamp": self.timestamp.strip(),
            "attributes": dict(self.attributes),
        }

    def to_event(self) -> ObservabilityEvent:
        """Convert alert record into observability event."""
        payload = self.to_dict()

        return build_observability_event(
            name=f"alert.{payload['rule_name']}",
            component=payload["component"],
            severity=payload["severity"],
            message=payload["message"],
            attributes=payload,
            timestamp=payload["timestamp"],
        )


@dataclass
class AlertManager:
    """In-memory alert manager."""

    rules: dict[str, AlertRule] = field(default_factory=dict)
    alerts: dict[str, AlertRecord] = field(default_factory=dict)

    def register_rule(self, rule: AlertRule) -> AlertRule:
        """Register an alert rule."""
        if not isinstance(rule, AlertRule):
            raise ValueError("Rule must be an AlertRule.")

        if rule.name in self.rules:
            raise ValueError("Alert rule already exists.")

        self.rules[rule.name] = rule
        return rule

    def upsert_rule(self, rule: AlertRule) -> AlertRule:
        """Create or replace an alert rule."""
        if not isinstance(rule, AlertRule):
            raise ValueError("Rule must be an AlertRule.")

        self.rules[rule.name] = rule
        return rule

    def get_rule(self, name: str) -> AlertRule | None:
        """Get an alert rule by name."""
        normalized = validate_non_empty_string(name, "Alert rule name")

        return self.rules.get(normalized)

    def get_required_rule(self, name: str) -> AlertRule:
        """Get an alert rule or raise."""
        rule = self.get_rule(name)

        if rule is None:
            raise ValueError("Alert rule not found.")

        return rule

    def list_rules(self) -> list[AlertRule]:
        """List alert rules."""
        return list(self.rules.values())

    def evaluate_point(self, point: MetricPoint) -> list[AlertRecord]:
        """Evaluate a metric point against all alert rules."""
        if not isinstance(point, MetricPoint):
            raise ValueError("Point must be a MetricPoint.")

        emitted: list[AlertRecord] = []

        for rule in self.rules.values():
            if rule.matches(point):
                alert = build_alert_record(
                    rule=rule,
                    point=point,
                )
                self.alerts[alert.alert_id] = alert
                emitted.append(alert)

        return emitted

    def evaluate_points(self, points: list[MetricPoint]) -> list[AlertRecord]:
        """Evaluate multiple metric points."""
        if not isinstance(points, list):
            raise ValueError("Points must be a list.")

        emitted: list[AlertRecord] = []

        for point in points:
            emitted.extend(self.evaluate_point(point))

        return emitted

    def get_alert(self, alert_id: str) -> AlertRecord | None:
        """Get alert by ID."""
        normalized = validate_non_empty_string(alert_id, "Alert ID")

        return self.alerts.get(normalized)

    def get_required_alert(self, alert_id: str) -> AlertRecord:
        """Get alert by ID or raise."""
        alert = self.get_alert(alert_id)

        if alert is None:
            raise ValueError("Alert not found.")

        return alert

    def resolve_alert(
        self,
        alert_id: str,
        *,
        message: str | None = None,
    ) -> AlertRecord:
        """Resolve alert by ID."""
        alert = self.get_required_alert(alert_id)

        return alert.resolve(message=message)

    def suppress_alert(
        self,
        alert_id: str,
        *,
        message: str | None = None,
    ) -> AlertRecord:
        """Suppress alert by ID."""
        alert = self.get_required_alert(alert_id)

        return alert.suppress(message=message)

    def active_alerts(self) -> list[AlertRecord]:
        """Return active alerts."""
        return [
            alert
            for alert in self.alerts.values()
            if normalize_alert_state(alert.state) == AlertState.ACTIVE
        ]

    def resolved_alerts(self) -> list[AlertRecord]:
        """Return resolved alerts."""
        return [
            alert
            for alert in self.alerts.values()
            if normalize_alert_state(alert.state) == AlertState.RESOLVED
        ]

    def suppressed_alerts(self) -> list[AlertRecord]:
        """Return suppressed alerts."""
        return [
            alert
            for alert in self.alerts.values()
            if normalize_alert_state(alert.state) == AlertState.SUPPRESSED
        ]

    def alerts_by_rule(self, rule_name: str) -> list[AlertRecord]:
        """Return alerts emitted by a rule."""
        normalized = validate_non_empty_string(rule_name, "Rule name")

        return [
            alert
            for alert in self.alerts.values()
            if alert.rule_name == normalized
        ]

    def summary(self) -> dict[str, Any]:
        """Return alert manager summary."""
        return {
            "rules": len(self.rules),
            "alerts": len(self.alerts),
            "active_alerts": len(self.active_alerts()),
            "resolved_alerts": len(self.resolved_alerts()),
            "suppressed_alerts": len(self.suppressed_alerts()),
            "rule_names": list(self.rules.keys()),
        }

    def clear_alerts(self) -> None:
        """Clear emitted alerts without deleting rules."""
        self.alerts.clear()

    def clear(self) -> None:
        """Clear rules and alerts."""
        self.rules.clear()
        self.alerts.clear()


def build_alert_id() -> str:
    """Build alert ID."""
    return f"alert-{uuid4().hex}"


def validate_alert_message(message: str) -> str:
    """Validate alert message."""
    if not isinstance(message, str):
        raise ValueError("Message must be a string.")

    return message.strip()


def normalize_alert_state(state: AlertState | str) -> AlertState:
    """Normalize alert state."""
    if isinstance(state, AlertState):
        return state

    normalized = validate_non_empty_string(state, "Alert state").lower()

    try:
        return AlertState(normalized)
    except ValueError as exc:
        valid = ", ".join(item.value for item in AlertState)
        raise ValueError(f"Invalid alert state '{state}'. Valid states: {valid}.") from exc


def normalize_alert_operator(operator: AlertOperator | str) -> AlertOperator:
    """Normalize alert comparison operator."""
    if isinstance(operator, AlertOperator):
        return operator

    normalized = validate_non_empty_string(operator, "Alert operator").lower()

    aliases = {
        ">": AlertOperator.GT,
        "gt": AlertOperator.GT,
        "greater_than": AlertOperator.GT,
        ">=": AlertOperator.GTE,
        "gte": AlertOperator.GTE,
        "greater_than_or_equal": AlertOperator.GTE,
        "<": AlertOperator.LT,
        "lt": AlertOperator.LT,
        "less_than": AlertOperator.LT,
        "<=": AlertOperator.LTE,
        "lte": AlertOperator.LTE,
        "less_than_or_equal": AlertOperator.LTE,
        "==": AlertOperator.EQ,
        "=": AlertOperator.EQ,
        "eq": AlertOperator.EQ,
        "equals": AlertOperator.EQ,
        "!=": AlertOperator.NE,
        "ne": AlertOperator.NE,
        "not_equals": AlertOperator.NE,
    }

    if normalized not in aliases:
        valid = ", ".join(item.value for item in AlertOperator)
        raise ValueError(f"Invalid alert operator '{operator}'. Valid operators: {valid}.")

    return aliases[normalized]


def compare_alert_values(
    value: float,
    operator: AlertOperator | str,
    threshold: float,
) -> bool:
    """Compare metric value against threshold."""
    left = validate_metric_value(value)
    right = validate_metric_value(threshold)
    normalized_operator = normalize_alert_operator(operator)

    if normalized_operator == AlertOperator.GT:
        return left > right

    if normalized_operator == AlertOperator.GTE:
        return left >= right

    if normalized_operator == AlertOperator.LT:
        return left < right

    if normalized_operator == AlertOperator.LTE:
        return left <= right

    if normalized_operator == AlertOperator.EQ:
        return left == right

    if normalized_operator == AlertOperator.NE:
        return left != right

    raise ValueError("Unsupported alert operator.")


def build_alert_record(
    *,
    rule: AlertRule,
    point: MetricPoint,
    alert_id: str | None = None,
    timestamp: str | None = None,
) -> AlertRecord:
    """Build alert record from rule and metric point."""
    if not isinstance(rule, AlertRule):
        raise ValueError("Rule must be an AlertRule.")

    if not isinstance(point, MetricPoint):
        raise ValueError("Point must be a MetricPoint.")

    point_payload = point.to_dict()
    rule_payload = rule.to_dict()

    message = rule_payload["message"] or (
        f"Alert rule '{rule_payload['name']}' triggered for "
        f"{point_payload['name']}."
    )

    alert_kwargs: dict[str, Any] = {
        "alert_id": alert_id or build_alert_id(),
        "rule_name": rule_payload["name"],
        "metric_name": point_payload["name"],
        "component": point_payload["component"],
        "severity": rule_payload["severity"],
        "state": AlertState.ACTIVE,
        "message": message,
        "value": point_payload["value"],
        "threshold": rule_payload["threshold"],
        "attributes": {
            "metric": point_payload,
            "rule": rule_payload,
            **rule_payload["attributes"],
        },
    }

    if timestamp is not None:
        alert_kwargs["timestamp"] = timestamp

    return AlertRecord(**alert_kwargs)


def build_alert_rule(
    *,
    name: str,
    metric_name: str,
    component: str,
    operator: AlertOperator | str,
    threshold: float,
    severity: ObservabilitySeverity | str = ObservabilitySeverity.WARNING,
    message: str = "",
    enabled: bool = True,
    attributes: dict[str, Any] | None = None,
) -> AlertRule:
    """Build alert rule."""
    return AlertRule(
        name=name,
        metric_name=metric_name,
        component=component,
        operator=operator,
        threshold=threshold,
        severity=severity,
        message=message,
        enabled=enabled,
        attributes=attributes or {},
    )