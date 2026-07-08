"""
Unit tests for AQOS brokers package scaffold.
"""

import pytest

from aqos.brokers import (
    BrokerAuthType,
    BrokerCapability,
    BrokerConfig,
    BrokerCredentials,
    BrokerHealth,
    BrokerResult,
    BrokerStatus,
    BrokerType,
    broker_failure,
    broker_success,
    build_broker_config,
    build_broker_credentials,
    build_broker_health,
    build_broker_result,
    mask_secret,
    normalize_broker_auth_type,
    normalize_broker_capability,
    normalize_broker_status,
    normalize_broker_type,
    validate_broker_capabilities,
    validate_metadata,
    validate_non_empty_string,
    validate_non_negative_float,
    validate_positive_float,
    validate_positive_integer,
    validate_string,
)


def test_broker_enum_values():
    assert BrokerType.PAPER.value == "paper"
    assert BrokerType.EXCHANGE.value == "exchange"
    assert BrokerType.FOREX.value == "forex"
    assert BrokerType.CFD.value == "cfd"
    assert BrokerType.CRYPTO.value == "crypto"
    assert BrokerType.STOCK.value == "stock"

    assert BrokerStatus.ACTIVE.value == "active"
    assert BrokerStatus.INACTIVE.value == "inactive"
    assert BrokerStatus.DEGRADED.value == "degraded"
    assert BrokerStatus.ERROR.value == "error"

    assert BrokerCapability.PAPER_TRADING.value == "paper_trading"
    assert BrokerCapability.LIVE_TRADING.value == "live_trading"
    assert BrokerCapability.MARKET_ORDERS.value == "market_orders"
    assert BrokerCapability.LIMIT_ORDERS.value == "limit_orders"
    assert BrokerCapability.STOP_ORDERS.value == "stop_orders"
    assert BrokerCapability.ACCOUNT_INFO.value == "account_info"
    assert BrokerCapability.POSITION_TRACKING.value == "position_tracking"
    assert BrokerCapability.TRADE_HISTORY.value == "trade_history"

    assert BrokerAuthType.NONE.value == "none"
    assert BrokerAuthType.API_KEY.value == "api_key"
    assert BrokerAuthType.BEARER_TOKEN.value == "bearer_token"
    assert BrokerAuthType.BASIC.value == "basic"


def test_broker_normalizers_accept_enum_and_string():
    assert normalize_broker_type(BrokerType.PAPER) == BrokerType.PAPER
    assert normalize_broker_type(" PAPER ") == BrokerType.PAPER
    assert normalize_broker_status(BrokerStatus.ACTIVE) == BrokerStatus.ACTIVE
    assert normalize_broker_status(" DEGRADED ") == BrokerStatus.DEGRADED
    assert normalize_broker_capability(BrokerCapability.MARKET_ORDERS) == BrokerCapability.MARKET_ORDERS
    assert normalize_broker_capability(" LIMIT_ORDERS ") == BrokerCapability.LIMIT_ORDERS
    assert normalize_broker_auth_type(BrokerAuthType.API_KEY) == BrokerAuthType.API_KEY
    assert normalize_broker_auth_type(" BEARER_TOKEN ") == BrokerAuthType.BEARER_TOKEN


def test_broker_normalizers_reject_invalid_values():
    with pytest.raises(ValueError):
        normalize_broker_type("bad")

    with pytest.raises(ValueError):
        normalize_broker_status("bad")

    with pytest.raises(ValueError):
        normalize_broker_capability("bad")

    with pytest.raises(ValueError):
        normalize_broker_auth_type("bad")


def test_broker_validators():
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


def test_validate_broker_capabilities():
    capabilities = [
        "paper_trading",
        BrokerCapability.MARKET_ORDERS,
    ]

    assert validate_broker_capabilities(capabilities) == capabilities

    with pytest.raises(ValueError):
        validate_broker_capabilities("bad")

    with pytest.raises(ValueError):
        validate_broker_capabilities(["bad"])


def test_mask_secret():
    assert mask_secret("") == ""
    assert mask_secret("secret") == "********"

    with pytest.raises(ValueError):
        mask_secret(123)


