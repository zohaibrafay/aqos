"""
AQOS live news connector registry.

This module provides a registry and selection layer for named live news,
financial news, macro calendar, public JSON, and crypto news connectors.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any

from aqos.news_providers.base import (
    NewsProviderCapability,
    NewsProviderCredentials,
    validate_metadata,
    validate_non_empty_string,
    validate_string,
)
from aqos.news_providers.cryptopanic_connector import build_cryptopanic_connector_definition
from aqos.news_providers.finnhub_connector import build_finnhub_connector_definition
from aqos.news_providers.gdelt_connector import build_gdelt_connector_definition
from aqos.news_providers.hackernews_connector import build_hackernews_connector_definition
from aqos.news_providers.live_connectors import (
    LiveNewsConnectorCategory,
    LiveNewsConnectorDefinition,
    LiveNewsConnectorId,
    LiveNewsConnectorRuntimeConfig,
    LiveNewsConnectorStatus,
    build_live_news_connector_runtime_config,
    connector_runtime_has_required_credentials,
    normalize_live_news_connector_category,
    normalize_live_news_connector_id,
    normalize_live_news_connector_status,
)
from aqos.news_providers.newsapi_connector import (
    build_marketaux_connector_definition,
    build_newsapi_connector_definition,
)
from aqos.news_providers.trading_economics_connector import (
    build_trading_economics_connector_definition,
)


class LiveNewsConnectorSelectionMode(str, Enum):
    """Supported connector selection modes."""

    ALL = "all"
    FIRST_READY = "first_ready"
    PREFERRED_ONLY = "preferred_only"
    FALLBACK_CHAIN = "fallback_chain"


@dataclass(frozen=True)
class NewsConnectorRegistryEntry:
    """Registry entry for one live news connector."""

    definition: LiveNewsConnectorDefinition
    priority: int = 100
    enabled: bool = True
    tags: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not isinstance(self.definition, LiveNewsConnectorDefinition):
            raise ValueError("Definition must be LiveNewsConnectorDefinition.")

        if not isinstance(self.priority, int) or self.priority < 0:
            raise ValueError("Priority must be a non-negative integer.")

        if not isinstance(self.enabled, bool):
            raise ValueError("Enabled must be a boolean.")

        validate_registry_string_list(self.tags, "Tags")
        validate_metadata(self.metadata, "Metadata")

    @property
    def connector_id(self) -> LiveNewsConnectorId:
        """Return normalized connector ID."""
        return normalize_live_news_connector_id(self.definition.connector_id)

    @property
    def category(self) -> LiveNewsConnectorCategory:
        """Return normalized connector category."""
        return normalize_live_news_connector_category(self.definition.category)

    @property
    def status(self) -> LiveNewsConnectorStatus:
        """Return normalized connector status."""
        return normalize_live_news_connector_status(self.definition.status)

    @property
    def ready(self) -> bool:
        """Return whether entry is enabled and ready/usable."""
        return self.enabled and self.status in {
            LiveNewsConnectorStatus.READY,
            LiveNewsConnectorStatus.NEEDS_API_KEY,
            LiveNewsConnectorStatus.EXPERIMENTAL,
        }

    def to_dict(self) -> dict[str, Any]:
        """Convert registry entry to dictionary."""
        return {
            "connector_id": self.connector_id.value,
            "category": self.category.value,
            "status": self.status.value,
            "priority": self.priority,
            "enabled": self.enabled,
            "ready": self.ready,
            "tags": [tag.strip().lower() for tag in self.tags],
            "definition": self.definition.to_dict(),
            "metadata": dict(self.metadata),
        }


@dataclass(frozen=True)
class NewsConnectorSelectionRequest:
    """Request for selecting live news connectors."""

    connector_ids: list[LiveNewsConnectorId | str] = field(default_factory=list)
    categories: list[LiveNewsConnectorCategory | str] = field(default_factory=list)
    capabilities: list[NewsProviderCapability | str] = field(default_factory=list)
    statuses: list[LiveNewsConnectorStatus | str] = field(default_factory=list)
    tags: list[str] = field(default_factory=list)
    mode: LiveNewsConnectorSelectionMode | str = LiveNewsConnectorSelectionMode.ALL
    include_disabled: bool = False
    require_credentials: bool = False
    credentials_by_connector_id: dict[str, NewsProviderCredentials] = field(default_factory=dict)
    limit: int = 0
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        validate_connector_id_list(self.connector_ids)
        validate_connector_category_list(self.categories)
        validate_connector_capability_list(self.capabilities)
        validate_connector_status_list(self.statuses)
        validate_registry_string_list(self.tags, "Tags")
        normalize_live_news_connector_selection_mode(self.mode)

        if not isinstance(self.include_disabled, bool):
            raise ValueError("Include disabled must be a boolean.")

        if not isinstance(self.require_credentials, bool):
            raise ValueError("Require credentials must be a boolean.")

        validate_credentials_mapping(self.credentials_by_connector_id)

        if not isinstance(self.limit, int) or self.limit < 0:
            raise ValueError("Limit must be a non-negative integer.")

        validate_metadata(self.metadata, "Metadata")

    def to_dict(self) -> dict[str, Any]:
        """Convert selection request to dictionary."""
        return {
            "connector_ids": [
                normalize_live_news_connector_id(connector_id).value
                for connector_id in self.connector_ids
            ],
            "categories": [
                normalize_live_news_connector_category(category).value
                for category in self.categories
            ],
            "capabilities": [
                normalize_capability_value(capability).value
                for capability in self.capabilities
            ],
            "statuses": [
                normalize_live_news_connector_status(status).value
                for status in self.statuses
            ],
            "tags": [tag.strip().lower() for tag in self.tags],
            "mode": normalize_live_news_connector_selection_mode(self.mode).value,
            "include_disabled": self.include_disabled,
            "require_credentials": self.require_credentials,
            "credential_connector_ids": sorted(self.credentials_by_connector_id),
            "limit": self.limit,
            "metadata": dict(self.metadata),
        }


@dataclass(frozen=True)
class NewsConnectorSelectionResult:
    """Selection result for live news connectors."""

    success: bool
    entries: list[NewsConnectorRegistryEntry] = field(default_factory=list)
    message: str = ""
    request: NewsConnectorSelectionRequest | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not isinstance(self.success, bool):
            raise ValueError("Success must be a boolean.")

        validate_registry_entries(self.entries)
        validate_string(self.message, "Message")

        if self.request is not None and not isinstance(self.request, NewsConnectorSelectionRequest):
            raise ValueError("Request must be NewsConnectorSelectionRequest.")

        validate_metadata(self.metadata, "Metadata")

    @property
    def connector_count(self) -> int:
        """Return selected connector count."""
        return len(self.entries)

    @property
    def definitions(self) -> list[LiveNewsConnectorDefinition]:
        """Return selected connector definitions."""
        return [entry.definition for entry in self.entries]

    def to_dict(self) -> dict[str, Any]:
        """Convert selection result to dictionary."""
        return {
            "success": self.success,
            "connector_count": self.connector_count,
            "entries": [entry.to_dict() for entry in self.entries],
            "connector_ids": [entry.connector_id.value for entry in self.entries],
            "message": self.message.strip(),
            "request": self.request.to_dict() if self.request is not None else None,
            "metadata": dict(self.metadata),
        }


@dataclass(frozen=True)
class NewsConnectorRegistry:
    """Registry of live news connector entries."""

    entries: dict[str, NewsConnectorRegistryEntry] = field(default_factory=dict)
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not isinstance(self.entries, dict):
            raise ValueError("Entries must be a dictionary.")

        for key, entry in self.entries.items():
            validate_non_empty_string(key, "Registry key")

            if not isinstance(entry, NewsConnectorRegistryEntry):
                raise ValueError("Registry entry must be NewsConnectorRegistryEntry.")

            if key != entry.connector_id.value:
                raise ValueError("Registry key must match connector ID.")

        validate_metadata(self.metadata, "Metadata")

    @property
    def connector_count(self) -> int:
        """Return connector count."""
        return len(self.entries)

    def has_connector(self, connector_id: LiveNewsConnectorId | str) -> bool:
        """Return whether registry has connector."""
        normalized = normalize_live_news_connector_id(connector_id)
        return normalized.value in self.entries

    def get_connector(
        self,
        connector_id: LiveNewsConnectorId | str,
    ) -> NewsConnectorRegistryEntry:
        """Get connector entry by ID."""
        normalized = normalize_live_news_connector_id(connector_id)

        if normalized.value not in self.entries:
            raise KeyError(f"Connector '{normalized.value}' was not found in registry.")

        return self.entries[normalized.value]

    def list_entries(self, *, include_disabled: bool = False) -> list[NewsConnectorRegistryEntry]:
        """List registry entries sorted by priority."""
        entries = list(self.entries.values())

        if not include_disabled:
            entries = [entry for entry in entries if entry.enabled]

        return sorted(entries, key=lambda entry: (entry.priority, entry.connector_id.value))

    def to_dict(self) -> dict[str, Any]:
        """Convert registry to dictionary."""
        return {
            "connector_count": self.connector_count,
            "entries": {
                connector_id: entry.to_dict()
                for connector_id, entry in sorted(self.entries.items())
            },
            "metadata": dict(self.metadata),
        }


def normalize_live_news_connector_selection_mode(
    value: LiveNewsConnectorSelectionMode | str,
) -> LiveNewsConnectorSelectionMode:
    """Normalize connector selection mode."""
    if isinstance(value, LiveNewsConnectorSelectionMode):
        return value

    normalized = validate_non_empty_string(value, "Live news connector selection mode").lower()

    try:
        return LiveNewsConnectorSelectionMode(normalized)
    except ValueError as exc:
        valid = ", ".join(item.value for item in LiveNewsConnectorSelectionMode)
        raise ValueError(
            f"Invalid live news connector selection mode '{value}'. Valid modes: {valid}.",
        ) from exc


def normalize_capability_value(value: NewsProviderCapability | str) -> NewsProviderCapability:
    """Normalize provider capability."""
    if isinstance(value, NewsProviderCapability):
        return value

    normalized = validate_non_empty_string(value, "Capability").lower()

    try:
        return NewsProviderCapability(normalized)
    except ValueError as exc:
        valid = ", ".join(item.value for item in NewsProviderCapability)
        raise ValueError(f"Invalid capability '{value}'. Valid capabilities: {valid}.") from exc


def validate_registry_string_list(values: list[str], field_name: str = "Values") -> list[str]:
    """Validate list of strings."""
    if not isinstance(values, list):
        raise ValueError(f"{field_name} must be a list.")

    for value in values:
        validate_non_empty_string(value, field_name)

    return values


def validate_connector_id_list(values: list[LiveNewsConnectorId | str]) -> list[LiveNewsConnectorId | str]:
    """Validate connector ID list."""
    if not isinstance(values, list):
        raise ValueError("Connector IDs must be a list.")

    for value in values:
        normalize_live_news_connector_id(value)

    return values


def validate_connector_category_list(
    values: list[LiveNewsConnectorCategory | str],
) -> list[LiveNewsConnectorCategory | str]:
    """Validate connector category list."""
    if not isinstance(values, list):
        raise ValueError("Categories must be a list.")

    for value in values:
        normalize_live_news_connector_category(value)

    return values


def validate_connector_capability_list(
    values: list[NewsProviderCapability | str],
) -> list[NewsProviderCapability | str]:
    """Validate connector capability list."""
    if not isinstance(values, list):
        raise ValueError("Capabilities must be a list.")

    for value in values:
        normalize_capability_value(value)

    return values


def validate_connector_status_list(
    values: list[LiveNewsConnectorStatus | str],
) -> list[LiveNewsConnectorStatus | str]:
    """Validate connector status list."""
    if not isinstance(values, list):
        raise ValueError("Statuses must be a list.")

    for value in values:
        normalize_live_news_connector_status(value)

    return values


def validate_credentials_mapping(
    value: dict[str, NewsProviderCredentials],
) -> dict[str, NewsProviderCredentials]:
    """Validate credentials mapping."""
    if not isinstance(value, dict):
        raise ValueError("Credentials by connector ID must be a dictionary.")

    for key, credentials in value.items():
        normalize_live_news_connector_id(key)

        if not isinstance(credentials, NewsProviderCredentials):
            raise ValueError("Credential mapping values must be NewsProviderCredentials.")

    return value


def validate_registry_entries(
    entries: list[NewsConnectorRegistryEntry],
) -> list[NewsConnectorRegistryEntry]:
    """Validate registry entries."""
    if not isinstance(entries, list):
        raise ValueError("Entries must be a list.")

    for entry in entries:
        if not isinstance(entry, NewsConnectorRegistryEntry):
            raise ValueError("Entry must be NewsConnectorRegistryEntry.")

    return entries


def build_news_connector_registry_entry(
    *,
    definition: LiveNewsConnectorDefinition,
    priority: int = 100,
    enabled: bool = True,
    tags: list[str] | None = None,
    metadata: dict[str, Any] | None = None,
) -> NewsConnectorRegistryEntry:
    """Build news connector registry entry."""
    return NewsConnectorRegistryEntry(
        definition=definition,
        priority=priority,
        enabled=enabled,
        tags=tags or [],
        metadata=metadata or {},
    )


def build_news_connector_selection_request(
    *,
    connector_ids: list[LiveNewsConnectorId | str] | None = None,
    categories: list[LiveNewsConnectorCategory | str] | None = None,
    capabilities: list[NewsProviderCapability | str] | None = None,
    statuses: list[LiveNewsConnectorStatus | str] | None = None,
    tags: list[str] | None = None,
    mode: LiveNewsConnectorSelectionMode | str = LiveNewsConnectorSelectionMode.ALL,
    include_disabled: bool = False,
    require_credentials: bool = False,
    credentials_by_connector_id: dict[str, NewsProviderCredentials] | None = None,
    limit: int = 0,
    metadata: dict[str, Any] | None = None,
) -> NewsConnectorSelectionRequest:
    """Build connector selection request."""
    return NewsConnectorSelectionRequest(
        connector_ids=connector_ids or [],
        categories=categories or [],
        capabilities=capabilities or [],
        statuses=statuses or [],
        tags=tags or [],
        mode=mode,
        include_disabled=include_disabled,
        require_credentials=require_credentials,
        credentials_by_connector_id=credentials_by_connector_id or {},
        limit=limit,
        metadata=metadata or {},
    )


def build_news_connector_selection_result(
    *,
    success: bool,
    entries: list[NewsConnectorRegistryEntry] | None = None,
    message: str = "",
    request: NewsConnectorSelectionRequest | None = None,
    metadata: dict[str, Any] | None = None,
) -> NewsConnectorSelectionResult:
    """Build connector selection result."""
    return NewsConnectorSelectionResult(
        success=success,
        entries=entries or [],
        message=message,
        request=request,
        metadata=metadata or {},
    )


def build_news_connector_registry(
    *,
    entries: list[NewsConnectorRegistryEntry] | None = None,
    metadata: dict[str, Any] | None = None,
) -> NewsConnectorRegistry:
    """Build connector registry from entries."""
    resolved_entries = entries or []

    return NewsConnectorRegistry(
        entries={
            entry.connector_id.value: entry
            for entry in resolved_entries
        },
        metadata=metadata or {},
    )


def build_default_news_connector_registry() -> NewsConnectorRegistry:
    """Build default AQOS live connector registry."""
    entries = [
        build_news_connector_registry_entry(
            definition=build_gdelt_connector_definition(),
            priority=10,
            tags=["global", "public", "no_key", "news"],
        ),
        build_news_connector_registry_entry(
            definition=build_hackernews_connector_definition(),
            priority=20,
            tags=["public", "no_key", "json", "technology"],
        ),
        build_news_connector_registry_entry(
            definition=build_newsapi_connector_definition(),
            priority=30,
            tags=["financial", "news", "api_key"],
        ),
        build_news_connector_registry_entry(
            definition=build_marketaux_connector_definition(),
            priority=40,
            tags=["financial", "news", "api_key"],
        ),
        build_news_connector_registry_entry(
            definition=build_finnhub_connector_definition(),
            priority=50,
            tags=["financial", "market", "api_key"],
        ),
        build_news_connector_registry_entry(
            definition=build_trading_economics_connector_definition(),
            priority=60,
            tags=["macro", "calendar", "api_key"],
        ),
        build_news_connector_registry_entry(
            definition=build_cryptopanic_connector_definition(),
            priority=70,
            tags=["crypto", "news", "api_key"],
        ),
    ]

    return build_news_connector_registry(
        entries=entries,
        metadata={
            "registry_name": "AQOS default live news connector registry",
            "version": "0.27",
        },
    )


def register_news_connector_definition(
    registry: NewsConnectorRegistry,
    *,
    definition: LiveNewsConnectorDefinition,
    priority: int = 100,
    enabled: bool = True,
    tags: list[str] | None = None,
    metadata: dict[str, Any] | None = None,
    overwrite: bool = False,
) -> NewsConnectorRegistry:
    """Register connector definition into registry and return new registry."""
    if not isinstance(registry, NewsConnectorRegistry):
        raise ValueError("Registry must be NewsConnectorRegistry.")

    entry = build_news_connector_registry_entry(
        definition=definition,
        priority=priority,
        enabled=enabled,
        tags=tags or [],
        metadata=metadata or {},
    )

    entries = dict(registry.entries)

    if entry.connector_id.value in entries and not overwrite:
        raise ValueError(f"Connector '{entry.connector_id.value}' already exists.")

    entries[entry.connector_id.value] = entry

    return NewsConnectorRegistry(
        entries=entries,
        metadata=dict(registry.metadata),
    )


def get_live_news_connector_definition(
    registry: NewsConnectorRegistry,
    connector_id: LiveNewsConnectorId | str,
) -> LiveNewsConnectorDefinition:
    """Get live connector definition from registry."""
    if not isinstance(registry, NewsConnectorRegistry):
        raise ValueError("Registry must be NewsConnectorRegistry.")

    return registry.get_connector(connector_id).definition


def list_live_news_connector_definitions(
    registry: NewsConnectorRegistry,
    *,
    include_disabled: bool = False,
) -> list[LiveNewsConnectorDefinition]:
    """List live connector definitions from registry."""
    if not isinstance(registry, NewsConnectorRegistry):
        raise ValueError("Registry must be NewsConnectorRegistry.")

    return [
        entry.definition
        for entry in registry.list_entries(include_disabled=include_disabled)
    ]


def connector_entry_has_capabilities(
    entry: NewsConnectorRegistryEntry,
    capabilities: list[NewsProviderCapability | str],
) -> bool:
    """Return whether connector entry has all requested capabilities."""
    if not isinstance(entry, NewsConnectorRegistryEntry):
        raise ValueError("Entry must be NewsConnectorRegistryEntry.")

    requested = {
        normalize_capability_value(capability)
        for capability in capabilities
    }
    available = {
        normalize_capability_value(capability)
        for capability in entry.definition.capabilities
    }

    return requested.issubset(available)


def connector_entry_has_tags(
    entry: NewsConnectorRegistryEntry,
    tags: list[str],
) -> bool:
    """Return whether connector entry has all requested tags."""
    if not isinstance(entry, NewsConnectorRegistryEntry):
        raise ValueError("Entry must be NewsConnectorRegistryEntry.")

    requested = {tag.strip().lower() for tag in tags}
    available = {tag.strip().lower() for tag in entry.tags}

    return requested.issubset(available)


def connector_entry_matches_selection_request(
    entry: NewsConnectorRegistryEntry,
    request: NewsConnectorSelectionRequest,
) -> bool:
    """Return whether entry matches selection request."""
    if not isinstance(entry, NewsConnectorRegistryEntry):
        raise ValueError("Entry must be NewsConnectorRegistryEntry.")

    if not isinstance(request, NewsConnectorSelectionRequest):
        raise ValueError("Request must be NewsConnectorSelectionRequest.")

    if not request.include_disabled and not entry.enabled:
        return False

    if request.connector_ids:
        connector_ids = {
            normalize_live_news_connector_id(connector_id)
            for connector_id in request.connector_ids
        }

        if entry.connector_id not in connector_ids:
            return False

    if request.categories:
        categories = {
            normalize_live_news_connector_category(category)
            for category in request.categories
        }

        if entry.category not in categories:
            return False

    if request.statuses:
        statuses = {
            normalize_live_news_connector_status(status)
            for status in request.statuses
        }

        if entry.status not in statuses:
            return False

    if request.capabilities and not connector_entry_has_capabilities(entry, request.capabilities):
        return False

    if request.tags and not connector_entry_has_tags(entry, request.tags):
        return False

    if request.require_credentials:
        credentials = request.credentials_by_connector_id.get(entry.connector_id.value)
        runtime_config = build_live_news_connector_runtime_config(
            connector=entry.definition,
            credentials=credentials or NewsProviderCredentials(),
        )

        if not connector_runtime_has_required_credentials(runtime_config):
            return False

    return True


def select_live_news_connectors(
    registry: NewsConnectorRegistry,
    request: NewsConnectorSelectionRequest | None = None,
) -> NewsConnectorSelectionResult:
    """Select live news connectors from registry."""
    if not isinstance(registry, NewsConnectorRegistry):
        raise ValueError("Registry must be NewsConnectorRegistry.")

    request = request or build_news_connector_selection_request()

    if not isinstance(request, NewsConnectorSelectionRequest):
        raise ValueError("Request must be NewsConnectorSelectionRequest.")

    entries = [
        entry
        for entry in registry.list_entries(include_disabled=request.include_disabled)
        if connector_entry_matches_selection_request(entry, request)
    ]

    mode = normalize_live_news_connector_selection_mode(request.mode)

    if mode == LiveNewsConnectorSelectionMode.FIRST_READY:
        entries = [entry for entry in entries if entry.ready][:1]

    elif mode == LiveNewsConnectorSelectionMode.PREFERRED_ONLY:
        if request.connector_ids:
            preferred_ids = [
                normalize_live_news_connector_id(connector_id).value
                for connector_id in request.connector_ids
            ]
            entries = [
                entry
                for entry in entries
                if entry.connector_id.value in preferred_ids
            ]

    elif mode == LiveNewsConnectorSelectionMode.FALLBACK_CHAIN:
        entries = [entry for entry in entries if entry.ready]

    if request.limit:
        entries = entries[: request.limit]

    return build_news_connector_selection_result(
        success=bool(entries),
        entries=entries,
        message="Selected live news connectors." if entries else "No live news connectors matched.",
        request=request,
        metadata={
            "registry_connector_count": registry.connector_count,
            "selection_mode": mode.value,
        },
    )


def select_connector_runtime_configs(
    registry: NewsConnectorRegistry,
    request: NewsConnectorSelectionRequest | None = None,
) -> list[LiveNewsConnectorRuntimeConfig]:
    """Select connector runtime configs from registry."""
    result = select_live_news_connectors(registry, request)
    request = result.request or build_news_connector_selection_request()

    runtime_configs = []

    for entry in result.entries:
        credentials = request.credentials_by_connector_id.get(entry.connector_id.value)

        runtime_configs.append(
            build_live_news_connector_runtime_config(
                connector=entry.definition,
                credentials=credentials or NewsProviderCredentials(),
            ),
        )

    return runtime_configs


def list_connectors_by_category(
    registry: NewsConnectorRegistry,
    category: LiveNewsConnectorCategory | str,
    *,
    include_disabled: bool = False,
) -> list[NewsConnectorRegistryEntry]:
    """List connectors by category."""
    request = build_news_connector_selection_request(
        categories=[category],
        include_disabled=include_disabled,
    )

    return select_live_news_connectors(registry, request).entries


def list_connectors_by_status(
    registry: NewsConnectorRegistry,
    status: LiveNewsConnectorStatus | str,
    *,
    include_disabled: bool = False,
) -> list[NewsConnectorRegistryEntry]:
    """List connectors by status."""
    request = build_news_connector_selection_request(
        statuses=[status],
        include_disabled=include_disabled,
    )

    return select_live_news_connectors(registry, request).entries


def list_connectors_by_capability(
    registry: NewsConnectorRegistry,
    capability: NewsProviderCapability | str,
    *,
    include_disabled: bool = False,
) -> list[NewsConnectorRegistryEntry]:
    """List connectors by capability."""
    request = build_news_connector_selection_request(
        capabilities=[capability],
        include_disabled=include_disabled,
    )

    return select_live_news_connectors(registry, request).entries