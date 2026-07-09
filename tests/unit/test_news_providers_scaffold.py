"""
Unit tests for AQOS news providers package scaffold.
"""

import pytest

from aqos.news_providers import (
    NewsEventRecord,
    NewsProviderAuthType,
    NewsProviderCapability,
    NewsProviderConfig,
    NewsProviderCredentials,
    NewsProviderHealth,
    NewsProviderIssue,
    NewsProviderResult,
    NewsProviderStatus,
    NewsProviderType,
    build_news_event_record,
    build_news_provider_config,
    build_news_provider_credentials,
    build_news_provider_health,
    build_news_provider_issue,
    build_news_provider_result,
    news_provider_failure,
    news_provider_success,
    normalize_news_provider_auth_type,
    normalize_news_provider_capability,
    normalize_news_provider_status,
    normalize_news_provider_type,
    normalize_news_symbol,
    validate_metadata,
    validate_news_event_records,
    validate_news_provider_capabilities,
    validate_news_provider_issues,
    validate_non_empty_string,
    validate_non_negative_float,
    validate_non_negative_integer,
    validate_number,
    validate_positive_integer,
    validate_score,
    validate_string,
)


def test_news_provider_enum_values():
    assert NewsProviderType.ECONOMIC_CALENDAR.value == "economic_calendar"
    assert NewsProviderType.NEWS_FEED.value == "news_feed"
    assert NewsProviderType.SENTIMENT.value == "sentiment"
    assert NewsProviderType.RSS.value == "rss"
    assert NewsProviderType.LOCAL_JSON.value == "local_json"
    assert NewsProviderType.HTTP.value == "http"
    assert NewsProviderType.AGGREGATOR.value == "aggregator"
    assert NewsProviderType.UNKNOWN.value == "unknown"

    assert NewsProviderStatus.ACTIVE.value == "active"
    assert NewsProviderStatus.INACTIVE.value == "inactive"
    assert NewsProviderStatus.DEGRADED.value == "degraded"
    assert NewsProviderStatus.ERROR.value == "error"
    assert NewsProviderStatus.UNKNOWN.value == "unknown"

    assert NewsProviderCapability.HISTORICAL_NEWS.value == "historical_news"
    assert NewsProviderCapability.LIVE_NEWS.value == "live_news"
    assert NewsProviderCapability.ECONOMIC_CALENDAR.value == "economic_calendar"
    assert NewsProviderCapability.MACRO_EVENTS.value == "macro_events"
    assert NewsProviderCapability.SENTIMENT.value == "sentiment"
    assert NewsProviderCapability.IMPACT_CLASSIFICATION.value == "impact_classification"
    assert NewsProviderCapability.SYMBOL_MAPPING.value == "symbol_mapping"
    assert NewsProviderCapability.COUNTRY_FILTERING.value == "country_filtering"
    assert NewsProviderCapability.CURRENCY_FILTERING.value == "currency_filtering"
    assert NewsProviderCapability.KEYWORD_FILTERING.value == "keyword_filtering"

    assert NewsProviderAuthType.NONE.value == "none"
    assert NewsProviderAuthType.API_KEY.value == "api_key"
    assert NewsProviderAuthType.BEARER_TOKEN.value == "bearer_token"
    assert NewsProviderAuthType.BASIC.value == "basic"
    assert NewsProviderAuthType.OAUTH.value == "oauth"


def test_news_provider_normalizers():
    assert normalize_news_provider_type(NewsProviderType.HTTP) == NewsProviderType.HTTP
    assert normalize_news_provider_type(" RSS ") == NewsProviderType.RSS
    assert normalize_news_provider_status(NewsProviderStatus.ACTIVE) == NewsProviderStatus.ACTIVE
    assert normalize_news_provider_status(" DEGRADED ") == NewsProviderStatus.DEGRADED
    assert normalize_news_provider_capability(NewsProviderCapability.LIVE_NEWS) == NewsProviderCapability.LIVE_NEWS
    assert normalize_news_provider_capability(" SENTIMENT ") == NewsProviderCapability.SENTIMENT
    assert normalize_news_provider_auth_type(NewsProviderAuthType.API_KEY) == NewsProviderAuthType.API_KEY
    assert normalize_news_provider_auth_type(" BASIC ") == NewsProviderAuthType.BASIC

    with pytest.raises(ValueError):
        normalize_news_provider_type("bad")

    with pytest.raises(ValueError):
        normalize_news_provider_status("bad")

    with pytest.raises(ValueError):
        normalize_news_provider_capability("bad")

    with pytest.raises(ValueError):
        normalize_news_provider_auth_type("bad")


