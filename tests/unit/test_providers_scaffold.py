"""
Unit tests for AQOS providers package scaffold.
"""

import pytest

from aqos.providers import (
    ProviderAuthType,
    ProviderCapability,
    ProviderConfig,
    ProviderCredentials,
    ProviderHealth,
    ProviderResult,
    ProviderStatus,
    ProviderType,
    build_provider_config,
    build_provider_credentials,
    build_provider_health,
    build_provider_result,
    mask_secret,
    normalize_provider_auth_type,
    normalize_provider_capability,
    normalize_provider_status,
    normalize_provider_type,
    provider_failure,
    provider_success,
    validate_metadata,
    validate_non_empty_string,
    validate_non_negative_float,
    validate_positive_float,
    validate_positive_integer,
    validate_provider_capabilities,
    validate_string,
)


def test_provider_enum_values():
    assert ProviderType.MARKET_DATA.value == "market_data"
    assert ProviderType.BROKER.value == "broker"
    assert ProviderType.NEWS.value == "news"
    assert ProviderType.CALENDAR.value == "calendar"
    assert ProviderType.RESEARCH.value == "research"

    assert ProviderStatus.ACTIVE.value == "active"
    assert ProviderStatus.INACTIVE.value == "inactive"
    assert ProviderStatus.DEGRADED.value == "degraded"
    assert ProviderStatus.ERROR.value == "error"

    assert ProviderCapability.HISTORICAL_OHLCV.value == "historical_ohlcv"
    assert ProviderCapability.LIVE_QUOTES.value == "live_quotes"
    assert ProviderCapability.TICKS.value == "ticks"
    assert ProviderCapability.ORDER_EXECUTION.value == "order_execution"
    assert ProviderCapability.NEWS_FEED.value == "news_feed"
    assert ProviderCapability.ECONOMIC_CALENDAR.value == "economic_calendar"

    assert ProviderAuthType.NONE.value == "none"
    assert ProviderAuthType.API_KEY.value == "api_key"
    assert ProviderAuthType.BEARER_TOKEN.value == "bearer_token"
    assert ProviderAuthType.BASIC.value == "basic"


def test_normalizers_accept_enum_and_string():
    assert normalize_provider_type(ProviderType.MARKET_DATA) == ProviderType.MARKET_DATA
    assert normalize_provider_type(" MARKET_DATA ") == ProviderType.MARKET_DATA
    assert normalize_provider_status(ProviderStatus.ACTIVE) == ProviderStatus.ACTIVE
    assert normalize_provider_status(" DEGRADED ") == ProviderStatus.DEGRADED
    assert normalize_provider_capability(ProviderCapability.HISTORICAL_OHLCV) == ProviderCapability.HISTORICAL_OHLCV
    assert normalize_provider_capability(" LIVE_QUOTES ") == ProviderCapability.LIVE_QUOTES
    assert normalize_provider_auth_type(ProviderAuthType.API_KEY) == ProviderAuthType.API_KEY
    assert normalize_provider_auth_type(" BEARER_TOKEN ") == ProviderAuthType.BEARER_TOKEN


def test_normalizers_reject_invalid_values():
    with pytest.raises(ValueError):
        normalize_provider_type("bad")

    with pytest.raises(ValueError):
        normalize_provider_status("bad")

    with pytest.raises(ValueError):
        normalize_provider_capability("bad")

    with pytest.raises(ValueError):
        normalize_provider_auth_type("bad")


def test_validators():
    assert validate_string("", "Field") == ""
    assert validate_string("value", "Field") == "value"
    assert validate_non_empty_string(" value ", "Field") == "value"
    assert validate_metadata({"a": 1}) == {"a": 1}
    assert validate_positive_integer(1, "Value") == 1
    assert validate_positive_float(1.5, "Value") == 1.5
    assert validate_non_negative_float(0, "Value") == 0.0

    with pytest.raises(ValueError):
        validate_string(123, "Field")

    with pytest.raises(ValueError):
        validate_non_empty_string("", "Field")

    with pytest.raises(ValueError):
        validate_metadata([])

    with pytest.raises(ValueError):
        validate_positive_integer(0, "Value")

    with pytest.raises(ValueError):
        validate_positive_integer(True, "Value")

    with pytest.raises(ValueError):
        validate_positive_float(0, "Value")

    with pytest.raises(ValueError):
        validate_positive_float(True, "Value")

    with pytest.raises(ValueError):
        validate_non_negative_float(-1, "Value")

    with pytest.raises(ValueError):
        validate_non_negative_float(True, "Value")


