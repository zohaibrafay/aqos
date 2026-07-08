"""
AQOS broker registry.

This module provides an in-memory registry for paper brokers, exchange adapters,
account adapters, and execution-side broker resolution.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from aqos.brokers.account import PositionAccountAdapter
from aqos.brokers.base import (
    BrokerCapability,
    BrokerConfig,
    BrokerResult,
    BrokerStatus,
    BrokerType,
    broker_failure,
    broker_success,
    normalize_broker_capability,
    normalize_broker_status,
    normalize_broker_type,
    validate_metadata,
    validate_non_empty_string,
)
from aqos.brokers.paper import PaperBrokerAdapter


@dataclass(frozen=True)
class BrokerRegistryEntry:
    """Broker registry entry."""

    config: BrokerConfig
    adapter: Any | None = None
    account_adapter: PositionAccountAdapter | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        validate_broker_config_object(self.config)

        if self.account_adapter is not None and not isinstance(
            self.account_adapter,
            PositionAccountAdapter,
        ):
            raise ValueError("Account adapter must be PositionAccountAdapter.")

        validate_metadata(self.metadata, "Metadata")

    @property
    def broker_id(self) -> str:
        """Return broker ID."""
        return self.config.broker_id.strip()

    @property
    def broker_type(self) -> BrokerType:
        """Return broker type."""
        return normalize_broker_type(self.config.broker_type)

    @property
    def status(self) -> BrokerStatus:
        """Return broker status."""
        return normalize_broker_status(self.config.status)

    @property
    def active(self) -> bool:
        """Return whether broker entry is active."""
        return self.config.active

    @property
    def has_adapter(self) -> bool:
        """Return whether entry has broker adapter."""
        return self.adapter is not None

    @property
    def has_account_adapter(self) -> bool:
        """Return whether entry has account adapter."""
        return self.account_adapter is not None

    def supports(self, capability: BrokerCapability | str) -> bool:
        """Return whether broker supports capability."""
        return self.config.supports(capability)

    def to_dict(self) -> dict[str, Any]:
        """Convert registry entry into dictionary."""
        return {
            "broker_id": self.broker_id,
            "broker_type": self.broker_type.value,
            "status": self.status.value,
            "active": self.active,
            "has_adapter": self.has_adapter,
            "adapter_type": type(self.adapter).__name__ if self.adapter is not None else "",
            "has_account_adapter": self.has_account_adapter,
            "account_adapter_type": type(self.account_adapter).__name__
            if self.account_adapter is not None
            else "",
            "config": self.config.to_dict(),
            "metadata": dict(self.metadata),
        }


@dataclass(frozen=True)
class BrokerRegistrySummary:
    """Broker registry summary."""

    total: int
    active: int = 0
    inactive: int = 0
    degraded: int = 0
    error: int = 0
    paper: int = 0
    exchange: int = 0
    with_adapters: int = 0
    with_account_adapters: int = 0
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        validate_non_negative_integer(self.total, "Total")
        validate_non_negative_integer(self.active, "Active")
        validate_non_negative_integer(self.inactive, "Inactive")
        validate_non_negative_integer(self.degraded, "Degraded")
        validate_non_negative_integer(self.error, "Error")
        validate_non_negative_integer(self.paper, "Paper")
        validate_non_negative_integer(self.exchange, "Exchange")
        validate_non_negative_integer(self.with_adapters, "With adapters")
        validate_non_negative_integer(self.with_account_adapters, "With account adapters")
        validate_metadata(self.metadata, "Metadata")

    def to_dict(self) -> dict[str, Any]:
        """Convert summary into dictionary."""
        return {
            "total": self.total,
            "active": self.active,
            "inactive": self.inactive,
            "degraded": self.degraded,
            "error": self.error,
            "paper": self.paper,
            "exchange": self.exchange,
            "with_adapters": self.with_adapters,
            "with_account_adapters": self.with_account_adapters,
            "metadata": dict(self.metadata),
        }


@dataclass
class BrokerRegistry:
    """In-memory broker registry."""

    entries: dict[str, BrokerRegistryEntry] = field(default_factory=dict)
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        validate_broker_registry_entries(self.entries)
        validate_metadata(self.metadata, "Metadata")

    def register_entry(self, entry: BrokerRegistryEntry) -> BrokerRegistryEntry:
        """Register broker entry."""
        if not isinstance(entry, BrokerRegistryEntry):
            raise ValueError("Entry must be BrokerRegistryEntry.")

        self.entries[entry.broker_id] = entry
        return entry

    def register_config(
        self,
        config: BrokerConfig,
        *,
        metadata: dict[str, Any] | None = None,
    ) -> BrokerRegistryEntry:
        """Register broker config."""
        entry = build_broker_registry_entry(
            config=config,
            metadata=metadata or {},
        )

        return self.register_entry(entry)

    def register_adapter(
        self,
        *,
        config: BrokerConfig,
        adapter: Any,
        account_adapter: PositionAccountAdapter | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> BrokerRegistryEntry:
        """Register broker adapter."""
        validate_broker_config_object(config)

        if adapter is None:
            raise ValueError("Adapter is required.")

        entry = build_broker_registry_entry(
            config=config,
            adapter=adapter,
            account_adapter=account_adapter,
            metadata=metadata or {},
        )

        return self.register_entry(entry)

    def attach_account_adapter(
        self,
        *,
        broker_id: str,
        account_adapter: PositionAccountAdapter,
        metadata: dict[str, Any] | None = None,
    ) -> BrokerRegistryEntry:
        """Attach account adapter to an existing broker entry."""
        entry = self.require(broker_id)

        if not isinstance(account_adapter, PositionAccountAdapter):
            raise ValueError("Account adapter must be PositionAccountAdapter.")

        updated = build_broker_registry_entry(
            config=entry.config,
            adapter=entry.adapter,
            account_adapter=account_adapter,
            metadata={
                **entry.metadata,
                **(metadata or {}),
            },
        )

        self.entries[updated.broker_id] = updated
        return updated

    def get(self, broker_id: str) -> BrokerRegistryEntry | None:
        """Get broker entry."""
        normalized_broker_id = validate_non_empty_string(broker_id, "Broker ID")
        return self.entries.get(normalized_broker_id)

    def require(self, broker_id: str) -> BrokerRegistryEntry:
        """Get broker entry or raise."""
        entry = self.get(broker_id)

        if entry is None:
            raise KeyError(f"Broker is not registered: {broker_id}")

        return entry

    def get_config(self, broker_id: str) -> BrokerConfig | None:
        """Get broker config."""
        entry = self.get(broker_id)
        return entry.config if entry is not None else None

    def get_adapter(self, broker_id: str) -> Any | None:
        """Get broker adapter."""
        entry = self.get(broker_id)
        return entry.adapter if entry is not None else None

    def get_account_adapter(self, broker_id: str) -> PositionAccountAdapter | None:
        """Get account adapter."""
        entry = self.get(broker_id)
        return entry.account_adapter if entry is not None else None

    def has(self, broker_id: str) -> bool:
        """Return whether broker exists."""
        return self.get(broker_id) is not None

    def remove(self, broker_id: str) -> BrokerRegistryEntry | None:
        """Remove broker entry."""
        normalized_broker_id = validate_non_empty_string(broker_id, "Broker ID")
        return self.entries.pop(normalized_broker_id, None)

    def clear(self) -> None:
        """Clear registry."""
        self.entries.clear()

    def count(self) -> int:
        """Return registry count."""
        return len(self.entries)

    def list_entries(self) -> list[BrokerRegistryEntry]:
        """List broker entries."""
        return list(self.entries.values())

    def list_configs(self) -> list[BrokerConfig]:
        """List broker configs."""
        return [entry.config for entry in self.entries.values()]

    def list_adapters(self) -> list[Any]:
        """List registered broker adapters."""
        return [
            entry.adapter
            for entry in self.entries.values()
            if entry.adapter is not None
        ]

    def list_account_adapters(self) -> list[PositionAccountAdapter]:
        """List registered account adapters."""
        return [
            entry.account_adapter
            for entry in self.entries.values()
            if entry.account_adapter is not None
        ]

    def broker_ids(self) -> list[str]:
        """List broker IDs."""
        return sorted(self.entries.keys())

    def active_entries(self) -> list[BrokerRegistryEntry]:
        """List active broker entries."""
        return [
            entry
            for entry in self.entries.values()
            if entry.active
        ]

    def entries_by_type(
        self,
        broker_type: BrokerType | str,
    ) -> list[BrokerRegistryEntry]:
        """List entries by broker type."""
        normalized_type = normalize_broker_type(broker_type)

        return [
            entry
            for entry in self.entries.values()
            if entry.broker_type == normalized_type
        ]

    def entries_supporting(
        self,
        capability: BrokerCapability | str,
    ) -> list[BrokerRegistryEntry]:
        """List entries supporting capability."""
        normalized_capability = normalize_broker_capability(capability)

        return [
            entry
            for entry in self.entries.values()
            if entry.supports(normalized_capability)
        ]

    def paper_entries(self) -> list[BrokerRegistryEntry]:
        """List paper broker entries."""
        return self.entries_by_type(BrokerType.PAPER)

    def live_entries(self) -> list[BrokerRegistryEntry]:
        """List live broker entries."""
        return [
            entry
            for entry in self.entries.values()
            if entry.config.live_mode
        ]

    def select_broker(
        self,
        *,
        preferred_broker_id: str = "",
        broker_type: BrokerType | str | None = None,
        capability: BrokerCapability | str | None = None,
        require_active: bool = True,
        require_adapter: bool = False,
    ) -> BrokerRegistryEntry | None:
        """Select broker entry."""
        if preferred_broker_id:
            entry = self.get(preferred_broker_id)

            if entry is None:
                return None

            if require_active and not entry.active:
                return None

            if broker_type is not None and entry.broker_type != normalize_broker_type(broker_type):
                return None

            if capability is not None and not entry.supports(capability):
                return None

            if require_adapter and not entry.has_adapter:
                return None

            return entry

        candidates = self.list_entries()

        if broker_type is not None:
            normalized_type = normalize_broker_type(broker_type)
            candidates = [
                entry
                for entry in candidates
                if entry.broker_type == normalized_type
            ]

        if capability is not None:
            candidates = [
                entry
                for entry in candidates
                if entry.supports(capability)
            ]

        if require_active:
            candidates = [
                entry
                for entry in candidates
                if entry.active
            ]

        if require_adapter:
            candidates = [
                entry
                for entry in candidates
                if entry.has_adapter
            ]

        return candidates[0] if candidates else None

    def resolve_adapter(
        self,
        *,
        preferred_broker_id: str = "",
        broker_type: BrokerType | str | None = None,
        capability: BrokerCapability | str | None = None,
    ) -> Any | None:
        """Resolve broker adapter."""
        entry = self.select_broker(
            preferred_broker_id=preferred_broker_id,
            broker_type=broker_type,
            capability=capability,
            require_active=True,
            require_adapter=True,
        )

        return entry.adapter if entry is not None else None

    def resolve_account_adapter(
        self,
        *,
        preferred_broker_id: str = "",
    ) -> PositionAccountAdapter | None:
        """Resolve account adapter."""
        if preferred_broker_id:
            entry = self.get(preferred_broker_id)
            return entry.account_adapter if entry is not None else None

        for entry in self.entries.values():
            if entry.active and entry.account_adapter is not None:
                return entry.account_adapter

        return None

    def summary(self) -> BrokerRegistrySummary:
        """Return registry summary."""
        return summarize_broker_registry_entries(
            list(self.entries.values()),
            metadata=dict(self.metadata),
        )

    def to_dict(self) -> dict[str, Any]:
        """Convert registry into dictionary."""
        return {
            "summary": self.summary().to_dict(),
            "entries": [
                entry.to_dict()
                for entry in self.entries.values()
            ],
            "metadata": dict(self.metadata),
        }


def validate_non_negative_integer(value: int, field_name: str) -> int:
    """Validate non-negative integer."""
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise ValueError(f"{field_name} must be a non-negative integer.")

    return value


def validate_broker_config_object(config: BrokerConfig) -> BrokerConfig:
    """Validate broker config object."""
    if not isinstance(config, BrokerConfig):
        raise ValueError("Broker config must be BrokerConfig.")

    return config


def validate_broker_registry_entries(
    entries: dict[str, BrokerRegistryEntry],
) -> dict[str, BrokerRegistryEntry]:
    """Validate broker registry entries dictionary."""
    if not isinstance(entries, dict):
        raise ValueError("Entries must be a dictionary.")

    for broker_id, entry in entries.items():
        validate_non_empty_string(broker_id, "Broker ID")

        if not isinstance(entry, BrokerRegistryEntry):
            raise ValueError("Entries must contain BrokerRegistryEntry objects.")

    return entries


def validate_broker_registry(registry: BrokerRegistry) -> BrokerRegistry:
    """Validate broker registry."""
    if not isinstance(registry, BrokerRegistry):
        raise ValueError("Registry must be BrokerRegistry.")

    return registry


def build_broker_registry_entry(
    *,
    config: BrokerConfig,
    adapter: Any | None = None,
    account_adapter: PositionAccountAdapter | None = None,
    metadata: dict[str, Any] | None = None,
) -> BrokerRegistryEntry:
    """Build broker registry entry."""
    return BrokerRegistryEntry(
        config=config,
        adapter=adapter,
        account_adapter=account_adapter,
        metadata=metadata or {},
    )


def build_broker_registry(
    *,
    entries: dict[str, BrokerRegistryEntry] | None = None,
    metadata: dict[str, Any] | None = None,
) -> BrokerRegistry:
    """Build broker registry."""
    return BrokerRegistry(
        entries=entries or {},
        metadata=metadata or {},
    )


def summarize_broker_registry_entries(
    entries: list[BrokerRegistryEntry],
    *,
    metadata: dict[str, Any] | None = None,
) -> BrokerRegistrySummary:
    """Summarize broker registry entries."""
    if not isinstance(entries, list):
        raise ValueError("Entries must be a list.")

    for entry in entries:
        if not isinstance(entry, BrokerRegistryEntry):
            raise ValueError("Entries must contain BrokerRegistryEntry objects.")

    return BrokerRegistrySummary(
        total=len(entries),
        active=len([entry for entry in entries if entry.status == BrokerStatus.ACTIVE]),
        inactive=len([entry for entry in entries if entry.status == BrokerStatus.INACTIVE]),
        degraded=len([entry for entry in entries if entry.status == BrokerStatus.DEGRADED]),
        error=len([entry for entry in entries if entry.status == BrokerStatus.ERROR]),
        paper=len([entry for entry in entries if entry.broker_type == BrokerType.PAPER]),
        exchange=len([entry for entry in entries if entry.broker_type == BrokerType.EXCHANGE]),
        with_adapters=len([entry for entry in entries if entry.has_adapter]),
        with_account_adapters=len([entry for entry in entries if entry.has_account_adapter]),
        metadata=metadata or {},
    )


def broker_registry_to_result(
    registry: BrokerRegistry,
) -> BrokerResult:
    """Convert broker registry into broker result."""
    validate_broker_registry(registry)

    return broker_success(
        broker_id="broker-registry",
        data={
            "registry": registry.to_dict(),
        },
        message="Broker registry generated.",
    )


def broker_registry_error_result(
    *,
    error: str,
    operation: str,
    metadata: dict[str, Any] | None = None,
) -> BrokerResult:
    """Build broker registry error result."""
    return broker_failure(
        broker_id="broker-registry",
        error=error,
        message="Broker registry operation failed.",
        metadata={
            "operation": validate_non_empty_string(operation, "Operation"),
            **(metadata or {}),
        },
    )


def register_broker_config(
    *,
    registry: BrokerRegistry,
    config: BrokerConfig,
    metadata: dict[str, Any] | None = None,
) -> BrokerRegistryEntry:
    """Register broker config."""
    validate_broker_registry(registry)
    return registry.register_config(
        config,
        metadata=metadata or {},
    )


def register_broker_adapter(
    *,
    registry: BrokerRegistry,
    config: BrokerConfig,
    adapter: Any,
    account_adapter: PositionAccountAdapter | None = None,
    metadata: dict[str, Any] | None = None,
) -> BrokerRegistryEntry:
    """Register broker adapter."""
    validate_broker_registry(registry)
    return registry.register_adapter(
        config=config,
        adapter=adapter,
        account_adapter=account_adapter,
        metadata=metadata or {},
    )


def register_paper_broker(
    *,
    registry: BrokerRegistry,
    adapter: PaperBrokerAdapter,
    account_adapter: PositionAccountAdapter | None = None,
    metadata: dict[str, Any] | None = None,
) -> BrokerRegistryEntry:
    """Register paper broker adapter."""
    validate_broker_registry(registry)

    if not isinstance(adapter, PaperBrokerAdapter):
        raise ValueError("Adapter must be PaperBrokerAdapter.")

    return registry.register_adapter(
        config=adapter.broker_config,
        adapter=adapter,
        account_adapter=account_adapter,
        metadata=metadata or {},
    )


def resolve_paper_broker_adapter(
    registry: BrokerRegistry,
    *,
    preferred_broker_id: str = "",
) -> PaperBrokerAdapter | None:
    """Resolve registered paper broker adapter."""
    validate_broker_registry(registry)

    adapter = registry.resolve_adapter(
        preferred_broker_id=preferred_broker_id,
        broker_type=BrokerType.PAPER,
        capability=BrokerCapability.PAPER_TRADING,
    )

    if adapter is None:
        return None

    if not isinstance(adapter, PaperBrokerAdapter):
        raise ValueError("Resolved adapter is not a PaperBrokerAdapter.")

    return adapter


def resolve_position_account_adapter(
    registry: BrokerRegistry,
    *,
    preferred_broker_id: str = "",
) -> PositionAccountAdapter | None:
    """Resolve registered position account adapter."""
    validate_broker_registry(registry)
    return registry.resolve_account_adapter(
        preferred_broker_id=preferred_broker_id,
    )