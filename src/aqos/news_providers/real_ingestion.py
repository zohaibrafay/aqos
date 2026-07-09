"""
AQOS real live news ingestion runner.

This module executes named AQOS live connectors through the connector registry.
It supports payload-based tests, mocked fetchers, and real HTTP execution when
credentials and network access are available.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable

from aqos.news_providers.base import (
    NewsProviderCredentials,
    NewsProviderResult,
    build_news_provider_issue,
    validate_metadata,
    validate_non_empty_string,
    validate_string,
)
from aqos.news_providers.connector_registry import (
    NewsConnectorRegistry,
    NewsConnectorSelectionRequest,
    build_default_news_connector_registry,
    build_news_connector_selection_request,
    select_live_news_connectors,
)
from aqos.news_providers.cryptopanic_connector import (
    CryptoPanicNewsQuery,
    build_cryptopanic_news_query,
    load_cryptopanic_news_provider_result,
)
from aqos.news_providers.finnhub_connector import (
    FinnhubNewsQuery,
    build_finnhub_news_query,
    load_finnhub_news_provider_result,
)
from aqos.news_providers.gdelt_connector import (
    GdeltNewsQuery,
    build_gdelt_news_query,
    load_gdelt_news_provider_result,
)
from aqos.news_providers.hackernews_connector import (
    HackerNewsQuery,
    build_hackernews_query,
    load_hackernews_news_provider_result,
)
from aqos.news_providers.http_provider import HttpNewsFetcher
from aqos.news_providers.newsapi_connector import (
    ApiNewsConnectorKind,
    ApiNewsQuery,
    build_api_news_query,
    load_api_news_provider_result,
)
from aqos.news_providers.trading_economics_connector import (
    TradingEconomicsMacroQuery,
    build_trading_economics_macro_query,
    load_trading_economics_news_provider_result,
)


class LiveIngestionExecutionStatus(str, Enum):
    """Supported live ingestion execution statuses."""

    SUCCESS = "success"
    PARTIAL = "partial"
    FAILED = "failed"
    EMPTY = "empty"


@dataclass(frozen=True)
class LiveConnectorIngestionRequest:
    """Request for one live connector ingestion run."""

    connector_id: str
    query: Any = None
    credentials: NewsProviderCredentials = field(default_factory=NewsProviderCredentials)
    payload: dict[str, Any] | list[dict[str, Any]] | None = None
    fetcher: HttpNewsFetcher | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        validate_non_empty_string(self.connector_id, "Connector ID")

        if not isinstance(self.credentials, NewsProviderCredentials):
            raise ValueError("Credentials must be NewsProviderCredentials.")

        if self.payload is not None and not isinstance(self.payload, dict | list):
            raise ValueError("Payload must be a dictionary, list, or None.")

        if self.fetcher is not None and not callable(self.fetcher):
            raise ValueError("Fetcher must be callable.")

        validate_metadata(self.metadata, "Metadata")

    def to_dict(self) -> dict[str, Any]:
        """Convert ingestion request to dictionary."""
        return {
            "connector_id": self.connector_id.strip().lower(),
            "query_type": type(self.query).__name__ if self.query is not None else "",
            "has_credentials": bool(self.credentials.api_key.strip()),
            "has_payload": self.payload is not None,
            "has_fetcher": self.fetcher is not None,
            "metadata": dict(self.metadata),
        }


@dataclass(frozen=True)
class LiveConnectorIngestionResult:
    """Result for one live connector ingestion run."""

    connector_id: str
    success: bool
    provider_result: NewsProviderResult
    message: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        validate_non_empty_string(self.connector_id, "Connector ID")

        if not isinstance(self.success, bool):
            raise ValueError("Success must be a boolean.")

        if not isinstance(self.provider_result, NewsProviderResult):
            raise ValueError("Provider result must be NewsProviderResult.")

        validate_string(self.message, "Message")
        validate_metadata(self.metadata, "Metadata")

    @property
    def record_count(self) -> int:
        """Return provider result record count."""
        return self.provider_result.record_count

    def to_dict(self) -> dict[str, Any]:
        """Convert result to dictionary."""
        return {
            "connector_id": self.connector_id.strip().lower(),
            "success": self.success,
            "record_count": self.record_count,
            "message": self.message.strip(),
            "provider_result": self.provider_result.to_dict(),
            "metadata": dict(self.metadata),
        }


@dataclass(frozen=True)
class LiveIngestionBatchResult:
    """Batch result for live connector ingestion."""

    status: LiveIngestionExecutionStatus | str
    results: list[LiveConnectorIngestionResult] = field(default_factory=list)
    message: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        normalize_live_ingestion_execution_status(self.status)
        validate_live_connector_ingestion_results(self.results)
        validate_string(self.message, "Message")
        validate_metadata(self.metadata, "Metadata")

    @property
    def connector_count(self) -> int:
        """Return connector result count."""
        return len(self.results)

    @property
    def success_count(self) -> int:
        """Return successful connector count."""
        return sum(1 for result in self.results if result.success)

    @property
    def failed_count(self) -> int:
        """Return failed connector count."""
        return sum(1 for result in self.results if not result.success)

    @property
    def total_record_count(self) -> int:
        """Return total record count."""
        return sum(result.record_count for result in self.results)

    @property
    def success(self) -> bool:
        """Return whether batch has at least one successful result."""
        return self.success_count > 0

    def to_dict(self) -> dict[str, Any]:
        """Convert batch result to dictionary."""
        return {
            "status": normalize_live_ingestion_execution_status(self.status).value,
            "success": self.success,
            "connector_count": self.connector_count,
            "success_count": self.success_count,
            "failed_count": self.failed_count,
            "total_record_count": self.total_record_count,
            "connector_ids": [result.connector_id for result in self.results],
            "results": [result.to_dict() for result in self.results],
            "message": self.message.strip(),
            "metadata": dict(self.metadata),
        }


def normalize_live_ingestion_execution_status(
    value: LiveIngestionExecutionStatus | str,
) -> LiveIngestionExecutionStatus:
    """Normalize live ingestion execution status."""
    if isinstance(value, LiveIngestionExecutionStatus):
        return value

    normalized = validate_non_empty_string(value, "Live ingestion execution status").lower()

    try:
        return LiveIngestionExecutionStatus(normalized)
    except ValueError as exc:
        valid = ", ".join(item.value for item in LiveIngestionExecutionStatus)
        raise ValueError(
            f"Invalid live ingestion execution status '{value}'. Valid statuses: {valid}.",
        ) from exc


def validate_live_connector_ingestion_results(
    results: list[LiveConnectorIngestionResult],
) -> list[LiveConnectorIngestionResult]:
    """Validate connector ingestion results."""
    if not isinstance(results, list):
        raise ValueError("Results must be a list.")

    for result in results:
        if not isinstance(result, LiveConnectorIngestionResult):
            raise ValueError("Result must be LiveConnectorIngestionResult.")

    return results


def build_live_connector_ingestion_request(
    *,
    connector_id: str,
    query: Any = None,
    credentials: NewsProviderCredentials | None = None,
    payload: dict[str, Any] | list[dict[str, Any]] | None = None,
    fetcher: HttpNewsFetcher | None = None,
    metadata: dict[str, Any] | None = None,
) -> LiveConnectorIngestionRequest:
    """Build live connector ingestion request."""
    return LiveConnectorIngestionRequest(
        connector_id=connector_id,
        query=query,
        credentials=credentials or NewsProviderCredentials(),
        payload=payload,
        fetcher=fetcher,
        metadata=metadata or {},
    )


def build_live_connector_ingestion_result(
    *,
    connector_id: str,
    success: bool,
    provider_result: NewsProviderResult,
    message: str = "",
    metadata: dict[str, Any] | None = None,
) -> LiveConnectorIngestionResult:
    """Build live connector ingestion result."""
    return LiveConnectorIngestionResult(
        connector_id=connector_id,
        success=success,
        provider_result=provider_result,
        message=message,
        metadata=metadata or {},
    )


def build_live_ingestion_batch_result(
    *,
    results: list[LiveConnectorIngestionResult] | None = None,
    message: str = "",
    metadata: dict[str, Any] | None = None,
) -> LiveIngestionBatchResult:
    """Build live ingestion batch result."""
    resolved_results = results or []
    status = infer_live_ingestion_execution_status(resolved_results)

    return LiveIngestionBatchResult(
        status=status,
        results=resolved_results,
        message=message,
        metadata=metadata or {},
    )


def infer_live_ingestion_execution_status(
    results: list[LiveConnectorIngestionResult],
) -> LiveIngestionExecutionStatus:
    """Infer batch execution status."""
    validate_live_connector_ingestion_results(results)

    if not results:
        return LiveIngestionExecutionStatus.EMPTY

    success_count = sum(1 for result in results if result.success)

    if success_count == len(results):
        return LiveIngestionExecutionStatus.SUCCESS

    if success_count > 0:
        return LiveIngestionExecutionStatus.PARTIAL

    return LiveIngestionExecutionStatus.FAILED


def build_default_query_for_live_connector(connector_id: str) -> Any:
    """Build default query object for a connector."""
    normalized = validate_non_empty_string(connector_id, "Connector ID").lower()

    if normalized == "gdelt":
        return build_gdelt_news_query(query_terms=["gold"], max_records=5)

    if normalized == "hacker_news":
        return build_hackernews_query(query_terms=["inflation", "markets"], hits_per_page=5)

    if normalized == "news_api":
        return build_api_news_query(query_terms=["gold", "inflation"], page_size=5)

    if normalized == "marketaux":
        return build_api_news_query(query_terms=["markets"], symbol="XAUUSD", page_size=5)

    if normalized == "finnhub":
        return build_finnhub_news_query(category="general", max_records=5)

    if normalized == "trading_economics":
        return build_trading_economics_macro_query(
            countries=["United States"],
            indicators=["Inflation Rate"],
            limit=5,
        )

    if normalized == "cryptopanic":
        return build_cryptopanic_news_query(currencies=["BTC"], page=1)

    raise ValueError(f"Unsupported live connector ID '{connector_id}'.")


def execute_live_connector_ingestion_request(
    request: LiveConnectorIngestionRequest,
) -> LiveConnectorIngestionResult:
    """Execute one live connector ingestion request."""
    if not isinstance(request, LiveConnectorIngestionRequest):
        raise ValueError("Request must be LiveConnectorIngestionRequest.")

    connector_id = request.connector_id.strip().lower()

    try:
        query = request.query or build_default_query_for_live_connector(connector_id)

        provider_result = dispatch_live_connector_loader(
            connector_id=connector_id,
            query=query,
            credentials=request.credentials,
            payload=request.payload,
            fetcher=request.fetcher,
        )

        return build_live_connector_ingestion_result(
            connector_id=connector_id,
            success=provider_result.success,
            provider_result=provider_result,
            message=provider_result.message,
            metadata={
                **request.metadata,
                "record_count": provider_result.record_count,
            },
        )
    except Exception as exc:
        failure_result = NewsProviderResult(
            success=False,
            records=[],
            message=str(exc),
            provider_id=connector_id,
            issues=[
                build_news_provider_issue(
                    code="live_connector_ingestion_failed",
                    message=str(exc),
                    provider_id=connector_id,
                ),
            ],
            metadata={},
        )

        return build_live_connector_ingestion_result(
            connector_id=connector_id,
            success=False,
            provider_result=failure_result,
            message=str(exc),
            metadata=dict(request.metadata),
        )


def dispatch_live_connector_loader(
    *,
    connector_id: str,
    query: Any,
    credentials: NewsProviderCredentials | None = None,
    payload: dict[str, Any] | list[dict[str, Any]] | None = None,
    fetcher: HttpNewsFetcher | None = None,
) -> NewsProviderResult:
    """Dispatch connector-specific provider loader."""
    normalized = validate_non_empty_string(connector_id, "Connector ID").lower()
    resolved_credentials = credentials or NewsProviderCredentials()

    if normalized == "gdelt":
        if not isinstance(query, GdeltNewsQuery):
            raise ValueError("GDELT query must be GdeltNewsQuery.")

        return load_gdelt_news_provider_result(
            query=query,
            payload=payload,
            fetcher=fetcher,
        )

    if normalized == "hacker_news":
        if not isinstance(query, HackerNewsQuery):
            raise ValueError("Hacker News query must be HackerNewsQuery.")

        return load_hackernews_news_provider_result(
            query=query,
            payload=payload,
            fetcher=fetcher,
        )

    if normalized == "news_api":
        if not isinstance(query, ApiNewsQuery):
            raise ValueError("NewsAPI query must be ApiNewsQuery.")

        return load_api_news_provider_result(
            connector_kind=ApiNewsConnectorKind.NEWS_API,
            query=query,
            credentials=resolved_credentials,
            payload=payload,
            fetcher=fetcher,
        )

    if normalized == "marketaux":
        if not isinstance(query, ApiNewsQuery):
            raise ValueError("MarketAux query must be ApiNewsQuery.")

        return load_api_news_provider_result(
            connector_kind=ApiNewsConnectorKind.MARKETAUX,
            query=query,
            credentials=resolved_credentials,
            payload=payload,
            fetcher=fetcher,
        )

    if normalized == "finnhub":
        if not isinstance(query, FinnhubNewsQuery):
            raise ValueError("Finnhub query must be FinnhubNewsQuery.")

        return load_finnhub_news_provider_result(
            query=query,
            credentials=resolved_credentials,
            payload=payload,
            fetcher=fetcher,
        )

    if normalized == "trading_economics":
        if not isinstance(query, TradingEconomicsMacroQuery):
            raise ValueError("Trading Economics query must be TradingEconomicsMacroQuery.")

        return load_trading_economics_news_provider_result(
            query=query,
            credentials=resolved_credentials,
            payload=payload,
            fetcher=fetcher,
        )

    if normalized == "cryptopanic":
        if not isinstance(query, CryptoPanicNewsQuery):
            raise ValueError("CryptoPanic query must be CryptoPanicNewsQuery.")

        return load_cryptopanic_news_provider_result(
            query=query,
            credentials=resolved_credentials,
            payload=payload,
            fetcher=fetcher,
        )

    raise ValueError(f"Unsupported live connector ID '{connector_id}'.")


def build_ingestion_requests_from_selection(
    registry: NewsConnectorRegistry,
    selection_request: NewsConnectorSelectionRequest | None = None,
    *,
    credentials_by_connector_id: dict[str, NewsProviderCredentials] | None = None,
    payloads_by_connector_id: dict[str, dict[str, Any] | list[dict[str, Any]]] | None = None,
    fetchers_by_connector_id: dict[str, HttpNewsFetcher] | None = None,
    query_factory_by_connector_id: dict[str, Callable[[], Any]] | None = None,
) -> list[LiveConnectorIngestionRequest]:
    """Build ingestion requests from registry selection."""
    if not isinstance(registry, NewsConnectorRegistry):
        raise ValueError("Registry must be NewsConnectorRegistry.")

    selection_result = select_live_news_connectors(
        registry,
        selection_request or build_news_connector_selection_request(),
    )

    credentials_map = credentials_by_connector_id or {}
    payload_map = payloads_by_connector_id or {}
    fetcher_map = fetchers_by_connector_id or {}
    query_factory_map = query_factory_by_connector_id or {}

    requests = []

    for entry in selection_result.entries:
        connector_id = entry.connector_id.value
        query_factory = query_factory_map.get(connector_id)
        query = query_factory() if query_factory is not None else build_default_query_for_live_connector(connector_id)

        requests.append(
            build_live_connector_ingestion_request(
                connector_id=connector_id,
                query=query,
                credentials=credentials_map.get(connector_id, NewsProviderCredentials()),
                payload=payload_map.get(connector_id),
                fetcher=fetcher_map.get(connector_id),
                metadata={
                    "registry_priority": entry.priority,
                    "registry_category": entry.category.value,
                },
            ),
        )

    return requests


def run_live_news_ingestion(
    *,
    registry: NewsConnectorRegistry | None = None,
    selection_request: NewsConnectorSelectionRequest | None = None,
    requests: list[LiveConnectorIngestionRequest] | None = None,
    credentials_by_connector_id: dict[str, NewsProviderCredentials] | None = None,
    payloads_by_connector_id: dict[str, dict[str, Any] | list[dict[str, Any]]] | None = None,
    fetchers_by_connector_id: dict[str, HttpNewsFetcher] | None = None,
    query_factory_by_connector_id: dict[str, Callable[[], Any]] | None = None,
    metadata: dict[str, Any] | None = None,
) -> LiveIngestionBatchResult:
    """Run live news ingestion for selected connectors."""
    resolved_registry = registry or build_default_news_connector_registry()

    if not isinstance(resolved_registry, NewsConnectorRegistry):
        raise ValueError("Registry must be NewsConnectorRegistry.")

    if requests is not None:
        if not isinstance(requests, list):
            raise ValueError("Requests must be a list.")

        for request in requests:
            if not isinstance(request, LiveConnectorIngestionRequest):
                raise ValueError("Request must be LiveConnectorIngestionRequest.")

        resolved_requests = requests
    else:
        resolved_requests = build_ingestion_requests_from_selection(
            resolved_registry,
            selection_request,
            credentials_by_connector_id=credentials_by_connector_id,
            payloads_by_connector_id=payloads_by_connector_id,
            fetchers_by_connector_id=fetchers_by_connector_id,
            query_factory_by_connector_id=query_factory_by_connector_id,
        )

    results = [
        execute_live_connector_ingestion_request(request)
        for request in resolved_requests
    ]

    return build_live_ingestion_batch_result(
        results=results,
        message="Live news ingestion completed.",
        metadata={
            **(metadata or {}),
            "registry_connector_count": resolved_registry.connector_count,
        },
    )