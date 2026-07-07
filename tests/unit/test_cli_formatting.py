"""
Unit tests for AQOS CLI formatting utilities.
"""

import json

import pytest

from aqos.api import (
    api_error,
    api_failure,
    api_success,
    validation_failure,
)
from aqos.cli import (
    CliOutput,
    CliOutputFormat,
    build_cli_output,
    format_api_response,
    format_cli_error,
    format_json,
    format_key_value_lines,
    format_scalar,
    format_text_data,
    normalize_output_format,
)


def test_cli_output_to_dict():
    output = CliOutput(
        success=True,
        output="SUCCESS: ok",
        exit_code=0,
        metadata={
            "format": "text",
        },
    )

    assert output.to_dict() == {
        "success": True,
        "output": "SUCCESS: ok",
        "exit_code": 0,
        "metadata": {
            "format": "text",
        },
    }


def test_cli_output_rejects_invalid_values():
    with pytest.raises(ValueError):
        CliOutput(
            success="yes",
            output="ok",
        )

    with pytest.raises(ValueError):
        CliOutput(
            success=True,
            output=[],
        )

    with pytest.raises(ValueError):
        CliOutput(
            success=True,
            output="ok",
            exit_code="0",
        )

    with pytest.raises(ValueError):
        CliOutput(
            success=True,
            output="ok",
            metadata=[],
        )


def test_normalize_output_format_accepts_enum_and_strings():
    assert normalize_output_format(CliOutputFormat.TEXT) == CliOutputFormat.TEXT
    assert normalize_output_format("text") == CliOutputFormat.TEXT
    assert normalize_output_format(" json ") == CliOutputFormat.JSON
    assert normalize_output_format("pretty_json") == CliOutputFormat.PRETTY_JSON
    assert normalize_output_format("pretty-json") == CliOutputFormat.PRETTY_JSON


def test_normalize_output_format_rejects_invalid_values():
    with pytest.raises(ValueError):
        normalize_output_format("bad")

    with pytest.raises(ValueError):
        normalize_output_format("")

    with pytest.raises(ValueError):
        normalize_output_format([])


def test_format_json_compact_and_pretty():
    data = {
        "symbol": "XAUUSD",
        "success": True,
    }

    compact = format_json(data)
    pretty = format_json(data, pretty=True)

    assert json.loads(compact) == data
    assert json.loads(pretty) == data
    assert "\n" not in compact
    assert "\n" in pretty


def test_format_scalar_values():
    assert format_scalar(None) == "null"
    assert format_scalar(True) == "true"
    assert format_scalar(False) == "false"
    assert format_scalar(10) == "10"
    assert format_scalar("XAUUSD") == "XAUUSD"


def test_format_key_value_lines_sorts_and_nests_dicts():
    lines = format_key_value_lines(
        {
            "symbol": "XAUUSD",
            "market": {
                "trend": "uptrend",
                "regime": "bullish",
            },
        }
    )

    assert lines == [
        "market:",
        "  regime: bullish",
        "  trend: uptrend",
        "symbol: XAUUSD",
    ]


def test_format_key_value_lines_handles_lists():
    lines = format_key_value_lines(
        {
            "items": [
                "one",
                "two",
            ],
        }
    )

    assert lines == [
        "items:",
        "- one",
        "- two",
    ]


def test_format_key_value_lines_rejects_non_dict():
    with pytest.raises(ValueError):
        format_key_value_lines([])


def test_format_text_data_handles_dict_list_scalar_and_none():
    assert format_text_data(None) == ""

    assert format_text_data(
        {
            "symbol": "XAUUSD",
        }
    ) == "symbol: XAUUSD"

    assert format_text_data(
        [
            "one",
            "two",
        ]
    ) == "- one\n- two"

    assert format_text_data("done") == "done"


def test_format_api_response_text_success_without_metadata():
    response = api_success(
        message="Market state loaded.",
        data={
            "symbol": "XAUUSD",
            "timeframe": "H1",
        },
        request_id="request-1",
    )

    output = format_api_response(response)

    assert output.startswith("SUCCESS: Market state loaded.")
    assert "Data:" in output
    assert "symbol: XAUUSD" in output
    assert "timeframe: H1" in output
    assert "Metadata:" not in output
    assert "request-1" not in output


