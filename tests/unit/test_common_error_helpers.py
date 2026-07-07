"""
Unit tests for common error helpers.
"""

import pytest

from aqos.common import (
    ErrorInfo,
    build_error_dict,
    build_error_info,
    build_not_found_error,
    build_type_error,
    build_validation_error,
    collect_errors,
    combine_error_messages,
    exception_to_dict,
    exception_to_error_info,
    first_error,
    format_error_message,
    get_exception_name,
    has_errors,
    normalize_error_code,
    normalize_error_message,
    raise_if,
    raise_if_none,
    safe_execute,
)


def test_error_info_to_dict():
    error = ErrorInfo(
        code="VALIDATION_ERROR",
        message="Invalid payload.",
        category="validation",
        details={
            "field": "symbol",
        },
    )

    assert error.to_dict() == {
        "code": "VALIDATION_ERROR",
        "message": "Invalid payload.",
        "category": "validation",
        "details": {
            "field": "symbol",
        },
    }


def test_normalize_error_code():
    assert normalize_error_code("validation error") == "VALIDATION_ERROR"
    assert normalize_error_code("not-found") == "NOT_FOUND"
    assert normalize_error_code("TYPE_ERROR") == "TYPE_ERROR"


def test_normalize_error_code_rejects_invalid_type():
    with pytest.raises(TypeError):
        normalize_error_code(123)


def test_normalize_error_code_rejects_empty_value():
    with pytest.raises(ValueError):
        normalize_error_code("")


def test_normalize_error_message():
    assert normalize_error_message(" Invalid payload. ") == "Invalid payload."


def test_normalize_error_message_rejects_invalid_type():
    with pytest.raises(TypeError):
        normalize_error_message(123)


def test_normalize_error_message_rejects_empty_value():
    with pytest.raises(ValueError):
        normalize_error_message("")


def test_build_error_info():
    error = build_error_info(
        code="validation-error",
        message="Invalid payload.",
        category="Validation",
        details={
            "field": "symbol",
        },
    )

    assert error == ErrorInfo(
        code="VALIDATION_ERROR",
        message="Invalid payload.",
        category="validation",
        details={
            "field": "symbol",
        },
    )


def test_build_error_info_defaults():
    error = build_error_info(
        code="general",
        message="Something failed.",
    )

    assert error.code == "GENERAL"
    assert error.message == "Something failed."
    assert error.category == "general"
    assert error.details == {}


def test_build_error_info_rejects_invalid_category_type():
    with pytest.raises(TypeError):
        build_error_info(
            code="error",
            message="Message.",
            category=123,
        )


def test_build_error_info_rejects_empty_category():
    with pytest.raises(ValueError):
        build_error_info(
            code="error",
            message="Message.",
            category="",
        )


def test_build_error_info_rejects_invalid_details_type():
    with pytest.raises(TypeError):
        build_error_info(
            code="error",
            message="Message.",
            details="invalid",
        )


def test_build_error_dict():
    assert build_error_dict(
        code="not-found",
        message="Missing.",
        category="not_found",
        details={
            "id": "x",
        },
    ) == {
        "code": "NOT_FOUND",
        "message": "Missing.",
        "category": "not_found",
        "details": {
            "id": "x",
        },
    }


def test_build_not_found_error():
    error = build_not_found_error(
        resource="Backtest run",
        identifier="run-1",
    )

    assert error.code == "NOT_FOUND"
    assert error.message == "Backtest run does not exist: run-1"
    assert error.category == "not_found"
    assert error.details == {
        "resource": "Backtest run",
        "identifier": "run-1",
    }


def test_build_validation_error():
    error = build_validation_error(
        message="Invalid symbol.",
        details={
            "symbol": "",
        },
    )

    assert error.code == "VALIDATION_ERROR"
    assert error.message == "Invalid symbol."
    assert error.category == "validation"
    assert error.details == {
        "symbol": "",
    }


def test_build_type_error():
    error = build_type_error(
        name="Payload",
        expected_type="a dictionary",
    )

    assert error.code == "TYPE_ERROR"
    assert error.message == "Payload must be a dictionary."
    assert error.category == "type"
    assert error.details == {
        "name": "Payload",
        "expected_type": "a dictionary",
    }


def test_get_exception_name():
    exc = ValueError("Invalid value.")

    assert get_exception_name(exc) == "ValueError"


def test_get_exception_name_rejects_invalid_type():
    with pytest.raises(TypeError):
        get_exception_name("invalid")


def test_exception_to_error_info():
    exc = ValueError("Invalid value.")

    error = exception_to_error_info(exc)

    assert error.code == "VALUEERROR"
    assert error.message == "Invalid value."
    assert error.category == "exception"
    assert error.details == {
        "exception_type": "ValueError",
    }


