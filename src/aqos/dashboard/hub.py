"""
AQOS dashboard aggregation hub.

This module aggregates market, signal/strategy, portfolio/risk, broker/provider
status, and custom dashboard payloads into one frontend-ready dashboard payload.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import Enum
from typing import Any

from aqos.dashboard.base import (
    DashboardComponent,
    DashboardIssue,
    DashboardMetric,
    DashboardPayload,
    DashboardRefreshMode,
    DashboardStatus,
    build_dashboard_component,
    build_dashboard_issue,
    build_dashboard_metric,
    build_dashboard_payload,
    normalize_dashboard_refresh_mode,
    normalize_dashboard_status,
    validate_dashboard_components,
    validate_dashboard_issues,
    validate_dashboard_metrics,
    validate_metadata,
    validate_non_empty_string,
    validate_string,
)


class DashboardSectionKind(str, Enum):
    """Supported dashboard aggregation section kinds."""

    MARKET = "market"
    SIGNALS = "signals"
    PORTFOLIO = "portfolio"
    STATUS = "status"
    CUSTOM = "custom"


class DashboardAggregationMode(str, Enum):
    """Supported dashboard aggregation modes."""

    FULL = "full"
    SUMMARY = "summary"
    COMPACT = "compact"


@dataclass(frozen=True)
class DashboardSection:
    """Dashboard aggregation section."""

    section_id: str
    title: str
    kind: DashboardSectionKind | str
    status: DashboardStatus | str = DashboardStatus.READY
    payload: DashboardPayload | None = None
    components: list[DashboardComponent] = field(default_factory=list)
    metrics: list[DashboardMetric] = field(default_factory=list)
    issues: list[DashboardIssue] = field(default_factory=list)
    data: dict[str, Any] = field(default_factory=dict)
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        validate_non_empty_string(self.section_id, "Section ID")
        validate_non_empty_string(self.title, "Section title")
        normalize_dashboard_section_kind(self.kind)
        normalize_dashboard_status(self.status)

        if self.payload is not None and not isinstance(self.payload, DashboardPayload):
            raise ValueError("Payload must be DashboardPayload.")

        validate_dashboard_components(self.components)
        validate_dashboard_metrics(self.metrics)
        validate_dashboard_issues(self.issues)
        validate_metadata(self.data, "Data")
        validate_metadata(self.metadata, "Metadata")

    @property
    def healthy(self) -> bool:
        """Return whether section is healthy."""
        if normalize_dashboard_status(self.status) != DashboardStatus.READY:
            return False

        if self.payload is not None:
            return self.payload.healthy

        return True

    @property
    def payload_id(self) -> str:
        """Return nested payload ID."""
        return self.payload.payload_id if self.payload is not None else ""

    @property
    def component_count(self) -> int:
        """Return component count."""
        nested_count = self.payload.component_count if self.payload is not None else 0
        return nested_count + len(self.components)

    @property
    def metric_count(self) -> int:
        """Return metric count."""
        nested_count = self.payload.metric_count if self.payload is not None else 0
        return nested_count + len(self.metrics)

    @property
    def issue_count(self) -> int:
        """Return issue count."""
        nested_count = self.payload.issue_count if self.payload is not None else 0
        return nested_count + len(self.issues)

    def resolved_components(self) -> list[DashboardComponent]:
        """Return section components including payload components."""
        payload_components = self.payload.components if self.payload is not None else []
        return [
            *payload_components,
            *self.components,
        ]

    def resolved_metrics(self) -> list[DashboardMetric]:
        """Return section metrics including payload metrics."""
        payload_metrics = self.payload.metrics if self.payload is not None else []
        return [
            *payload_metrics,
            *self.metrics,
        ]

    def resolved_issues(self) -> list[DashboardIssue]:
        """Return section issues including payload issues."""
        payload_issues = self.payload.issues if self.payload is not None else []
        return [
            *payload_issues,
            *self.issues,
        ]

    def to_dict(self) -> dict[str, Any]:
        """Convert section into dictionary."""
        return {
            "section_id": self.section_id.strip(),
            "title": self.title.strip(),
            "kind": normalize_dashboard_section_kind(self.kind).value,
            "status": normalize_dashboard_status(self.status).value,
            "healthy": self.healthy,
            "payload_id": self.payload_id,
            "payload": self.payload.to_dict() if self.payload is not None else None,
            "components": [component.to_dict() for component in self.components],
            "metrics": [metric.to_dict() for metric in self.metrics],
            "issues": [issue.to_dict() for issue in self.issues],
            "data": dict(self.data),
            "component_count": self.component_count,
            "metric_count": self.metric_count,
            "issue_count": self.issue_count,
            "metadata": dict(self.metadata),
        }


@dataclass(frozen=True)
class DashboardAggregationSnapshot:
    """Aggregated dashboard snapshot."""

    snapshot_id: str
    title: str
    sections: list[DashboardSection] = field(default_factory=list)
    status: DashboardStatus | str = DashboardStatus.READY
    refresh_mode: DashboardRefreshMode | str = DashboardRefreshMode.AUTO
    generated_at: str = field(default_factory=lambda: datetime.now(UTC).isoformat())
    data: dict[str, Any] = field(default_factory=dict)
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        validate_non_empty_string(self.snapshot_id, "Snapshot ID")
        validate_non_empty_string(self.title, "Snapshot title")
        validate_dashboard_sections(self.sections)
        normalize_dashboard_status(self.status)
        normalize_dashboard_refresh_mode(self.refresh_mode)
        validate_non_empty_string(self.generated_at, "Generated at")
        validate_metadata(self.data, "Data")
        validate_metadata(self.metadata, "Metadata")

    @property
    def section_count(self) -> int:
        """Return section count."""
        return len(self.sections)

    @property
    def payload_count(self) -> int:
        """Return nested payload count."""
        return len([section for section in self.sections if section.payload is not None])

    @property
    def component_count(self) -> int:
        """Return total component count."""
        return sum(section.component_count for section in self.sections)

    @property
    def metric_count(self) -> int:
        """Return total metric count."""
        return sum(section.metric_count for section in self.sections)

    @property
    def issue_count(self) -> int:
        """Return total issue count."""
        return sum(section.issue_count for section in self.sections)

    @property
    def healthy(self) -> bool:
        """Return whether aggregated snapshot is healthy."""
        return normalize_dashboard_status(self.status) == DashboardStatus.READY and all(
            section.healthy for section in self.sections
        )

    def resolved_components(self) -> list[DashboardComponent]:
        """Return aggregated components."""
        components: list[DashboardComponent] = []

        for section in self.sections:
            components.extend(section.resolved_components())

        return components

    def resolved_metrics(self) -> list[DashboardMetric]:
        """Return aggregated metrics."""
        metrics: list[DashboardMetric] = []

        for section in self.sections:
            metrics.extend(section.resolved_metrics())

        return metrics

    def resolved_issues(self) -> list[DashboardIssue]:
        """Return aggregated issues."""
        issues: list[DashboardIssue] = []

        for section in self.sections:
            issues.extend(section.resolved_issues())

        return issues

    def to_dashboard_payload(
        self,
        *,
        mode: DashboardAggregationMode | str = DashboardAggregationMode.FULL,
    ) -> DashboardPayload:
        """Convert aggregation snapshot into dashboard payload."""
        resolved_mode = normalize_dashboard_aggregation_mode(mode)

        if resolved_mode == DashboardAggregationMode.COMPACT:
            components: list[DashboardComponent] = []
            metrics = build_aggregation_summary_metrics(self)
        elif resolved_mode == DashboardAggregationMode.SUMMARY:
            components = build_section_summary_components(self.sections)
            metrics = build_aggregation_summary_metrics(self)
        else:
            components = [
                *build_section_summary_components(self.sections),
                *self.resolved_components(),
            ]
            metrics = [
                *build_aggregation_summary_metrics(self),
                *self.resolved_metrics(),
            ]

        status = normalize_dashboard_status(self.status)

        if self.issue_count > 0 and status == DashboardStatus.READY:
            status = DashboardStatus.WARNING

        if not self.sections:
            status = DashboardStatus.EMPTY

        return build_dashboard_payload(
            payload_id=self.snapshot_id,
            title=self.title,
            status=status,
            refresh_mode=self.refresh_mode,
            generated_at=self.generated_at,
            components=components,
            metrics=metrics,
            issues=self.resolved_issues(),
            data={
                **self.data,
                "sections": [section.to_dict() for section in self.sections],
                "section_count": self.section_count,
                "payload_count": self.payload_count,
                "aggregation_mode": resolved_mode.value,
            },
            metadata={
                **self.metadata,
                "source": "dashboard.hub",
            },
        )

    def to_dict(self) -> dict[str, Any]:
        """Convert aggregation snapshot into dictionary."""
        return {
            "snapshot_id": self.snapshot_id.strip(),
            "title": self.title.strip(),
            "status": normalize_dashboard_status(self.status).value,
            "healthy": self.healthy,
            "refresh_mode": normalize_dashboard_refresh_mode(self.refresh_mode).value,
            "generated_at": self.generated_at.strip(),
            "sections": [section.to_dict() for section in self.sections],
            "section_count": self.section_count,
            "payload_count": self.payload_count,
            "component_count": self.component_count,
            "metric_count": self.metric_count,
            "issue_count": self.issue_count,
            "data": dict(self.data),
            "metadata": dict(self.metadata),
        }


@dataclass
class DashboardAggregationHub:
    """Dashboard aggregation hub."""

    sections: dict[str, DashboardSection] = field(default_factory=dict)
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        validate_dashboard_section_dict(self.sections)
        validate_metadata(self.metadata, "Metadata")

    @property
    def section_count(self) -> int:
        """Return registered section count."""
        return len(self.sections)

    def register_section(self, section: DashboardSection) -> DashboardSection:
        """Register dashboard section."""
        if not isinstance(section, DashboardSection):
            raise ValueError("Section must be DashboardSection.")

        self.sections[section.section_id.strip()] = section
        return section

    def register_payload(
        self,
        *,
        section_id: str,
        title: str,
        kind: DashboardSectionKind | str,
        payload: DashboardPayload,
        status: DashboardStatus | str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> DashboardSection:
        """Register dashboard payload as a section."""
        if not isinstance(payload, DashboardPayload):
            raise ValueError("Payload must be DashboardPayload.")

        section = build_dashboard_section(
            section_id=section_id,
            title=title,
            kind=kind,
            status=status or payload.status,
            payload=payload,
            metadata=metadata or {},
        )

        return self.register_section(section)

    def get_section(self, section_id: str) -> DashboardSection | None:
        """Get registered section."""
        normalized_section_id = validate_non_empty_string(section_id, "Section ID")
        return self.sections.get(normalized_section_id)

    def require_section(self, section_id: str) -> DashboardSection:
        """Require registered section."""
        section = self.get_section(section_id)

        if section is None:
            raise KeyError(f"Dashboard section '{section_id}' is not registered.")

        return section

    def remove_section(self, section_id: str) -> DashboardSection | None:
        """Remove registered section."""
        normalized_section_id = validate_non_empty_string(section_id, "Section ID")
        return self.sections.pop(normalized_section_id, None)

    def clear(self) -> None:
        """Clear registered sections."""
        self.sections.clear()

    def list_sections(self) -> list[DashboardSection]:
        """List registered sections."""
        return list(self.sections.values())

    def build_snapshot(
        self,
        *,
        snapshot_id: str = "aqos-dashboard",
        title: str = "AQOS Dashboard",
        status: DashboardStatus | str | None = None,
        refresh_mode: DashboardRefreshMode | str = DashboardRefreshMode.AUTO,
        generated_at: str | None = None,
        data: dict[str, Any] | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> DashboardAggregationSnapshot:
        """Build aggregated dashboard snapshot."""
        sections = self.list_sections()
        resolved_status = status or infer_aggregation_status(sections)

        snapshot_kwargs: dict[str, Any] = {
            "snapshot_id": snapshot_id,
            "title": title,
            "sections": sections,
            "status": resolved_status,
            "refresh_mode": refresh_mode,
            "data": data or {},
            "metadata": {
                **self.metadata,
                **(metadata or {}),
            },
        }

        if generated_at is not None:
            snapshot_kwargs["generated_at"] = generated_at

        return DashboardAggregationSnapshot(**snapshot_kwargs)

    def build_payload(
        self,
        *,
        snapshot_id: str = "aqos-dashboard",
        title: str = "AQOS Dashboard",
        mode: DashboardAggregationMode | str = DashboardAggregationMode.FULL,
    ) -> DashboardPayload:
        """Build aggregated dashboard payload."""
        return self.build_snapshot(
            snapshot_id=snapshot_id,
            title=title,
        ).to_dashboard_payload(mode=mode)

    def summary(self) -> dict[str, Any]:
        """Return hub summary."""
        snapshot = self.build_snapshot()

        return {
            "section_count": self.section_count,
            "component_count": snapshot.component_count,
            "metric_count": snapshot.metric_count,
            "issue_count": snapshot.issue_count,
            "metadata": dict(self.metadata),
        }


def normalize_dashboard_section_kind(
    kind: DashboardSectionKind | str,
) -> DashboardSectionKind:
    """Normalize dashboard section kind."""
    if isinstance(kind, DashboardSectionKind):
        return kind

    normalized = validate_non_empty_string(kind, "Dashboard section kind").lower()

    try:
        return DashboardSectionKind(normalized)
    except ValueError as exc:
        valid = ", ".join(item.value for item in DashboardSectionKind)
        raise ValueError(
            f"Invalid dashboard section kind '{kind}'. Valid kinds: {valid}.",
        ) from exc


def normalize_dashboard_aggregation_mode(
    mode: DashboardAggregationMode | str,
) -> DashboardAggregationMode:
    """Normalize dashboard aggregation mode."""
    if isinstance(mode, DashboardAggregationMode):
        return mode

    normalized = validate_non_empty_string(mode, "Dashboard aggregation mode").lower()

    try:
        return DashboardAggregationMode(normalized)
    except ValueError as exc:
        valid = ", ".join(item.value for item in DashboardAggregationMode)
        raise ValueError(
            f"Invalid dashboard aggregation mode '{mode}'. Valid modes: {valid}.",
        ) from exc


def validate_dashboard_sections(
    sections: list[DashboardSection],
) -> list[DashboardSection]:
    """Validate dashboard sections."""
    if not isinstance(sections, list):
        raise ValueError("Sections must be a list.")

    for section in sections:
        if not isinstance(section, DashboardSection):
            raise ValueError("Sections must contain DashboardSection objects.")

    return sections


def validate_dashboard_section_dict(
    sections: dict[str, DashboardSection],
) -> dict[str, DashboardSection]:
    """Validate dashboard section dictionary."""
    if not isinstance(sections, dict):
        raise ValueError("Sections must be a dictionary.")

    for key, section in sections.items():
        validate_non_empty_string(str(key), "Section key")

        if not isinstance(section, DashboardSection):
            raise ValueError("Section dictionary values must be DashboardSection objects.")

    return sections


def build_dashboard_section(
    *,
    section_id: str,
    title: str,
    kind: DashboardSectionKind | str,
    status: DashboardStatus | str = DashboardStatus.READY,
    payload: DashboardPayload | None = None,
    components: list[DashboardComponent] | None = None,
    metrics: list[DashboardMetric] | None = None,
    issues: list[DashboardIssue] | None = None,
    data: dict[str, Any] | None = None,
    metadata: dict[str, Any] | None = None,
) -> DashboardSection:
    """Build dashboard section."""
    return DashboardSection(
        section_id=section_id,
        title=title,
        kind=kind,
        status=status,
        payload=payload,
        components=components or [],
        metrics=metrics or [],
        issues=issues or [],
        data=data or {},
        metadata=metadata or {},
    )


def build_dashboard_aggregation_snapshot(
    *,
    snapshot_id: str,
    title: str,
    sections: list[DashboardSection] | None = None,
    status: DashboardStatus | str = DashboardStatus.READY,
    refresh_mode: DashboardRefreshMode | str = DashboardRefreshMode.AUTO,
    generated_at: str | None = None,
    data: dict[str, Any] | None = None,
    metadata: dict[str, Any] | None = None,
) -> DashboardAggregationSnapshot:
    """Build dashboard aggregation snapshot."""
    snapshot_kwargs: dict[str, Any] = {
        "snapshot_id": snapshot_id,
        "title": title,
        "sections": sections or [],
        "status": status,
        "refresh_mode": refresh_mode,
        "data": data or {},
        "metadata": metadata or {},
    }

    if generated_at is not None:
        snapshot_kwargs["generated_at"] = generated_at

    return DashboardAggregationSnapshot(**snapshot_kwargs)


def build_dashboard_aggregation_hub(
    *,
    sections: dict[str, DashboardSection] | None = None,
    metadata: dict[str, Any] | None = None,
) -> DashboardAggregationHub:
    """Build dashboard aggregation hub."""
    return DashboardAggregationHub(
        sections=sections or {},
        metadata=metadata or {},
    )


def build_section_from_payload(
    *,
    section_id: str,
    title: str,
    kind: DashboardSectionKind | str,
    payload: DashboardPayload,
    metadata: dict[str, Any] | None = None,
) -> DashboardSection:
    """Build dashboard section from payload."""
    if not isinstance(payload, DashboardPayload):
        raise ValueError("Payload must be DashboardPayload.")

    return build_dashboard_section(
        section_id=section_id,
        title=title,
        kind=kind,
        status=payload.status,
        payload=payload,
        metadata=metadata or {},
    )


def infer_aggregation_status(
    sections: list[DashboardSection],
) -> DashboardStatus:
    """Infer aggregation status from sections."""
    validate_dashboard_sections(sections)

    if not sections:
        return DashboardStatus.EMPTY

    statuses = [normalize_dashboard_status(section.status) for section in sections]

    if DashboardStatus.ERROR in statuses:
        return DashboardStatus.ERROR

    if DashboardStatus.WARNING in statuses:
        return DashboardStatus.WARNING

    if all(status == DashboardStatus.EMPTY for status in statuses):
        return DashboardStatus.EMPTY

    if DashboardStatus.EMPTY in statuses:
        return DashboardStatus.WARNING

    return DashboardStatus.READY


def build_aggregation_summary_metrics(
    snapshot: DashboardAggregationSnapshot,
) -> list[DashboardMetric]:
    """Build aggregation summary metrics."""
    if not isinstance(snapshot, DashboardAggregationSnapshot):
        raise ValueError("Snapshot must be DashboardAggregationSnapshot.")

    status = DashboardStatus.READY if snapshot.healthy else DashboardStatus.WARNING

    if normalize_dashboard_status(snapshot.status) == DashboardStatus.ERROR:
        status = DashboardStatus.ERROR

    if snapshot.section_count == 0:
        status = DashboardStatus.EMPTY

    return [
        build_dashboard_metric(name="section_count", label="Sections", value=snapshot.section_count, status=status),
        build_dashboard_metric(name="payload_count", label="Payloads", value=snapshot.payload_count, status=status),
        build_dashboard_metric(name="component_count", label="Components", value=snapshot.component_count, status=status),
        build_dashboard_metric(name="metric_count", label="Metrics", value=snapshot.metric_count, status=status),
        build_dashboard_metric(name="issue_count", label="Issues", value=snapshot.issue_count, status=status),
    ]


def build_section_summary_components(
    sections: list[DashboardSection],
) -> list[DashboardComponent]:
    """Build summary components for sections."""
    validate_dashboard_sections(sections)

    return [
        build_dashboard_component(
            component_id=f"section-summary-{section.section_id.strip()}",
            title=section.title,
            component_type="section",
            status=section.status,
            description=f"{normalize_dashboard_section_kind(section.kind).value.title()} dashboard section.",
            data={
                "section_id": section.section_id,
                "kind": normalize_dashboard_section_kind(section.kind).value,
                "payload_id": section.payload_id,
                "component_count": section.component_count,
                "metric_count": section.metric_count,
                "issue_count": section.issue_count,
            },
            metrics=[
                build_dashboard_metric(name="component_count", label="Components", value=section.component_count),
                build_dashboard_metric(name="metric_count", label="Metrics", value=section.metric_count),
                build_dashboard_metric(name="issue_count", label="Issues", value=section.issue_count),
            ],
            issues=section.issues,
            metadata=dict(section.metadata),
        )
        for section in sections
    ]


def aggregate_dashboard_payloads(
    *,
    payloads: dict[str, DashboardPayload],
    section_kinds: dict[str, DashboardSectionKind | str] | None = None,
    snapshot_id: str = "aqos-dashboard",
    title: str = "AQOS Dashboard",
    mode: DashboardAggregationMode | str = DashboardAggregationMode.FULL,
) -> DashboardPayload:
    """Aggregate dashboard payloads into one dashboard payload."""
    validate_payload_dict(payloads)
    resolved_section_kinds = section_kinds or {}

    hub = build_dashboard_aggregation_hub()

    for section_id, payload in payloads.items():
        hub.register_payload(
            section_id=section_id,
            title=payload.title,
            kind=resolved_section_kinds.get(section_id, DashboardSectionKind.CUSTOM),
            payload=payload,
        )

    return hub.build_payload(
        snapshot_id=snapshot_id,
        title=title,
        mode=mode,
    )


def validate_payload_dict(
    payloads: dict[str, DashboardPayload],
) -> dict[str, DashboardPayload]:
    """Validate payload dictionary."""
    if not isinstance(payloads, dict):
        raise ValueError("Payloads must be a dictionary.")

    for key, payload in payloads.items():
        validate_non_empty_string(str(key), "Payload key")

        if not isinstance(payload, DashboardPayload):
            raise ValueError("Payload dictionary values must be DashboardPayload objects.")

    return payloads


def dashboard_aggregation_error_payload(
    *,
    error_code: str,
    error_message: str,
    payload_id: str = "aqos-dashboard-error",
    title: str = "AQOS Dashboard Error",
    source: str = "dashboard.hub",
    metadata: dict[str, Any] | None = None,
) -> DashboardPayload:
    """Build dashboard aggregation error payload."""
    validate_non_empty_string(error_code, "Error code")
    validate_non_empty_string(error_message, "Error message")
    validate_string(source, "Source")

    return build_dashboard_payload(
        payload_id=payload_id,
        title=title,
        status=DashboardStatus.ERROR,
        issues=[
            build_dashboard_issue(
                code=error_code,
                message=error_message,
                severity="error",
                source=source,
            ),
        ],
        metadata=metadata or {},
    )