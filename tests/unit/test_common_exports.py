"""
Unit tests for common package exports.
"""

import aqos.common as common


EXPECTED_EXPORTS = [
    "AQOS_FULL_NAME",
    "AQOS_NAME",
    "BUY_SIGNAL",
    "DATE_FORMAT",
    "DEFAULT_ACCOUNT_BALANCE",
    "DEFAULT_MAX_RISK_PERCENT",
    "DEFAULT_MEMORY_IMPORTANCE",
    "DEFAULT_NAMESPACE",
    "DEFAULT_RISK_PERCENT",
    "DEFAULT_SEARCH_LIMIT",
    "DEFAULT_SOURCE",
    "DEFAULT_SYMBOL",
    "DEFAULT_TIMEFRAME",
    "EXPERIMENT_NAMESPACE",
    "ErrorInfo",
    "HOLD_SIGNAL",
    "ID_SEPARATOR",
    "ISO_DATETIME_FORMAT",
    "LONG_POSITION",
    "MEMORY_NAMESPACE",
    "MESSAGE_NOT_CONFIGURED",
    "MESSAGE_NOT_FOUND",
    "MESSAGE_TRADE_ALLOWED",
    "MODEL_NAMESPACE",
    "NO_POSITION",
    "OHLCV_COLUMNS",
    "PRICE_COLUMNS",
    "RESEARCH_NAMESPACE",
    "SELL_SIGNAL",
    "SHORT_POSITION",
    "STATUS_ERROR",
    "STATUS_OK",
    "VALID_EXPERIMENT_STATUSES",
    "VALID_IMPACTS",
    "VALID_MEMORY_TYPES",
    "VALID_ORDER_STATUSES",
    "VALID_ORDER_TYPES",
    "VALID_POSITION_STATUSES",
    "VALID_SENTIMENTS",
    "VALID_SIDES",
    "VALID_SIGNALS",
    "VALID_TIMEFRAMES",
    "add_days",
    "add_hours",
    "add_minutes",
    "add_seconds",
    "build_compound_id",
    "build_error_dict",
    "build_error_info",
    "build_not_found_error",
    "build_timestamp_id",
    "build_type_error",
    "build_validation_error",
    "clamp",
    "collect_errors",
    "combine_error_messages",
    "compact_dict",
    "cumulative_sum",
    "datetime_to_timestamp",
    "days_between",
    "deep_merge_dicts",
    "ensure_unique_id",
    "exception_to_dict",
    "exception_to_error_info",
    "first_error",
    "flatten_dict",
    "format_date",
    "format_datetime",
    "format_error_message",
    "from_json",
    "generate_prefixed_id",
    "generate_short_id",
    "generate_uuid",
    "get_exception_name",
    "has_errors",
    "hours_between",
    "is_future",
    "is_past",
    "is_valid_id",
    "is_within_window",
    "max_drawdown",
    "mean",
    "median",
    "merge_dicts",
    "minutes_between",
    "normalize_error_code",
    "normalize_error_message",
    "normalize_id",
    "normalize_id_part",
    "normalize_min_max",
    "normalize_time_payload",
    "parse_date",
    "parse_datetime",
    "percentage_change",
    "percentage_return",
    "profit_factor",
    "raise_if",
    "raise_if_none",
    "remove_none_values",
    "rolling_mean",
    "round_to_decimals",
    "safe_divide",
    "safe_execute",
    "safe_get",
    "seconds_between",
    "serialize_dict",
    "serialize_list",
    "standard_deviation",
    "timestamp_to_datetime",
    "to_json",
    "to_serializable",
    "to_utc",
    "today_utc",
    "unflatten_dict",
    "utc_now",
    "utc_now_iso",
    "validate_account_balance",
    "validate_id",
    "validate_impact",
    "validate_memory_type",
    "validate_metadata",
    "validate_non_empty_dict",
    "validate_non_empty_list",
    "validate_non_empty_string",
    "validate_non_negative_number",
    "validate_number",
    "validate_numbers",
    "validate_ohlcv_columns",
    "validate_ohlcv_record",
    "validate_one_of",
    "validate_order_type",
    "validate_payload",
    "validate_positive_integer",
    "validate_positive_number",
    "validate_prefix",
    "validate_price",
    "validate_quantity",
    "validate_ratio",
    "validate_required_columns",
    "validate_required_keys",
    "validate_risk_percent",
    "validate_sentiment",
    "validate_separator",
    "validate_side",
    "validate_signal",
    "validate_symbol",
    "validate_timeframe",
    "variance",
    "weighted_average",
    "win_rate",
]


def test_common_all_exports_match_expected_exports():
    assert sorted(common.__all__) == sorted(EXPECTED_EXPORTS)


def test_common_exports_are_available():
    for export_name in EXPECTED_EXPORTS:
        assert hasattr(common, export_name), export_name


def test_common_constants_are_exported():
    assert common.AQOS_NAME == "AQOS"
    assert common.DEFAULT_SYMBOL == "XAUUSD"
    assert common.DEFAULT_TIMEFRAME == "H1"
    assert common.BUY_SIGNAL == "buy"


def test_common_validator_exports_are_callable():
    assert callable(common.validate_symbol)
    assert callable(common.validate_timeframe)
    assert callable(common.validate_price)
    assert callable(common.validate_risk_percent)


def test_common_id_helper_exports_are_callable():
    assert callable(common.generate_uuid)
    assert callable(common.generate_prefixed_id)
    assert callable(common.build_compound_id)
    assert callable(common.validate_id)


def test_common_time_utility_exports_are_callable():
    assert callable(common.utc_now)
    assert callable(common.parse_datetime)
    assert callable(common.format_datetime)
    assert callable(common.is_within_window)


def test_common_serialization_exports_are_callable():
    assert callable(common.to_serializable)
    assert callable(common.to_json)
    assert callable(common.from_json)
    assert callable(common.flatten_dict)


def test_common_math_exports_are_callable():
    assert callable(common.safe_divide)
    assert callable(common.mean)
    assert callable(common.max_drawdown)
    assert callable(common.win_rate)


def test_common_error_exports_are_callable():
    assert callable(common.build_error_info)
    assert callable(common.exception_to_dict)
    assert callable(common.safe_execute)
    assert common.ErrorInfo is not None