def test_broker_credentials_none_auth():
    credentials = BrokerCredentials()

    assert credentials.configured is True
    assert credentials.masked() == {
        "auth_type": "none",
        "api_key": "",
        "secret": "",
        "token": "",
        "username": "",
        "password": "",
        "account_id": "",
        "configured": True,
        "metadata": {},
    }


def test_broker_credentials_api_key():
    credentials = build_broker_credentials(
        auth_type="api_key",
        api_key="abc123",
        secret="secret123",
        account_id="account-1",
        metadata={
            "source": "test",
        },
    )

    assert isinstance(credentials, BrokerCredentials)
    assert credentials.configured is True
    assert credentials.masked()["api_key"] == "********"
    assert credentials.masked()["secret"] == "********"
    assert credentials.masked()["account_id"] == "account-1"
    assert credentials.masked()["metadata"] == {
        "source": "test",
    }


def test_broker_credentials_bearer_token_and_basic():
    token_credentials = build_broker_credentials(
        auth_type="bearer_token",
        token="token",
    )
    basic_credentials = build_broker_credentials(
        auth_type="basic",
        username="user",
        password="pass",
    )

    assert token_credentials.configured is True
    assert token_credentials.masked()["token"] == "********"
    assert basic_credentials.configured is True
    assert basic_credentials.masked()["password"] == "********"


def test_broker_credentials_reject_invalid_values():
    with pytest.raises(ValueError):
        BrokerCredentials(auth_type="bad")

    with pytest.raises(ValueError):
        BrokerCredentials(api_key=123)

    with pytest.raises(ValueError):
        BrokerCredentials(secret=123)

    with pytest.raises(ValueError):
        BrokerCredentials(token=123)

    with pytest.raises(ValueError):
        BrokerCredentials(username=123)

    with pytest.raises(ValueError):
        BrokerCredentials(password=123)

    with pytest.raises(ValueError):
        BrokerCredentials(account_id=123)

    with pytest.raises(ValueError):
        BrokerCredentials(metadata=[])


def test_broker_config_to_dict():
    credentials = build_broker_credentials(
        auth_type="api_key",
        api_key="abc",
        secret="secret",
        account_id="account-1",
    )
    config = BrokerConfig(
        broker_id=" broker-1 ",
        name=" Demo Broker ",
        broker_type="PAPER",
        base_url=" https://example.com ",
        status="ACTIVE",
        capabilities=["paper_trading", "market_orders"],
        credentials=credentials,
        paper_mode=True,
        timeout_seconds=10,
        rate_limit_per_minute=120,
        metadata={
            "env": "test",
        },
    )

    payload = config.to_dict()

    assert payload["broker_id"] == "broker-1"
    assert payload["name"] == "Demo Broker"
    assert payload["broker_type"] == "paper"
    assert payload["base_url"] == "https://example.com"
    assert payload["status"] == "active"
    assert payload["active"] is True
    assert payload["paper_mode"] is True
    assert payload["live_mode"] is False
    assert payload["capabilities"] == ["paper_trading", "market_orders"]
    assert payload["credentials"]["api_key"] == "********"
    assert payload["credentials"]["secret"] == "********"
    assert payload["timeout_seconds"] == 10.0
    assert payload["rate_limit_per_minute"] == 120
    assert payload["metadata"] == {
        "env": "test",
    }

    assert config.supports("paper_trading") is True
    assert config.supports("limit_orders") is False


def test_broker_config_live_mode():
    config = build_broker_config(
        broker_id="live-1",
        name="Live Broker",
        broker_type="exchange",
        capabilities=["live_trading"],
        paper_mode=False,
    )

    assert config.paper_mode is False
    assert config.live_mode is True


def test_broker_config_rejects_invalid_values():
    with pytest.raises(ValueError):
        BrokerConfig(broker_id="", name="Broker", broker_type="paper")

    with pytest.raises(ValueError):
        BrokerConfig(broker_id="broker-1", name="", broker_type="paper")

    with pytest.raises(ValueError):
        BrokerConfig(broker_id="broker-1", name="Broker", broker_type="bad")

    with pytest.raises(ValueError):
        BrokerConfig(broker_id="broker-1", name="Broker", broker_type="paper", status="bad")

    with pytest.raises(ValueError):
        BrokerConfig(broker_id="broker-1", name="Broker", broker_type="paper", capabilities=["bad"])

    with pytest.raises(ValueError):
        BrokerConfig(broker_id="broker-1", name="Broker", broker_type="paper", credentials="bad")

    with pytest.raises(ValueError):
        BrokerConfig(broker_id="broker-1", name="Broker", broker_type="paper", paper_mode="yes")

    with pytest.raises(ValueError):
        BrokerConfig(broker_id="broker-1", name="Broker", broker_type="paper", timeout_seconds=0)

    with pytest.raises(ValueError):
        BrokerConfig(broker_id="broker-1", name="Broker", broker_type="paper", rate_limit_per_minute=0)

    with pytest.raises(ValueError):
        BrokerConfig(broker_id="broker-1", name="Broker", broker_type="paper", metadata=[])


