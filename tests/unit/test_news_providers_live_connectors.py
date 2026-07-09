"""
Unit tests for AQOS live news connector scaffold.
"""

import pytest

from aqos.news_providers import (
    HttpNewsProviderConfig,
    LiveNewsConnectorCategory,
    LiveNewsConnectorDefinition,
    LiveNewsConnectorEndpoint,
    LiveNewsConnectorId,
    LiveNewsConnectorRuntimeConfig,
    LiveNewsConnectorStatus,
    NewsProviderCapability,
    NewsProviderCredentials,
    build_live_connector_headers,
    build_live_connector_query_params,
    build_live_news_connector_definition,
    build_live_news_connector_endpoint,
    build_live_news_connector_runtime_config,
    connector_definition_requires_credentials,
    connector_runtime_has_required_credentials,
    list_default_live_connector_capabilities,
    live_connector_runtime_to_http_config,
    normalize_live_news_connector_category,
    normalize_live_news_connector_id,
    normalize_live_news_connector_status,
    validate_news_provider_capability_list,
)


def sample_endpoint():
    return build_live_news_connector_endpoint(
        base_url="https://api.example.com",
        endpoint="/news",
        payload_key="articles",
        default_query_params={"format": "json"},
        default_headers={"Accept": "application/json"},
        timeout_seconds=15,
    )


def sample_definition():
    return build_live_news_connector_definition(
        connector_id="gdelt",
        name="GDELT",
        category="global_news",
        endpoint=sample_endpoint(),
        auth_type="none",
        status="ready",
        capabilities=["live_news", "historical_news"],
        keyword_query_param="query",
        country_query_param="country",
    )


def test_live_connector_enums_and_normalizers():
    assert LiveNewsConnectorId.GDELT.value == "gdelt"
    assert LiveNewsConnectorId.HACKER_NEWS.value == "hacker_news"
    assert LiveNewsConnectorId.NEWS_API.value == "news_api"
    assert LiveNewsConnectorId.MARKETAUX.value == "marketaux"
    assert LiveNewsConnectorId.FINNHUB.value == "finnhub"
    assert LiveNewsConnectorId.FMP.value == "financial_modeling_prep"
    assert LiveNewsConnectorId.TRADING_ECONOMICS.value == "trading_economics"
    assert LiveNewsConnectorId.CRYPTOPANIC.value == "cryptopanic"
    assert LiveNewsConnectorId.CUSTOM_HTTP.value == "custom_http"
    assert LiveNewsConnectorId.UNKNOWN.value == "unknown"

    assert LiveNewsConnectorCategory.GLOBAL_NEWS.value == "global_news"
    assert LiveNewsConnectorCategory.FINANCIAL_NEWS.value == "financial_news"
    assert LiveNewsConnectorCategory.MACRO_CALENDAR.value == "macro_calendar"
    assert LiveNewsConnectorCategory.CRYPTO_NEWS.value == "crypto_news"
    assert LiveNewsConnectorCategory.PUBLIC_JSON.value == "public_json"
    assert LiveNewsConnectorCategory.CUSTOM.value == "custom"
    assert LiveNewsConnectorCategory.UNKNOWN.value == "unknown"

    assert LiveNewsConnectorStatus.READY.value == "ready"
    assert LiveNewsConnectorStatus.NEEDS_API_KEY.value == "needs_api_key"
    assert LiveNewsConnectorStatus.DISABLED.value == "disabled"
    assert LiveNewsConnectorStatus.EXPERIMENTAL.value == "experimental"
    assert LiveNewsConnectorStatus.UNKNOWN.value == "unknown"

    assert normalize_live_news_connector_id(" GDELT ") == LiveNewsConnectorId.GDELT
    assert normalize_live_news_connector_category(" GLOBAL_NEWS ") == LiveNewsConnectorCategory.GLOBAL_NEWS
    assert normalize_live_news_connector_status(" READY ") == LiveNewsConnectorStatus.READY

    with pytest.raises(ValueError):
        normalize_live_news_connector_id("bad")

    with pytest.raises(ValueError):
        normalize_live_news_connector_category("bad")

    with pytest.raises(ValueError):
        normalize_live_news_connector_status("bad")


