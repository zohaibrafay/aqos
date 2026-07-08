"""
Unit tests for AQOS product API scaffold.
"""

import pytest

from aqos.product_api import (
    ProductApiError,
    ProductApiErrorCode,
    ProductApiMeta,
    ProductApiRequestContext,
    ProductApiResponse,
    ProductApiStatus,
    build_product_api_context,
    build_product_api_error,
    build_product_api_meta,
    build_product_api_response,
    normalize_product_api_error_code,
    normalize_product_api_status,
    product_api_error,
    product_api_failure,
    product_api_success,
    safe_product_api_call,
    validate_boolean,
    validate_metadata,
    validate_non_empty_string,
    validate_non_negative_float,
    validate_percentage,
    validate_product_symbol,
    validate_product_timeframe,
    validate_string,
)


def test_product_api_status_values():
    assert ProductApiStatus.SUCCESS.value == "success"
    assert ProductApiStatus.FAILURE.value == "failure"
    assert ProductApiStatus.ERROR.value == "error"


def test_product_api_error_code_values():
    assert ProductApiErrorCode.VALIDATION_ERROR.value == "validation_error"
    assert ProductApiErrorCode.NOT_FOUND.value == "not_found"
    assert ProductApiErrorCode.UNAUTHORIZED.value == "unauthorized"
    assert ProductApiErrorCode.FORBIDDEN.value == "forbidden"
    assert ProductApiErrorCode.CONFLICT.value == "conflict"
    assert ProductApiErrorCode.RATE_LIMITED.value == "rate_limited"
    assert ProductApiErrorCode.INTERNAL_ERROR.value == "internal_error"


def test_normalize_product_api_status_accepts_enum_and_string():
    assert normalize_product_api_status(ProductApiStatus.SUCCESS) == ProductApiStatus.SUCCESS
    assert normalize_product_api_status(" SUCCESS ") == ProductApiStatus.SUCCESS
    assert normalize_product_api_status("failure") == ProductApiStatus.FAILURE
    assert normalize_product_api_status("ERROR") == ProductApiStatus.ERROR


def test_normalize_product_api_status_rejects_invalid_value():
    with pytest.raises(ValueError):
        normalize_product_api_status("bad")

    with pytest.raises(ValueError):
        normalize_product_api_status("")


def test_normalize_product_api_error_code_accepts_enum_and_string():
    assert normalize_product_api_error_code(ProductApiErrorCode.NOT_FOUND) == ProductApiErrorCode.NOT_FOUND
    assert normalize_product_api_error_code(" NOT_FOUND ") == ProductApiErrorCode.NOT_FOUND
    assert normalize_product_api_error_code("validation_error") == ProductApiErrorCode.VALIDATION_ERROR
    assert normalize_product_api_error_code("INTERNAL_ERROR") == ProductApiErrorCode.INTERNAL_ERROR


def test_normalize_product_api_error_code_rejects_invalid_value():
    with pytest.raises(ValueError):
        normalize_product_api_error_code("bad")

    with pytest.raises(ValueError):
        normalize_product_api_error_code("")


def test_validate_string():
    assert validate_string("", "Field") == ""
    assert validate_string("value", "Field") == "value"

    with pytest.raises(ValueError):
        validate_string(123, "Field")


def test_validate_non_empty_string():
    assert validate_non_empty_string(" value ", "Field") == "value"

    with pytest.raises(ValueError):
        validate_non_empty_string("", "Field")

    with pytest.raises(ValueError):
        validate_non_empty_string("   ", "Field")


def test_validate_metadata():
    metadata = {
        "source": "test",
    }

    assert validate_metadata(metadata) == metadata

    with pytest.raises(ValueError):
        validate_metadata([])


def test_validate_boolean():
    assert validate_boolean(True, "Enabled") is True
    assert validate_boolean(False, "Enabled") is False

    with pytest.raises(ValueError):
        validate_boolean("true", "Enabled")


def test_validate_non_negative_float():
    assert validate_non_negative_float(0, "Value") == 0.0
    assert validate_non_negative_float(1.5, "Value") == 1.5

    with pytest.raises(ValueError):
        validate_non_negative_float(-1, "Value")

    with pytest.raises(ValueError):
        validate_non_negative_float(True, "Value")

    with pytest.raises(ValueError):
        validate_non_negative_float("1", "Value")


def test_validate_percentage():
    assert validate_percentage(0, "Confidence") == 0.0
    assert validate_percentage(50.5, "Confidence") == 50.5
    assert validate_percentage(100, "Confidence") == 100.0

    with pytest.raises(ValueError):
        validate_percentage(-1, "Confidence")

    with pytest.raises(ValueError):
        validate_percentage(101, "Confidence")