def test_validate_provider_capabilities():
    capabilities = [
        "historical_ohlcv",
        ProviderCapability.LIVE_QUOTES,
    ]

    assert validate_provider_capabilities(capabilities) == capabilities

    with pytest.raises(ValueError):
        validate_provider_capabilities("bad")

    with pytest.raises(ValueError):
        validate_provider_capabilities(["bad"])


def test_mask_secret():
    assert mask_secret("") == ""
    assert mask_secret("secret") == "********"

    with pytest.raises(ValueError):
        mask_secret(123)


def test_provider_credentials_none_auth():
    credentials = ProviderCredentials()

    assert credentials.configured is True
    assert credentials.masked() == {
        "auth_type": "none",
        "api_key": "",
        "token": "",
        "username": "",
        "password": "",
        "configured": True,
        "metadata": {},
    }


def test_provider_credentials_api_key():
    credentials = build_provider_credentials(
        auth_type="api_key",
        api_key="abc123",
        metadata={
            "source": "test",
        },
    )

    assert isinstance(credentials, ProviderCredentials)
    assert credentials.configured is True
    assert credentials.masked()["api_key"] == "********"
    assert credentials.masked()["metadata"] == {
        "source": "test",
    }


def test_provider_credentials_bearer_token_and_basic():
    token_credentials = build_provider_credentials(
        auth_type="bearer_token",
        token="token",
    )
    basic_credentials = build_provider_credentials(
        auth_type="basic",
        username="user",
        password="pass",
    )

    assert token_credentials.configured is True
    assert basic_credentials.configured is True
    assert basic_credentials.masked()["password"] == "********"


def test_provider_credentials_reject_invalid_values():
    with pytest.raises(ValueError):
        ProviderCredentials(auth_type="bad")

    with pytest.raises(ValueError):
        ProviderCredentials(api_key=123)

    with pytest.raises(ValueError):
        ProviderCredentials(metadata=[])


def test_provider_config_to_dict():
    credentials = build_provider_credentials(
        auth_type="api_key",
        api_key="abc",
    )
    config = ProviderConfig(
        provider_id=" provider-1 ",
        name=" Demo Provider ",
        provider_type="MARKET_DATA",
        base_url=" https://example.com ",
        status="ACTIVE",
        capabilities=["historical_ohlcv", "live_quotes"],
        credentials=credentials,
        timeout_seconds=10,
        rate_limit_per_minute=120,
        metadata={
            "env": "test",
        },
    )

    payload = config.to_dict()

    assert payload["provider_id"] == "provider-1"
    assert payload["name"] == "Demo Provider"
    assert payload["provider_type"] == "market_data"
    assert payload["base_url"] == "https://example.com"
    assert payload["status"] == "active"
    assert payload["active"] is True
    assert payload["capabilities"] == ["historical_ohlcv", "live_quotes"]
    assert payload["credentials"]["api_key"] == "********"
    assert payload["timeout_seconds"] == 10.0
    assert payload["rate_limit_per_minute"] == 120
    assert payload["metadata"] == {
        "env": "test",
    }

    assert config.supports("historical_ohlcv") is True
    assert config.supports("ticks") is False


def test_provider_config_rejects_invalid_values():
    with pytest.raises(ValueError):
        ProviderConfig(provider_id="", name="Provider", provider_type="market_data")

    with pytest.raises(ValueError):
        ProviderConfig(provider_id="provider-1", name="", provider_type="market_data")

    with pytest.raises(ValueError):
        ProviderConfig(provider_id="provider-1", name="Provider", provider_type="bad")

    with pytest.raises(ValueError):
        ProviderConfig(provider_id="provider-1", name="Provider", provider_type="market_data", status="bad")

    with pytest.raises(ValueError):
        ProviderConfig(provider_id="provider-1", name="Provider", provider_type="market_data", capabilities=["bad"])

    with pytest.raises(ValueError):
        ProviderConfig(provider_id="provider-1", name="Provider", provider_type="market_data", credentials="bad")

    with pytest.raises(ValueError):
        ProviderConfig(provider_id="provider-1", name="Provider", provider_type="market_data", timeout_seconds=0)

    with pytest.raises(ValueError):
        ProviderConfig(provider_id="provider-1", name="Provider", provider_type="market_data", rate_limit_per_minute=0)

    with pytest.raises(ValueError):
        ProviderConfig(provider_id="provider-1", name="Provider", provider_type="market_data", metadata=[])