def test_live_connector_endpoint_to_dict_and_rejections():
    endpoint = LiveNewsConnectorEndpoint(
        base_url=" https://api.example.com ",
        endpoint=" /news ",
        method=" get ",
        payload_key=" articles ",
        default_query_params={"format": "json"},
        default_headers={"Accept": "application/json"},
        timeout_seconds=20,
        metadata={"source": "test"},
    )

    payload = endpoint.to_dict()
    built = sample_endpoint()

    assert payload["base_url"] == "https://api.example.com"
    assert payload["endpoint"] == "/news"
    assert payload["url"] == "https://api.example.com/news"
    assert payload["method"] == "GET"
    assert payload["payload_key"] == "articles"
    assert isinstance(built, LiveNewsConnectorEndpoint)

    with pytest.raises(ValueError):
        LiveNewsConnectorEndpoint(base_url="")

    with pytest.raises(ValueError):
        LiveNewsConnectorEndpoint(base_url="https://api.example.com", endpoint=123)

    with pytest.raises(ValueError):
        LiveNewsConnectorEndpoint(base_url="https://api.example.com", default_query_params=[])

    with pytest.raises(ValueError):
        LiveNewsConnectorEndpoint(base_url="https://api.example.com", default_headers=[])

    with pytest.raises(ValueError):
        LiveNewsConnectorEndpoint(base_url="https://api.example.com", timeout_seconds=0)

    with pytest.raises(ValueError):
        LiveNewsConnectorEndpoint(base_url="https://api.example.com", metadata=[])


def test_live_connector_definition_to_dict_and_rejections():
    definition = LiveNewsConnectorDefinition(
        connector_id=" gdelt ",
        name=" GDELT ",
        category=" global_news ",
        provider_type=" http ",
        auth_type=" none ",
        status=" ready ",
        endpoint=sample_endpoint(),
        capabilities=[" live_news ", " historical_news "],
        api_key_header=" X-API-Key ",
        keyword_query_param=" query ",
        country_query_param=" country ",
        description=" Global news connector. ",
        metadata={"source": "test"},
    )

    payload = definition.to_dict()
    built = sample_definition()

    assert payload["connector_id"] == "gdelt"
    assert payload["name"] == "GDELT"
    assert payload["category"] == "global_news"
    assert payload["provider_type"] == "http"
    assert payload["auth_type"] == "none"
    assert payload["status"] == "ready"
    assert payload["capabilities"] == ["live_news", "historical_news"]
    assert payload["ready_without_credentials"] is True
    assert definition.requires_api_key is False
    assert isinstance(built, LiveNewsConnectorDefinition)

    with pytest.raises(ValueError):
        LiveNewsConnectorDefinition(
            connector_id="bad",
            name="Name",
            category="global_news",
            endpoint=sample_endpoint(),
        )

    with pytest.raises(ValueError):
        LiveNewsConnectorDefinition(
            connector_id="gdelt",
            name="",
            category="global_news",
            endpoint=sample_endpoint(),
        )

    with pytest.raises(ValueError):
        LiveNewsConnectorDefinition(
            connector_id="gdelt",
            name="Name",
            category="bad",
            endpoint=sample_endpoint(),
        )

    with pytest.raises(ValueError):
        LiveNewsConnectorDefinition(
            connector_id="gdelt",
            name="Name",
            category="global_news",
            endpoint="bad",
        )

    with pytest.raises(ValueError):
        LiveNewsConnectorDefinition(
            connector_id="gdelt",
            name="Name",
            category="global_news",
            endpoint=sample_endpoint(),
            capabilities=["bad"],
        )

    with pytest.raises(ValueError):
        LiveNewsConnectorDefinition(
            connector_id="gdelt",
            name="Name",
            category="global_news",
            endpoint=sample_endpoint(),
            metadata=[],
        )


def test_live_connector_runtime_config_to_dict_and_rejections():
    runtime = LiveNewsConnectorRuntimeConfig(
        connector=sample_definition(),
        credentials=NewsProviderCredentials(),
        symbol=" xauusd ",
        keywords=[" Gold ", " Inflation "],
        country=" us ",
        currency=" usd ",
        query_params={"maxrecords": 5},
        headers={"User-Agent": "AQOS"},
        payload_key=" articles ",
        metadata={"source": "test"},
    )

    payload = runtime.to_dict()
    built = build_live_news_connector_runtime_config(
        connector=sample_definition(),
        symbol="XAUUSD",
    )

    assert payload["symbol"] == "XAUUSD"
    assert payload["keywords"] == ["gold", "inflation"]
    assert payload["country"] == "US"
    assert payload["currency"] == "USD"
    assert payload["payload_key"] == "articles"
    assert isinstance(built, LiveNewsConnectorRuntimeConfig)

    with pytest.raises(ValueError):
        LiveNewsConnectorRuntimeConfig(connector="bad")

    with pytest.raises(ValueError):
        LiveNewsConnectorRuntimeConfig(
            connector=sample_definition(),
            credentials="bad",
        )

    with pytest.raises(ValueError):
        LiveNewsConnectorRuntimeConfig(
            connector=sample_definition(),
            symbol="bad symbol",
        )

    with pytest.raises(ValueError):
        LiveNewsConnectorRuntimeConfig(
            connector=sample_definition(),
            keywords="bad",
        )

    with pytest.raises(ValueError):
        LiveNewsConnectorRuntimeConfig(
            connector=sample_definition(),
            query_params=[],
        )

    with pytest.raises(ValueError):
        LiveNewsConnectorRuntimeConfig(
            connector=sample_definition(),
            headers=[],
        )

    with pytest.raises(ValueError):
        LiveNewsConnectorRuntimeConfig(
            connector=sample_definition(),
            metadata=[],
        )


