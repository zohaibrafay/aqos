"""
AQOS broker and provider status dashboard payloads.

This module prepares frontend-ready broker/provider status widgets, health cards,
tables, and payloads for dashboards and external clients.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any

from aqos.dashboard.base import (
    DashboardPayload,
    DashboardStatus,
    build_dashboard_component,
    build_dashboard_issue,
    build_dashboard_metric,
    build_dashboard_payload,
    validate_metadata,
    validate_non_empty_string,
    validate_non_negative_float,
    validate_non_negative_float as validate_latency,
    validate_non_negative_float as validate_count_float,
    validate_string,
)
from aqos.dashboard.signals import validate_non_negative_integer
from aqos.dashboard.widgets import (
    DashboardCard,
    DashboardWidget,
    DashboardWidgetSize,
    DashboardWidgetType,
    build_dashboard_card,
    build_dashboard_chart_series,
    build_dashboard_table_column,
    build_dashboard_widget,
    build_dashboard_widget_action,
    card_to_dashboard_component,
    widget_to_dashboard_component,
)


class IntegrationStatusKind(str, Enum):
    """Supported integration status kinds."""

    BROKER = "broker"
    PROVIDER = "provider"
    EXCHANGE = "exchange"
    DATA = "data"
    EXECUTION = "execution"
    UNKNOWN = "unknown"


class IntegrationHealthState(str, Enum):
    """Supported integration health states."""

    ONLINE = "online"
    OFFLINE = "offline"
    DEGRADED = "degraded"
    ERROR = "error"
    UNKNOWN = "unknown"


@dataclass(frozen=True)
class IntegrationStatusItem:
    """Frontend-ready broker/provider status item."""

    status_id: str
    name: str
    kind: IntegrationStatusKind | str
    health: IntegrationHealthState | str = IntegrationHealthState.UNKNOWN
    connected: bool = False
    active: bool = False
    capability_count: int = 0
    capabilities: list[str] = field(default_factory=list)
    latency_ms: float = 0.0
    last_checked_at: str = ""
    message: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        validate_non_empty_string(self.status_id, "Status ID")
        validate_non_empty_string(self.name, "Name")
        normalize_integration_status_kind(self.kind)
        normalize_integration_health_state(self.health)

        if not isinstance(self.connected, bool):
            raise ValueError("Connected must be a boolean.")

        if not isinstance(self.active, bool):
            raise ValueError("Active must be a boolean.")

        validate_non_negative_integer(self.capability_count, "Capability count")
        validate_capability_names(self.capabilities)
        validate_latency(self.latency_ms, "Latency milliseconds")
        validate_string(self.last_checked_at, "Last checked at")
        validate_string(self.message, "Message")
        validate_metadata(self.metadata, "Metadata")

    @property
    def healthy(self) -> bool:
        """Return whether integration is healthy."""
        return normalize_integration_health_state(self.health) == IntegrationHealthState.ONLINE

    @property
    def unhealthy(self) -> bool:
        """Return whether integration is unhealthy."""
        return normalize_integration_health_state(self.health) in {
            IntegrationHealthState.OFFLINE,
            IntegrationHealthState.ERROR,
        }

    @property
    def degraded(self) -> bool:
        """Return whether integration is degraded."""
        return normalize_integration_health_state(self.health) == IntegrationHealthState.DEGRADED

    def to_dict(self) -> dict[str, Any]:
        """Convert status item into dictionary."""
        return {
            "status_id": self.status_id.strip(),
            "name": self.name.strip(),
            "kind": normalize_integration_status_kind(self.kind).value,
            "health": normalize_integration_health_state(self.health).value,
            "connected": self.connected,
            "active": self.active,
            "healthy": self.healthy,
            "unhealthy": self.unhealthy,
            "degraded": self.degraded,
            "capability_count": self.capability_count,
            "capabilities": [capability.strip() for capability in self.capabilities],
            "latency_ms": float(self.latency_ms),
            "last_checked_at": self.last_checked_at.strip(),
            "message": self.message.strip(),
            "metadata": dict(self.metadata),
        }


@dataclass(frozen=True)
class BrokerProviderStatusSnapshot:
    """Frontend-ready broker/provider status snapshot."""

    snapshot_id: str
    items: list[IntegrationStatusItem] = field(default_factory=list)
    generated_at: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        validate_non_empty_string(self.snapshot_id, "Snapshot ID")
        validate_integration_status_items(self.items)
        validate_string(self.generated_at, "Generated at")
        validate_metadata(self.metadata, "Metadata")

    @property
    def item_count(self) -> int:
        """Return total item count."""
        return len(self.items)

    @property
    def broker_count(self) -> int:
        """Return broker count."""
        return len(
            [
                item
                for item in self.items
                if normalize_integration_status_kind(item.kind)
                in {IntegrationStatusKind.BROKER, IntegrationStatusKind.EXCHANGE, IntegrationStatusKind.EXECUTION}
            ],
        )

    @property
    def provider_count(self) -> int:
        """Return provider count."""
        return len(
            [
                item
                for item in self.items
                if normalize_integration_status_kind(item.kind)
                in {IntegrationStatusKind.PROVIDER, IntegrationStatusKind.DATA}
            ],
        )

    @property
    def online_count(self) -> int:
        """Return online count."""
        return len([item for item in self.items if item.healthy])

    @property
    def degraded_count(self) -> int:
        """Return degraded count."""
        return len([item for item in self.items if item.degraded])

    @property
    def error_count(self) -> int:
        """Return error/offline count."""
        return len([item for item in self.items if item.unhealthy])

    @property
    def healthy(self) -> bool:
        """Return whether all integrations are healthy."""
        return self.item_count > 0 and self.error_count == 0

    def status_counts(self) -> dict[str, int]:
        """Return health counts."""
        counts = {
            IntegrationHealthState.ONLINE.value: 0,
            IntegrationHealthState.OFFLINE.value: 0,
            IntegrationHealthState.DEGRADED.value: 0,
            IntegrationHealthState.ERROR.value: 0,
            IntegrationHealthState.UNKNOWN.value: 0,
        }

        for item in self.items:
            counts[normalize_integration_health_state(item.health).value] += 1

        return counts

    def to_dict(self) -> dict[str, Any]:
        """Convert status snapshot into dictionary."""
        return {
            "snapshot_id": self.snapshot_id.strip(),
            "items": [item.to_dict() for item in self.items],
            "generated_at": self.generated_at.strip(),
            "item_count": self.item_count,
            "broker_count": self.broker_count,
            "provider_count": self.provider_count,
            "online_count": self.online_count,
            "degraded_count": self.degraded_count,
            "error_count": self.error_count,
            "healthy": self.healthy,
            "status_counts": self.status_counts(),
            "metadata": dict(self.metadata),
        }


def normalize_integration_status_kind(
    kind: IntegrationStatusKind | str,
) -> IntegrationStatusKind:
    """Normalize integration status kind."""
    if isinstance(kind, IntegrationStatusKind):
        return kind

    normalized = validate_non_empty_string(kind, "Integration kind").lower()

    try:
        return IntegrationStatusKind(normalized)
    except ValueError as exc:
        valid = ", ".join(item.value for item in IntegrationStatusKind)
        raise ValueError(
            f"Invalid integration kind '{kind}'. Valid kinds: {valid}.",
        ) from exc


def normalize_integration_health_state(
    health: IntegrationHealthState | str,
) -> IntegrationHealthState:
    """Normalize integration health state."""
    if isinstance(health, IntegrationHealthState):
        return health

    normalized = validate_non_empty_string(health, "Integration health").lower()

    try:
        return IntegrationHealthState(normalized)
    except ValueError as exc:
        valid = ", ".join(item.value for item in IntegrationHealthState)
        raise ValueError(
            f"Invalid integration health '{health}'. Valid states: {valid}.",
        ) from exc


def validate_capability_names(capabilities: list[str]) -> list[str]:
    """Validate capability names."""
    if not isinstance(capabilities, list):
        raise ValueError("Capabilities must be a list.")

    for capability in capabilities:
        validate_non_empty_string(capability, "Capability")

    return capabilities


def validate_integration_status_items(
    items: list[IntegrationStatusItem],
) -> list[IntegrationStatusItem]:
    """Validate integration status items."""
    if not isinstance(items, list):
        raise ValueError("Items must be a list.")

    for item in items:
        if not isinstance(item, IntegrationStatusItem):
            raise ValueError("Items must contain IntegrationStatusItem objects.")

    return items


def integration_health_from_status(status: Any) -> IntegrationHealthState:
    """Convert broker/provider status values into dashboard health."""
    value = str(getattr(status, "value", status)).strip().lower()

    if value in {"active", "ready", "online", "ok", "healthy"}:
        return IntegrationHealthState.ONLINE

    if value in {"inactive", "offline", "empty"}:
        return IntegrationHealthState.OFFLINE

    if value in {"degraded", "warning"}:
        return IntegrationHealthState.DEGRADED

    if value in {"error", "failed", "failure"}:
        return IntegrationHealthState.ERROR

    return IntegrationHealthState.UNKNOWN


def dashboard_status_from_integration_health(
    health: IntegrationHealthState | str,
) -> DashboardStatus:
    """Convert integration health into dashboard status."""
    normalized = normalize_integration_health_state(health)

    if normalized == IntegrationHealthState.ONLINE:
        return DashboardStatus.READY

    if normalized == IntegrationHealthState.DEGRADED:
        return DashboardStatus.WARNING

    if normalized in {IntegrationHealthState.ERROR, IntegrationHealthState.OFFLINE}:
        return DashboardStatus.ERROR

    return DashboardStatus.EMPTY


def build_integration_status_item(
    *,
    status_id: str,
    name: str,
    kind: IntegrationStatusKind | str,
    health: IntegrationHealthState | str = IntegrationHealthState.UNKNOWN,
    connected: bool = False,
    active: bool = False,
    capability_count: int | None = None,
    capabilities: list[str] | None = None,
    latency_ms: float = 0.0,
    last_checked_at: str = "",
    message: str = "",
    metadata: dict[str, Any] | None = None,
) -> IntegrationStatusItem:
    """Build integration status item."""
    resolved_capabilities = capabilities or []

    return IntegrationStatusItem(
        status_id=status_id,
        name=name,
        kind=kind,
        health=health,
        connected=connected,
        active=active,
        capability_count=len(resolved_capabilities) if capability_count is None else capability_count,
        capabilities=resolved_capabilities,
        latency_ms=latency_ms,
        last_checked_at=last_checked_at,
        message=message,
        metadata=metadata or {},
    )


def status_dict_to_integration_item(status: dict[str, Any]) -> IntegrationStatusItem:
    """Convert raw status dictionary into integration item."""
    validate_metadata(status, "Status")

    return build_integration_status_item(
        status_id=str(status.get("status_id") or status.get("id") or ""),
        name=str(status.get("name", "")),
        kind=str(status.get("kind", IntegrationStatusKind.UNKNOWN.value)),
        health=str(status.get("health", IntegrationHealthState.UNKNOWN.value)),
        connected=bool(status.get("connected", False)),
        active=bool(status.get("active", False)),
        capability_count=int(status.get("capability_count", len(status.get("capabilities", []))) or 0),
        capabilities=[str(capability) for capability in status.get("capabilities", [])],
        latency_ms=float(status.get("latency_ms", 0.0) or 0.0),
        last_checked_at=str(status.get("last_checked_at", "")),
        message=str(status.get("message", "")),
        metadata=dict(status.get("metadata", {})),
    )


def broker_config_to_integration_item(config: Any) -> IntegrationStatusItem:
    """Convert BrokerConfig-like object into integration item."""
    if config is None:
        raise ValueError("Broker config is required.")

    broker_id = str(getattr(config, "broker_id", ""))
    name = str(getattr(config, "name", broker_id))
    broker_type = str(getattr(getattr(config, "broker_type", ""), "value", getattr(config, "broker_type", ""))).lower()
    status = getattr(config, "status", "unknown")
    capabilities = [
        str(getattr(capability, "value", capability))
        for capability in getattr(config, "capabilities", [])
    ]

    kind = IntegrationStatusKind.EXCHANGE if broker_type == "exchange" else IntegrationStatusKind.BROKER

    return build_integration_status_item(
        status_id=broker_id,
        name=name,
        kind=kind,
        health=integration_health_from_status(status),
        connected=bool(getattr(config, "active", False)),
        active=bool(getattr(config, "active", False)),
        capabilities=capabilities,
        message=f"Broker status: {str(getattr(status, 'value', status))}",
        metadata={
            "broker_type": broker_type,
            "paper_mode": bool(getattr(config, "paper_mode", False)),
            "base_url": str(getattr(config, "base_url", "")),
        },
    )


def provider_config_to_integration_item(config: Any) -> IntegrationStatusItem:
    """Convert ProviderConfig-like object into integration item."""
    if config is None:
        raise ValueError("Provider config is required.")

    provider_id = str(getattr(config, "provider_id", ""))
    name = str(getattr(config, "name", provider_id))
    provider_type = str(getattr(getattr(config, "provider_type", ""), "value", getattr(config, "provider_type", ""))).lower()
    status = getattr(config, "status", "unknown")
    capabilities = [
        str(getattr(capability, "value", capability))
        for capability in getattr(config, "capabilities", [])
    ]

    kind = IntegrationStatusKind.DATA if provider_type in {"market_data", "csv", "historical", "live"} else IntegrationStatusKind.PROVIDER

    return build_integration_status_item(
        status_id=provider_id,
        name=name,
        kind=kind,
        health=integration_health_from_status(status),
        connected=bool(getattr(config, "active", False)),
        active=bool(getattr(config, "active", False)),
        capabilities=capabilities,
        message=f"Provider status: {str(getattr(status, 'value', status))}",
        metadata={
            "provider_type": provider_type,
            "base_url": str(getattr(config, "base_url", "")),
        },
    )


def broker_registry_to_status_items(registry: Any) -> list[IntegrationStatusItem]:
    """Convert broker registry into status items."""
    if registry is None or not hasattr(registry, "list_entries"):
        raise ValueError("Broker registry must provide list_entries().")

    items: list[IntegrationStatusItem] = []

    for entry in registry.list_entries():
        item = broker_config_to_integration_item(entry.config)
        items.append(
            build_integration_status_item(
                status_id=item.status_id,
                name=item.name,
                kind=item.kind,
                health=item.health,
                connected=item.connected and bool(getattr(entry, "has_adapter", False)),
                active=item.active,
                capability_count=item.capability_count,
                capabilities=item.capabilities,
                message=item.message,
                metadata={
                    **item.metadata,
                    "has_adapter": bool(getattr(entry, "has_adapter", False)),
                    "has_account_adapter": bool(getattr(entry, "has_account_adapter", False)),
                },
            ),
        )

    return items


def provider_registry_to_status_items(registry: Any) -> list[IntegrationStatusItem]:
    """Convert provider registry into status items."""
    if registry is None or not hasattr(registry, "list_entries"):
        raise ValueError("Provider registry must provide list_entries().")

    items: list[IntegrationStatusItem] = []

    for entry in registry.list_entries():
        item = provider_config_to_integration_item(entry.config)
        items.append(
            build_integration_status_item(
                status_id=item.status_id,
                name=item.name,
                kind=item.kind,
                health=item.health,
                connected=item.connected and bool(getattr(entry, "has_adapter", False)),
                active=item.active,
                capability_count=item.capability_count,
                capabilities=item.capabilities,
                message=item.message,
                metadata={
                    **item.metadata,
                    "has_adapter": bool(getattr(entry, "has_adapter", False)),
                },
            ),
        )

    return items


def build_broker_provider_status_snapshot(
    *,
    snapshot_id: str = "broker-provider-status",
    broker_items: list[IntegrationStatusItem] | None = None,
    provider_items: list[IntegrationStatusItem] | None = None,
    generated_at: str = "",
    metadata: dict[str, Any] | None = None,
) -> BrokerProviderStatusSnapshot:
    """Build broker/provider status snapshot."""
    items = [
        *(broker_items or []),
        *(provider_items or []),
    ]

    return BrokerProviderStatusSnapshot(
        snapshot_id=snapshot_id,
        items=items,
        generated_at=generated_at,
        metadata=metadata or {},
    )


def build_broker_provider_status_snapshot_from_registries(
    *,
    broker_registry: Any | None = None,
    provider_registry: Any | None = None,
    snapshot_id: str = "broker-provider-status",
    generated_at: str = "",
    metadata: dict[str, Any] | None = None,
) -> BrokerProviderStatusSnapshot:
    """Build broker/provider status snapshot from registries."""
    broker_items = broker_registry_to_status_items(broker_registry) if broker_registry is not None else []
    provider_items = provider_registry_to_status_items(provider_registry) if provider_registry is not None else []

    return build_broker_provider_status_snapshot(
        snapshot_id=snapshot_id,
        broker_items=broker_items,
        provider_items=provider_items,
        generated_at=generated_at,
        metadata=metadata or {},
    )


def status_snapshot_to_metrics(
    snapshot: BrokerProviderStatusSnapshot,
) -> list:
    """Build status summary metrics."""
    if not isinstance(snapshot, BrokerProviderStatusSnapshot):
        raise ValueError("Snapshot must be BrokerProviderStatusSnapshot.")

    status = DashboardStatus.READY if snapshot.healthy else DashboardStatus.WARNING

    if snapshot.error_count > 0:
        status = DashboardStatus.ERROR

    return [
        build_dashboard_metric(name="integration_count", label="Integrations", value=snapshot.item_count, status=status),
        build_dashboard_metric(name="broker_count", label="Brokers", value=snapshot.broker_count, status=status),
        build_dashboard_metric(name="provider_count", label="Providers", value=snapshot.provider_count, status=status),
        build_dashboard_metric(name="online_count", label="Online", value=snapshot.online_count, status=status),
        build_dashboard_metric(name="degraded_count", label="Degraded", value=snapshot.degraded_count, status=status),
        build_dashboard_metric(name="error_count", label="Errors", value=snapshot.error_count, status=status),
    ]


def build_status_summary_widget(
    snapshot: BrokerProviderStatusSnapshot,
) -> DashboardWidget:
    """Build broker/provider status summary widget."""
    if not isinstance(snapshot, BrokerProviderStatusSnapshot):
        raise ValueError("Snapshot must be BrokerProviderStatusSnapshot.")

    status = DashboardStatus.READY if snapshot.healthy else DashboardStatus.WARNING

    if snapshot.error_count > 0:
        status = DashboardStatus.ERROR

    issues = []

    if snapshot.error_count > 0:
        issues.append(
            build_dashboard_issue(
                code="integration_errors",
                message="One or more broker/provider integrations are offline or in error state.",
                severity="error",
                source="dashboard.status",
                metadata={
                    "error_count": snapshot.error_count,
                },
            ),
        )
    elif snapshot.degraded_count > 0:
        issues.append(
            build_dashboard_issue(
                code="integration_degraded",
                message="One or more broker/provider integrations are degraded.",
                severity="warning",
                source="dashboard.status",
                metadata={
                    "degraded_count": snapshot.degraded_count,
                },
            ),
        )

    return build_dashboard_widget(
        widget_id="broker-provider-status-summary",
        title="Broker / Provider Status",
        widget_type=DashboardWidgetType.PROVIDER,
        status=status,
        size=DashboardWidgetSize.LARGE,
        chart_type="pie",
        description="Broker and provider health summary.",
        data=snapshot.to_dict(),
        metrics=status_snapshot_to_metrics(snapshot),
        issues=issues,
        actions=[
            build_dashboard_widget_action(
                action_id="refresh-status",
                label="Refresh",
                action_type="refresh",
                target="status",
            ),
        ],
        chart_series=[
            build_dashboard_chart_series(
                name="Health States",
                points=[
                    {"label": key, "value": value}
                    for key, value in snapshot.status_counts().items()
                ],
                chart_type="pie",
            ),
        ],
        metadata={
            "snapshot_id": snapshot.snapshot_id,
        },
    )


def build_status_table_widget(
    snapshot: BrokerProviderStatusSnapshot,
) -> DashboardWidget:
    """Build broker/provider status table widget."""
    if not isinstance(snapshot, BrokerProviderStatusSnapshot):
        raise ValueError("Snapshot must be BrokerProviderStatusSnapshot.")

    rows = [item.to_dict() for item in snapshot.items]

    return build_dashboard_widget(
        widget_id="broker-provider-status-table",
        title="Integration Status Table",
        widget_type=DashboardWidgetType.PROVIDER,
        status=DashboardStatus.READY if rows else DashboardStatus.EMPTY,
        size=DashboardWidgetSize.FULL,
        description="Broker and provider integration statuses.",
        table_columns=[
            build_dashboard_table_column(key="status_id", label="ID"),
            build_dashboard_table_column(key="name", label="Name"),
            build_dashboard_table_column(key="kind", label="Kind"),
            build_dashboard_table_column(key="health", label="Health"),
            build_dashboard_table_column(key="connected", label="Connected", data_type="boolean"),
            build_dashboard_table_column(key="active", label="Active", data_type="boolean"),
            build_dashboard_table_column(key="capability_count", label="Capabilities", data_type="number"),
            build_dashboard_table_column(key="latency_ms", label="Latency", data_type="number"),
            build_dashboard_table_column(key="message", label="Message"),
        ],
        table_rows=rows,
        metadata={
            "item_count": len(rows),
        },
    )


def build_broker_status_widget(
    snapshot: BrokerProviderStatusSnapshot,
) -> DashboardWidget:
    """Build broker status widget."""
    if not isinstance(snapshot, BrokerProviderStatusSnapshot):
        raise ValueError("Snapshot must be BrokerProviderStatusSnapshot.")

    broker_items = [
        item
        for item in snapshot.items
        if normalize_integration_status_kind(item.kind)
        in {IntegrationStatusKind.BROKER, IntegrationStatusKind.EXCHANGE, IntegrationStatusKind.EXECUTION}
    ]

    return build_dashboard_widget(
        widget_id="broker-status",
        title="Broker Status",
        widget_type=DashboardWidgetType.BROKER,
        status=DashboardStatus.READY if broker_items else DashboardStatus.EMPTY,
        size=DashboardWidgetSize.MEDIUM,
        description="Broker and exchange execution status.",
        metrics=[
            build_dashboard_metric(name="broker_count", label="Brokers", value=len(broker_items)),
            build_dashboard_metric(name="broker_online", label="Online", value=len([item for item in broker_items if item.healthy])),
            build_dashboard_metric(name="broker_errors", label="Errors", value=len([item for item in broker_items if item.unhealthy])),
        ],
        table_rows=[item.to_dict() for item in broker_items],
        metadata={
            "broker_count": len(broker_items),
        },
    )


def build_provider_status_widget(
    snapshot: BrokerProviderStatusSnapshot,
) -> DashboardWidget:
    """Build provider status widget."""
    if not isinstance(snapshot, BrokerProviderStatusSnapshot):
        raise ValueError("Snapshot must be BrokerProviderStatusSnapshot.")

    provider_items = [
        item
        for item in snapshot.items
        if normalize_integration_status_kind(item.kind)
        in {IntegrationStatusKind.PROVIDER, IntegrationStatusKind.DATA}
    ]

    return build_dashboard_widget(
        widget_id="provider-status",
        title="Provider Status",
        widget_type=DashboardWidgetType.PROVIDER,
        status=DashboardStatus.READY if provider_items else DashboardStatus.EMPTY,
        size=DashboardWidgetSize.MEDIUM,
        description="Market data provider status.",
        metrics=[
            build_dashboard_metric(name="provider_count", label="Providers", value=len(provider_items)),
            build_dashboard_metric(name="provider_online", label="Online", value=len([item for item in provider_items if item.healthy])),
            build_dashboard_metric(name="provider_errors", label="Errors", value=len([item for item in provider_items if item.unhealthy])),
        ],
        table_rows=[item.to_dict() for item in provider_items],
        metadata={
            "provider_count": len(provider_items),
        },
    )


def build_broker_provider_status_card(
    snapshot: BrokerProviderStatusSnapshot,
) -> DashboardCard:
    """Build broker/provider status dashboard card."""
    if not isinstance(snapshot, BrokerProviderStatusSnapshot):
        raise ValueError("Snapshot must be BrokerProviderStatusSnapshot.")

    status = DashboardStatus.READY if snapshot.healthy else DashboardStatus.WARNING

    if snapshot.error_count > 0:
        status = DashboardStatus.ERROR

    return build_dashboard_card(
        card_id="broker-provider-status-card",
        title="Broker / Provider Status",
        status=status,
        subtitle="System integrations",
        primary_metric=build_dashboard_metric(
            name="integration_count",
            label="Integrations",
            value=snapshot.item_count,
            status=status,
        ),
        metrics=[
            build_dashboard_metric(name="online_count", label="Online", value=snapshot.online_count, status=status),
            build_dashboard_metric(name="degraded_count", label="Degraded", value=snapshot.degraded_count, status=status),
            build_dashboard_metric(name="error_count", label="Errors", value=snapshot.error_count, status=status),
        ],
        widgets=[
            build_status_summary_widget(snapshot),
            build_broker_status_widget(snapshot),
            build_provider_status_widget(snapshot),
            build_status_table_widget(snapshot),
        ],
        data=snapshot.to_dict(),
        metadata={
            "snapshot_id": snapshot.snapshot_id,
        },
    )


def build_broker_provider_status_payload(
    *,
    snapshot: BrokerProviderStatusSnapshot,
    payload_id: str = "broker-provider-status-dashboard",
    title: str = "Broker / Provider Status Dashboard",
) -> DashboardPayload:
    """Build broker/provider status dashboard payload."""
    if not isinstance(snapshot, BrokerProviderStatusSnapshot):
        raise ValueError("Snapshot must be BrokerProviderStatusSnapshot.")

    if not snapshot.items:
        return build_dashboard_payload(
            payload_id=payload_id,
            title=title,
            status=DashboardStatus.EMPTY,
            components=[
                build_dashboard_component(
                    component_id="status-empty",
                    title="No Integrations",
                    component_type="status",
                    status=DashboardStatus.EMPTY,
                    description="No broker/provider integrations are registered.",
                ),
            ],
        )

    card = build_broker_provider_status_card(snapshot)
    summary_widget = build_status_summary_widget(snapshot)
    table_widget = build_status_table_widget(snapshot)

    status = DashboardStatus.READY if snapshot.healthy else DashboardStatus.WARNING

    if snapshot.error_count > 0:
        status = DashboardStatus.ERROR

    return build_dashboard_payload(
        payload_id=payload_id,
        title=title,
        status=status,
        refresh_mode="auto",
        components=[
            card_to_dashboard_component(card),
            widget_to_dashboard_component(summary_widget),
            widget_to_dashboard_component(table_widget),
        ],
        metrics=status_snapshot_to_metrics(snapshot),
        data=snapshot.to_dict(),
        metadata={
            "source": "dashboard.status",
        },
    )