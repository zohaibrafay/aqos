"""
Unit tests for AQOS dashboard frontend serialization helpers.
"""

import json
from dataclasses import dataclass
from datetime import date, datetime

import pytest

from aqos.dashboard import (
    DashboardApiEnvelope,
    DashboardApiResponseStatus,
    DashboardPagination,
    DashboardSerializationFormat,
    DashboardStatus,
    build_dashboard_api_envelope,
    build_dashboard_component,
    build_dashboard_issue,
    build_dashboard_metric,
    build_dashboard_pagination,
    build_dashboard_payload,
    build_frontend_ready_dashboard_payload,
    dashboard_component_to_dict,
    dashboard_components_to_collection_envelope,
    dashboard_envelope_to_json,
    dashboard_error_api_envelope,
    dashboard_issue_to_dict,
    dashboard_metric_to_dict,
    dashboard_metrics_to_collection_envelope,
    dashboard_payload_to_api_envelope,
    dashboard_payload_to_dict,
    dashboard_payload_to_json,
    dashboard_payloads_to_collection_envelope,
    frontend_response_from_error,
    frontend_response_from_payload,
    normalize_dashboard_api_response_status,
    normalize_dashboard_serialization_format,
    normalize_payload_status,
    paginate_dashboard_items,
    sanitize_dashboard_value,
    validate_positive_integer,
)


@dataclass
class SampleDataclass:
    name: str
    value: int


def sample_payload(payload_id="dashboard", status=DashboardStatus.READY):
    return build_dashboard_payload(
        payload_id=payload_id,
        title="Dashboard",
        status=status,
        generated_at="2026-01-01T00:00:00+00:00",
        components=[
            build_dashboard_component(
                component_id="component-1",
                title="Component 1",
                component_type="card",
                data={
                    "created": datetime(2026, 1, 1),
                },
            )
        ],
        metrics=[
            build_dashboard_metric(
                name="count",
                value=1,
            )
        ],
        issues=[
            build_dashboard_issue(
                code="info",
                message="Info issue.",
                severity="info",
            )
        ],
        data={
            "ok": True,
            "date": date(2026, 1, 1),
        },
        metadata={
            "source": "test",
        },
    )


def test_serialization_enum_values():
    assert DashboardSerializationFormat.DICT.value == "dict"
    assert DashboardSerializationFormat.JSON.value == "json"

    assert DashboardApiResponseStatus.SUCCESS.value == "success"
    assert DashboardApiResponseStatus.ERROR.value == "error"


def test_serialization_normalizers():
    assert normalize_dashboard_serialization_format(DashboardSerializationFormat.DICT) == DashboardSerializationFormat.DICT
    assert normalize_dashboard_serialization_format(" JSON ") == DashboardSerializationFormat.JSON
    assert normalize_dashboard_api_response_status(DashboardApiResponseStatus.SUCCESS) == DashboardApiResponseStatus.SUCCESS
    assert normalize_dashboard_api_response_status(" ERROR ") == DashboardApiResponseStatus.ERROR
    assert normalize_payload_status(DashboardStatus.READY) == DashboardStatus.READY
    assert normalize_payload_status(" WARNING ") == DashboardStatus.WARNING

    with pytest.raises(ValueError):
        normalize_dashboard_serialization_format("bad")

    with pytest.raises(ValueError):
        normalize_dashboard_api_response_status("bad")

    with pytest.raises(ValueError):
        normalize_payload_status("bad")


def test_validate_positive_integer():
    assert validate_positive_integer(1, "Value") == 1

    with pytest.raises(ValueError):
        validate_positive_integer(0, "Value")

    with pytest.raises(ValueError):
        validate_positive_integer(-1, "Value")

    with pytest.raises(ValueError):
        validate_positive_integer(True, "Value")

    with pytest.raises(ValueError):
        validate_positive_integer("1", "Value")


def test_dashboard_pagination_to_dict():
    pagination = DashboardPagination(
        page=2,
        page_size=10,
        total_items=25,
        metadata={
            "source": "test",
        },
    )

    assert pagination.total_pages == 3
    assert pagination.offset == 10
    assert pagination.limit == 10
    assert pagination.has_next is True
    assert pagination.has_previous is True
    assert pagination.to_dict() == {
        "page": 2,
        "page_size": 10,
        "total_items": 25,
        "total_pages": 3,
        "offset": 10,
        "limit": 10,
        "has_next": True,
        "has_previous": True,
        "metadata": {
            "source": "test",
        },
    }


def test_dashboard_pagination_empty_and_builder():
    pagination = build_dashboard_pagination(
        page=1,
        page_size=25,
        total_items=0,
    )

    assert pagination.total_pages == 0
    assert pagination.has_next is False
    assert pagination.has_previous is False


def test_dashboard_pagination_rejects_invalid_values():
    with pytest.raises(ValueError):
        DashboardPagination(page=0)

    with pytest.raises(ValueError):
        DashboardPagination(page=1, page_size=0)

    with pytest.raises(ValueError):
        DashboardPagination(page=1, page_size=10, total_items=-1)

    with pytest.raises(ValueError):
        DashboardPagination(page=1, page_size=10, metadata=[])