def test_validate_product_symbol():
    assert validate_product_symbol("xauusd") == "XAUUSD"
    assert validate_product_symbol("btc/usdt") == "BTC/USDT"
    assert validate_product_symbol("eth-usdt") == "ETH-USDT"

    with pytest.raises(ValueError):
        validate_product_symbol("")

    with pytest.raises(ValueError):
        validate_product_symbol("BAD SYMBOL")

    with pytest.raises(ValueError):
        validate_product_symbol("BTC_USDT")


def test_validate_product_timeframe():
    assert validate_product_timeframe("h1") == "H1"
    assert validate_product_timeframe(" M15 ") == "M15"
    assert validate_product_timeframe("d1") == "D1"

    with pytest.raises(ValueError):
        validate_product_timeframe("")

    with pytest.raises(ValueError):
        validate_product_timeframe("H2")


def test_product_api_error_to_dict():
    error = ProductApiError(
        code="VALIDATION_ERROR",
        message=" Invalid request. ",
        details={
            "field": "symbol",
        },
    )

    assert error.to_dict() == {
        "code": "validation_error",
        "message": "Invalid request.",
        "details": {
            "field": "symbol",
        },
    }


def test_product_api_error_rejects_invalid_values():
    with pytest.raises(ValueError):
        ProductApiError(code="bad", message="Error.")

    with pytest.raises(ValueError):
        ProductApiError(code="validation_error", message="")

    with pytest.raises(ValueError):
        ProductApiError(code="validation_error", message="Error.", details=[])


def test_build_product_api_error():
    error = build_product_api_error(
        code="not_found",
        message="Missing.",
        details={
            "id": "signal-1",
        },
    )

    assert isinstance(error, ProductApiError)
    assert error.code == "not_found"
    assert error.details == {
        "id": "signal-1",
    }


def test_product_api_meta_to_dict():
    meta = ProductApiMeta(
        request_id=" req-1 ",
        api_version=" v1 ",
        timestamp="2026-01-01T00:00:00+00:00",
        source=" product ",
        metadata={
            "tenant": "demo",
        },
    )

    assert meta.to_dict() == {
        "request_id": "req-1",
        "api_version": "v1",
        "timestamp": "2026-01-01T00:00:00+00:00",
        "source": "product",
        "metadata": {
            "tenant": "demo",
        },
    }


def test_product_api_meta_rejects_invalid_values():
    with pytest.raises(ValueError):
        ProductApiMeta(request_id="")

    with pytest.raises(ValueError):
        ProductApiMeta(request_id="req-1", api_version="")

    with pytest.raises(ValueError):
        ProductApiMeta(request_id="req-1", timestamp="")

    with pytest.raises(ValueError):
        ProductApiMeta(request_id="req-1", source="")

    with pytest.raises(ValueError):
        ProductApiMeta(request_id="req-1", metadata=[])


def test_build_product_api_meta():
    meta = build_product_api_meta(
        request_id="req-1",
        timestamp="2026-01-01T00:00:00+00:00",
        metadata={
            "source": "test",
        },
    )

    assert isinstance(meta, ProductApiMeta)
    assert meta.metadata == {
        "source": "test",
    }


def test_product_api_context_to_meta_and_dict():
    context = ProductApiRequestContext(
        request_id=" req-1 ",
        user_id=" user-1 ",
        tenant_id=" tenant-1 ",
        role=" admin ",
        api_version=" v1 ",
        source=" dashboard ",
        metadata={
            "trace": "abc",
        },
    )

    payload = context.to_dict()

    assert payload == {
        "request_id": "req-1",
        "user_id": "user-1",
        "tenant_id": "tenant-1",
        "role": "admin",
        "api_version": "v1",
        "source": "dashboard",
        "metadata": {
            "trace": "abc",
        },
    }

    meta = context.to_meta()

    assert meta.request_id == " req-1 "
    assert meta.api_version == " v1 "
    assert meta.source == " dashboard "
    assert meta.metadata == {
        "user_id": "user-1",
        "tenant_id": "tenant-1",
        "role": "admin",
        "trace": "abc",
    }


def test_product_api_context_rejects_invalid_values():
    with pytest.raises(ValueError):
        ProductApiRequestContext(request_id="")

    with pytest.raises(ValueError):
        ProductApiRequestContext(request_id="req-1", user_id=123)

    with pytest.raises(ValueError):
        ProductApiRequestContext(request_id="req-1", tenant_id=123)

    with pytest.raises(ValueError):
        ProductApiRequestContext(request_id="req-1", role="")

    with pytest.raises(ValueError):
        ProductApiRequestContext(request_id="req-1", api_version="")

    with pytest.raises(ValueError):
        ProductApiRequestContext(request_id="req-1", source="")

    with pytest.raises(ValueError):
        ProductApiRequestContext(request_id="req-1", metadata=[])