def test_news_symbol_normalizer():
    assert normalize_news_symbol(" xauusd ") == "XAUUSD"
    assert normalize_news_symbol("btc/usdt") == "BTC/USDT"
    assert normalize_news_symbol("eth-usdt") == "ETH-USDT"

    with pytest.raises(ValueError):
        normalize_news_symbol("")

    with pytest.raises(ValueError):
        normalize_news_symbol("bad symbol")

    with pytest.raises(ValueError):
        normalize_news_symbol("bad_symbol")


def test_base_validators():
    assert validate_string("", "Field") == ""
    assert validate_string("value", "Field") == "value"
    assert validate_non_empty_string(" value ", "Field") == "value"
    assert validate_metadata({"a": 1}) == {"a": 1}
    assert validate_number(1, "Value") == 1.0
    assert validate_non_negative_integer(0, "Count") == 0
    assert validate_positive_integer(1, "Count") == 1
    assert validate_non_negative_float(0.5, "Value") == 0.5
    assert validate_score(0.5, "Score") == 0.5
    assert validate_news_provider_capabilities(["live_news", NewsProviderCapability.SENTIMENT]) == [
        "live_news",
        NewsProviderCapability.SENTIMENT,
    ]

    with pytest.raises(ValueError):
        validate_string(123, "Field")

    with pytest.raises(ValueError):
        validate_non_empty_string("", "Field")

    with pytest.raises(ValueError):
        validate_metadata([])

    with pytest.raises(ValueError):
        validate_number(True, "Value")

    with pytest.raises(ValueError):
        validate_number("1", "Value")

    with pytest.raises(ValueError):
        validate_non_negative_integer(-1, "Count")

    with pytest.raises(ValueError):
        validate_positive_integer(0, "Count")

    with pytest.raises(ValueError):
        validate_non_negative_float(-1, "Value")

    with pytest.raises(ValueError):
        validate_score(1.1, "Score")

    with pytest.raises(ValueError):
        validate_news_provider_capabilities("bad")

    with pytest.raises(ValueError):
        validate_news_provider_capabilities(["bad"])


def test_news_provider_credentials_to_safe_dict():
    credentials = NewsProviderCredentials(
        auth_type=" api_key ",
        api_key="secret",
        metadata={"source": "test"},
    )

    payload = credentials.to_safe_dict()

    assert credentials.requires_secret is True
    assert credentials.configured is True
    assert payload == {
        "auth_type": "api_key",
        "requires_secret": True,
        "configured": True,
        "has_api_key": True,
        "has_bearer_token": False,
        "has_username": False,
        "metadata": {"source": "test"},
    }


def test_news_provider_credentials_builder_and_rejections():
    none_credentials = build_news_provider_credentials()
    bearer_credentials = build_news_provider_credentials(
        auth_type="bearer_token",
        bearer_token="token",
    )
    basic_credentials = build_news_provider_credentials(
        auth_type="basic",
        username="user",
        password="pass",
    )

    assert isinstance(none_credentials, NewsProviderCredentials)
    assert none_credentials.configured is True
    assert bearer_credentials.configured is True
    assert basic_credentials.configured is True

    with pytest.raises(ValueError):
        NewsProviderCredentials(auth_type="bad")

    with pytest.raises(ValueError):
        NewsProviderCredentials(api_key=123)

    with pytest.raises(ValueError):
        NewsProviderCredentials(metadata=[])


def test_news_provider_config_to_dict():
    credentials = build_news_provider_credentials(
        auth_type="api_key",
        api_key="secret",
    )
    config = NewsProviderConfig(
        provider_id=" news-api ",
        name=" News API ",
        provider_type=" http ",
        base_url=" https://example.com ",
        status=" active ",
        capabilities=["live_news", "sentiment"],
        credentials=credentials,
        timeout_seconds=20,
        rate_limit_per_minute=60,
        metadata={"tier": "test"},
    )

    payload = config.to_dict()

    assert config.active is True
    assert config.capability_count == 2
    assert config.has_capability("sentiment") is True
    assert payload["provider_id"] == "news-api"
    assert payload["name"] == "News API"
    assert payload["provider_type"] == "http"
    assert payload["base_url"] == "https://example.com"
    assert payload["status"] == "active"
    assert payload["capabilities"] == ["live_news", "sentiment"]
    assert payload["timeout_seconds"] == 20
    assert payload["rate_limit_per_minute"] == 60


