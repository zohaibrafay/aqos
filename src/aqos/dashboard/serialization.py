"""
AQOS dashboard frontend serialization helpers.

This module converts dashboard payloads, components, metrics, widgets, and
aggregation outputs into JSON-safe API responses for frontend dashboards,
SaaS UI, mobile apps, and external clients.
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field, is_dataclass
from datetime import date, datetime
from enum import Enum
from math import ceil
from typing import Any

from aqos.dashboard.base import (
    DashboardComponent,
    DashboardIssue,
    DashboardMetric,
    DashboardPayload,
    DashboardStatus,
    build_dashboard_issue,
    build_dashboard_payload,
    validate_dashboard_components,
    validate_dashboard_issues,
    validate_dashboard_metrics,
    validate_metadata,
    validate_non_empty_string,
    validate_string,
)
from aqos.dashboard.signals import validate_non_negative_integer


class DashboardSerializationFormat(str, Enum):
    """Supported dashboard serialization formats."""

    DICT = "dict"
    JSON = "json"


class DashboardApiResponseStatus(str, Enum):
    """Supported dashboard API response statuses."""

    SUCCESS = "success"
    ERROR = "error"


@dataclass(frozen=True)
class DashboardPagination:
    """Frontend pagination metadata."""

    page: int = 1
    page_size: int = 25
    total_items: int = 0
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        validate_positive_integer(self.page, "Page")
        validate_positive_integer(self.page_size, "Page size")
        validate_non_negative_integer(self.total_items, "Total items")
        validate_metadata(self.metadata, "Metadata")

    @property
    def total_pages(self) -> int:
        """Return total page count."""
        if self.total_items <= 0:
            return 0

        return ceil(self.total_items / self.page_size)

    @property
    def offset(self) -> int:
        """Return zero-based offset."""
        return (self.page - 1) * self.page_size

    @property
    def limit(self) -> int:
        """Return limit."""
        return self.page_size

    @property
    def has_next(self) -> bool:
        """Return whether next page exists."""
        return self.total_pages > 0 and self.page < self.total_pages

    @property
    def has_previous(self) -> bool:
        """Return whether previous page exists."""
        return self.page > 1 and self.total_pages > 0

    def to_dict(self) -> dict[str, Any]:
        """Convert pagination into dictionary."""
        return {
            "page": self.page,
            "page_size": self.page_size,
            "total_items": self.total_items,
            "total_pages": self.total_pages,
            "offset": self.offset,
            "limit": self.limit,
            "has_next": self.has_next,
            "has_previous": self.has_previous,
            "metadata": dict(self.metadata),
        }


@dataclass(frozen=True)
class DashboardApiEnvelope:
    """Frontend/API response envelope."""

    response_id: str
    status: DashboardApiResponseStatus | str
    payload: dict[str, Any] = field(default_factory=dict)
    error: str = ""
    issues: list[DashboardIssue] = field(default_factory=list)
    pagination: DashboardPagination | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        validate_non_empty_string(self.response_id, "Response ID")
        normalize_dashboard_api_response_status(self.status)
        validate_metadata(self.payload, "Payload")
        validate_string(self.error, "Error")
        validate_dashboard_issues(self.issues)

        if self.pagination is not None and not isinstance(self.pagination, DashboardPagination):
            raise ValueError("Pagination must be DashboardPagination.")

        validate_metadata(self.metadata, "Metadata")

    @property
    def success(self) -> bool:
        """Return whether envelope is successful."""
        return normalize_dashboard_api_response_status(self.status) == DashboardApiResponseStatus.SUCCESS

    @property
    def failed(self) -> bool:
        """Return whether envelope failed."""
        return not self.success

    @property
    def issue_count(self) -> int:
        """Return issue count."""
        return len(self.issues)

    def to_dict(self) -> dict[str, Any]:
        """Convert envelope into dictionary."""
        return {
            "response_id": self.response_id.strip(),
            "status": normalize_dashboard_api_response_status(self.status).value,
            "success": self.success,
            "failed": self.failed,
            "payload": sanitize_dashboard_value(self.payload),
            "error": self.error.strip(),
            "issues": [issue.to_dict() for issue in self.issues],
            "issue_count": self.issue_count,
            "pagination": self.pagination.to_dict() if self.pagination else None,
            "metadata": sanitize_dashboard_value(self.metadata),
        }


def normalize_dashboard_serialization_format(
    serialization_format: DashboardSerializationFormat | str,
) -> DashboardSerializationFormat:
    """Normalize dashboard serialization format."""
    if isinstance(serialization_format, DashboardSerializationFormat):
        return serialization_format

    normalized = validate_non_empty_string(serialization_format, "Serialization format").lower()

    try:
        return DashboardSerializationFormat(normalized)
    except ValueError as exc:
        valid = ", ".join(item.value for item in DashboardSerializationFormat)
        raise ValueError(
            f"Invalid serialization format '{serialization_format}'. Valid formats: {valid}.",
        ) from exc


def normalize_dashboard_api_response_status(
    status: DashboardApiResponseStatus | str,
) -> DashboardApiResponseStatus:
    """Normalize dashboard API response status."""
    if isinstance(status, DashboardApiResponseStatus):
        return status

    normalized = validate_non_empty_string(status, "API response status").lower()

    try:
        return DashboardApiResponseStatus(normalized)
    except ValueError as exc:
        valid = ", ".join(item.value for item in DashboardApiResponseStatus)
        raise ValueError(
            f"Invalid API response status '{status}'. Valid statuses: {valid}.",
        ) from exc


def validate_positive_integer(value: int, field_name: str) -> int:
    """Validate positive integer."""
    if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
        raise ValueError(f"{field_name} must be a positive integer.")

    return value


def sanitize_dashboard_value(value: Any) -> Any:
    """Convert value into JSON-safe frontend value."""
    if value is None or isinstance(value, str | int | float | bool):
        return value

    if isinstance(value, Enum):
        return value.value

    if isinstance(value, datetime | date):
        return value.isoformat()

    if hasattr(value, "to_dict") and callable(value.to_dict):
        return sanitize_dashboard_value(value.to_dict())

    if is_dataclass(value):
        return sanitize_dashboard_value(asdict(value))

    if isinstance(value, dict):
        return {
            str(key): sanitize_dashboard_value(item)
            for key, item in value.items()
        }

    if isinstance(value, list | tuple | set):
        return [
            sanitize_dashboard_value(item)
            for item in value
        ]

    return str(value)


def dashboard_payload_to_dict(payload: DashboardPayload) -> dict[str, Any]:
    """Convert dashboard payload into JSON-safe dictionary."""
    if not isinstance(payload, DashboardPayload):
        raise ValueError("Payload must be DashboardPayload.")

    return sanitize_dashboard_value(payload.to_dict())


def dashboard_component_to_dict(component: DashboardComponent) -> dict[str, Any]:
    """Convert dashboard component into JSON-safe dictionary."""
    if not isinstance(component, DashboardComponent):
        raise ValueError("Component must be DashboardComponent.")

    return sanitize_dashboard_value(component.to_dict())


def dashboard_metric_to_dict(metric: DashboardMetric) -> dict[str, Any]:
    """Convert dashboard metric into JSON-safe dictionary."""
    if not isinstance(metric, DashboardMetric):
        raise ValueError("Metric must be DashboardMetric.")

    return sanitize_dashboard_value(metric.to_dict())


def dashboard_issue_to_dict(issue: DashboardIssue) -> dict[str, Any]:
    """Convert dashboard issue into JSON-safe dictionary."""
    if not isinstance(issue, DashboardIssue):
        raise ValueError("Issue must be DashboardIssue.")

    return sanitize_dashboard_value(issue.to_dict())


def dashboard_payload_to_json(
    payload: DashboardPayload,
    *,
    indent: int | None = None,
    sort_keys: bool = True,
) -> str:
    """Convert dashboard payload into JSON string."""
    return json.dumps(
        dashboard_payload_to_dict(payload),
        indent=indent,
        sort_keys=sort_keys,
    )


def dashboard_envelope_to_json(
    envelope: DashboardApiEnvelope,
    *,
    indent: int | None = None,
    sort_keys: bool = True,
) -> str:
    """Convert dashboard API envelope into JSON string."""
    if not isinstance(envelope, DashboardApiEnvelope):
        raise ValueError("Envelope must be DashboardApiEnvelope.")

    return json.dumps(
        envelope.to_dict(),
        indent=indent,
        sort_keys=sort_keys,
    )


def build_dashboard_pagination(
    *,
    page: int = 1,
    page_size: int = 25,
    total_items: int = 0,
    metadata: dict[str, Any] | None = None,
) -> DashboardPagination:
    """Build dashboard pagination metadata."""
    return DashboardPagination(
        page=page,
        page_size=page_size,
        total_items=total_items,
        metadata=metadata or {},
    )


def paginate_dashboard_items(
    items: list[dict[str, Any]],
    *,
    page: int = 1,
    page_size: int = 25,
) -> tuple[list[dict[str, Any]], DashboardPagination]:
    """Paginate frontend item dictionaries."""
    if not isinstance(items, list):
        raise ValueError("Items must be a list.")

    for item in items:
        validate_metadata(item, "Item")

    pagination = build_dashboard_pagination(
        page=page,
        page_size=page_size,
        total_items=len(items),
    )

    start = pagination.offset
    end = start + pagination.limit

    return items[start:end], pagination


def build_dashboard_api_envelope(
    *,
    response_id: str,
    status: DashboardApiResponseStatus | str,
    payload: dict[str, Any] | None = None,
    error: str = "",
    issues: list[DashboardIssue] | None = None,
    pagination: DashboardPagination | None = None,
    metadata: dict[str, Any] | None = None,
) -> DashboardApiEnvelope:
    """Build dashboard API envelope."""
    return DashboardApiEnvelope(
        response_id=response_id,
        status=status,
        payload=payload or {},
        error=error,
        issues=issues or [],
        pagination=pagination,
        metadata=metadata or {},
    )


def dashboard_payload_to_api_envelope(
    payload: DashboardPayload,
    *,
    response_id: str | None = None,
    metadata: dict[str, Any] | None = None,
) -> DashboardApiEnvelope:
    """Convert dashboard payload into API envelope."""
    if not isinstance(payload, DashboardPayload):
        raise ValueError("Payload must be DashboardPayload.")

    status = DashboardApiResponseStatus.SUCCESS

    if normalize_payload_status(payload.status) == DashboardStatus.ERROR:
        status = DashboardApiResponseStatus.ERROR

    return build_dashboard_api_envelope(
        response_id=response_id or payload.payload_id,
        status=status,
        payload=dashboard_payload_to_dict(payload),
        error="Dashboard payload is in error state." if status == DashboardApiResponseStatus.ERROR else "",
        issues=payload.issues,
        metadata={
            "payload_id": payload.payload_id,
            "dashboard_status": normalize_payload_status(payload.status).value,
            **(metadata or {}),
        },
    )


def dashboard_payloads_to_collection_envelope(
    *,
    payloads: list[DashboardPayload],
    response_id: str = "dashboard-payloads",
    page: int = 1,
    page_size: int = 25,
    metadata: dict[str, Any] | None = None,
) -> DashboardApiEnvelope:
    """Convert dashboard payload list into paginated API collection envelope."""
    if not isinstance(payloads, list):
        raise ValueError("Payloads must be a list.")

    for payload in payloads:
        if not isinstance(payload, DashboardPayload):
            raise ValueError("Payloads must contain DashboardPayload objects.")

    payload_items = [dashboard_payload_to_dict(payload) for payload in payloads]
    paginated_items, pagination = paginate_dashboard_items(
        payload_items,
        page=page,
        page_size=page_size,
    )

    return build_dashboard_api_envelope(
        response_id=response_id,
        status=DashboardApiResponseStatus.SUCCESS,
        payload={
            "items": paginated_items,
            "count": len(paginated_items),
            "total_count": len(payload_items),
        },
        pagination=pagination,
        metadata=metadata or {},
    )


def dashboard_components_to_collection_envelope(
    *,
    components: list[DashboardComponent],
    response_id: str = "dashboard-components",
    page: int = 1,
    page_size: int = 25,
    metadata: dict[str, Any] | None = None,
) -> DashboardApiEnvelope:
    """Convert dashboard components into paginated API collection envelope."""
    validate_dashboard_components(components)
    component_items = [dashboard_component_to_dict(component) for component in components]
    paginated_items, pagination = paginate_dashboard_items(
        component_items,
        page=page,
        page_size=page_size,
    )

    return build_dashboard_api_envelope(
        response_id=response_id,
        status=DashboardApiResponseStatus.SUCCESS,
        payload={
            "items": paginated_items,
            "count": len(paginated_items),
            "total_count": len(component_items),
        },
        pagination=pagination,
        metadata=metadata or {},
    )


def dashboard_metrics_to_collection_envelope(
    *,
    metrics: list[DashboardMetric],
    response_id: str = "dashboard-metrics",
    metadata: dict[str, Any] | None = None,
) -> DashboardApiEnvelope:
    """Convert dashboard metrics into API collection envelope."""
    validate_dashboard_metrics(metrics)

    return build_dashboard_api_envelope(
        response_id=response_id,
        status=DashboardApiResponseStatus.SUCCESS,
        payload={
            "items": [dashboard_metric_to_dict(metric) for metric in metrics],
            "count": len(metrics),
        },
        metadata=metadata or {},
    )


def dashboard_error_api_envelope(
    *,
    response_id: str = "dashboard-error",
    error_code: str,
    error_message: str,
    source: str = "dashboard.serialization",
    metadata: dict[str, Any] | None = None,
) -> DashboardApiEnvelope:
    """Build dashboard API error envelope."""
    issue = build_dashboard_issue(
        code=error_code,
        message=error_message,
        severity="error",
        source=source,
    )

    return build_dashboard_api_envelope(
        response_id=response_id,
        status=DashboardApiResponseStatus.ERROR,
        payload={},
        error=error_message,
        issues=[issue],
        metadata=metadata or {},
    )


def normalize_payload_status(status: DashboardStatus | str) -> DashboardStatus:
    """Normalize payload status."""
    if isinstance(status, DashboardStatus):
        return status

    normalized = validate_non_empty_string(status, "Payload status").lower()

    try:
        return DashboardStatus(normalized)
    except ValueError as exc:
        valid = ", ".join(item.value for item in DashboardStatus)
        raise ValueError(
            f"Invalid payload status '{status}'. Valid statuses: {valid}.",
        ) from exc


def frontend_response_from_payload(
    payload: DashboardPayload,
    *,
    as_json: bool = False,
    indent: int | None = None,
) -> dict[str, Any] | str:
    """Build frontend response from dashboard payload."""
    envelope = dashboard_payload_to_api_envelope(payload)

    if as_json:
        return dashboard_envelope_to_json(
            envelope,
            indent=indent,
        )

    return envelope.to_dict()


def frontend_response_from_error(
    *,
    error_code: str,
    error_message: str,
    response_id: str = "dashboard-error",
    as_json: bool = False,
    indent: int | None = None,
) -> dict[str, Any] | str:
    """Build frontend error response."""
    envelope = dashboard_error_api_envelope(
        response_id=response_id,
        error_code=error_code,
        error_message=error_message,
    )

    if as_json:
        return dashboard_envelope_to_json(
            envelope,
            indent=indent,
        )

    return envelope.to_dict()


def build_frontend_ready_dashboard_payload(
    *,
    payload_id: str,
    title: str,
    components: list[DashboardComponent] | None = None,
    metrics: list[DashboardMetric] | None = None,
    issues: list[DashboardIssue] | None = None,
    data: dict[str, Any] | None = None,
    status: DashboardStatus | str = DashboardStatus.READY,
    metadata: dict[str, Any] | None = None,
) -> DashboardPayload:
    """Build sanitized frontend-ready dashboard payload."""
    return build_dashboard_payload(
        payload_id=payload_id,
        title=title,
        status=status,
        components=components or [],
        metrics=metrics or [],
        issues=issues or [],
        data=sanitize_dashboard_value(data or {}),
        metadata=sanitize_dashboard_value(metadata or {}),
    )