def test_format_api_response_text_success_with_metadata():
    response = api_success(
        message="Market state loaded.",
        data={
            "symbol": "XAUUSD",
        },
        request_id="request-1",
    )

    output = format_api_response(
        response,
        include_metadata=True,
    )

    assert "SUCCESS: Market state loaded." in output
    assert "Metadata:" in output
    assert "request_id: request-1" in output


def test_format_api_response_text_failure():
    response = api_failure(
        message="Market state failed.",
        errors=[
            api_error(
                code="MARKET_ERROR",
                message="Market agent failed.",
                field="market",
            )
        ],
    )

    output = format_api_response(response)

    assert output.startswith("ERROR: Market state failed.")
    assert "Errors:" in output
    assert "- MARKET_ERROR: Market agent failed. (field: market)" in output


def test_format_api_response_json_without_metadata():
    response = api_success(
        message="Market state loaded.",
        data={
            "symbol": "XAUUSD",
        },
        request_id="request-1",
    )

    output = format_api_response(
        response,
        output_format="json",
    )

    payload = json.loads(output)

    assert payload["success"] is True
    assert payload["status"] == "success"
    assert payload["message"] == "Market state loaded."
    assert payload["data"] == {
        "symbol": "XAUUSD",
    }
    assert "metadata" not in payload


def test_format_api_response_pretty_json_with_metadata():
    response = api_success(
        message="Market state loaded.",
        data={
            "symbol": "XAUUSD",
        },
        request_id="request-1",
    )

    output = format_api_response(
        response,
        output_format="pretty-json",
        include_metadata=True,
    )

    payload = json.loads(output)

    assert "\n" in output
    assert payload["metadata"]["request_id"] == "request-1"


def test_format_api_response_rejects_non_api_response():
    with pytest.raises(ValueError):
        format_api_response(
            {
                "success": True,
            }
        )


def test_build_cli_output_success():
    response = api_success(
        message="Done.",
        data={
            "ok": True,
        },
    )

    cli_output = build_cli_output(
        response,
        output_format="text",
    )

    assert cli_output.success is True
    assert cli_output.exit_code == 0
    assert cli_output.metadata == {
        "format": "text",
        "api_status": "success",
    }
    assert cli_output.output.startswith("SUCCESS: Done.")


def test_build_cli_output_failure():
    response = validation_failure(
        message="Invalid symbol.",
        field="symbol",
    )

    cli_output = build_cli_output(
        response,
        output_format="json",
        failure_exit_code=2,
    )

    payload = json.loads(cli_output.output)

    assert cli_output.success is False
    assert cli_output.exit_code == 2
    assert cli_output.metadata == {
        "format": "json",
        "api_status": "error",
    }
    assert payload["errors"][0]["code"] == "VALIDATION_ERROR"


def test_build_cli_output_rejects_invalid_exit_codes():
    response = api_success(message="Done.")

    with pytest.raises(ValueError):
        build_cli_output(
            response,
            success_exit_code="0",
        )

    with pytest.raises(ValueError):
        build_cli_output(
            response,
            failure_exit_code="1",
        )


def test_format_cli_error_text():
    output = format_cli_error(
        "Command failed.",
        code="bad_command",
    )

    assert output == (
        "ERROR: Command failed.\n"
        "\n"
        "Errors:\n"
        "- BAD_COMMAND: Command failed."
    )


def test_format_cli_error_json():
    output = format_cli_error(
        "Command failed.",
        code="bad_command",
        output_format="json",
    )

    payload = json.loads(output)

    assert payload["success"] is False
    assert payload["status"] == "error"
    assert payload["message"] == "Command failed."
    assert payload["errors"][0]["code"] == "BAD_COMMAND"


def test_format_cli_error_rejects_invalid_values():
    with pytest.raises(ValueError):
        format_cli_error("")

    with pytest.raises(ValueError):
        format_cli_error("Failed.", code="")