def test_build_provider_config():
    config = build_provider_config(
        provider_id="provider-1",
        name="Demo",
        provider_type="market_data",
        capabilities=["historical_ohlcv"],
    )

    assert isinstance(config, ProviderConfig)
    assert config.supports("historical_ohlcv") is True


def test_provider_health_to_dict():
    health = ProviderHealth(
        provider_id=" provider-1 ",
        status="ACTIVE",
        message=" OK ",
        latency_ms=12.5,
        checked_at="2026-01-01T00:00:00+00:00",
        metadata={
            "source": "test",
        },
    )

    assert health.healthy is True
    assert health.to_dict() == {
        "provider_id": "provider-1",
        "status": "active",
        "healthy": True,
        "message": "OK",
        "latency_ms": 12.5,
        "checked_at": "2026-01-01T00:00:00+00:00",
        "metadata": {
            "source": "test",
        },
    }


def test_provider_health_rejects_invalid_values():
    with pytest.raises(ValueError):
        ProviderHealth(provider_id="", status="active")

    with pytest.raises(ValueError):
        ProviderHealth(provider_id="provider-1", status="bad")

    with pytest.raises(ValueError):
        ProviderHealth(provider_id="provider-1", status="active", message=123)

    with pytest.raises(ValueError):
        ProviderHealth(provider_id="provider-1", status="active", latency_ms=-1)

    with pytest.raises(ValueError):
        ProviderHealth(provider_id="provider-1", status="active", checked_at="")

    with pytest.raises(ValueError):
        ProviderHealth(provider_id="provider-1", status="active", metadata=[])


def test_build_provider_health():
    health = build_provider_health(
        provider_id="provider-1",
        status="active",
        checked_at="2026-01-01T00:00:00+00:00",
    )

    assert isinstance(health, ProviderHealth)
    assert health.healthy is True


def test_provider_result_to_dict_success_and_failure():
    success = ProviderResult(
        provider_id=" provider-1 ",
        success=True,
        data={
            "rows": 10,
        },
        message=" Done ",
    )
    failure = ProviderResult(
        provider_id="provider-1",
        success=False,
        error="boom",
    )

    assert success.failed is False
    assert success.to_dict() == {
        "provider_id": "provider-1",
        "success": True,
        "failed": False,
        "data": {
            "rows": 10,
        },
        "message": "Done",
        "error": "",
        "metadata": {},
    }

    assert failure.failed is True
    assert failure.to_dict()["error"] == "boom"


def test_provider_result_rejects_invalid_values():
    with pytest.raises(ValueError):
        ProviderResult(provider_id="", success=True)

    with pytest.raises(ValueError):
        ProviderResult(provider_id="provider-1", success="yes")

    with pytest.raises(ValueError):
        ProviderResult(provider_id="provider-1", success=True, data=[])

    with pytest.raises(ValueError):
        ProviderResult(provider_id="provider-1", success=True, message=123)

    with pytest.raises(ValueError):
        ProviderResult(provider_id="provider-1", success=True, error=123)

    with pytest.raises(ValueError):
        ProviderResult(provider_id="provider-1", success=True, metadata=[])


def test_build_provider_result_helpers():
    result = build_provider_result(
        provider_id="provider-1",
        success=True,
        data={
            "ok": True,
        },
    )

    success = provider_success(
        provider_id="provider-1",
        data={
            "rows": 5,
        },
    )

    failure = provider_failure(
        provider_id="provider-1",
        error="failed",
    )

    assert isinstance(result, ProviderResult)
    assert success.success is True
    assert success.data == {
        "rows": 5,
    }
    assert failure.success is False
    assert failure.error == "failed"


def test_provider_exports_are_sorted_and_exist():
    import aqos.providers as providers

    assert providers.__all__ == sorted(providers.__all__)

    for export_name in providers.__all__:
        assert hasattr(providers, export_name), export_name