"""
AQOS provider base primitives.

This module contains dependency-free provider primitives for external market
data, broker, research, and future third-party provider integrations.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import Enum
from typing import Any


class ProviderType(str, Enum):
    """Supported provider types."""

    MARKET_DATA = "market_data"
    BROKER = "broker"
    NEWS = "news"
    CALENDAR = "calendar"
    RESEARCH = "research"


class ProviderStatus(str, Enum):
    """Supported provider statuses."""

    ACTIVE = "active"
    INACTIVE = "inactive"
    DEGRADED = "degraded"
    ERROR = "error"


class ProviderCapability(str, Enum):
    """Supported provider capabilities."""

    HISTORICAL_OHLCV = "historical_ohlcv"
    LIVE_QUOTES = "live_quotes"
    TICKS = "ticks"
    ORDER_EXECUTION = "order_execution"
    NEWS_FEED = "news_feed"
    ECONOMIC_CALENDAR = "economic_calendar"


class ProviderAuthType(str, Enum):
    """Supported provider authentication types."""

    NONE = "none"
    API_KEY = "api_key"
    BEARER_TOKEN = "bearer_token"
    BASIC = "basic"


@dataclass(frozen=True)
class ProviderCredentials:
    """Provider credentials container."""

    auth_type: ProviderAuthType | str = ProviderAuthType.NONE
    api_key: str = ""
    token: str = ""
    username: str = ""
    password: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        normalize_provider_auth_type(self.auth_type)
        validate_string(self.api_key, "API key")
        validate_string(self.token, "Token")
        validate_string(self.username, "Username")
        validate_string(self.password, "Password")
        validate_metadata(self.metadata, "Metadata")

    @property
    def configured(self) -> bool:
        """Return whether credentials are configured."""
        auth_type = normalize_provider_auth_type(self.auth_type)

        if auth_type == ProviderAuthType.NONE:
            return True

        if auth_type == ProviderAuthType.API_KEY:
            return bool(self.api_key.strip())

        if auth_type == ProviderAuthType.BEARER_TOKEN:
            return bool(self.token.strip())

        if auth_type == ProviderAuthType.BASIC:
            return bool(self.username.strip()) and bool(self.password.strip())

        return False

    def masked(self) -> dict[str, Any]:
        """Return masked credentials."""
        return {
            "auth_type": normalize_provider_auth_type(self.auth_type).value,
            "api_key": mask_secret(self.api_key),
            "token": mask_secret(self.token),
            "username": self.username.strip(),
            "password": mask_secret(self.password),
            "configured": self.configured,
            "metadata": dict(self.metadata),
        }


@dataclass(frozen=True)
class ProviderConfig:
    """Provider configuration."""

    provider_id: str
    name: str
    provider_type: ProviderType | str
    base_url: str = ""
    status: ProviderStatus | str = ProviderStatus.ACTIVE
    capabilities: list[ProviderCapability | str] = field(default_factory=list)
    credentials: ProviderCredentials = field(default_factory=ProviderCredentials)
    timeout_seconds: float = 30.0
    rate_limit_per_minute: int = 60
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        validate_non_empty_string(self.provider_id, "Provider ID")
        validate_non_empty_string(self.name, "Provider name")
        normalize_provider_type(self.provider_type)
        validate_string(self.base_url, "Base URL")
        normalize_provider_status(self.status)
        validate_provider_capabilities(self.capabilities)

        if not isinstance(self.credentials, ProviderCredentials):
            raise ValueError("Credentials must be ProviderCredentials.")

        validate_positive_float(self.timeout_seconds, "Timeout seconds")
        validate_positive_integer(self.rate_limit_per_minute, "Rate limit per minute")
        validate_metadata(self.metadata, "Metadata")

    @property
    def active(self) -> bool:
        """Return whether provider is active."""
        return normalize_provider_status(self.status) == ProviderStatus.ACTIVE

    def supports(self, capability: ProviderCapability | str) -> bool:
        """Return whether provider supports capability."""
        normalized_capability = normalize_provider_capability(capability)

        return normalized_capability in {
            normalize_provider_capability(item)
            for item in self.capabilities
        }

    def to_dict(self) -> dict[str, Any]:
        """Convert provider config into dictionary."""
        return {
            "provider_id": self.provider_id.strip(),
            "name": self.name.strip(),
            "provider_type": normalize_provider_type(self.provider_type).value,
            "base_url": self.base_url.strip(),
            "status": normalize_provider_status(self.status).value,
            "active": self.active,
            "capabilities": [
                normalize_provider_capability(item).value
                for item in self.capabilities
            ],
            "credentials": self.credentials.masked(),
            "timeout_seconds": float(self.timeout_seconds),
            "rate_limit_per_minute": self.rate_limit_per_minute,
            "metadata": dict(self.metadata),
        }


@dataclass(frozen=True)
class ProviderHealth:
    """Provider health snapshot."""

    provider_id: str
    status: ProviderStatus | str
    message: str = ""
    latency_ms: float = 0.0
    checked_at: str = field(default_factory=lambda: datetime.now(UTC).isoformat())
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        validate_non_empty_string(self.provider_id, "Provider ID")
        normalize_provider_status(self.status)
        validate_string(self.message, "Message")
        validate_non_negative_float(self.latency_ms, "Latency milliseconds")
        validate_non_empty_string(self.checked_at, "Checked at")
        validate_metadata(self.metadata, "Metadata")

    @property
    def healthy(self) -> bool:
        """Return whether provider health is active."""
        return normalize_provider_status(self.status) == ProviderStatus.ACTIVE

    def to_dict(self) -> dict[str, Any]:
        """Convert health snapshot into dictionary."""
        return {
            "provider_id": self.provider_id.strip(),
            "status": normalize_provider_status(self.status).value,
            "healthy": self.healthy,
            "message": self.message.strip(),
            "latency_ms": float(self.latency_ms),
            "checked_at": self.checked_at.strip(),
            "metadata": dict(self.metadata),
        }


@dataclass(frozen=True)
class ProviderResult:
    """Generic provider operation result."""

    provider_id: str
    success: bool
    data: dict[str, Any] = field(default_factory=dict)
    message: str = ""
    error: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        validate_non_empty_string(self.provider_id, "Provider ID")

        if not isinstance(self.success, bool):
            raise ValueError("Success must be a boolean.")

        validate_metadata(self.data, "Data")
        validate_string(self.message, "Message")
        validate_string(self.error, "Error")
        validate_metadata(self.metadata, "Metadata")

    @property
    def failed(self) -> bool:
        """Return whether result failed."""
        return not self.success

    def to_dict(self) -> dict[str, Any]:
        """Convert provider result into dictionary."""
        return {
            "provider_id": self.provider_id.strip(),
            "success": self.success,
            "failed": self.failed,
            "data": dict(self.data),
            "message": self.message.strip(),
            "error": self.error.strip(),
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


def validate_positive_integer(value: int, field_name: str) -> int:
    """Validate positive integer."""
    if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
        raise ValueError(f"{field_name} must be a positive integer.")

    return value


def validate_positive_float(value: float | int, field_name: str) -> float:
    """Validate positive number."""
    if isinstance(value, bool) or not isinstance(value, int | float) or value <= 0:
        raise ValueError(f"{field_name} must be a positive number.")

    return float(value)


def validate_non_negative_float(value: float | int, field_name: str) -> float:
    """Validate non-negative number."""
    if isinstance(value, bool) or not isinstance(value, int | float) or value < 0:
        raise ValueError(f"{field_name} must be a non-negative number.")

    return float(value)


def normalize_provider_type(provider_type: ProviderType | str) -> ProviderType:
    """Normalize provider type."""
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


def normalize_provider_status(status: ProviderStatus | str) -> ProviderStatus:
    """Normalize provider status."""
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


def normalize_provider_capability(
    capability: ProviderCapability | str,
) -> ProviderCapability:
    """Normalize provider capability."""
    if isinstance(capability, ProviderCapability):
        return capability

    normalized = validate_non_empty_string(capability, "Provider capability").lower()

    try:
        return ProviderCapability(normalized)
    except ValueError as exc:
        valid = ", ".join(item.value for item in ProviderCapability)
        raise ValueError(
            f"Invalid provider capability '{capability}'. Valid capabilities: {valid}.",
        ) from exc


def normalize_provider_auth_type(auth_type: ProviderAuthType | str) -> ProviderAuthType:
    """Normalize provider auth type."""
    if isinstance(auth_type, ProviderAuthType):
        return auth_type

    normalized = validate_non_empty_string(auth_type, "Provider auth type").lower()

    try:
        return ProviderAuthType(normalized)
    except ValueError as exc:
        valid = ", ".join(item.value for item in ProviderAuthType)
        raise ValueError(
            f"Invalid provider auth type '{auth_type}'. Valid auth types: {valid}.",
        ) from exc


def validate_provider_capabilities(
    capabilities: list[ProviderCapability | str],
) -> list[ProviderCapability | str]:
    """Validate provider capabilities."""
    if not isinstance(capabilities, list):
        raise ValueError("Capabilities must be a list.")

    for capability in capabilities:
        normalize_provider_capability(capability)

    return capabilities


def mask_secret(value: str) -> str:
    """Mask secret value."""
    validate_string(value, "Secret")

    if not value:
        return ""

    return "********"


def build_provider_credentials(
    *,
    auth_type: ProviderAuthType | str = ProviderAuthType.NONE,
    api_key: str = "",
    token: str = "",
    username: str = "",
    password: str = "",
    metadata: dict[str, Any] | None = None,
) -> ProviderCredentials:
    """Build provider credentials."""
    return ProviderCredentials(
        auth_type=auth_type,
        api_key=api_key,
        token=token,
        username=username,
        password=password,
        metadata=metadata or {},
    )


def build_provider_config(
    *,
    provider_id: str,
    name: str,
    provider_type: ProviderType | str,
    base_url: str = "",
    status: ProviderStatus | str = ProviderStatus.ACTIVE,
    capabilities: list[ProviderCapability | str] | None = None,
    credentials: ProviderCredentials | None = None,
    timeout_seconds: float = 30.0,
    rate_limit_per_minute: int = 60,
    metadata: dict[str, Any] | None = None,
) -> ProviderConfig:
    """Build provider config."""
    return ProviderConfig(
        provider_id=provider_id,
        name=name,
        provider_type=provider_type,
        base_url=base_url,
        status=status,
        capabilities=capabilities or [],
        credentials=credentials or ProviderCredentials(),
        timeout_seconds=timeout_seconds,
        rate_limit_per_minute=rate_limit_per_minute,
        metadata=metadata or {},
    )


def build_provider_health(
    *,
    provider_id: str,
    status: ProviderStatus | str,
    message: str = "",
    latency_ms: float = 0.0,
    checked_at: str | None = None,
    metadata: dict[str, Any] | None = None,
) -> ProviderHealth:
    """Build provider health."""
    health_kwargs: dict[str, Any] = {
        "provider_id": provider_id,
        "status": status,
        "message": message,
        "latency_ms": latency_ms,
        "metadata": metadata or {},
    }

    if checked_at is not None:
        health_kwargs["checked_at"] = checked_at

    return ProviderHealth(**health_kwargs)


def build_provider_result(
    *,
    provider_id: str,
    success: bool,
    data: dict[str, Any] | None = None,
    message: str = "",
    error: str = "",
    metadata: dict[str, Any] | None = None,
) -> ProviderResult:
    """Build provider result."""
    return ProviderResult(
        provider_id=provider_id,
        success=success,
        data=data or {},
        message=message,
        error=error,
        metadata=metadata or {},
    )


def provider_success(
    *,
    provider_id: str,
    data: dict[str, Any] | None = None,
    message: str = "Provider operation completed.",
    metadata: dict[str, Any] | None = None,
) -> ProviderResult:
    """Build successful provider result."""
    return build_provider_result(
        provider_id=provider_id,
        success=True,
        data=data or {},
        message=message,
        metadata=metadata or {},
    )


def provider_failure(
    *,
    provider_id: str,
    error: str,
    data: dict[str, Any] | None = None,
    message: str = "Provider operation failed.",
    metadata: dict[str, Any] | None = None,
) -> ProviderResult:
    """Build failed provider result."""
    return build_provider_result(
        provider_id=provider_id,
        success=False,
        data=data or {},
        message=message,
        error=error,
        metadata=metadata or {},
    )