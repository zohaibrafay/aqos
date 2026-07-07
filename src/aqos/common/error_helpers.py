"""
Common error helpers.

Defines reusable error formatting, normalization, collection,
and exception conversion helpers for AQOS modules.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class ErrorInfo:
    """
    Structured error information.
    """

    code: str
    message: str
    category: str = "general"
    details: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """
        Convert error info to dictionary.
        """

        return {
            "code": self.code,
            "message": self.message,
            "category": self.category,
            "details": self.details,
        }


def normalize_error_code(
    value: str,
) -> str:
    """
    Normalize an error code.
    """

    if not isinstance(value, str):
        raise TypeError("Error code must be a string.")

    normalized = value.strip().replace("-", "_").replace(" ", "_").upper()

    if not normalized:
        raise ValueError("Error code cannot be empty.")

    return normalized


def normalize_error_message(
    value: str,
) -> str:
    """
    Normalize an error message.
    """

    if not isinstance(value, str):
        raise TypeError("Error message must be a string.")

    normalized = value.strip()

    if not normalized:
        raise ValueError("Error message cannot be empty.")

    return normalized


def build_error_info(
    code: str,
    message: str,
    category: str = "general",
    details: dict[str, Any] | None = None,
) -> ErrorInfo:
    """
    Build structured error info.
    """

    if not isinstance(category, str):
        raise TypeError("Error category must be a string.")

    normalized_category = category.strip().lower()

    if not normalized_category:
        raise ValueError("Error category cannot be empty.")

    if details is not None and not isinstance(details, dict):
        raise TypeError("Error details must be a dictionary.")

    return ErrorInfo(
        code=normalize_error_code(code),
        message=normalize_error_message(message),
        category=normalized_category,
        details=details or {},
    )


def build_error_dict(
    code: str,
    message: str,
    category: str = "general",
    details: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """
    Build structured error dictionary.
    """

    return build_error_info(
        code=code,
        message=message,
        category=category,
        details=details,
    ).to_dict()


def build_not_found_error(
    resource: str,
    identifier: str,
) -> ErrorInfo:
    """
    Build not-found error info.
    """

    return build_error_info(
        code="not_found",
        message=f"{resource} does not exist: {identifier}",
        category="not_found",
        details={
            "resource": resource,
            "identifier": identifier,
        },
    )


def build_validation_error(
    message: str,
    details: dict[str, Any] | None = None,
) -> ErrorInfo:
    """
    Build validation error info.
    """

    return build_error_info(
        code="validation_error",
        message=message,
        category="validation",
        details=details,
    )


def build_type_error(
    name: str,
    expected_type: str,
) -> ErrorInfo:
    """
    Build type error info.
    """

    return build_error_info(
        code="type_error",
        message=f"{name} must be {expected_type}.",
        category="type",
        details={
            "name": name,
            "expected_type": expected_type,
        },
    )


def get_exception_name(
    exc: BaseException,
) -> str:
    """
    Return exception class name.
    """

    if not isinstance(exc, BaseException):
        raise TypeError("Exception value must be an exception.")

    return exc.__class__.__name__


def exception_to_error_info(
    exc: BaseException,
    code: str | None = None,
    category: str = "exception",
    include_type: bool = True,
) -> ErrorInfo:
    """
    Convert exception to ErrorInfo.
    """

    if not isinstance(exc, BaseException):
        raise TypeError("Exception value must be an exception.")

    details: dict[str, Any] = {}

    if include_type:
        details["exception_type"] = get_exception_name(exc)

    return build_error_info(
        code=code or get_exception_name(exc),
        message=str(exc) or get_exception_name(exc),
        category=category,
        details=details,
    )


def exception_to_dict(
    exc: BaseException,
    code: str | None = None,
    category: str = "exception",
    include_type: bool = True,
) -> dict[str, Any]:
    """
    Convert exception to dictionary.
    """

    return exception_to_error_info(
        exc=exc,
        code=code,
        category=category,
        include_type=include_type,
    ).to_dict()


def format_error_message(
    message: str,
    prefix: str | None = None,
) -> str:
    """
    Format an error message with optional prefix.
    """

    normalized_message = normalize_error_message(message)

    if prefix is None:
        return normalized_message

    normalized_prefix = normalize_error_message(prefix)

    return f"{normalized_prefix}: {normalized_message}"


def collect_errors(
    *errors: str | ErrorInfo | dict[str, Any] | None,
) -> list[str | dict[str, Any]]:
    """
    Collect non-empty errors into a list.
    """

    collected: list[str | dict[str, Any]] = []

    for error in errors:
        if error is None:
            continue

        if isinstance(error, ErrorInfo):
            collected.append(error.to_dict())
            continue

        if isinstance(error, dict):
            if error:
                collected.append(error)
            continue

        if isinstance(error, str):
            normalized = error.strip()

            if normalized:
                collected.append(normalized)

            continue

        raise TypeError("Errors must be strings, dictionaries, ErrorInfo, or None.")

    return collected


def has_errors(
    errors: list[Any],
) -> bool:
    """
    Return True if errors list has items.
    """

    if not isinstance(errors, list):
        raise TypeError("Errors must be a list.")

    return len(errors) > 0


def first_error(
    errors: list[Any],
    default: Any = None,
) -> Any:
    """
    Return first error or default.
    """

    if not isinstance(errors, list):
        raise TypeError("Errors must be a list.")

    if not errors:
        return default

    return errors[0]


def combine_error_messages(
    errors: list[str],
    separator: str = "; ",
) -> str:
    """
    Combine error messages into one string.
    """

    if not isinstance(errors, list):
        raise TypeError("Errors must be a list.")

    if not isinstance(separator, str):
        raise TypeError("Separator must be a string.")

    return separator.join(
        error.strip()
        for error in errors
        if isinstance(error, str) and error.strip()
    )


def raise_if(
    condition: bool,
    exception: BaseException,
) -> None:
    """
    Raise exception if condition is True.
    """

    if not isinstance(condition, bool):
        raise TypeError("Condition must be a boolean.")

    if not isinstance(exception, BaseException):
        raise TypeError("Exception value must be an exception.")

    if condition:
        raise exception


def raise_if_none(
    value: Any,
    exception: BaseException,
) -> Any:
    """
    Raise exception if value is None.

    Returns value when it is not None.
    """

    if not isinstance(exception, BaseException):
        raise TypeError("Exception value must be an exception.")

    if value is None:
        raise exception

    return value


def safe_execute(
    func: Callable[..., Any],
    *args: Any,
    default: Any = None,
    expected_exceptions: tuple[type[BaseException], ...] = (Exception,),
    **kwargs: Any,
) -> Any:
    """
    Execute a callable safely.

    Returns default when an expected exception is raised.
    """

    if not callable(func):
        raise TypeError("Function must be callable.")

    if not isinstance(expected_exceptions, tuple):
        raise TypeError("Expected exceptions must be a tuple.")

    try:
        return func(*args, **kwargs)
    except expected_exceptions:
        return default


__all__ = [
    "ErrorInfo",
    "build_error_dict",
    "build_error_info",
    "build_not_found_error",
    "build_type_error",
    "build_validation_error",
    "collect_errors",
    "combine_error_messages",
    "exception_to_dict",
    "exception_to_error_info",
    "first_error",
    "format_error_message",
    "get_exception_name",
    "has_errors",
    "normalize_error_code",
    "normalize_error_message",
    "raise_if",
    "raise_if_none",
    "safe_execute",
]