def test_build_live_connector_query_params_and_headers():
    runtime = build_live_news_connector_runtime_config(
        connector=sample_definition(),
        keywords=["gold", "inflation"],
        country="US",
        query_params={"maxrecords": 5},
        headers={"User-Agent": "AQOS"},
    )

    params = build_live_connector_query_params(runtime)
    headers = build_live_connector_headers(runtime)

    assert params["format"] == "json"
    assert params["query"] == "gold OR inflation"
    assert params["country"] == "US"
    assert params["maxrecords"] == 5
    assert headers["Accept"] == "application/json"
    assert headers["User-Agent"] == "AQOS"

    with pytest.raises(ValueError):
        build_live_connector_query_params("bad")

    with pytest.raises(ValueError):
        build_live_connector_headers("bad")


def test_live_connector_runtime_to_http_config():
    runtime = build_live_news_connector_runtime_config(
        connector=sample_definition(),
        keywords=["gold"],
        country="US",
        payload_key="articles",
    )

    config = live_connector_runtime_to_http_config(runtime)

    assert isinstance(config, HttpNewsProviderConfig)
    assert config.provider_id == "gdelt"
    assert config.name == "GDELT"
    assert config.base_url == "https://api.example.com"
    assert config.endpoint == "/news"
    assert config.payload_key == "articles"
    assert config.default_query_params["query"] == "gold"
    assert config.default_query_params["country"] == "US"

    with pytest.raises(ValueError):
        live_connector_runtime_to_http_config("bad")


def test_connector_credentials_helpers():
    public_definition = sample_definition()
    api_definition = build_live_news_connector_definition(
        connector_id="news_api",
        name="NewsAPI",
        category="financial_news",
        endpoint=sample_endpoint(),
        auth_type="api_key",
        status="needs_api_key",
        api_key_query_param="apiKey",
    )
    missing_runtime = build_live_news_connector_runtime_config(
        connector=api_definition,
    )
    valid_runtime = build_live_news_connector_runtime_config(
        connector=api_definition,
        credentials=NewsProviderCredentials(
            auth_type="api_key",
            api_key="secret",
        ),
    )

    assert connector_definition_requires_credentials(public_definition) is False
    assert connector_definition_requires_credentials(api_definition) is True
    assert connector_runtime_has_required_credentials(missing_runtime) is False
    assert connector_runtime_has_required_credentials(valid_runtime) is True

    with pytest.raises(ValueError):
        connector_definition_requires_credentials("bad")

    with pytest.raises(ValueError):
        connector_runtime_has_required_credentials("bad")


def test_default_capabilities_by_category():
    macro = list_default_live_connector_capabilities(category="macro_calendar")
    crypto = list_default_live_connector_capabilities(category="crypto_news")
    global_news = list_default_live_connector_capabilities(category="global_news")
    custom = list_default_live_connector_capabilities(category="custom")

    assert NewsProviderCapability.ECONOMIC_CALENDAR in macro
    assert NewsProviderCapability.MACRO_EVENTS in macro
    assert NewsProviderCapability.SENTIMENT in crypto
    assert NewsProviderCapability.IMPACT_CLASSIFICATION in global_news
    assert NewsProviderCapability.LIVE_NEWS in custom

    with pytest.raises(ValueError):
        list_default_live_connector_capabilities(category="bad")


def test_live_connector_validators_and_exports_exist():
    assert validate_news_provider_capability_list(["live_news"]) == ["live_news"]

    with pytest.raises(ValueError):
        validate_news_provider_capability_list("bad")

    with pytest.raises(ValueError):
        validate_news_provider_capability_list(["bad"])

    import aqos.news_providers as news_providers

    expected_exports = [
        "LiveNewsConnectorCategory",
        "LiveNewsConnectorDefinition",
        "LiveNewsConnectorEndpoint",
        "LiveNewsConnectorId",
        "LiveNewsConnectorRuntimeConfig",
        "LiveNewsConnectorStatus",
        "build_live_connector_headers",
        "build_live_connector_query_params",
        "build_live_news_connector_definition",
        "build_live_news_connector_endpoint",
        "build_live_news_connector_runtime_config",
        "connector_definition_requires_credentials",
        "connector_runtime_has_required_credentials",
        "list_default_live_connector_capabilities",
        "live_connector_runtime_to_http_config",
        "normalize_live_news_connector_category",
        "normalize_live_news_connector_id",
        "normalize_live_news_connector_status",
        "validate_news_provider_capability_list",
    ]

    for export_name in expected_exports:
        assert hasattr(news_providers, export_name), export_name