def test_api_envelope_to_dict():
    envelope = DashboardApiEnvelope(
        response_id=" response-1 ",
        status=" SUCCESS ",
        payload={
            "ok": True,
        },
        issues=[
            build_dashboard_issue(
                code="info",
                message="Info.",
            )
        ],
        pagination=build_dashboard_pagination(total_items=1),
        metadata={
            "source": "test",
        },
    )

    payload = envelope.to_dict()

    assert envelope.success is True
    assert envelope.failed is False
    assert envelope.issue_count == 1
    assert payload["response_id"] == "response-1"
    assert payload["status"] == "success"
    assert payload["payload"] == {
        "ok": True,
    }
    assert payload["pagination"]["total_items"] == 1


def test_api_envelope_rejects_invalid_values():
    with pytest.raises(ValueError):
        DashboardApiEnvelope(response_id="", status="success")

    with pytest.raises(ValueError):
        DashboardApiEnvelope(response_id="response", status="bad")

    with pytest.raises(ValueError):
        DashboardApiEnvelope(response_id="response", status="success", payload=[])

    with pytest.raises(ValueError):
        DashboardApiEnvelope(response_id="response", status="success", error=123)

    with pytest.raises(ValueError):
        DashboardApiEnvelope(response_id="response", status="success", issues=["bad"])

    with pytest.raises(ValueError):
        DashboardApiEnvelope(response_id="response", status="success", pagination="bad")

    with pytest.raises(ValueError):
        DashboardApiEnvelope(response_id="response", status="success", metadata=[])


def test_sanitize_dashboard_value():
    payload = {
        "status": DashboardStatus.READY,
        "datetime": datetime(2026, 1, 1, 12, 0, 0),
        "date": date(2026, 1, 1),
        "dataclass": SampleDataclass(name="a", value=1),
        "set": {"a", "b"},
        "metric": build_dashboard_metric(name="count", value=1),
        "nested": {
            "tuple": (1, 2),
        },
        "object": object(),
    }

    sanitized = sanitize_dashboard_value(payload)

    assert sanitized["status"] == "ready"
    assert sanitized["datetime"] == "2026-01-01T12:00:00"
    assert sanitized["date"] == "2026-01-01"
    assert sanitized["dataclass"] == {
        "name": "a",
        "value": 1,
    }
    assert sorted(sanitized["set"]) == ["a", "b"]
    assert sanitized["metric"]["name"] == "count"
    assert sanitized["nested"]["tuple"] == [1, 2]
    assert isinstance(sanitized["object"], str)


def test_dashboard_object_to_dict_helpers():
    payload = sample_payload()
    component = payload.components[0]
    metric = payload.metrics[0]
    issue = payload.issues[0]

    payload_dict = dashboard_payload_to_dict(payload)
    component_dict = dashboard_component_to_dict(component)
    metric_dict = dashboard_metric_to_dict(metric)
    issue_dict = dashboard_issue_to_dict(issue)

    assert payload_dict["payload_id"] == "dashboard"
    assert payload_dict["data"]["date"] == "2026-01-01"
    assert component_dict["component_id"] == "component-1"
    assert component_dict["data"]["created"] == "2026-01-01T00:00:00"
    assert metric_dict["name"] == "count"
    assert issue_dict["code"] == "info"

    with pytest.raises(ValueError):
        dashboard_payload_to_dict("bad")

    with pytest.raises(ValueError):
        dashboard_component_to_dict("bad")

    with pytest.raises(ValueError):
        dashboard_metric_to_dict("bad")

    with pytest.raises(ValueError):
        dashboard_issue_to_dict("bad")


def test_dashboard_payload_to_json():
    payload = sample_payload()
    json_payload = dashboard_payload_to_json(payload)

    decoded = json.loads(json_payload)

    assert decoded["payload_id"] == "dashboard"
    assert decoded["status"] == "ready"


def test_dashboard_envelope_to_json():
    envelope = build_dashboard_api_envelope(
        response_id="response",
        status="success",
        payload={
            "ok": True,
        },
    )
    json_payload = dashboard_envelope_to_json(envelope)

    decoded = json.loads(json_payload)

    assert decoded["response_id"] == "response"
    assert decoded["status"] == "success"

    with pytest.raises(ValueError):
        dashboard_envelope_to_json("bad")


def test_paginate_dashboard_items():
    items = [{"id": index} for index in range(30)]
    page_items, pagination = paginate_dashboard_items(
        items,
        page=2,
        page_size=10,
    )

    assert len(page_items) == 10
    assert page_items[0] == {
        "id": 10,
    }
    assert pagination.page == 2
    assert pagination.total_pages == 3

    with pytest.raises(ValueError):
        paginate_dashboard_items("bad")

    with pytest.raises(ValueError):
        paginate_dashboard_items(["bad"])