def test_build_broker_config():
    config = build_broker_config(
        broker_id="broker-1",
        name="Demo",
        broker_type="paper",
        capabilities=["paper_trading"],
    )

    assert isinstance(config, BrokerConfig)
    assert config.supports("paper_trading") is True


def test_broker_health_to_dict():
    health = BrokerHealth(
        broker_id=" broker-1 ",
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
        "broker_id": "broker-1",
        "status": "active",
        "healthy": True,
        "message": "OK",
        "latency_ms": 12.5,
        "checked_at": "2026-01-01T00:00:00+00:00",
        "metadata": {
            "source": "test",
        },
    }


def test_broker_health_rejects_invalid_values():
    with pytest.raises(ValueError):
        BrokerHealth(broker_id="", status="active")

    with pytest.raises(ValueError):
        BrokerHealth(broker_id="broker-1", status="bad")

    with pytest.raises(ValueError):
        BrokerHealth(broker_id="broker-1", status="active", message=123)

    with pytest.raises(ValueError):
        BrokerHealth(broker_id="broker-1", status="active", latency_ms=-1)

    with pytest.raises(ValueError):
        BrokerHealth(broker_id="broker-1", status="active", checked_at="")

    with pytest.raises(ValueError):
        BrokerHealth(broker_id="broker-1", status="active", metadata=[])


def test_build_broker_health():
    health = build_broker_health(
        broker_id="broker-1",
        status="active",
        checked_at="2026-01-01T00:00:00+00:00",
    )

    assert isinstance(health, BrokerHealth)
    assert health.healthy is True


def test_broker_result_to_dict_success_and_failure():
    success = BrokerResult(
        broker_id=" broker-1 ",
        success=True,
        data={
            "order_id": "order-1",
        },
        message=" Done ",
    )
    failure = BrokerResult(
        broker_id="broker-1",
        success=False,
        error="boom",
    )

    assert success.failed is False
    assert success.to_dict() == {
        "broker_id": "broker-1",
        "success": True,
        "failed": False,
        "data": {
            "order_id": "order-1",
        },
        "message": "Done",
        "error": "",
        "metadata": {},
    }

    assert failure.failed is True
    assert failure.to_dict()["error"] == "boom"


def test_broker_result_rejects_invalid_values():
    with pytest.raises(ValueError):
        BrokerResult(broker_id="", success=True)

    with pytest.raises(ValueError):
        BrokerResult(broker_id="broker-1", success="yes")

    with pytest.raises(ValueError):
        BrokerResult(broker_id="broker-1", success=True, data=[])

    with pytest.raises(ValueError):
        BrokerResult(broker_id="broker-1", success=True, message=123)

    with pytest.raises(ValueError):
        BrokerResult(broker_id="broker-1", success=True, error=123)

    with pytest.raises(ValueError):
        BrokerResult(broker_id="broker-1", success=True, metadata=[])


def test_build_broker_result_helpers():
    result = build_broker_result(
        broker_id="broker-1",
        success=True,
        data={
            "ok": True,
        },
    )

    success = broker_success(
        broker_id="broker-1",
        data={
            "order_id": "order-1",
        },
    )

    failure = broker_failure(
        broker_id="broker-1",
        error="failed",
    )

    assert isinstance(result, BrokerResult)
    assert success.success is True
    assert success.data == {
        "order_id": "order-1",
    }
    assert failure.success is False
    assert failure.error == "failed"


def test_broker_exports_are_sorted_and_exist():
    import aqos.brokers as brokers

    assert brokers.__all__ == sorted(brokers.__all__)

    for export_name in brokers.__all__:
        assert hasattr(brokers, export_name), export_name