"""
AQOS dashboard base primitives.

This module contains dependency-free dashboard primitives used to expose AQOS
state to frontend dashboards, SaaS UI, mobile apps, and external clients.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import Enum
from typing import Any


class DashboardStatus(str, Enum):
    """Supported dashboard payload statuses."""

    READY = "ready"
    WARNING = "warning"
    ERROR = "error"
    EMPTY = "empty"


class DashboardSeverity(str, Enum):
    """Supported dashboard issue severities."""

    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"


class DashboardRefreshMode(str, Enum):
    """Supported dashboard refresh modes."""

    MANUAL = "manual"
    AUTO = "auto"
    STREAMING = "streaming"


class DashboardComponentType(str, Enum):
    """Supported dashboard component types."""

    PAGE = "page"
    SECTION = "section"
    CARD = "card"
    TABLE = "table"
    CHART = "chart"
    METRIC = "metric"
    STATUS = "status"


@dataclass(frozen=True)
class DashboardIssue:
    """Dashboard issue or warning."""

    code: str
    message: str
    severity: DashboardSeverity | str = DashboardSeverity.INFO
    source: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        validate_non_empty_string(self.code, "Issue code")
        validate_non_empty_string(self.message, "Issue message")
        normalize_dashboard_severity(self.severity)
        validate_string(self.source, "Source")
        validate_metadata(self.metadata, "Metadata")

    def to_dict(self) -> dict[str, Any]:
        """Convert issue into dictionary."""
        return {
            "code": self.code.strip(),
            "message": self.message.strip(),
            "severity": normalize_dashboard_severity(self.severity).value,
            "source": self.source.strip(),
            "metadata": dict(self.metadata),
        }


@dataclass(frozen=True)
class DashboardMetric:
    """Dashboard metric primitive."""

    name: str
    value: int | float | str | bool
    label: str = ""
    unit: str = ""
    previous_value: int | float | None = None
    change: int | float | None = None
    change_pct: int | float | None = None
    status: DashboardStatus | str = DashboardStatus.READY
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        validate_non_empty_string(self.name, "Metric name")
        validate_metric_value(self.value, "Metric value")
        validate_string(self.label, "Metric label")
        validate_string(self.unit, "Metric unit")

        if self.previous_value is not None:
            validate_number(self.previous_value, "Previous value")

        if self.change is not None:
            validate_number(self.change, "Change")

        if self.change_pct is not None:
            validate_number(self.change_pct, "Change percentage")

        normalize_dashboard_status(self.status)
        validate_metadata(self.metadata, "Metadata")

    @property
    def display_label(self) -> str:
        """Return display label."""
        return self.label.strip() or self.name.strip().replace("_", " ").title()

    def to_dict(self) -> dict[str, Any]:
        """Convert metric into dictionary."""
        return {
            "name": self.name.strip(),
            "label": self.display_label,
            "value": self.value,
            "unit": self.unit.strip(),
            "previous_value": self.previous_value,
            "change": self.change,
            "change_pct": self.change_pct,
            "status": normalize_dashboard_status(self.status).value,
            "metadata": dict(self.metadata),
        }


@dataclass(frozen=True)
class DashboardTimeRange:
    """Dashboard time range."""

    label: str = "default"
    start: str = ""
    end: str = ""
    timezone: str = "UTC"
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        validate_non_empty_string(self.label, "Time range label")
        validate_string(self.start, "Start")
        validate_string(self.end, "End")
        validate_non_empty_string(self.timezone, "Timezone")
        validate_metadata(self.metadata, "Metadata")

    @property
    def bounded(self) -> bool:
        """Return whether start and end are both present."""
        return bool(self.start.strip()) and bool(self.end.strip())

    def to_dict(self) -> dict[str, Any]:
        """Convert time range into dictionary."""
        return {
            "label": self.label.strip(),
            "start": self.start.strip(),
            "end": self.end.strip(),
            "timezone": self.timezone.strip(),
            "bounded": self.bounded,
            "metadata": dict(self.metadata),
        }


@dataclass(frozen=True)
class DashboardComponent:
    """Dashboard component primitive."""

    component_id: str
    title: str
    component_type: DashboardComponentType | str
    status: DashboardStatus | str = DashboardStatus.READY
    description: str = ""
    data: dict[str, Any] = field(default_factory=dict)
    metrics: list[DashboardMetric] = field(default_factory=list)
    issues: list[DashboardIssue] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        validate_non_empty_string(self.component_id, "Component ID")
        validate_non_empty_string(self.title, "Component title")
        normalize_dashboard_component_type(self.component_type)
        normalize_dashboard_status(self.status)
        validate_string(self.description, "Description")
        validate_metadata(self.data, "Data")
        validate_dashboard_metrics(self.metrics)
        validate_dashboard_issues(self.issues)
        validate_metadata(self.metadata, "Metadata")

    @property
    def healthy(self) -> bool:
        """Return whether component is healthy."""
        return normalize_dashboard_status(self.status) == DashboardStatus.READY

    @property
    def metric_count(self) -> int:
        """Return metric count."""
        return len(self.metrics)

    @property
    def issue_count(self) -> int:
        """Return issue count."""
        return len(self.issues)

    def to_dict(self) -> dict[str, Any]:
        """Convert dashboard component into dictionary."""
        return {
            "component_id": self.component_id.strip(),
            "title": self.title.strip(),
            "component_type": normalize_dashboard_component_type(self.component_type).value,
            "status": normalize_dashboard_status(self.status).value,
            "healthy": self.healthy,
            "description": self.description.strip(),
            "data": dict(self.data),
            "metrics": [metric.to_dict() for metric in self.metrics],
            "issues": [issue.to_dict() for issue in self.issues],
            "metric_count": self.metric_count,
            "issue_count": self.issue_count,
            "metadata": dict(self.metadata),
        }


@dataclass(frozen=True)
class DashboardPayload:
    """Top-level dashboard payload."""

    payload_id: str
    title: str
    status: DashboardStatus | str = DashboardStatus.READY
    refresh_mode: DashboardRefreshMode | str = DashboardRefreshMode.MANUAL
    generated_at: str = field(default_factory=lambda: datetime.now(UTC).isoformat())
    time_range: DashboardTimeRange = field(default_factory=DashboardTimeRange)
    components: list[DashboardComponent] = field(default_factory=list)
    metrics: list[DashboardMetric] = field(default_factory=list)
    issues: list[DashboardIssue] = field(default_factory=list)
    data: dict[str, Any] = field(default_factory=dict)
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        validate_non_empty_string(self.payload_id, "Payload ID")
        validate_non_empty_string(self.title, "Payload title")
        normalize_dashboard_status(self.status)
        normalize_dashboard_refresh_mode(self.refresh_mode)
        validate_non_empty_string(self.generated_at, "Generated at")

        if not isinstance(self.time_range, DashboardTimeRange):
            raise ValueError("Time range must be DashboardTimeRange.")

        validate_dashboard_components(self.components)
        validate_dashboard_metrics(self.metrics)
        validate_dashboard_issues(self.issues)
        validate_metadata(self.data, "Data")
        validate_metadata(self.metadata, "Metadata")

    @property
    def healthy(self) -> bool:
        """Return whether payload is healthy."""
        return normalize_dashboard_status(self.status) == DashboardStatus.READY

    @property
    def component_count(self) -> int:
        """Return component count."""
        return len(self.components)

    @property
    def metric_count(self) -> int:
        """Return metric count."""
        return len(self.metrics)

    @property
    def issue_count(self) -> int:
        """Return issue count."""
        return len(self.issues) + sum(component.issue_count for component in self.components)

    def to_dict(self) -> dict[str, Any]:
        """Convert dashboard payload into dictionary."""
        return {
            "payload_id": self.payload_id.strip(),
            "title": self.title.strip(),
            "status": normalize_dashboard_status(self.status).value,
            "healthy": self.healthy,
            "refresh_mode": normalize_dashboard_refresh_mode(self.refresh_mode).value,
            "generated_at": self.generated_at.strip(),
            "time_range": self.time_range.to_dict(),
            "components": [component.to_dict() for component in self.components],
            "metrics": [metric.to_dict() for metric in self.metrics],
            "issues": [issue.to_dict() for issue in self.issues],
            "data": dict(self.data),
            "component_count": self.component_count,
            "metric_count": self.metric_count,
            "issue_count": self.issue_count,
            "metadata": dict(self.metadata),
        }


def validate_string(value: str, field_name: str) -> str:
    """Validate string."""
    if not isinstance(value, str):
        raise ValueError(f"{field_name} must be a string.")

    return value


def validate_non_empty_string(value: str, field_name: str) -> str:
    """Validate non-empty string."""
    validate_string(value, field_name)

    if not value.strip():
        raise ValueError(f"{field_name} must be a non-empty string.")

    return value.strip()


def validate_metadata(value: dict[str, Any], field_name: str = "Metadata") -> dict[str, Any]:
    """Validate metadata dictionary."""
    if not isinstance(value, dict):
        raise ValueError(f"{field_name} must be a dictionary.")

    return value


def validate_number(value: int | float, field_name: str) -> float:
    """Validate number."""
    if isinstance(value, bool) or not isinstance(value, int | float):
        raise ValueError(f"{field_name} must be a number.")

    return float(value)


def validate_non_negative_float(value: int | float, field_name: str) -> float:
    """Validate non-negative number."""
    validate_number(value, field_name)

    if value < 0:
        raise ValueError(f"{field_name} must be a non-negative number.")

    return float(value)


def validate_positive_float(value: int | float, field_name: str) -> float:
    """Validate positive number."""
    validate_number(value, field_name)

    if value <= 0:
        raise ValueError(f"{field_name} must be a positive number.")

    return float(value)


def validate_metric_value(value: int | float | str | bool, field_name: str) -> int | float | str | bool:
    """Validate metric value."""
    if not isinstance(value, int | float | str | bool):
        raise ValueError(f"{field_name} must be a number, string, or boolean.")

    return value


def normalize_dashboard_status(status: DashboardStatus | str) -> DashboardStatus:
    """Normalize dashboard status."""
    if isinstance(status, DashboardStatus):
        return status

    normalized = validate_non_empty_string(status, "Dashboard status").lower()

    try:
        return DashboardStatus(normalized)
    except ValueError as exc:
        valid = ", ".join(item.value for item in DashboardStatus)
        raise ValueError(
            f"Invalid dashboard status '{status}'. Valid statuses: {valid}.",
        ) from exc


def normalize_dashboard_severity(severity: DashboardSeverity | str) -> DashboardSeverity:
    """Normalize dashboard severity."""
    if isinstance(severity, DashboardSeverity):
        return severity

    normalized = validate_non_empty_string(severity, "Dashboard severity").lower()

    try:
        return DashboardSeverity(normalized)
    except ValueError as exc:
        valid = ", ".join(item.value for item in DashboardSeverity)
        raise ValueError(
            f"Invalid dashboard severity '{severity}'. Valid severities: {valid}.",
        ) from exc


def normalize_dashboard_refresh_mode(
    refresh_mode: DashboardRefreshMode | str,
) -> DashboardRefreshMode:
    """Normalize dashboard refresh mode."""
    if isinstance(refresh_mode, DashboardRefreshMode):
        return refresh_mode

    normalized = validate_non_empty_string(refresh_mode, "Dashboard refresh mode").lower()

    try:
        return DashboardRefreshMode(normalized)
    except ValueError as exc:
        valid = ", ".join(item.value for item in DashboardRefreshMode)
        raise ValueError(
            f"Invalid dashboard refresh mode '{refresh_mode}'. Valid modes: {valid}.",
        ) from exc


def normalize_dashboard_component_type(
    component_type: DashboardComponentType | str,
) -> DashboardComponentType:
    """Normalize dashboard component type."""
    if isinstance(component_type, DashboardComponentType):
        return component_type

    normalized = validate_non_empty_string(component_type, "Dashboard component type").lower()

    try:
        return DashboardComponentType(normalized)
    except ValueError as exc:
        valid = ", ".join(item.value for item in DashboardComponentType)
        raise ValueError(
            f"Invalid dashboard component type '{component_type}'. Valid types: {valid}.",
        ) from exc


def validate_dashboard_metrics(metrics: list[DashboardMetric]) -> list[DashboardMetric]:
    """Validate dashboard metrics."""
    if not isinstance(metrics, list):
        raise ValueError("Metrics must be a list.")

    for metric in metrics:
        if not isinstance(metric, DashboardMetric):
            raise ValueError("Metrics must contain DashboardMetric objects.")

    return metrics


def validate_dashboard_issues(issues: list[DashboardIssue]) -> list[DashboardIssue]:
    """Validate dashboard issues."""
    if not isinstance(issues, list):
        raise ValueError("Issues must be a list.")

    for issue in issues:
        if not isinstance(issue, DashboardIssue):
            raise ValueError("Issues must contain DashboardIssue objects.")

    return issues


def validate_dashboard_components(
    components: list[DashboardComponent],
) -> list[DashboardComponent]:
    """Validate dashboard components."""
    if not isinstance(components, list):
        raise ValueError("Components must be a list.")

    for component in components:
        if not isinstance(component, DashboardComponent):
            raise ValueError("Components must contain DashboardComponent objects.")

    return components


def build_dashboard_issue(
    *,
    code: str,
    message: str,
    severity: DashboardSeverity | str = DashboardSeverity.INFO,
    source: str = "",
    metadata: dict[str, Any] | None = None,
) -> DashboardIssue:
    """Build dashboard issue."""
    return DashboardIssue(
        code=code,
        message=message,
        severity=severity,
        source=source,
        metadata=metadata or {},
    )


def build_dashboard_metric(
    *,
    name: str,
    value: int | float | str | bool,
    label: str = "",
    unit: str = "",
    previous_value: int | float | None = None,
    change: int | float | None = None,
    change_pct: int | float | None = None,
    status: DashboardStatus | str = DashboardStatus.READY,
    metadata: dict[str, Any] | None = None,
) -> DashboardMetric:
    """Build dashboard metric."""
    return DashboardMetric(
        name=name,
        value=value,
        label=label,
        unit=unit,
        previous_value=previous_value,
        change=change,
        change_pct=change_pct,
        status=status,
        metadata=metadata or {},
    )


def build_dashboard_time_range(
    *,
    label: str = "default",
    start: str = "",
    end: str = "",
    timezone: str = "UTC",
    metadata: dict[str, Any] | None = None,
) -> DashboardTimeRange:
    """Build dashboard time range."""
    return DashboardTimeRange(
        label=label,
        start=start,
        end=end,
        timezone=timezone,
        metadata=metadata or {},
    )


def build_dashboard_component(
    *,
    component_id: str,
    title: str,
    component_type: DashboardComponentType | str,
    status: DashboardStatus | str = DashboardStatus.READY,
    description: str = "",
    data: dict[str, Any] | None = None,
    metrics: list[DashboardMetric] | None = None,
    issues: list[DashboardIssue] | None = None,
    metadata: dict[str, Any] | None = None,
) -> DashboardComponent:
    """Build dashboard component."""
    return DashboardComponent(
        component_id=component_id,
        title=title,
        component_type=component_type,
        status=status,
        description=description,
        data=data or {},
        metrics=metrics or [],
        issues=issues or [],
        metadata=metadata or {},
    )


def build_dashboard_payload(
    *,
    payload_id: str,
    title: str,
    status: DashboardStatus | str = DashboardStatus.READY,
    refresh_mode: DashboardRefreshMode | str = DashboardRefreshMode.MANUAL,
    generated_at: str | None = None,
    time_range: DashboardTimeRange | None = None,
    components: list[DashboardComponent] | None = None,
    metrics: list[DashboardMetric] | None = None,
    issues: list[DashboardIssue] | None = None,
    data: dict[str, Any] | None = None,
    metadata: dict[str, Any] | None = None,
) -> DashboardPayload:
    """Build dashboard payload."""
    payload_kwargs: dict[str, Any] = {
        "payload_id": payload_id,
        "title": title,
        "status": status,
        "refresh_mode": refresh_mode,
        "time_range": time_range or DashboardTimeRange(),
        "components": components or [],
        "metrics": metrics or [],
        "issues": issues or [],
        "data": data or {},
        "metadata": metadata or {},
    }

    if generated_at is not None:
        payload_kwargs["generated_at"] = generated_at

    return DashboardPayload(**payload_kwargs)


def dashboard_success_payload(
    *,
    payload_id: str,
    title: str,
    data: dict[str, Any] | None = None,
    components: list[DashboardComponent] | None = None,
    metrics: list[DashboardMetric] | None = None,
    metadata: dict[str, Any] | None = None,
) -> DashboardPayload:
    """Build successful dashboard payload."""
    return build_dashboard_payload(
        payload_id=payload_id,
        title=title,
        status=DashboardStatus.READY,
        data=data or {},
        components=components or [],
        metrics=metrics or [],
        metadata=metadata or {},
    )


def dashboard_error_payload(
    *,
    payload_id: str,
    title: str,
    error_code: str,
    error_message: str,
    source: str = "",
    metadata: dict[str, Any] | None = None,
) -> DashboardPayload:
    """Build dashboard error payload."""
    return build_dashboard_payload(
        payload_id=payload_id,
        title=title,
        status=DashboardStatus.ERROR,
        issues=[
            build_dashboard_issue(
                code=error_code,
                message=error_message,
                severity=DashboardSeverity.ERROR,
                source=source,
            ),
        ],
        metadata=metadata or {},
    )