"""
AQOS provider registry.

This module provides a dependency-free registry for provider configs and
provider adapter instances.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from aqos.providers.base import (
    ProviderCapability,
    ProviderConfig,
    ProviderResult,
    ProviderStatus,
    ProviderType,
    build_provider_config,
    provider_failure,
    provider_success,
    validate_metadata,
    validate_non_empty_string,
    validate_provider_capabilities,
)
from aqos.providers.historical import HistoricalOhlcvAdapter
from aqos.providers.live import LiveMarketDataAdapter


@dataclass
class ProviderRegistryEntry:
    """Provider registry entry."""

    config: ProviderConfig
    adapter: Any = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        validate_provider_config_object(self.config)
        validate_metadata(self.metadata, "Metadata")

    @property
    def provider_id(self) -> str:
        """Return provider ID."""
        return self.config.provider_id.strip()

    @property
    def active(self) -> bool:
        """Return whether provider is active."""
        return self.config.active

    @property
    def has_adapter(self) -> bool:
        """Return whether entry has adapter."""
        return self.adapter is not None

    def supports(self, capability: ProviderCapability | str) -> bool:
        """Return whether entry supports capability."""
        return self.config.supports(capability)

    def to_dict(self) -> dict[str, Any]:
        """Convert entry into dictionary."""
        return {
            "provider_id": self.provider_id,
            "config": self.config.to_dict(),
            "has_adapter": self.has_adapter,
            "adapter_type": type(self.adapter).__name__ if self.adapter is not None else "",
            "metadata": dict(self.metadata),
        }


@dataclass
class ProviderRegistrySummary:
    """Provider registry summary."""

    total: int = 0
    active: int = 0
    inactive: int = 0
    degraded: int = 0
    error: int = 0
    with_adapters: int = 0
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        validate_non_negative_integer(self.total, "Total")
        validate_non_negative_integer(self.active, "Active")
        validate_non_negative_integer(self.inactive, "Inactive")
        validate_non_negative_integer(self.degraded, "Degraded")
        validate_non_negative_integer(self.error, "Error")
        validate_non_negative_integer(self.with_adapters, "With adapters")
        validate_metadata(self.metadata, "Metadata")

    def to_dict(self) -> dict[str, Any]:
        """Convert summary into dictionary."""
        return {
            "total": self.total,
            "active": self.active,
            "inactive": self.inactive,
            "degraded": self.degraded,
            "error": self.error,
            "with_adapters": self.with_adapters,
            "metadata": dict(self.metadata),
        }


@dataclass
class ProviderRegistry:
    """In-memory provider registry."""

    entries: dict[str, ProviderRegistryEntry] = field(default_factory=dict)
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        validate_provider_registry_entries(self.entries)
        validate_metadata(self.metadata, "Metadata")

    def register_entry(self, entry: ProviderRegistryEntry) -> ProviderRegistryEntry:
        """Register provider entry."""
        if not isinstance(entry, ProviderRegistryEntry):
            raise ValueError("Entry must be a ProviderRegistryEntry.")

        self.entries[entry.provider_id] = entry
        return entry

    def register_config(
        self,
        config: ProviderConfig,
        *,
        metadata: dict[str, Any] | None = None,
    ) -> ProviderRegistryEntry:
        """Register provider config."""
        entry = build_provider_registry_entry(
            config=config,
            metadata=metadata or {},
        )
        return self.register_entry(entry)

    def register_adapter(
        self,
        *,
        config: ProviderConfig,
        adapter: Any,
        metadata: dict[str, Any] | None = None,
    ) -> ProviderRegistryEntry:
        """Register provider adapter with config."""
        entry = build_provider_registry_entry(
            config=config,
            adapter=adapter,
            metadata=metadata or {},
        )
        return self.register_entry(entry)

    def get(self, provider_id: str) -> ProviderRegistryEntry | None:
        """Get provider entry."""
        normalized_provider_id = validate_non_empty_string(provider_id, "Provider ID")
        return self.entries.get(normalized_provider_id)

    def require(self, provider_id: str) -> ProviderRegistryEntry:
        """Require provider entry."""
        entry = self.get(provider_id)

        if entry is None:
            raise ValueError(f"Provider '{provider_id}' is not registered.")

        return entry

    def get_config(self, provider_id: str) -> ProviderConfig | None:
        """Get provider config."""
        entry = self.get(provider_id)
        return entry.config if entry is not None else None

    def get_adapter(self, provider_id: str) -> Any:
        """Get provider adapter."""
        entry = self.get(provider_id)
        return entry.adapter if entry is not None else None

    def has(self, provider_id: str) -> bool:
        """Return whether provider exists."""
        return self.get(provider_id) is not None

    def remove(self, provider_id: str) -> ProviderRegistryEntry | None:
        """Remove provider entry."""
        normalized_provider_id = validate_non_empty_string(provider_id, "Provider ID")
        return self.entries.pop(normalized_provider_id, None)

    def clear(self) -> None:
        """Clear provider registry."""
        self.entries.clear()

    def count(self) -> int:
        """Return provider count."""
        return len(self.entries)

    def list_entries(self) -> list[ProviderRegistryEntry]:
        """List provider entries."""
        return list(self.entries.values())

    def list_configs(self) -> list[ProviderConfig]:
        """List provider configs."""
        return [entry.config for entry in self.entries.values()]

    def list_adapters(self) -> list[Any]:
        """List registered adapters."""
        return [
            entry.adapter
            for entry in self.entries.values()
            if entry.adapter is not None
        ]

    def provider_ids(self) -> list[str]:
        """List provider IDs."""
        return sorted(self.entries.keys())

    def active_entries(self) -> list[ProviderRegistryEntry]:
        """List active entries."""
        return [
            entry
            for entry in self.entries.values()
            if entry.active
        ]

    def entries_by_type(
        self,
        provider_type: ProviderType | str,
        *,
        active_only: bool = False,
    ) -> list[ProviderRegistryEntry]:
        """List entries by provider type."""
        normalized_provider_type = normalize_provider_type_value(provider_type)
        entries = [
            entry
            for entry in self.entries.values()
            if normalize_provider_type_value(entry.config.provider_type) == normalized_provider_type
        ]

        if active_only:
            entries = [entry for entry in entries if entry.active]

        return entries

    def entries_supporting(
        self,
        capability: ProviderCapability | str,
        *,
        active_only: bool = False,
    ) -> list[ProviderRegistryEntry]:
        """List entries supporting capability."""
        entries = [
            entry
            for entry in self.entries.values()
            if entry.supports(capability)
        ]

        if active_only:
            entries = [entry for entry in entries if entry.active]

        return entries

    def select_provider(
        self,
        *,
        provider_type: ProviderType | str | None = None,
        capability: ProviderCapability | str | None = None,
        active_only: bool = True,
    ) -> ProviderRegistryEntry | None:
        """Select first matching provider."""
        entries = self.list_entries()

        if provider_type is not None:
            normalized_provider_type = normalize_provider_type_value(provider_type)
            entries = [
                entry
                for entry in entries
                if normalize_provider_type_value(entry.config.provider_type) == normalized_provider_type
            ]

        if capability is not None:
            entries = [
                entry
                for entry in entries
                if entry.supports(capability)
            ]

        if active_only:
            entries = [
                entry
                for entry in entries
                if entry.active
            ]

        return entries[0] if entries else None

    def resolve_adapter(
        self,
        *,
        provider_type: ProviderType | str | None = None,
        capability: ProviderCapability | str | None = None,
        active_only: bool = True,
    ) -> Any:
        """Resolve first matching adapter."""
        entry = self.select_provider(
            provider_type=provider_type,
            capability=capability,
            active_only=active_only,
        )

        if entry is None:
            return None

        return entry.adapter

    def summary(self) -> ProviderRegistrySummary:
        """Return provider registry summary."""
        entries = self.list_entries()
        return summarize_provider_registry_entries(entries)

    def to_dict(self) -> dict[str, Any]:
        """Convert registry into dictionary."""
        return {
            "summary": self.summary().to_dict(),
            "providers": [
                entry.to_dict()
                for entry in self.list_entries()
            ],
            "metadata": dict(self.metadata),
        }


def validate_non_negative_integer(value: int, field_name: str) -> int:
    """Validate non-negative integer."""
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise ValueError(f"{field_name} must be a non-negative integer.")

    return value


def normalize_provider_type_value(provider_type: ProviderType | str) -> ProviderType:
    """Normalize provider type value."""
    if isinstance(provider_type, ProviderType):
        return provider_type

    normalized = validate_non_empty_string(provider_type, "Provider type").lower()

    try:
        return ProviderType(normalized)
    except ValueError as exc:
        valid = ", ".join(item.value for item in ProviderType)
        raise ValueError(
            f"Invalid provider type '{provider_type}'. Valid provider types: {valid}.",
        ) from exc


def normalize_provider_status_value(status: ProviderStatus | str) -> ProviderStatus:
    """Normalize provider status value."""
    if isinstance(status, ProviderStatus):
        return status

    normalized = validate_non_empty_string(status, "Provider status").lower()

    try:
        return ProviderStatus(normalized)
    except ValueError as exc:
        valid = ", ".join(item.value for item in ProviderStatus)
        raise ValueError(
            f"Invalid provider status '{status}'. Valid statuses: {valid}.",
        ) from exc


def validate_provider_config_object(config: ProviderConfig) -> ProviderConfig:
    """Validate provider config object."""
    if not isinstance(config, ProviderConfig):
        raise ValueError("Config must be a ProviderConfig.")

    return config


def validate_provider_registry_entries(
    entries: dict[str, ProviderRegistryEntry],
) -> dict[str, ProviderRegistryEntry]:
    """Validate provider registry entries."""
    if not isinstance(entries, dict):
        raise ValueError("Entries must be a dictionary.")

    for provider_id, entry in entries.items():
        validate_non_empty_string(provider_id, "Provider ID")

        if not isinstance(entry, ProviderRegistryEntry):
            raise ValueError("Entries must contain ProviderRegistryEntry objects.")

    return entries


def validate_provider_registry(registry: ProviderRegistry) -> ProviderRegistry:
    """Validate provider registry."""
    if not isinstance(registry, ProviderRegistry):
        raise ValueError("Registry must be a ProviderRegistry.")

    return registry


def build_provider_registry_entry(
    *,
    config: ProviderConfig,
    adapter: Any = None,
    metadata: dict[str, Any] | None = None,
) -> ProviderRegistryEntry:
    """Build provider registry entry."""
    return ProviderRegistryEntry(
        config=config,
        adapter=adapter,
        metadata=metadata or {},
    )


def build_provider_registry(
    *,
    entries: dict[str, ProviderRegistryEntry] | None = None,
    metadata: dict[str, Any] | None = None,
) -> ProviderRegistry:
    """Build provider registry."""
    return ProviderRegistry(
        entries=entries or {},
        metadata=metadata or {},
    )


def summarize_provider_registry_entries(
    entries: list[ProviderRegistryEntry],
    *,
    metadata: dict[str, Any] | None = None,
) -> ProviderRegistrySummary:
    """Summarize provider registry entries."""
    if not isinstance(entries, list):
        raise ValueError("Entries must be a list.")

    for entry in entries:
        if not isinstance(entry, ProviderRegistryEntry):
            raise ValueError("Entries must contain ProviderRegistryEntry objects.")

    active = sum(
        1
        for entry in entries
        if normalize_provider_status_value(entry.config.status) == ProviderStatus.ACTIVE
    )
    inactive = sum(
        1
        for entry in entries
        if normalize_provider_status_value(entry.config.status) == ProviderStatus.INACTIVE
    )
    degraded = sum(
        1
        for entry in entries
        if normalize_provider_status_value(entry.config.status) == ProviderStatus.DEGRADED
    )
    error = sum(
        1
        for entry in entries
        if normalize_provider_status_value(entry.config.status) == ProviderStatus.ERROR
    )

    return ProviderRegistrySummary(
        total=len(entries),
        active=active,
        inactive=inactive,
        degraded=degraded,
        error=error,
        with_adapters=sum(1 for entry in entries if entry.has_adapter),
        metadata=metadata or {},
    )


def provider_registry_to_result(
    registry: ProviderRegistry,
    *,
    provider_id: str = "provider-registry",
) -> ProviderResult:
    """Convert registry summary into provider result."""
    validate_provider_registry(registry)

    return provider_success(
        provider_id=provider_id,
        data={
            "registry": registry.to_dict(),
        },
        message="Provider registry summary generated.",
    )


def provider_registry_error_result(
    *,
    provider_id: str = "provider-registry",
    error: str,
    metadata: dict[str, Any] | None = None,
) -> ProviderResult:
    """Build provider registry error result."""
    return provider_failure(
        provider_id=provider_id,
        error=error,
        message="Provider registry operation failed.",
        metadata=metadata or {},
    )


def register_market_data_provider(
    *,
    registry: ProviderRegistry,
    provider_id: str,
    name: str,
    capabilities: list[ProviderCapability | str],
    adapter: Any = None,
    status: ProviderStatus | str = ProviderStatus.ACTIVE,
    metadata: dict[str, Any] | None = None,
) -> ProviderRegistryEntry:
    """Register market data provider."""
    validate_provider_registry(registry)
    validate_provider_capabilities(capabilities)

    config = build_provider_config(
        provider_id=provider_id,
        name=name,
        provider_type=ProviderType.MARKET_DATA,
        status=status,
        capabilities=capabilities,
        metadata=metadata or {},
    )

    return registry.register_adapter(
        config=config,
        adapter=adapter,
        metadata=metadata or {},
    )


def resolve_historical_adapter(
    registry: ProviderRegistry,
) -> HistoricalOhlcvAdapter | None:
    """Resolve historical OHLCV adapter."""
    validate_provider_registry(registry)
    adapter = registry.resolve_adapter(
        provider_type=ProviderType.MARKET_DATA,
        capability=ProviderCapability.HISTORICAL_OHLCV,
        active_only=True,
    )

    if adapter is None:
        return None

    if not isinstance(adapter, HistoricalOhlcvAdapter):
        raise ValueError("Resolved adapter is not a HistoricalOhlcvAdapter.")

    return adapter


def resolve_live_adapter(
    registry: ProviderRegistry,
) -> LiveMarketDataAdapter | None:
    """Resolve live market data adapter."""
    validate_provider_registry(registry)
    adapter = registry.resolve_adapter(
        provider_type=ProviderType.MARKET_DATA,
        capability=ProviderCapability.LIVE_QUOTES,
        active_only=True,
    )

    if adapter is None:
        adapter = registry.resolve_adapter(
            provider_type=ProviderType.MARKET_DATA,
            capability=ProviderCapability.TICKS,
            active_only=True,
        )

    if adapter is None:
        return None

    if not isinstance(adapter, LiveMarketDataAdapter):
        raise ValueError("Resolved adapter is not a LiveMarketDataAdapter.")

    return adapter