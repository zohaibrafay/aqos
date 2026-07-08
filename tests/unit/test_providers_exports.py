"""
Unit tests for AQOS providers package exports.
"""

import inspect

import aqos.providers as providers


EXPECTED_PROVIDER_EXPORTS = sorted(
    [
        "AqosMarketDataPayload",
        "CsvOhlcvColumnMap",
        "CsvOhlcvLoadRequest",
        "HistoricalDataCoverage",
        "HistoricalOhlcvAdapter",
        "HistoricalOhlcvRequest",
        "HttpMarketDataProvider",
        "HttpProviderMethod",
        "HttpProviderRequest",
        "HttpProviderResponse",
        "LiveMarketDataAdapter",
        "LiveMarketDataSnapshot",
        "LiveQuoteRequest",
        "LocalCsvOhlcvProvider",
        "MarketDataBatch",
        "MarketDataPriceType",
        "MarketDataQuality",
        "MarketDataRequestType",
        "MarketDataTimeframe",
        "MarketQuote",
        "MarketTick",
        "OhlcvCandle",
        "ProviderAuthType",
        "ProviderCapability",
        "ProviderConfig",
        "ProviderCredentials",
        "ProviderHealth",
        "ProviderIntegrationHub",
        "ProviderRegistry",
        "ProviderRegistryEntry",
        "ProviderRegistrySummary",
        "ProviderResult",
        "ProviderStatus",
        "ProviderType",
        "TickDataRequest",
        "build_aqos_market_data_payload",
        "build_csv_ohlcv_column_map",
        "build_csv_ohlcv_load_request",
        "build_historical_batch_request",
        "build_historical_data_coverage",
        "build_historical_ohlcv_adapter",
        "build_historical_ohlcv_request",
        "build_http_market_data_provider",
        "build_http_provider_request",
        "build_http_provider_response",
        "build_live_market_data_adapter",
        "build_live_market_data_snapshot",
        "build_live_quote_request",
        "build_live_quote_request_for_adapter",
        "build_local_csv_ohlcv_provider",
        "build_market_data_batch",
        "build_market_quote",
        "build_market_tick",
        "build_ohlcv_candle",
        "build_provider_config",
        "build_provider_credentials",
        "build_provider_health",
        "build_provider_integration_hub",
        "build_provider_registry",
        "build_provider_registry_entry",
        "build_provider_result",
        "build_sample_provider_integration_hub",
        "build_sample_provider_registry",
        "build_tick_data_request",
        "build_tick_data_request_for_adapter",
        "candles_to_ohlcv_rows",
        "create_sample_historical_adapter",
        "create_sample_live_adapter",
        "default_http_transport",
        "fetch_historical_market_data",
        "fetch_historical_ohlcv",
        "fetch_http_historical_ohlcv",
        "fetch_http_live_quote",
        "fetch_http_market_ticks",
        "fetch_live_market_quote",
        "fetch_live_market_ticks",
        "fetch_live_quote",
        "fetch_market_ticks",
        "filter_historical_candles",
        "historical_batch_from_rows",
        "historical_batch_key",
        "historical_batch_to_rows",
        "http_provider_error_result",
        "integration_failure",
        "is_success_http_status",
        "join_http_url",
        "json_payload_to_market_quote",
        "json_payload_to_market_ticks",
        "json_payload_to_ohlcv_rows",
        "live_symbol_key",
        "load_csv_ohlcv_into_adapter",
        "market_data_batch_to_provider_result",
        "market_data_batch_to_service_payload",
        "market_data_error_result",
        "market_quote_to_provider_result",
        "market_ticks_to_provider_result",
        "mask_secret",
        "normalize_csv_ohlcv_row",
        "normalize_http_provider_method",
        "normalize_market_data_price_type",
        "normalize_market_data_quality",
        "normalize_market_data_request_type",
        "normalize_market_data_timeframe",
        "normalize_provider_auth_type",
        "normalize_provider_capability",
        "normalize_provider_status",
        "normalize_provider_status_value",
        "normalize_provider_type",
        "normalize_provider_type_value",
        "ohlcv_rows_to_candles",
        "provider_failure",
        "provider_registry_error_result",
        "provider_registry_to_result",
        "provider_result_batch",
        "provider_result_quote",
        "provider_result_ticks",
        "provider_success",
        "quote_payload_to_market_quote",
        "read_ohlcv_csv_rows",
        "register_historical_adapter",
        "register_live_adapter",
        "register_market_data_provider",
        "resolve_historical_adapter",
        "resolve_live_adapter",
        "summarize_provider_registry_entries",
        "tick_payload_to_market_tick",
        "validate_aqos_market_data_rows",
        "validate_aqos_market_data_ticks",
        "validate_csv_columns",
        "validate_csv_file_path",
        "validate_historical_batches",
        "validate_historical_provider_config",
        "validate_http_headers",
        "validate_http_params",
        "validate_http_provider_config",
        "validate_http_status_code",
        "validate_http_url",
        "validate_live_provider_config",
        "validate_live_quotes_dict",
        "validate_live_ticks_dict",
        "validate_market_data_limit",
        "validate_market_quotes",
        "validate_market_symbol",
        "validate_market_ticks",
        "validate_metadata",
        "validate_non_empty_string",
        "validate_non_negative_float",
        "validate_ohlcv_candles",
        "validate_positive_float",
        "validate_positive_integer",
        "validate_provider_capabilities",
        "validate_provider_config_object",
        "validate_provider_integration_hub",
        "validate_provider_registry",
        "validate_provider_registry_entries",
        "validate_string",
        "validate_symbol_list",
        "write_ohlcv_csv_rows",
    ],
)