def test_news_provider_config_builder_and_rejections():
    config = build_news_provider_config(
        provider_id="rss",
        name="RSS Provider",
        provider_type="rss",
        capabilities=["live_news"],
    )

    assert isinstance(config, NewsProviderConfig)

    with pytest.raises(ValueError):
        NewsProviderConfig(provider_id="", name="Provider")

    with pytest.raises(ValueError):
        NewsProviderConfig(provider_id="provider", name="")

    with pytest.raises(ValueError):
        NewsProviderConfig(provider_id="provider", name="Provider", provider_type="bad")

    with pytest.raises(ValueError):
        NewsProviderConfig(provider_id="provider", name="Provider", base_url=123)

    with pytest.raises(ValueError):
        NewsProviderConfig(provider_id="provider", name="Provider", status="bad")

    with pytest.raises(ValueError):
        NewsProviderConfig(provider_id="provider", name="Provider", capabilities="bad")

    with pytest.raises(ValueError):
        NewsProviderConfig(provider_id="provider", name="Provider", credentials="bad")

    with pytest.raises(ValueError):
        NewsProviderConfig(provider_id="provider", name="Provider", timeout_seconds=0)

    with pytest.raises(ValueError):
        NewsProviderConfig(provider_id="provider", name="Provider", rate_limit_per_minute=-1)

    with pytest.raises(ValueError):
        NewsProviderConfig(provider_id="provider", name="Provider", metadata=[])


def test_news_provider_health_to_dict():
    health = NewsProviderHealth(
        provider_id=" provider ",
        status=" active ",
        connected=True,
        message=" OK ",
        latency_ms=12.5,
        checked_at="2026-01-01T00:00:00+00:00",
        metadata={"source": "test"},
    )

    payload = health.to_dict()

    assert health.healthy is True
    assert payload == {
        "provider_id": "provider",
        "status": "active",
        "connected": True,
        "healthy": True,
        "message": "OK",
        "latency_ms": 12.5,
        "checked_at": "2026-01-01T00:00:00+00:00",
        "metadata": {"source": "test"},
    }


def test_news_provider_health_builder_and_rejections():
    health = build_news_provider_health(
        provider_id="provider",
        status="active",
        connected=True,
        checked_at="2026-01-01T00:00:00+00:00",
    )

    assert isinstance(health, NewsProviderHealth)
    assert health.healthy is True

    with pytest.raises(ValueError):
        NewsProviderHealth(provider_id="")

    with pytest.raises(ValueError):
        NewsProviderHealth(provider_id="provider", status="bad")

    with pytest.raises(ValueError):
        NewsProviderHealth(provider_id="provider", connected="yes")

    with pytest.raises(ValueError):
        NewsProviderHealth(provider_id="provider", message=123)

    with pytest.raises(ValueError):
        NewsProviderHealth(provider_id="provider", latency_ms=-1)

    with pytest.raises(ValueError):
        NewsProviderHealth(provider_id="provider", checked_at="")

    with pytest.raises(ValueError):
        NewsProviderHealth(provider_id="provider", metadata=[])


def test_news_provider_issue_to_dict():
    issue = NewsProviderIssue(
        code=" provider_error ",
        message=" Provider failed ",
        provider_id=" provider ",
        status=" error ",
        metadata={"source": "test"},
    )

    payload = issue.to_dict()

    assert payload == {
        "code": "provider_error",
        "message": "Provider failed",
        "provider_id": "provider",
        "status": "error",
        "metadata": {"source": "test"},
    }


def test_news_provider_issue_builder_and_rejections():
    issue = build_news_provider_issue(
        code="issue",
        message="Issue",
        provider_id="provider",
    )

    assert isinstance(issue, NewsProviderIssue)

    with pytest.raises(ValueError):
        NewsProviderIssue(code="", message="Message")

    with pytest.raises(ValueError):
        NewsProviderIssue(code="code", message="")

    with pytest.raises(ValueError):
        NewsProviderIssue(code="code", message="Message", provider_id=123)

    with pytest.raises(ValueError):
        NewsProviderIssue(code="code", message="Message", status="bad")

    with pytest.raises(ValueError):
        NewsProviderIssue(code="code", message="Message", metadata=[])


def test_news_event_record_to_dict():
    record = NewsEventRecord(
        event_id=" event-001 ",
        timestamp=" 2026-01-01T00:00:00+00:00 ",
        title=" Gold CPI reaction ",
        event_type=" news ",
        symbol=" xauusd ",
        impact=" high ",
        sentiment=" bearish ",
        source=" Reuters ",
        provider_id=" provider ",
        url=" https://example.com/news ",
        description=" Hot CPI pressured gold. ",
        country=" us ",
        currency=" usd ",
        relevance_score=0.95,
        raw_payload={"id": 1},
        metadata={"source": "test"},
    )

    payload = record.to_dict()

    assert record.high_impact is True
    assert record.directional is True
    assert payload["event_id"] == "event-001"
    assert payload["timestamp"] == "2026-01-01T00:00:00+00:00"
    assert payload["title"] == "Gold CPI reaction"
    assert payload["event_type"] == "news"
    assert payload["symbol"] == "XAUUSD"
    assert payload["impact"] == "high"
    assert payload["sentiment"] == "bearish"
    assert payload["country"] == "US"
    assert payload["currency"] == "USD"
    assert payload["relevance_score"] == 0.95


