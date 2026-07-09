"""
AQOS news providers base primitives.

This package connects AQOS to real news, macro, economic calendar,
sentiment, and event data providers.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import Enum
from typing import Any

from aqos.training_data.events import (
    HistoricalEventImpact,
    HistoricalEventSentiment,
    HistoricalEventType,
    normalize_historical_event_impact,
    normalize_historical_event_sentiment,
    normalize_historical_event_type,
)


class NewsProviderType(str, Enum):
    """Supported news provider types."""

    ECONOMIC_CALENDAR = "economic_calendar"
    NEWS_FEED = "news_feed"
    SENTIMENT = "sentiment"
    RSS = "rss"
    LOCAL_JSON = "local_json"
    HTTP = "http"
    AGGREGATOR = "aggregator"
    UNKNOWN = "unknown"


class NewsProviderStatus(str, Enum):
    """Supported news provider statuses."""

    ACTIVE = "active"
    INACTIVE = "inactive"
    DEGRADED = "degraded"
    ERROR = "error"
    UNKNOWN = "unknown"


class NewsProviderCapability(str, Enum):
    """Supported news provider capabilities."""

    HISTORICAL_NEWS = "historical_news"
    LIVE_NEWS = "live_news"
    ECONOMIC_CALENDAR = "economic_calendar"
    MACRO_EVENTS = "macro_events"
    SENTIMENT = "sentiment"
    IMPACT_CLASSIFICATION = "impact_classification"
    SYMBOL_MAPPING = "symbol_mapping"
    COUNTRY_FILTERING = "country_filtering"
    CURRENCY_FILTERING = "currency_filtering"
    KEYWORD_FILTERING = "keyword_filtering"


class NewsProviderAuthType(str, Enum):
    """Supported news provider authentication types."""

    NONE = "none"
    API_KEY = "api_key"
    BEARER_TOKEN = "bearer_token"
    BASIC = "basic"
    OAUTH = "oauth"


@dataclass(frozen=True)
class NewsProviderCredentials:
    """News provider credentials."""

    auth_type: NewsProviderAuthType | str = NewsProviderAuthType.NONE
    api_key: str = ""
    bearer_token: str = ""
    username: str = ""
    password: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        normalize_news_provider_auth_type(self.auth_type)
        validate_string(self.api_key, "API key")
        validate_string(self.bearer_token, "Bearer token")
        validate_string(self.username, "Username")
        validate_string(self.password, "Password")
        validate_metadata(self.metadata, "Metadata")

    @property
    def requires_secret(self) -> bool:
        """Return whether credentials require a secret."""
        return normalize_news_provider_auth_type(self.auth_type) != NewsProviderAuthType.NONE

    @property
    def configured(self) -> bool:
        """Return whether credentials are configured."""
        auth_type = normalize_news_provider_auth_type(self.auth_type)

        if auth_type == NewsProviderAuthType.NONE:
            return True

        if auth_type == NewsProviderAuthType.API_KEY:
            return bool(self.api_key.strip())

        if auth_type == NewsProviderAuthType.BEARER_TOKEN:
            return bool(self.bearer_token.strip())

        if auth_type == NewsProviderAuthType.BASIC:
            return bool(self.username.strip()) and bool(self.password.strip())

        if auth_type == NewsProviderAuthType.OAUTH:
            return bool(self.bearer_token.strip())

        return False

    def to_safe_dict(self) -> dict[str, Any]:
        """Convert credentials to safe dictionary."""
        return {
            "auth_type": normalize_news_provider_auth_type(self.auth_type).value,
            "requires_secret": self.requires_secret,
            "configured": self.configured,
            "has_api_key": bool(self.api_key.strip()),
            "has_bearer_token": bool(self.bearer_token.strip()),
            "has_username": bool(self.username.strip()),
            "metadata": dict(self.metadata),
        }


@dataclass(frozen=True)
class NewsProviderConfig:
    """News provider configuration."""

    provider_id: str
    name: str
    provider_type: NewsProviderType | str = NewsProviderType.UNKNOWN
    base_url: str = ""
    status: NewsProviderStatus | str = NewsProviderStatus.INACTIVE
    capabilities: list[NewsProviderCapability | str] = field(default_factory=list)
    credentials: NewsProviderCredentials = field(default_factory=NewsProviderCredentials)
    timeout_seconds: int = 30
    rate_limit_per_minute: int = 0
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        validate_non_empty_string(self.provider_id, "Provider ID")
        validate_non_empty_string(self.name, "Provider name")
        normalize_news_provider_type(self.provider_type)
        validate_string(self.base_url, "Base URL")
        normalize_news_provider_status(self.status)
        validate_news_provider_capabilities(self.capabilities)

        if not isinstance(self.credentials, NewsProviderCredentials):
            raise ValueError("Credentials must be NewsProviderCredentials.")

        validate_positive_integer(self.timeout_seconds, "Timeout seconds")
        validate_non_negative_integer(self.rate_limit_per_minute, "Rate limit per minute")
        validate_metadata(self.metadata, "Metadata")

    @property
    def active(self) -> bool:
        """Return whether provider is active."""
        return normalize_news_provider_status(self.status) == NewsProviderStatus.ACTIVE

    @property
    def capability_count(self) -> int:
        """Return capability count."""
        return len(self.capabilities)

    def has_capability(self, capability: NewsProviderCapability | str) -> bool:
        """Return whether provider has capability."""
        normalized = normalize_news_provider_capability(capability)

        return normalized in [
            normalize_news_provider_capability(item)
            for item in self.capabilities
        ]

    def to_dict(self) -> dict[str, Any]:
        """Convert config to dictionary."""
        return {
            "provider_id": self.provider_id.strip(),
            "name": self.name.strip(),
            "provider_type": normalize_news_provider_type(self.provider_type).value,
            "base_url": self.base_url.strip(),
            "status": normalize_news_provider_status(self.status).value,
            "active": self.active,
            "capabilities": [
                normalize_news_provider_capability(item).value
                for item in self.capabilities
            ],
            "capability_count": self.capability_count,
            "credentials": self.credentials.to_safe_dict(),
            "timeout_seconds": self.timeout_seconds,
            "rate_limit_per_minute": self.rate_limit_per_minute,
            "metadata": dict(self.metadata),
        }


@dataclass(frozen=True)
class NewsProviderHealth:
    """News provider health result."""

    provider_id: str
    status: NewsProviderStatus | str = NewsProviderStatus.UNKNOWN
    connected: bool = False
    message: str = ""
    latency_ms: float = 0.0
    checked_at: str = field(default_factory=lambda: datetime.now(UTC).isoformat())
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        validate_non_empty_string(self.provider_id, "Provider ID")
        normalize_news_provider_status(self.status)

        if not isinstance(self.connected, bool):
            raise ValueError("Connected must be a boolean.")

        validate_string(self.message, "Message")
        validate_non_negative_float(self.latency_ms, "Latency milliseconds")
        validate_non_empty_string(self.checked_at, "Checked at")
        validate_metadata(self.metadata, "Metadata")

    @property
    def healthy(self) -> bool:
        """Return whether provider is healthy."""
        return self.connected and normalize_news_provider_status(self.status) == NewsProviderStatus.ACTIVE

    def to_dict(self) -> dict[str, Any]:
        """Convert health to dictionary."""
        return {
            "provider_id": self.provider_id.strip(),
            "status": normalize_news_provider_status(self.status).value,
            "connected": self.connected,
            "healthy": self.healthy,
            "message": self.message.strip(),
            "latency_ms": float(self.latency_ms),
            "checked_at": self.checked_at.strip(),
            "metadata": dict(self.metadata),
        }


@dataclass(frozen=True)
class NewsProviderIssue:
    """News provider issue."""

    code: str
    message: str
    provider_id: str = ""
    status: NewsProviderStatus | str = NewsProviderStatus.ERROR
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        validate_non_empty_string(self.code, "Issue code")
        validate_non_empty_string(self.message, "Issue message")
        validate_string(self.provider_id, "Provider ID")
        normalize_news_provider_status(self.status)
        validate_metadata(self.metadata, "Metadata")

    def to_dict(self) -> dict[str, Any]:
        """Convert issue to dictionary."""
        return {
            "code": self.code.strip(),
            "message": self.message.strip(),
            "provider_id": self.provider_id.strip(),
            "status": normalize_news_provider_status(self.status).value,
            "metadata": dict(self.metadata),
        }


@dataclass(frozen=True)
class NewsEventRecord:
    """Normalized provider news/event record."""

    event_id: str
    timestamp: str
    title: str
    event_type: HistoricalEventType | str = HistoricalEventType.UNKNOWN
    symbol: str = ""
    impact: HistoricalEventImpact | str = HistoricalEventImpact.UNKNOWN
    sentiment: HistoricalEventSentiment | str = HistoricalEventSentiment.UNKNOWN
    source: str = ""
    provider_id: str = ""
    url: str = ""
    description: str = ""
    country: str = ""
    currency: str = ""
    relevance_score: float = 0.0
    raw_payload: dict[str, Any] = field(default_factory=dict)
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        validate_non_empty_string(self.event_id, "Event ID")
        validate_non_empty_string(self.timestamp, "Timestamp")
        validate_non_empty_string(self.title, "Title")
        normalize_historical_event_type(self.event_type)
        validate_string(self.symbol, "Symbol")

        if self.symbol.strip():
            normalize_news_symbol(self.symbol)

        normalize_historical_event_impact(self.impact)
        normalize_historical_event_sentiment(self.sentiment)
        validate_string(self.source, "Source")
        validate_string(self.provider_id, "Provider ID")
        validate_string(self.url, "URL")
        validate_string(self.description, "Description")
        validate_string(self.country, "Country")
        validate_string(self.currency, "Currency")
        validate_score(self.relevance_score, "Relevance score")
        validate_metadata(self.raw_payload, "Raw payload")
        validate_metadata(self.metadata, "Metadata")

    @property
    def high_impact(self) -> bool:
        """Return whether record is high impact."""
        return normalize_historical_event_impact(self.impact) in {
            HistoricalEventImpact.HIGH,
            HistoricalEventImpact.CRITICAL,
        }

    @property
    def directional(self) -> bool:
        """Return whether record is directional."""
        return normalize_historical_event_sentiment(self.sentiment) in {
            HistoricalEventSentiment.BULLISH,
            HistoricalEventSentiment.BEARISH,
        }

    def to_dict(self) -> dict[str, Any]:
        """Convert event record to dictionary."""
        return {
            "event_id": self.event_id.strip(),
            "timestamp": self.timestamp.strip(),
            "title": self.title.strip(),
            "event_type": normalize_historical_event_type(self.event_type).value,
            "symbol": normalize_news_symbol(self.symbol) if self.symbol.strip() else "",
            "impact": normalize_historical_event_impact(self.impact).value,
            "sentiment": normalize_historical_event_sentiment(self.sentiment).value,
            "source": self.source.strip(),
            "provider_id": self.provider_id.strip(),
            "url": self.url.strip(),
            "description": self.description.strip(),
            "country": self.country.strip().upper(),
            "currency": self.currency.strip().upper(),
            "relevance_score": float(self.relevance_score),
            "high_impact": self.high_impact,
            "directional": self.directional,
            "raw_payload": dict(self.raw_payload),
            "metadata": dict(self.metadata),
        }


@dataclass(frozen=True)
class NewsProviderResult:
    """News provider result."""

    success: bool
    records: list[NewsEventRecord] = field(default_factory=list)
    message: str = ""
    provider_id: str = ""
    issues: list[NewsProviderIssue] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not isinstance(self.success, bool):
            raise ValueError("Success must be a boolean.")

        validate_news_event_records(self.records)
        validate_string(self.message, "Message")
        validate_string(self.provider_id, "Provider ID")
        validate_news_provider_issues(self.issues)
        validate_metadata(self.metadata, "Metadata")

    @property
    def failed(self) -> bool:
        """Return whether result failed."""
        return not self.success

    @property
    def record_count(self) -> int:
        """Return record count."""
        return len(self.records)

    @property
    def issue_count(self) -> int:
        """Return issue count."""
        return len(self.issues)

    def to_dict(self) -> dict[str, Any]:
        """Convert result to dictionary."""
        return {
            "success": self.success,
            "failed": self.failed,
            "records": [record.to_dict() for record in self.records],
            "record_count": self.record_count,
            "message": self.message.strip(),
            "provider_id": self.provider_id.strip(),
            "issues": [issue.to_dict() for issue in self.issues],
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


def validate_non_negative_integer(value: int, field_name: str) -> int:
    """Validate non-negative integer."""
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise ValueError(f"{field_name} must be a non-negative integer.")

    return value


def validate_positive_integer(value: int, field_name: str) -> int:
    """Validate positive integer."""
    if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
        raise ValueError(f"{field_name} must be a positive integer.")

    return value


def validate_non_negative_float(value: int | float, field_name: str) -> float:
    """Validate non-negative float."""
    numeric = validate_number(value, field_name)

    if numeric < 0:
        raise ValueError(f"{field_name} must be a non-negative number.")

    return numeric


def validate_score(value: int | float, field_name: str) -> float:
    """Validate score between 0 and 1."""
    score = validate_number(value, field_name)

    if score < 0 or score > 1:
        raise ValueError(f"{field_name} must be between 0 and 1.")

    return score


def normalize_news_symbol(symbol: str) -> str:
    """Normalize news symbol."""
    normalized = validate_non_empty_string(symbol, "Symbol").upper()

    if not normalized.replace("/", "").replace("-", "").isalnum():
        raise ValueError("Symbol must be alphanumeric and may include '/' or '-'.")

    return normalized


def normalize_news_provider_type(value: NewsProviderType | str) -> NewsProviderType:
    """Normalize news provider type."""
    if isinstance(value, NewsProviderType):
        return value

    normalized = validate_non_empty_string(value, "News provider type").lower()

    try:
        return NewsProviderType(normalized)
    except ValueError as exc:
        valid = ", ".join(item.value for item in NewsProviderType)
        raise ValueError(
            f"Invalid news provider type '{value}'. Valid types: {valid}.",
        ) from exc


def normalize_news_provider_status(value: NewsProviderStatus | str) -> NewsProviderStatus:
    """Normalize news provider status."""
    if isinstance(value, NewsProviderStatus):
        return value

    normalized = validate_non_empty_string(value, "News provider status").lower()

    try:
        return NewsProviderStatus(normalized)
    except ValueError as exc:
        valid = ", ".join(item.value for item in NewsProviderStatus)
        raise ValueError(
            f"Invalid news provider status '{value}'. Valid statuses: {valid}.",
        ) from exc


def normalize_news_provider_capability(
    value: NewsProviderCapability | str,
) -> NewsProviderCapability:
    """Normalize news provider capability."""
    if isinstance(value, NewsProviderCapability):
        return value

    normalized = validate_non_empty_string(value, "News provider capability").lower()

    try:
        return NewsProviderCapability(normalized)
    except ValueError as exc:
        valid = ", ".join(item.value for item in NewsProviderCapability)
        raise ValueError(
            f"Invalid news provider capability '{value}'. Valid capabilities: {valid}.",
        ) from exc


def normalize_news_provider_auth_type(value: NewsProviderAuthType | str) -> NewsProviderAuthType:
    """Normalize news provider auth type."""
    if isinstance(value, NewsProviderAuthType):
        return value

    normalized = validate_non_empty_string(value, "News provider auth type").lower()

    try:
        return NewsProviderAuthType(normalized)
    except ValueError as exc:
        valid = ", ".join(item.value for item in NewsProviderAuthType)
        raise ValueError(
            f"Invalid news provider auth type '{value}'. Valid auth types: {valid}.",
        ) from exc


def validate_news_provider_capabilities(
    capabilities: list[NewsProviderCapability | str],
) -> list[NewsProviderCapability | str]:
    """Validate news provider capabilities."""
    if not isinstance(capabilities, list):
        raise ValueError("Capabilities must be a list.")

    for capability in capabilities:
        normalize_news_provider_capability(capability)

    return capabilities


def validate_news_event_records(records: list[NewsEventRecord]) -> list[NewsEventRecord]:
    """Validate news event records."""
    if not isinstance(records, list):
        raise ValueError("Records must be a list.")

    for record in records:
        if not isinstance(record, NewsEventRecord):
            raise ValueError("Records must contain NewsEventRecord objects.")

    return records


def validate_news_provider_issues(
    issues: list[NewsProviderIssue],
) -> list[NewsProviderIssue]:
    """Validate news provider issues."""
    if not isinstance(issues, list):
        raise ValueError("Issues must be a list.")

    for issue in issues:
        if not isinstance(issue, NewsProviderIssue):
            raise ValueError("Issues must contain NewsProviderIssue objects.")

    return issues


def build_news_provider_credentials(
    *,
    auth_type: NewsProviderAuthType | str = NewsProviderAuthType.NONE,
    api_key: str = "",
    bearer_token: str = "",
    username: str = "",
    password: str = "",
    metadata: dict[str, Any] | None = None,
) -> NewsProviderCredentials:
    """Build news provider credentials."""
    return NewsProviderCredentials(
        auth_type=auth_type,
        api_key=api_key,
        bearer_token=bearer_token,
        username=username,
        password=password,
        metadata=metadata or {},
    )


def build_news_provider_config(
    *,
    provider_id: str,
    name: str,
    provider_type: NewsProviderType | str = NewsProviderType.UNKNOWN,
    base_url: str = "",
    status: NewsProviderStatus | str = NewsProviderStatus.INACTIVE,
    capabilities: list[NewsProviderCapability | str] | None = None,
    credentials: NewsProviderCredentials | None = None,
    timeout_seconds: int = 30,
    rate_limit_per_minute: int = 0,
    metadata: dict[str, Any] | None = None,
) -> NewsProviderConfig:
    """Build news provider config."""
    return NewsProviderConfig(
        provider_id=provider_id,
        name=name,
        provider_type=provider_type,
        base_url=base_url,
        status=status,
        capabilities=capabilities or [],
        credentials=credentials or NewsProviderCredentials(),
        timeout_seconds=timeout_seconds,
        rate_limit_per_minute=rate_limit_per_minute,
        metadata=metadata or {},
    )


def build_news_provider_health(
    *,
    provider_id: str,
    status: NewsProviderStatus | str = NewsProviderStatus.UNKNOWN,
    connected: bool = False,
    message: str = "",
    latency_ms: float = 0.0,
    checked_at: str | None = None,
    metadata: dict[str, Any] | None = None,
) -> NewsProviderHealth:
    """Build news provider health."""
    health_kwargs: dict[str, Any] = {
        "provider_id": provider_id,
        "status": status,
        "connected": connected,
        "message": message,
        "latency_ms": latency_ms,
        "metadata": metadata or {},
    }

    if checked_at is not None:
        health_kwargs["checked_at"] = checked_at

    return NewsProviderHealth(**health_kwargs)


def build_news_provider_issue(
    *,
    code: str,
    message: str,
    provider_id: str = "",
    status: NewsProviderStatus | str = NewsProviderStatus.ERROR,
    metadata: dict[str, Any] | None = None,
) -> NewsProviderIssue:
    """Build news provider issue."""
    return NewsProviderIssue(
        code=code,
        message=message,
        provider_id=provider_id,
        status=status,
        metadata=metadata or {},
    )


def build_news_event_record(
    *,
    event_id: str,
    timestamp: str,
    title: str,
    event_type: HistoricalEventType | str = HistoricalEventType.UNKNOWN,
    symbol: str = "",
    impact: HistoricalEventImpact | str = HistoricalEventImpact.UNKNOWN,
    sentiment: HistoricalEventSentiment | str = HistoricalEventSentiment.UNKNOWN,
    source: str = "",
    provider_id: str = "",
    url: str = "",
    description: str = "",
    country: str = "",
    currency: str = "",
    relevance_score: float = 0.0,
    raw_payload: dict[str, Any] | None = None,
    metadata: dict[str, Any] | None = None,
) -> NewsEventRecord:
    """Build news event record."""
    return NewsEventRecord(
        event_id=event_id,
        timestamp=timestamp,
        title=title,
        event_type=event_type,
        symbol=symbol,
        impact=impact,
        sentiment=sentiment,
        source=source,
        provider_id=provider_id,
        url=url,
        description=description,
        country=country,
        currency=currency,
        relevance_score=relevance_score,
        raw_payload=raw_payload or {},
        metadata=metadata or {},
    )


def build_news_provider_result(
    *,
    success: bool,
    records: list[NewsEventRecord] | None = None,
    message: str = "",
    provider_id: str = "",
    issues: list[NewsProviderIssue] | None = None,
    metadata: dict[str, Any] | None = None,
) -> NewsProviderResult:
    """Build news provider result."""
    return NewsProviderResult(
        success=success,
        records=records or [],
        message=message,
        provider_id=provider_id,
        issues=issues or [],
        metadata=metadata or {},
    )


def news_provider_success(
    *,
    records: list[NewsEventRecord] | None = None,
    message: str = "",
    provider_id: str = "",
    metadata: dict[str, Any] | None = None,
) -> NewsProviderResult:
    """Build successful news provider result."""
    return build_news_provider_result(
        success=True,
        records=records or [],
        message=message,
        provider_id=provider_id,
        metadata=metadata or {},
    )


def news_provider_failure(
    *,
    message: str,
    code: str = "news_provider_error",
    provider_id: str = "",
    metadata: dict[str, Any] | None = None,
) -> NewsProviderResult:
    """Build failed news provider result."""
    issue = build_news_provider_issue(
        code=code,
        message=message,
        provider_id=provider_id,
        status=NewsProviderStatus.ERROR,
    )

    return build_news_provider_result(
        success=False,
        message=message,
        provider_id=provider_id,
        issues=[issue],
        metadata=metadata or {},
    )