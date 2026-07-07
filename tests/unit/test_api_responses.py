"""
Unit tests for AQOS API response envelopes.
"""

import pytest

from aqos.api import (
    ApiError,
    ApiResponse,
    ApiStatus,
    api_error,
    api_failure,
    api_success,
    build_api_metadata,
    exception_failure,
    not_found_failure,
    validation_failure,
)


def test_api_error_to_dict_minimal():
    error = ApiError(
        code="validation_error",
        message="Invalid symbol.",
    )

    assert error.to_dict() == {
        "code": "VALIDATION_ERROR",
        "message": "Invalid symbol.",
    }


def test_api_error_to_dict_with_field_and_details():
    error = ApiError(
        code="validation_error",
        message="Invalid timeframe.",
        field="timeframe",
        details={
            "allowed": ["M1", "M5", "H1"],
        },
    )

    assert error.to_dict() == {
        "code": "VALIDATION_ERROR",
        "message": "Invalid timeframe.",
        "field": "timeframe",
        "details": {
            "allowed": ["M1", "M5", "H1"],
        },
    }


def test_api_error_rejects_invalid_values():
    with pytest.raises(ValueError, match="API error code"):
        ApiError(code="", message="Invalid.")

    with pytest.raises(ValueError, match="API error message"):
        ApiError(code="INVALID", message="")

    with pytest.raises(ValueError, match="API error field"):
        ApiError(code="INVALID", message="Invalid.", field=123)

    with pytest.raises(ValueError, match="API error details"):
        ApiError(code="INVALID", message="Invalid.", details=[])


def test_api_success_response():
    response = api_success(
        message="Market state loaded.",
        data={
            "symbol": "XAUUSD",
            "timeframe": "H1",
        },
        request_id="request-1",
    )

    assert response.success is True
    assert response.status == ApiStatus.SUCCESS
    assert response.message == "Market state loaded."
    assert response.data == {
        "symbol": "XAUUSD",
        "timeframe": "H1",
    }
    assert response.errors == []
    assert response.metadata["request_id"] == "request-1"
    assert response.metadata["source"] == "aqos-api"
    assert "timestamp" in response.metadata


def test_api_success_to_dict():
    response = api_success(
        message="Strategy signal generated.",
        data={
            "signal": "buy",
        },
    )

    payload = response.to_dict()

    assert payload["success"] is True
    assert payload["status"] == "success"
    assert payload["message"] == "Strategy signal generated."
    assert payload["data"] == {
        "signal": "buy",
    }
    assert payload["errors"] == []
    assert payload["metadata"]["source"] == "aqos-api"


def test_api_failure_response():
    error = api_error(
        code="RISK_REJECTED",
        message="Trade rejected by risk engine.",
        field="risk_percent",
        details={
            "max_risk_percent": 0.02,
        },
    )

    response = api_failure(
        message="Risk check failed.",
        errors=[error],
        request_id="request-2",
    )

    assert response.success is False
    assert response.status == ApiStatus.ERROR
    assert response.message == "Risk check failed."
    assert response.data is None
    assert len(response.errors) == 1
    assert response.errors[0].code == "RISK_REJECTED"
    assert response.metadata["request_id"] == "request-2"


def test_api_failure_to_dict():
    response = api_failure(
        message="Execution failed.",
        errors=[
            api_error(
                code="EXECUTION_ERROR",
                message="Order could not be placed.",
            )
        ],
    )

    payload = response.to_dict()

    assert payload["success"] is False
    assert payload["status"] == "error"
    assert payload["message"] == "Execution failed."
    assert payload["data"] is None
    assert payload["errors"] == [
        {
            "code": "EXECUTION_ERROR",
            "message": "Order could not be placed.",
        }
    ]


def test_validation_failure_response():
    response = validation_failure(
        message="Invalid symbol.",
        field="symbol",
        details={
            "value": "",
        },
        request_id="request-3",
    )

    payload = response.to_dict()

    assert payload["success"] is False
    assert payload["status"] == "error"
    assert payload["message"] == "Invalid symbol."
    assert payload["errors"][0]["code"] == "VALIDATION_ERROR"
    assert payload["errors"][0]["field"] == "symbol"
    assert payload["errors"][0]["details"] == {
        "value": "",
    }
    assert payload["metadata"]["request_id"] == "request-3"


def test_not_found_failure_response():
    response = not_found_failure(
        resource="Backtest run",
        identifier="run-1",
    )

    payload = response.to_dict()

    assert payload["success"] is False
    assert payload["status"] == "error"
    assert payload["message"] == "Backtest run was not found."
    assert payload["errors"][0]["code"] == "NOT_FOUND"
    assert payload["errors"][0]["field"] == "identifier"
    assert payload["errors"][0]["details"] == {
        "resource": "Backtest run",
        "identifier": "run-1",
    }


def test_exception_failure_response():
    exception = ValueError("Invalid API payload.")

    response = exception_failure(
        exception,
        request_id="request-4",
    )

    payload = response.to_dict()

    assert payload["success"] is False
    assert payload["status"] == "error"
    assert payload["message"] == "Unexpected API error."
    assert payload["errors"][0]["code"] == "VALUEERROR"
    assert payload["errors"][0]["message"] == "Invalid API payload."
    assert payload["errors"][0]["details"] == {
        "exception_type": "ValueError",
    }
    assert payload["metadata"]["request_id"] == "request-4"


def test_build_api_metadata_with_extra_values():
    metadata = build_api_metadata(
        request_id="request-5",
        source="aqos-test",
        extra={
            "module": "health",
        },
    )

    assert metadata["request_id"] == "request-5"
    assert metadata["source"] == "aqos-test"
    assert metadata["module"] == "health"
    assert "timestamp" in metadata


def test_api_response_rejects_invalid_values():
    with pytest.raises(ValueError, match="API response success"):
        ApiResponse(success="yes", message="Invalid.")

    with pytest.raises(ValueError, match="API response message"):
        ApiResponse(success=True, message="")

    with pytest.raises(ValueError, match="API response errors"):
        ApiResponse(success=False, message="Invalid.", errors={})

    with pytest.raises(ValueError, match="API response errors"):
        ApiResponse(
            success=False,
            message="Invalid.",
            errors=["not-api-error"],
        )

    with pytest.raises(ValueError, match="API response metadata"):
        ApiResponse(success=True, message="Invalid.", metadata=[])