def test_news_event_record_builder_and_rejections():
    record = build_news_event_record(
        event_id="event",
        timestamp="2026-01-01",
        title="News",
        symbol="XAUUSD",
    )

    assert isinstance(record, NewsEventRecord)

    with pytest.raises(ValueError):
        NewsEventRecord(event_id="", timestamp="t", title="Title")

    with pytest.raises(ValueError):
        NewsEventRecord(event_id="id", timestamp="", title="Title")

    with pytest.raises(ValueError):
        NewsEventRecord(event_id="id", timestamp="t", title="")

    with pytest.raises(ValueError):
        NewsEventRecord(event_id="id", timestamp="t", title="Title", event_type="bad")

    with pytest.raises(ValueError):
        NewsEventRecord(event_id="id", timestamp="t", title="Title", symbol="bad symbol")

    with pytest.raises(ValueError):
        NewsEventRecord(event_id="id", timestamp="t", title="Title", impact="bad")

    with pytest.raises(ValueError):
        NewsEventRecord(event_id="id", timestamp="t", title="Title", sentiment="bad")

    with pytest.raises(ValueError):
        NewsEventRecord(event_id="id", timestamp="t", title="Title", source=123)

    with pytest.raises(ValueError):
        NewsEventRecord(event_id="id", timestamp="t", title="Title", relevance_score=2)

    with pytest.raises(ValueError):
        NewsEventRecord(event_id="id", timestamp="t", title="Title", raw_payload=[])

    with pytest.raises(ValueError):
        NewsEventRecord(event_id="id", timestamp="t", title="Title", metadata=[])


def test_news_provider_result_to_dict():
    record = build_news_event_record(
        event_id="event",
        timestamp="2026-01-01",
        title="News",
        provider_id="provider",
    )
    issue = build_news_provider_issue(
        code="warning",
        message="Warning",
        provider_id="provider",
        status="degraded",
    )
    result = NewsProviderResult(
        success=True,
        records=[record],
        message=" OK ",
        provider_id=" provider ",
        issues=[issue],
        metadata={"source": "test"},
    )

    payload = result.to_dict()

    assert result.failed is False
    assert result.record_count == 1
    assert result.issue_count == 1
    assert payload["success"] is True
    assert payload["failed"] is False
    assert payload["record_count"] == 1
    assert payload["issue_count"] == 1


def test_news_provider_result_builders_and_rejections():
    record = build_news_event_record(
        event_id="event",
        timestamp="2026-01-01",
        title="News",
    )
    success = news_provider_success(
        records=[record],
        provider_id="provider",
    )
    failure = news_provider_failure(
        message="Failed.",
        code="failed",
        provider_id="provider",
    )
    custom = build_news_provider_result(
        success=True,
        records=[record],
    )

    assert isinstance(success, NewsProviderResult)
    assert success.record_count == 1
    assert failure.failed is True
    assert failure.issue_count == 1
    assert failure.issues[0].code == "failed"
    assert isinstance(custom, NewsProviderResult)

    with pytest.raises(ValueError):
        NewsProviderResult(success="yes")

    with pytest.raises(ValueError):
        NewsProviderResult(success=True, records="bad")

    with pytest.raises(ValueError):
        NewsProviderResult(success=True, records=["bad"])

    with pytest.raises(ValueError):
        NewsProviderResult(success=True, message=123)

    with pytest.raises(ValueError):
        NewsProviderResult(success=True, provider_id=123)

    with pytest.raises(ValueError):
        NewsProviderResult(success=True, issues="bad")

    with pytest.raises(ValueError):
        NewsProviderResult(success=True, issues=["bad"])

    with pytest.raises(ValueError):
        NewsProviderResult(success=True, metadata=[])

    assert validate_news_event_records([record]) == [record]
    assert validate_news_provider_issues([failure.issues[0]]) == [failure.issues[0]]


def test_news_provider_exports_are_sorted_and_exist():
    import aqos.news_providers as news_providers

    assert news_providers.__all__ == sorted(news_providers.__all__)

    for export_name in news_providers.__all__:
        assert hasattr(news_providers, export_name), export_name