CLASS_EXPORTS = [
    "AqosMarketDataPayload",
    "CsvOhlcvColumnMap",
    "CsvOhlcvLoadRequest",
    "HistoricalDataCoverage",
    "HistoricalOhlcvAdapter",
    "HistoricalOhlcvRequest",
    "HttpMarketDataProvider",
    "HttpProviderMethod",
    "HttpProviderRequest",
    "HttpProviderResponse",
    "LiveMarketDataAdapter",
    "LiveMarketDataSnapshot",
    "LiveQuoteRequest",
    "LocalCsvOhlcvProvider",
    "MarketDataBatch",
    "MarketDataPriceType",
    "MarketDataQuality",
    "MarketDataRequestType",
    "MarketDataTimeframe",
    "MarketQuote",
    "MarketTick",
    "OhlcvCandle",
    "ProviderAuthType",
    "ProviderCapability",
    "ProviderConfig",
    "ProviderCredentials",
    "ProviderHealth",
    "ProviderIntegrationHub",
    "ProviderRegistry",
    "ProviderRegistryEntry",
    "ProviderRegistrySummary",
    "ProviderResult",
    "ProviderStatus",
    "ProviderType",
    "TickDataRequest",
]


FUNCTION_EXPORTS = [
    export_name
    for export_name in EXPECTED_PROVIDER_EXPORTS
    if export_name not in CLASS_EXPORTS
]


def test_provider_exports_are_complete():
    assert providers.__all__ == EXPECTED_PROVIDER_EXPORTS


def test_provider_exports_are_sorted():
    assert providers.__all__ == sorted(providers.__all__)


def test_provider_exports_are_unique():
    assert len(providers.__all__) == len(set(providers.__all__))


def test_provider_exports_exist_on_package():
    for export_name in EXPECTED_PROVIDER_EXPORTS:
        assert hasattr(providers, export_name), export_name


def test_provider_class_exports_are_classes():
    for export_name in CLASS_EXPORTS:
        assert inspect.isclass(getattr(providers, export_name)), export_name


def test_provider_function_exports_are_callables():
    for export_name in FUNCTION_EXPORTS:
        assert callable(getattr(providers, export_name)), export_name


def test_provider_core_exports_import_directly():
    from aqos.providers import (  # noqa: PLC0415
        AqosMarketDataPayload,
        HistoricalOhlcvAdapter,
        HttpMarketDataProvider,
        LiveMarketDataAdapter,
        MarketDataBatch,
        ProviderConfig,
        ProviderRegistry,
        ProviderResult,
    )

    assert AqosMarketDataPayload.__name__ == "AqosMarketDataPayload"
    assert HistoricalOhlcvAdapter.__name__ == "HistoricalOhlcvAdapter"
    assert HttpMarketDataProvider.__name__ == "HttpMarketDataProvider"
    assert LiveMarketDataAdapter.__name__ == "LiveMarketDataAdapter"
    assert MarketDataBatch.__name__ == "MarketDataBatch"
    assert ProviderConfig.__name__ == "ProviderConfig"
    assert ProviderRegistry.__name__ == "ProviderRegistry"
    assert ProviderResult.__name__ == "ProviderResult"


def test_provider_export_groups_exist():
    base_exports = {
        "ProviderAuthType",
        "ProviderCapability",
        "ProviderConfig",
        "ProviderCredentials",
        "ProviderHealth",
        "ProviderResult",
        "ProviderStatus",
        "ProviderType",
    }
    market_data_exports = {
        "HistoricalOhlcvRequest",
        "LiveQuoteRequest",
        "MarketDataBatch",
        "MarketQuote",
        "MarketTick",
        "OhlcvCandle",
        "TickDataRequest",
    }
    historical_exports = {
        "HistoricalDataCoverage",
        "HistoricalOhlcvAdapter",
        "build_historical_ohlcv_adapter",
        "fetch_historical_ohlcv",
    }
    live_exports = {
        "LiveMarketDataAdapter",
        "LiveMarketDataSnapshot",
        "build_live_market_data_adapter",
        "fetch_live_quote",
        "fetch_market_ticks",
    }
    registry_exports = {
        "ProviderRegistry",
        "ProviderRegistryEntry",
        "ProviderRegistrySummary",
        "resolve_historical_adapter",
        "resolve_live_adapter",
    }
    csv_exports = {
        "CsvOhlcvColumnMap",
        "CsvOhlcvLoadRequest",
        "LocalCsvOhlcvProvider",
        "read_ohlcv_csv_rows",
        "write_ohlcv_csv_rows",
    }
    http_exports = {
        "HttpMarketDataProvider",
        "HttpProviderRequest",
        "HttpProviderResponse",
        "fetch_http_historical_ohlcv",
        "fetch_http_live_quote",
    }
    integration_exports = {
        "AqosMarketDataPayload",
        "ProviderIntegrationHub",
        "build_provider_integration_hub",
        "fetch_historical_market_data",
        "fetch_live_market_quote",
    }

    exports = set(providers.__all__)

    assert base_exports.issubset(exports)
    assert market_data_exports.issubset(exports)
    assert historical_exports.issubset(exports)
    assert live_exports.issubset(exports)
    assert registry_exports.issubset(exports)
    assert csv_exports.issubset(exports)
    assert http_exports.issubset(exports)
    assert integration_exports.issubset(exports)