def test_build_product_api_context():
    context = build_product_api_context(
        request_id="req-1",
        user_id="user-1",
        metadata={
            "source": "test",
        },
    )

    assert isinstance(context, ProductApiRequestContext)
    assert context.user_id == "user-1"
    assert context.metadata == {
        "source": "test",
    }


def test_product_api_response_to_dict_success():
    meta = build_product_api_meta(
        request_id="req-1",
        timestamp="2026-01-01T00:00:00+00:00",
    )

    response = ProductApiResponse(
        status="SUCCESS",
        data={
            "signal": "buy",
        },
        message=" Done. ",
        meta=meta,
    )

    assert response.success is True
    assert response.failed is False

    assert response.to_dict() == {
        "status": "success",
        "success": True,
        "failed": False,
        "message": "Done.",
        "data": {
            "signal": "buy",
        },
        "error": None,
        "meta": meta.to_dict(),
    }


def test_product_api_response_to_dict_failure():
    error = build_product_api_error(
        code="validation_error",
        message="Invalid.",
    )

    response = ProductApiResponse(
        status="failure",
        message="Invalid.",
        error=error,
    )

    assert response.success is False
    assert response.failed is True
    assert response.to_dict()["error"] == error.to_dict()


def test_product_api_response_rejects_invalid_values():
    with pytest.raises(ValueError):
        ProductApiResponse(status="bad")

    with pytest.raises(ValueError):
        ProductApiResponse(status="success", data=[])

    with pytest.raises(ValueError):
        ProductApiResponse(status="success", message=123)

    with pytest.raises(ValueError):
        ProductApiResponse(status="success", error="bad")

    with pytest.raises(ValueError):
        ProductApiResponse(status="success", meta="bad")


def test_build_product_api_response():
    response = build_product_api_response(
        status="success",
        data={
            "ok": True,
        },
        message="OK.",
    )

    assert isinstance(response, ProductApiResponse)
    assert response.success is True


def test_product_api_success_with_context():
    context = build_product_api_context(
        request_id="req-1",
        user_id="user-1",
    )

    response = product_api_success(
        data={
            "ok": True,
        },
        message="OK.",
        context=context,
    )

    assert response.status == ProductApiStatus.SUCCESS
    assert response.success is True
    assert response.meta is not None
    assert response.meta.request_id == "req-1"


def test_product_api_failure_with_context():
    context = build_product_api_context(
        request_id="req-1",
    )

    response = product_api_failure(
        message="Invalid request.",
        code="validation_error",
        details={
            "field": "symbol",
        },
        context=context,
    )

    assert response.status == ProductApiStatus.FAILURE
    assert response.failed is True
    assert response.error is not None
    assert response.error.code == "validation_error"
    assert response.error.details == {
        "field": "symbol",
    }


def test_product_api_error_with_context():
    context = build_product_api_context(
        request_id="req-1",
    )

    response = product_api_error(
        message="Internal error.",
        context=context,
    )

    assert response.status == ProductApiStatus.ERROR
    assert response.failed is True
    assert response.error is not None
    assert response.error.code == ProductApiErrorCode.INTERNAL_ERROR


def test_safe_product_api_call_success():
    expected = product_api_success(
        data={
            "ok": True,
        },
    )

    response = safe_product_api_call(
        lambda: expected,
        operation_name="test-operation",
    )

    assert response is expected


def test_safe_product_api_call_catches_exception():
    context = build_product_api_context(
        request_id="req-1",
    )

    def fail():
        raise RuntimeError("boom")

    response = safe_product_api_call(
        fail,
        context=context,
        operation_name="failing-operation",
    )

    assert response.status == ProductApiStatus.ERROR
    assert response.error is not None
    assert response.error.details["operation"] == "failing-operation"
    assert response.error.details["error"] == "boom"
    assert response.meta is not None
    assert response.meta.request_id == "req-1"


def test_safe_product_api_call_rejects_invalid_values():
    with pytest.raises(ValueError):
        safe_product_api_call(
            "bad",
            operation_name="test",
        )

    with pytest.raises(ValueError):
        safe_product_api_call(
            lambda: product_api_success(),
            operation_name="",
        )

    response = safe_product_api_call(
        lambda: "bad",
        operation_name="test",
    )

    assert response.status == ProductApiStatus.ERROR
    assert response.error is not None
    assert response.error.details["error_type"] == "ValueError"


def test_product_api_exports_are_sorted():
    import aqos.product_api as product_api

    assert product_api.__all__ == sorted(product_api.__all__)


def test_product_api_exports_exist():
    import aqos.product_api as product_api

    for export_name in product_api.__all__:
        assert hasattr(product_api, export_name), export_name