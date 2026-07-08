"""
Unit tests for AQOS brokers package exports.
"""

import inspect

import aqos.brokers as brokers


EXPECTED_BROKER_EXPORTS = sorted(
    [
        "BrokerAccount",
        "BrokerAccountSnapshot",
        "BrokerAuthType",
        "BrokerCapability",
        "BrokerConfig",
        "BrokerCredentials",
        "BrokerExecutionHub",
        "BrokerExecutionPayload",
        "BrokerHealth",
        "BrokerOrder",
        "BrokerOrderRequest",
        "BrokerPosition",
        "BrokerRegistry",
        "BrokerRegistryEntry",
        "BrokerRegistrySummary",
        "BrokerResult",
        "BrokerStatus",
        "BrokerTrade",
        "BrokerType",
        "ExchangeHttpBrokerAdapter",
        "ExchangeHttpMethod",
        "ExchangeHttpRequest",
        "ExchangeHttpResponse",
        "OrderSide",
        "OrderStatus",
        "OrderType",
        "PaperBrokerAdapter",
        "PaperBrokerSnapshot",
        "PaperFillPolicy",
        "PositionAccountAdapter",
        "PositionSide",
        "TimeInForce",
        "TradeStatus",
        "apply_trade_to_broker_account",
        "apply_trade_to_position",
        "broker_account_snapshot_to_payload",
        "broker_failure",
        "broker_registry_error_result",
        "broker_registry_to_result",
        "broker_result_account",
        "broker_result_order",
        "broker_result_positions",
        "broker_result_snapshot",
        "broker_result_to_execution_payload",
        "broker_result_trade",
        "broker_success",
        "build_broker_account",
        "build_broker_account_snapshot",
        "build_broker_config",
        "build_broker_credentials",
        "build_broker_execution_hub",
        "build_broker_execution_payload",
        "build_broker_health",
        "build_broker_order",
        "build_broker_order_request",
        "build_broker_position",
        "build_broker_registry",
        "build_broker_registry_entry",
        "build_broker_result",
        "build_broker_trade",
        "build_exchange_http_broker_adapter",
        "build_exchange_http_request",
        "build_exchange_http_response",
        "build_paper_broker_adapter",
        "build_paper_broker_snapshot",
        "build_position_account_adapter",
        "build_sample_broker_execution_hub",
        "build_sample_broker_registry",
        "calculate_realized_pnl",
        "cancel_broker_order",
        "cancel_broker_order_via_hub",
        "cancel_exchange_http_order",
        "cancel_paper_order",
        "default_exchange_http_transport",
        "exchange_http_error_result",
        "execution_failure",
        "fetch_broker_account_snapshot",
        "fetch_exchange_http_account",
        "fetch_exchange_http_positions",
        "fill_broker_order",
        "fill_paper_order",
        "is_success_exchange_http_status",
        "join_exchange_http_url",
        "json_payload_to_broker_account",
        "json_payload_to_broker_order",
        "json_payload_to_broker_position",
        "json_payload_to_broker_positions",
        "json_payload_to_broker_trade",
        "mask_secret",
        "normalize_broker_auth_type",
        "normalize_broker_capability",
        "normalize_broker_status",
        "normalize_broker_type",
        "normalize_exchange_http_method",
        "normalize_order_side",
        "normalize_order_status",
        "normalize_order_type",
        "normalize_paper_fill_policy",
        "normalize_position_side",
        "normalize_time_in_force",
        "normalize_trade_status",
        "opposite_position_side",
        "order_error_result",
        "order_request_to_order",
        "order_to_broker_result",
        "paper_broker_error_result",
        "paper_broker_snapshot_result",
        "position_id_for_symbol",
        "position_side_from_trade_side",
        "register_broker_adapter",
        "register_broker_config",
        "register_execution_adapters",
        "register_paper_broker",
        "reject_broker_order",
        "reject_paper_order",
        "resolve_paper_broker_adapter",
        "resolve_paper_fill_price",
        "resolve_position_account_adapter",
        "should_auto_fill_order",
        "submit_broker_order",
        "submit_exchange_http_order",
        "submit_market_broker_order",
        "submit_paper_order",
        "summarize_broker_registry_entries",
        "trade_to_broker_result",
        "validate_account_currency",
        "validate_broker_capabilities",
        "validate_broker_config_object",
        "validate_broker_execution_hub",
        "validate_broker_positions",
        "validate_broker_registry",
        "validate_broker_registry_entries",
        "validate_broker_trades",
        "validate_exchange_http_broker_config",
        "validate_exchange_http_headers",
        "validate_exchange_http_params",
        "validate_exchange_http_status_code",
        "validate_exchange_http_url",
        "validate_execution_positions",
        "validate_metadata",
        "validate_non_empty_string",
        "validate_non_negative_float",
        "validate_number",
        "validate_order_symbol",
        "validate_paper_broker_config",
        "validate_paper_order_dict",
        "validate_paper_orders",
        "validate_paper_price_dict",
        "validate_paper_trade_dict",
        "validate_paper_trades",
        "validate_position_dict",
        "validate_positive_float",
        "validate_positive_integer",
        "validate_string",
        "validate_trade_dict",
    ],
)