def test_dashboard_payload_to_api_envelope():
    payload = sample_payload()
    envelope = dashboard_payload_to_api_envelope(payload)

    assert isinstance(envelope, DashboardApiEnvelope)
    assert envelope.success is True
    assert envelope.response_id == "dashboard"
    assert envelope.payload["payload_id"] == "dashboard"
    assert envelope.metadata["dashboard_status"] == "ready"

    error_payload = sample_payload(
        payload_id="error-dashboard",
        status=DashboardStatus.ERROR,
    )
    error_envelope = dashboard_payload_to_api_envelope(error_payload)

    assert error_envelope.failed is True
    assert error_envelope.status == DashboardApiResponseStatus.ERROR

    with pytest.raises(ValueError):
        dashboard_payload_to_api_envelope("bad")


def test_collection_envelopes():
    payloads = [
        sample_payload(payload_id=f"payload-{index}")
        for index in range(3)
    ]
    components = sample_payload().components
    metrics = sample_payload().metrics

    payload_collection = dashboard_payloads_to_collection_envelope(
        payloads=payloads,
        page=1,
        page_size=2,
    )
    component_collection = dashboard_components_to_collection_envelope(
        components=components,
    )
    metric_collection = dashboard_metrics_to_collection_envelope(
        metrics=metrics,
    )

    assert payload_collection.success is True
    assert payload_collection.payload["count"] == 2
    assert payload_collection.payload["total_count"] == 3
    assert payload_collection.pagination.total_pages == 2

    assert component_collection.payload["count"] == 1
    assert metric_collection.payload["count"] == 1

    with pytest.raises(ValueError):
        dashboard_payloads_to_collection_envelope(payloads="bad")

    with pytest.raises(ValueError):
        dashboard_payloads_to_collection_envelope(payloads=["bad"])

    with pytest.raises(ValueError):
        dashboard_components_to_collection_envelope(components=["bad"])

    with pytest.raises(ValueError):
        dashboard_metrics_to_collection_envelope(metrics=["bad"])


def test_dashboard_error_api_envelope():
    envelope = dashboard_error_api_envelope(
        response_id="error",
        error_code="failed",
        error_message="Dashboard failed.",
    )

    assert envelope.failed is True
    assert envelope.error == "Dashboard failed."
    assert envelope.issues[0].code == "failed"


def test_frontend_response_helpers():
    payload = sample_payload()

    response = frontend_response_from_payload(payload)
    json_response = frontend_response_from_payload(
        payload,
        as_json=True,
    )
    error_response = frontend_response_from_error(
        error_code="failed",
        error_message="Dashboard failed.",
    )
    json_error_response = frontend_response_from_error(
        error_code="failed",
        error_message="Dashboard failed.",
        as_json=True,
    )

    assert response["status"] == "success"
    assert response["payload"]["payload_id"] == "dashboard"

    decoded = json.loads(json_response)
    assert decoded["status"] == "success"

    assert error_response["status"] == "error"
    assert error_response["error"] == "Dashboard failed."

    decoded_error = json.loads(json_error_response)
    assert decoded_error["status"] == "error"


def test_build_frontend_ready_dashboard_payload():
    payload = build_frontend_ready_dashboard_payload(
        payload_id="frontend",
        title="Frontend",
        data={
            "date": date(2026, 1, 1),
            "status": DashboardStatus.READY,
        },
        metadata={
            "generated": datetime(2026, 1, 1),
        },
    )

    payload_dict = dashboard_payload_to_dict(payload)

    assert payload.payload_id == "frontend"
    assert payload_dict["data"]["date"] == "2026-01-01"
    assert payload_dict["data"]["status"] == "ready"
    assert payload_dict["metadata"]["generated"] == "2026-01-01T00:00:00"


def test_dashboard_serialization_exports_exist():
    import aqos.dashboard as dashboard

    expected_exports = [
        "DashboardApiEnvelope",
        "DashboardApiResponseStatus",
        "DashboardPagination",
        "DashboardSerializationFormat",
        "build_dashboard_api_envelope",
        "build_dashboard_pagination",
        "build_frontend_ready_dashboard_payload",
        "dashboard_component_to_dict",
        "dashboard_components_to_collection_envelope",
        "dashboard_envelope_to_json",
        "dashboard_error_api_envelope",
        "dashboard_issue_to_dict",
        "dashboard_metric_to_dict",
        "dashboard_metrics_to_collection_envelope",
        "dashboard_payload_to_api_envelope",
        "dashboard_payload_to_dict",
        "dashboard_payload_to_json",
        "dashboard_payloads_to_collection_envelope",
        "frontend_response_from_error",
        "frontend_response_from_payload",
        "normalize_dashboard_api_response_status",
        "normalize_dashboard_serialization_format",
        "normalize_payload_status",
        "paginate_dashboard_items",
        "sanitize_dashboard_value",
        "validate_positive_integer",
    ]

    for export_name in expected_exports:
        assert hasattr(dashboard, export_name), export_name