def test_exception_to_error_info_with_custom_code_and_category():
    exc = ValueError("Invalid value.")

    error = exception_to_error_info(
        exc=exc,
        code="validation_error",
        category="validation",
    )

    assert error.code == "VALIDATION_ERROR"
    assert error.category == "validation"


def test_exception_to_error_info_without_type():
    exc = ValueError("Invalid value.")

    error = exception_to_error_info(
        exc=exc,
        include_type=False,
    )

    assert error.details == {}


def test_exception_to_error_info_rejects_invalid_exception():
    with pytest.raises(TypeError):
        exception_to_error_info("invalid")


def test_exception_to_dict():
    exc = ValueError("Invalid value.")

    assert exception_to_dict(exc) == {
        "code": "VALUEERROR",
        "message": "Invalid value.",
        "category": "exception",
        "details": {
            "exception_type": "ValueError",
        },
    }


def test_format_error_message_without_prefix():
    assert format_error_message(" Invalid value. ") == "Invalid value."


def test_format_error_message_with_prefix():
    assert format_error_message(
        message="Invalid value.",
        prefix="Validation",
    ) == "Validation: Invalid value."


def test_collect_errors():
    error_info = build_validation_error("Invalid symbol.")

    errors = collect_errors(
        " Error one. ",
        None,
        "",
        error_info,
        {
            "message": "Error two.",
        },
    )

    assert errors == [
        "Error one.",
        {
            "code": "VALIDATION_ERROR",
            "message": "Invalid symbol.",
            "category": "validation",
            "details": {},
        },
        {
            "message": "Error two.",
        },
    ]


def test_collect_errors_rejects_invalid_type():
    with pytest.raises(TypeError):
        collect_errors(123)


def test_has_errors_true():
    assert has_errors(["Error."]) is True


def test_has_errors_false():
    assert has_errors([]) is False


def test_has_errors_rejects_invalid_type():
    with pytest.raises(TypeError):
        has_errors("invalid")


def test_first_error():
    assert first_error(["Error one.", "Error two."]) == "Error one."


def test_first_error_default():
    assert first_error([], default="No error.") == "No error."


def test_first_error_rejects_invalid_type():
    with pytest.raises(TypeError):
        first_error("invalid")


def test_combine_error_messages():
    assert combine_error_messages(
        [
            "Error one.",
            "",
            " Error two. ",
        ]
    ) == "Error one.; Error two."


def test_combine_error_messages_with_custom_separator():
    assert combine_error_messages(
        [
            "Error one.",
            "Error two.",
        ],
        separator=" | ",
    ) == "Error one. | Error two."


def test_combine_error_messages_rejects_invalid_errors_type():
    with pytest.raises(TypeError):
        combine_error_messages("invalid")


def test_combine_error_messages_rejects_invalid_separator_type():
    with pytest.raises(TypeError):
        combine_error_messages([], separator=123)


def test_raise_if_raises():
    with pytest.raises(ValueError):
        raise_if(
            condition=True,
            exception=ValueError("Invalid value."),
        )


def test_raise_if_does_not_raise():
    assert raise_if(
        condition=False,
        exception=ValueError("Invalid value."),
    ) is None


def test_raise_if_rejects_invalid_condition_type():
    with pytest.raises(TypeError):
        raise_if(
            condition="true",
            exception=ValueError("Invalid value."),
        )


def test_raise_if_rejects_invalid_exception_type():
    with pytest.raises(TypeError):
        raise_if(
            condition=True,
            exception="invalid",
        )


def test_raise_if_none_raises():
    with pytest.raises(ValueError):
        raise_if_none(
            value=None,
            exception=ValueError("Missing value."),
        )


def test_raise_if_none_returns_value():
    assert raise_if_none(
        value="XAUUSD",
        exception=ValueError("Missing value."),
    ) == "XAUUSD"


def test_raise_if_none_rejects_invalid_exception_type():
    with pytest.raises(TypeError):
        raise_if_none(
            value=None,
            exception="invalid",
        )


def test_safe_execute_success():
    result = safe_execute(
        lambda value: value * 2,
        5,
    )

    assert result == 10


def test_safe_execute_returns_default_on_expected_exception():
    result = safe_execute(
        lambda: 1 / 0,
        default="failed",
    )

    assert result == "failed"


def test_safe_execute_does_not_catch_unexpected_exception():
    with pytest.raises(ValueError):
        safe_execute(
            lambda: (_ for _ in ()).throw(ValueError("Invalid value.")),
            expected_exceptions=(KeyError,),
        )


def test_safe_execute_rejects_invalid_function():
    with pytest.raises(TypeError):
        safe_execute("invalid")


def test_safe_execute_rejects_invalid_expected_exceptions_type():
    with pytest.raises(TypeError):
        safe_execute(
            lambda: "ok",
            expected_exceptions=Exception,
        )