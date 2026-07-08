"""
AQOS broker base primitives.

This module contains dependency-free broker/exchange primitives for order
execution, paper trading, live broker adapters, and future exchange integration.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import Enum
from typing import Any


class BrokerType(str, Enum):
    """Supported broker types."""

    PAPER = "paper"
    EXCHANGE = "exchange"
    FOREX = "forex"
    CFD = "cfd"
    CRYPTO = "crypto"
    STOCK = "stock"


class BrokerStatus(str, Enum):
    """Supported broker statuses."""

    ACTIVE = "active"
    INACTIVE = "inactive"
    DEGRADED = "degraded"
    ERROR = "error"


class BrokerCapability(str, Enum):
    """Supported broker capabilities."""

    PAPER_TRADING = "paper_trading"
    LIVE_TRADING = "live_trading"
    MARKET_ORDERS = "market_orders"
    LIMIT_ORDERS = "limit_orders"
    STOP_ORDERS = "stop_orders"
    ACCOUNT_INFO = "account_info"
    POSITION_TRACKING = "position_tracking"
    TRADE_HISTORY = "trade_history"


class BrokerAuthType(str, Enum):
    """Supported broker authentication types."""

    NONE = "none"
    API_KEY = "api_key"
    BEARER_TOKEN = "bearer_token"
    BASIC = "basic"


@dataclass(frozen=True)
class BrokerCredentials:
    """Broker credentials container."""

    auth_type: BrokerAuthType | str = BrokerAuthType.NONE
    api_key: str = ""
    secret: str = ""
    token: str = ""
    username: str = ""
    password: str = ""
    account_id: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        normalize_broker_auth_type(self.auth_type)
        validate_string(self.api_key, "API key")
        validate_string(self.secret, "Secret")
        validate_string(self.token, "Token")
        validate_string(self.username, "Username")
        validate_string(self.password, "Password")
        validate_string(self.account_id, "Account ID")
        validate_metadata(self.metadata, "Metadata")

    @property
    def configured(self) -> bool:
        """Return whether credentials are configured."""
        auth_type = normalize_broker_auth_type(self.auth_type)

        if auth_type == BrokerAuthType.NONE:
            return True

        if auth_type == BrokerAuthType.API_KEY:
            return bool(self.api_key.strip()) and bool(self.secret.strip())

        if auth_type == BrokerAuthType.BEARER_TOKEN:
            return bool(self.token.strip())

        if auth_type == BrokerAuthType.BASIC:
            return bool(self.username.strip()) and bool(self.password.strip())

        return False

    def masked(self) -> dict[str, Any]:
        """Return masked credentials."""
        return {
            "auth_type": normalize_broker_auth_type(self.auth_type).value,
            "api_key": mask_secret(self.api_key),
            "secret": mask_secret(self.secret),
            "token": mask_secret(self.token),
            "username": self.username.strip(),
            "password": mask_secret(self.password),
            "account_id": self.account_id.strip(),
            "configured": self.configured,
            "metadata": dict(self.metadata),
        }


@dataclass(frozen=True)
class BrokerConfig:
    """Broker configuration."""

    broker_id: str
    name: str
    broker_type: BrokerType | str
    base_url: str = ""
    status: BrokerStatus | str = BrokerStatus.ACTIVE
    capabilities: list[BrokerCapability | str] = field(default_factory=list)
    credentials: BrokerCredentials = field(default_factory=BrokerCredentials)
    paper_mode: bool = True
    timeout_seconds: float = 30.0
    rate_limit_per_minute: int = 60
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        validate_non_empty_string(self.broker_id, "Broker ID")
        validate_non_empty_string(self.name, "Broker name")
        normalize_broker_type(self.broker_type)
        validate_string(self.base_url, "Base URL")
        normalize_broker_status(self.status)
        validate_broker_capabilities(self.capabilities)

        if not isinstance(self.credentials, BrokerCredentials):
            raise ValueError("Credentials must be BrokerCredentials.")

        if not isinstance(self.paper_mode, bool):
            raise ValueError("Paper mode must be a boolean.")

        validate_positive_float(self.timeout_seconds, "Timeout seconds")
        validate_positive_integer(self.rate_limit_per_minute, "Rate limit per minute")
        validate_metadata(self.metadata, "Metadata")

    @property
    def active(self) -> bool:
        """Return whether broker is active."""
        return normalize_broker_status(self.status) == BrokerStatus.ACTIVE

    @property
    def live_mode(self) -> bool:
        """Return whether broker is configured for live mode."""
        return not self.paper_mode

    def supports(self, capability: BrokerCapability | str) -> bool:
        """Return whether broker supports capability."""
        normalized_capability = normalize_broker_capability(capability)

        return normalized_capability in {
            normalize_broker_capability(item)
            for item in self.capabilities
        }

    def to_dict(self) -> dict[str, Any]:
        """Convert broker config into dictionary."""
        return {
            "broker_id": self.broker_id.strip(),
            "name": self.name.strip(),
            "broker_type": normalize_broker_type(self.broker_type).value,
            "base_url": self.base_url.strip(),
            "status": normalize_broker_status(self.status).value,
            "active": self.active,
            "paper_mode": self.paper_mode,
            "live_mode": self.live_mode,
            "capabilities": [
                normalize_broker_capability(item).value
                for item in self.capabilities
            ],
            "credentials": self.credentials.masked(),
            "timeout_seconds": float(self.timeout_seconds),
            "rate_limit_per_minute": self.rate_limit_per_minute,
            "metadata": dict(self.metadata),
        }


@dataclass(frozen=True)
class BrokerHealth:
    """Broker health snapshot."""

    broker_id: str
    status: BrokerStatus | str
    message: str = ""
    latency_ms: float = 0.0
    checked_at: str = field(default_factory=lambda: datetime.now(UTC).isoformat())
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        validate_non_empty_string(self.broker_id, "Broker ID")
        normalize_broker_status(self.status)
        validate_string(self.message, "Message")
        validate_non_negative_float(self.latency_ms, "Latency milliseconds")
        validate_non_empty_string(self.checked_at, "Checked at")
        validate_metadata(self.metadata, "Metadata")

    @property
    def healthy(self) -> bool:
        """Return whether broker is healthy."""
        return normalize_broker_status(self.status) == BrokerStatus.ACTIVE

    def to_dict(self) -> dict[str, Any]:
        """Convert health snapshot into dictionary."""
        return {
            "broker_id": self.broker_id.strip(),
            "status": normalize_broker_status(self.status).value,
            "healthy": self.healthy,
            "message": self.message.strip(),
            "latency_ms": float(self.latency_ms),
            "checked_at": self.checked_at.strip(),
            "metadata": dict(self.metadata),
        }


@dataclass(frozen=True)
class BrokerResult:
    """Generic broker operation result."""

    broker_id: str
    success: bool
    data: dict[str, Any] = field(default_factory=dict)
    message: str = ""
    error: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        validate_non_empty_string(self.broker_id, "Broker ID")

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
        """Convert broker result into dictionary."""
        return {
            "broker_id": self.broker_id.strip(),
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


def normalize_broker_type(broker_type: BrokerType | str) -> BrokerType:
    """Normalize broker type."""
    if isinstance(broker_type, BrokerType):
        return broker_type

    normalized = validate_non_empty_string(broker_type, "Broker type").lower()

    try:
        return BrokerType(normalized)
    except ValueError as exc:
        valid = ", ".join(item.value for item in BrokerType)
        raise ValueError(
            f"Invalid broker type '{broker_type}'. Valid broker types: {valid}.",
        ) from exc


def normalize_broker_status(status: BrokerStatus | str) -> BrokerStatus:
    """Normalize broker status."""
    if isinstance(status, BrokerStatus):
        return status

    normalized = validate_non_empty_string(status, "Broker status").lower()

    try:
        return BrokerStatus(normalized)
    except ValueError as exc:
        valid = ", ".join(item.value for item in BrokerStatus)
        raise ValueError(
            f"Invalid broker status '{status}'. Valid statuses: {valid}.",
        ) from exc


def normalize_broker_capability(capability: BrokerCapability | str) -> BrokerCapability:
    """Normalize broker capability."""
    if isinstance(capability, BrokerCapability):
        return capability

    normalized = validate_non_empty_string(capability, "Broker capability").lower()

    try:
        return BrokerCapability(normalized)
    except ValueError as exc:
        valid = ", ".join(item.value for item in BrokerCapability)
        raise ValueError(
            f"Invalid broker capability '{capability}'. Valid capabilities: {valid}.",
        ) from exc


def normalize_broker_auth_type(auth_type: BrokerAuthType | str) -> BrokerAuthType:
    """Normalize broker auth type."""
    if isinstance(auth_type, BrokerAuthType):
        return auth_type

    normalized = validate_non_empty_string(auth_type, "Broker auth type").lower()

    try:
        return BrokerAuthType(normalized)
    except ValueError as exc:
        valid = ", ".join(item.value for item in BrokerAuthType)
        raise ValueError(
            f"Invalid broker auth type '{auth_type}'. Valid auth types: {valid}.",
        ) from exc


def validate_broker_capabilities(
    capabilities: list[BrokerCapability | str],
) -> list[BrokerCapability | str]:
    """Validate broker capabilities."""
    if not isinstance(capabilities, list):
        raise ValueError("Capabilities must be a list.")

    for capability in capabilities:
        normalize_broker_capability(capability)

    return capabilities


def mask_secret(value: str) -> str:
    """Mask secret value."""
    validate_string(value, "Secret")

    if not value:
        return ""

    return "********"


def build_broker_credentials(
    *,
    auth_type: BrokerAuthType | str = BrokerAuthType.NONE,
    api_key: str = "",
    secret: str = "",
    token: str = "",
    username: str = "",
    password: str = "",
    account_id: str = "",
    metadata: dict[str, Any] | None = None,
) -> BrokerCredentials:
    """Build broker credentials."""
    return BrokerCredentials(
        auth_type=auth_type,
        api_key=api_key,
        secret=secret,
        token=token,
        username=username,
        password=password,
        account_id=account_id,
        metadata=metadata or {},
    )


def build_broker_config(
    *,
    broker_id: str,
    name: str,
    broker_type: BrokerType | str,
    base_url: str = "",
    status: BrokerStatus | str = BrokerStatus.ACTIVE,
    capabilities: list[BrokerCapability | str] | None = None,
    credentials: BrokerCredentials | None = None,
    paper_mode: bool = True,
    timeout_seconds: float = 30.0,
    rate_limit_per_minute: int = 60,
    metadata: dict[str, Any] | None = None,
) -> BrokerConfig:
    """Build broker config."""
    return BrokerConfig(
        broker_id=broker_id,
        name=name,
        broker_type=broker_type,
        base_url=base_url,
        status=status,
        capabilities=capabilities or [],
        credentials=credentials or BrokerCredentials(),
        paper_mode=paper_mode,
        timeout_seconds=timeout_seconds,
        rate_limit_per_minute=rate_limit_per_minute,
        metadata=metadata or {},
    )


def build_broker_health(
    *,
    broker_id: str,
    status: BrokerStatus | str,
    message: str = "",
    latency_ms: float = 0.0,
    checked_at: str | None = None,
    metadata: dict[str, Any] | None = None,
) -> BrokerHealth:
    """Build broker health."""
    health_kwargs: dict[str, Any] = {
        "broker_id": broker_id,
        "status": status,
        "message": message,
        "latency_ms": latency_ms,
        "metadata": metadata or {},
    }

    if checked_at is not None:
        health_kwargs["checked_at"] = checked_at

    return BrokerHealth(**health_kwargs)


def build_broker_result(
    *,
    broker_id: str,
    success: bool,
    data: dict[str, Any] | None = None,
    message: str = "",
    error: str = "",
    metadata: dict[str, Any] | None = None,
) -> BrokerResult:
    """Build broker result."""
    return BrokerResult(
        broker_id=broker_id,
        success=success,
        data=data or {},
        message=message,
        error=error,
        metadata=metadata or {},
    )


def broker_success(
    *,
    broker_id: str,
    data: dict[str, Any] | None = None,
    message: str = "Broker operation completed.",
    metadata: dict[str, Any] | None = None,
) -> BrokerResult:
    """Build successful broker result."""
    return build_broker_result(
        broker_id=broker_id,
        success=True,
        data=data or {},
        message=message,
        metadata=metadata or {},
    )


def broker_failure(
    *,
    broker_id: str,
    error: str,
    data: dict[str, Any] | None = None,
    message: str = "Broker operation failed.",
    metadata: dict[str, Any] | None = None,
) -> BrokerResult:
    """Build failed broker result."""
    return build_broker_result(
        broker_id=broker_id,
        success=False,
        data=data or {},
        message=message,
        error=error,
        metadata=metadata or {},
    )