CLASS_EXPORTS = [
    "BrokerAccount",
    "BrokerAccountSnapshot",
    "BrokerAuthType",
    "BrokerCapability",
    "BrokerConfig",
    "BrokerCredentials",
    "BrokerExecutionHub",
    "BrokerExecutionPayload",
    "BrokerHealth",
    "BrokerOrder",
    "BrokerOrderRequest",
    "BrokerPosition",
    "BrokerRegistry",
    "BrokerRegistryEntry",
    "BrokerRegistrySummary",
    "BrokerResult",
    "BrokerStatus",
    "BrokerTrade",
    "BrokerType",
    "ExchangeHttpBrokerAdapter",
    "ExchangeHttpMethod",
    "ExchangeHttpRequest",
    "ExchangeHttpResponse",
    "OrderSide",
    "OrderStatus",
    "OrderType",
    "PaperBrokerAdapter",
    "PaperBrokerSnapshot",
    "PaperFillPolicy",
    "PositionAccountAdapter",
    "PositionSide",
    "TimeInForce",
    "TradeStatus",
]


FUNCTION_EXPORTS = [
    export_name
    for export_name in EXPECTED_BROKER_EXPORTS
    if export_name not in CLASS_EXPORTS
]


def test_broker_exports_are_complete():
    assert brokers.__all__ == EXPECTED_BROKER_EXPORTS


def test_broker_exports_are_sorted():
    assert brokers.__all__ == sorted(brokers.__all__)


def test_broker_exports_are_unique():
    assert len(brokers.__all__) == len(set(brokers.__all__))


def test_broker_exports_exist_on_package():
    for export_name in EXPECTED_BROKER_EXPORTS:
        assert hasattr(brokers, export_name), export_name


def test_broker_class_exports_are_classes():
    for export_name in CLASS_EXPORTS:
        assert inspect.isclass(getattr(brokers, export_name)), export_name


def test_broker_function_exports_are_callables():
    for export_name in FUNCTION_EXPORTS:
        assert callable(getattr(brokers, export_name)), export_name


def test_broker_core_exports_import_directly():
    from aqos.brokers import (  # noqa: PLC0415
        BrokerAccount,
        BrokerConfig,
        BrokerExecutionHub,
        BrokerOrder,
        BrokerRegistry,
        BrokerResult,
        ExchangeHttpBrokerAdapter,
        PaperBrokerAdapter,
    )

    assert BrokerAccount.__name__ == "BrokerAccount"
    assert BrokerConfig.__name__ == "BrokerConfig"
    assert BrokerExecutionHub.__name__ == "BrokerExecutionHub"
    assert BrokerOrder.__name__ == "BrokerOrder"
    assert BrokerRegistry.__name__ == "BrokerRegistry"
    assert BrokerResult.__name__ == "BrokerResult"
    assert ExchangeHttpBrokerAdapter.__name__ == "ExchangeHttpBrokerAdapter"
    assert PaperBrokerAdapter.__name__ == "PaperBrokerAdapter"


def test_broker_export_groups_exist():
    base_exports = {
        "BrokerAuthType",
        "BrokerCapability",
        "BrokerConfig",
        "BrokerCredentials",
        "BrokerHealth",
        "BrokerResult",
        "BrokerStatus",
        "BrokerType",
        "build_broker_config",
        "broker_success",
        "broker_failure",
    }
    order_exports = {
        "BrokerOrder",
        "BrokerOrderRequest",
        "BrokerTrade",
        "OrderSide",
        "OrderStatus",
        "OrderType",
        "build_broker_order_request",
        "fill_broker_order",
    }
    paper_exports = {
        "PaperBrokerAdapter",
        "PaperBrokerSnapshot",
        "PaperFillPolicy",
        "build_paper_broker_adapter",
        "submit_paper_order",
        "cancel_paper_order",
    }
    account_exports = {
        "BrokerAccount",
        "BrokerAccountSnapshot",
        "BrokerPosition",
        "PositionAccountAdapter",
        "PositionSide",
        "build_position_account_adapter",
        "apply_trade_to_position",
    }
    registry_exports = {
        "BrokerRegistry",
        "BrokerRegistryEntry",
        "BrokerRegistrySummary",
        "build_broker_registry",
        "register_paper_broker",
        "resolve_paper_broker_adapter",
    }
    exchange_exports = {
        "ExchangeHttpBrokerAdapter",
        "ExchangeHttpMethod",
        "ExchangeHttpRequest",
        "ExchangeHttpResponse",
        "build_exchange_http_broker_adapter",
        "submit_exchange_http_order",
    }
    integration_exports = {
        "BrokerExecutionHub",
        "BrokerExecutionPayload",
        "build_broker_execution_hub",
        "submit_market_broker_order",
        "fetch_broker_account_snapshot",
    }

    exports = set(brokers.__all__)

    assert base_exports.issubset(exports)
    assert order_exports.issubset(exports)
    assert paper_exports.issubset(exports)
    assert account_exports.issubset(exports)
    assert registry_exports.issubset(exports)
    assert exchange_exports.issubset(exports)
    assert integration_exports.issubset(exports)