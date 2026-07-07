"""
AQOS CLI output formatting utilities.

This module provides framework-independent CLI helpers for converting AQOS
ApiResponse objects and plain dictionaries into terminal-friendly output.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

from aqos.api import ApiResponse
from aqos.common.serialization import to_serializable


class CliOutputFormat(str, Enum):
    """
    Supported CLI output formats.
    """

    TEXT = "text"
    JSON = "json"
    PRETTY_JSON = "pretty-json"


@dataclass(frozen=True)
class CliOutput:
    """
    Standard CLI command output container.
    """

    success: bool
    output: str
    exit_code: int = 0
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not isinstance(self.success, bool):
            raise ValueError("CLI output success must be a boolean.")

        if not isinstance(self.output, str):
            raise ValueError("CLI output must be a string.")

        if not isinstance(self.exit_code, int):
            raise ValueError("CLI output exit code must be an integer.")

        if not isinstance(self.metadata, dict):
            raise ValueError("CLI output metadata must be a dictionary.")

    def to_dict(self) -> dict[str, Any]:
        """Convert CLI output into a serializable dictionary."""
        return {
            "success": self.success,
            "output": self.output,
            "exit_code": self.exit_code,
            "metadata": self.metadata,
        }


def normalize_output_format(
    output_format: CliOutputFormat | str = CliOutputFormat.TEXT,
) -> CliOutputFormat:
    """Normalize a CLI output format value."""
    if isinstance(output_format, CliOutputFormat):
        return output_format

    if not isinstance(output_format, str) or not output_format.strip():
        raise ValueError("CLI output format must be a non-empty string.")

    normalized = output_format.strip().lower().replace("_", "-")

    try:
        return CliOutputFormat(normalized)
    except ValueError as exception:
        raise ValueError(
            "CLI output format must be one of: text, json, pretty-json."
        ) from exception


def format_json(
    data: Any,
    *,
    pretty: bool = False,
) -> str:
    """Format data as JSON."""
    serializable_data = to_serializable(data)

    if pretty:
        return json.dumps(
            serializable_data,
            indent=2,
            sort_keys=True,
        )

    return json.dumps(
        serializable_data,
        separators=(",", ":"),
        sort_keys=True,
    )


def format_scalar(value: Any) -> str:
    """Format scalar values for text output."""
    if value is None:
        return "null"

    if isinstance(value, bool):
        return "true" if value else "false"

    return str(value)


def format_key_value_lines(
    data: dict[str, Any],
    *,
    indent: int = 0,
) -> list[str]:
    """Format a dictionary as nested key-value text lines."""
    if not isinstance(data, dict):
        raise ValueError("Key-value formatter requires a dictionary.")

    lines: list[str] = []
    prefix = " " * indent

    for key in sorted(data):
        value = data[key]

        if isinstance(value, dict):
            lines.append(f"{prefix}{key}:")
            lines.extend(
                format_key_value_lines(
                    value,
                    indent=indent + 2,
                )
            )
            continue

        if isinstance(value, list):
            lines.append(f"{prefix}{key}:")
            for item in value:
                if isinstance(item, dict):
                    lines.append(f"{prefix}-")
                    lines.extend(
                        format_key_value_lines(
                            item,
                            indent=indent + 2,
                        )
                    )
                else:
                    lines.append(f"{prefix}- {format_scalar(item)}")
            continue

        lines.append(f"{prefix}{key}: {format_scalar(value)}")

    return lines


def format_text_data(data: Any) -> str:
    """Format arbitrary data into CLI-friendly text."""
    if data is None:
        return ""

    if isinstance(data, dict):
        return "\n".join(format_key_value_lines(data))

    if isinstance(data, list):
        lines: list[str] = []

        for item in data:
            if isinstance(item, dict):
                lines.append("-")
                lines.extend(format_key_value_lines(item, indent=2))
            else:
                lines.append(f"- {format_scalar(item)}")

        return "\n".join(lines)

    return format_scalar(data)


def format_api_response_text(
    response: ApiResponse,
    *,
    include_metadata: bool = False,
) -> str:
    """Format an ApiResponse as terminal-friendly text."""
    payload = response.to_dict()

    status = "SUCCESS" if payload["success"] else "ERROR"
    lines = [
        f"{status}: {payload['message']}",
    ]

    data = payload.get("data")

    if data is not None:
        formatted_data = format_text_data(data)

        if formatted_data:
            lines.append("")
            lines.append("Data:")
            lines.append(formatted_data)

    errors = payload.get("errors", [])

    if errors:
        lines.append("")
        lines.append("Errors:")

        for error in errors:
            error_line = (
                f"- {error.get('code')}: {error.get('message')}"
            )

            if error.get("field"):
                error_line += f" (field: {error['field']})"

            lines.append(error_line)

    if include_metadata:
        metadata = payload.get("metadata", {})
        formatted_metadata = format_text_data(metadata)

        if formatted_metadata:
            lines.append("")
            lines.append("Metadata:")
            lines.append(formatted_metadata)

    return "\n".join(lines)


def format_api_response(
    response: ApiResponse,
    *,
    output_format: CliOutputFormat | str = CliOutputFormat.TEXT,
    include_metadata: bool = False,
) -> str:
    """Format an ApiResponse for CLI output."""
    if not isinstance(response, ApiResponse):
        raise ValueError("CLI formatter requires an ApiResponse.")

    normalized_format = normalize_output_format(output_format)

    if normalized_format == CliOutputFormat.TEXT:
        return format_api_response_text(
            response,
            include_metadata=include_metadata,
        )

    payload = response.to_dict()

    if not include_metadata:
        payload = {
            key: value
            for key, value in payload.items()
            if key != "metadata"
        }

    return format_json(
        payload,
        pretty=normalized_format == CliOutputFormat.PRETTY_JSON,
    )


def build_cli_output(
    response: ApiResponse,
    *,
    output_format: CliOutputFormat | str = CliOutputFormat.TEXT,
    include_metadata: bool = False,
    success_exit_code: int = 0,
    failure_exit_code: int = 1,
) -> CliOutput:
    """Build a CLI output object from an ApiResponse."""
    if not isinstance(success_exit_code, int):
        raise ValueError("Success exit code must be an integer.")

    if not isinstance(failure_exit_code, int):
        raise ValueError("Failure exit code must be an integer.")

    output = format_api_response(
        response,
        output_format=output_format,
        include_metadata=include_metadata,
    )

    payload = response.to_dict()
    success = payload["success"]

    return CliOutput(
        success=success,
        output=output,
        exit_code=success_exit_code if success else failure_exit_code,
        metadata={
            "format": normalize_output_format(output_format).value,
            "api_status": payload["status"],
        },
    )


def format_cli_error(
    message: str,
    *,
    code: str = "CLI_ERROR",
    output_format: CliOutputFormat | str = CliOutputFormat.TEXT,
) -> str:
    """Format a CLI-level error without requiring an ApiResponse."""
    if not isinstance(message, str) or not message.strip():
        raise ValueError("CLI error message must be a non-empty string.")

    if not isinstance(code, str) or not code.strip():
        raise ValueError("CLI error code must be a non-empty string.")

    normalized_format = normalize_output_format(output_format)

    payload = {
        "success": False,
        "status": "error",
        "message": message.strip(),
        "errors": [
            {
                "code": code.strip().upper(),
                "message": message.strip(),
            }
        ],
    }

    if normalized_format == CliOutputFormat.TEXT:
        return "\n".join(
            [
                f"ERROR: {message.strip()}",
                "",
                "Errors:",
                f"- {code.strip().upper()}: {message.strip()}",
            ]
        )

    return format_json(
        payload,
        pretty=normalized_format == CliOutputFormat.PRETTY_JSON,
    )