"""
Unit tests for AQOS dashboard package scaffold.
"""

import pytest

from aqos.dashboard import (
    DashboardComponent,
    DashboardComponentType,
    DashboardIssue,
    DashboardMetric,
    DashboardPayload,
    DashboardRefreshMode,
    DashboardSeverity,
    DashboardStatus,
    DashboardTimeRange,
    build_dashboard_component,
    build_dashboard_issue,
    build_dashboard_metric,
    build_dashboard_payload,
    build_dashboard_time_range,
    dashboard_error_payload,
    dashboard_success_payload,
    normalize_dashboard_component_type,
    normalize_dashboard_refresh_mode,
    normalize_dashboard_severity,
    normalize_dashboard_status,
    validate_dashboard_components,
    validate_dashboard_issues,
    validate_dashboard_metrics,
    validate_metadata,
    validate_metric_value,
    validate_non_empty_string,
    validate_non_negative_float,
    validate_number,
    validate_positive_float,
    validate_string,
)


def test_dashboard_enum_values():
    assert DashboardStatus.READY.value == "ready"
    assert DashboardStatus.WARNING.value == "warning"
    assert DashboardStatus.ERROR.value == "error"
    assert DashboardStatus.EMPTY.value == "empty"

    assert DashboardSeverity.INFO.value == "info"
    assert DashboardSeverity.WARNING.value == "warning"
    assert DashboardSeverity.ERROR.value == "error"
    assert DashboardSeverity.CRITICAL.value == "critical"

    assert DashboardRefreshMode.MANUAL.value == "manual"
    assert DashboardRefreshMode.AUTO.value == "auto"
    assert DashboardRefreshMode.STREAMING.value == "streaming"

    assert DashboardComponentType.PAGE.value == "page"
    assert DashboardComponentType.SECTION.value == "section"
    assert DashboardComponentType.CARD.value == "card"
    assert DashboardComponentType.TABLE.value == "table"
    assert DashboardComponentType.CHART.value == "chart"
    assert DashboardComponentType.METRIC.value == "metric"
    assert DashboardComponentType.STATUS.value == "status"


def test_dashboard_normalizers_accept_enum_and_string():
    assert normalize_dashboard_status(DashboardStatus.READY) == DashboardStatus.READY
    assert normalize_dashboard_status(" WARNING ") == DashboardStatus.WARNING
    assert normalize_dashboard_severity(DashboardSeverity.ERROR) == DashboardSeverity.ERROR
    assert normalize_dashboard_severity(" CRITICAL ") == DashboardSeverity.CRITICAL
    assert normalize_dashboard_refresh_mode(DashboardRefreshMode.AUTO) == DashboardRefreshMode.AUTO
    assert normalize_dashboard_refresh_mode(" STREAMING ") == DashboardRefreshMode.STREAMING
    assert normalize_dashboard_component_type(DashboardComponentType.CARD) == DashboardComponentType.CARD
    assert normalize_dashboard_component_type(" CHART ") == DashboardComponentType.CHART


def test_dashboard_normalizers_reject_invalid_values():
    with pytest.raises(ValueError):
        normalize_dashboard_status("bad")

    with pytest.raises(ValueError):
        normalize_dashboard_severity("bad")

    with pytest.raises(ValueError):
        normalize_dashboard_refresh_mode("bad")

    with pytest.raises(ValueError):
        normalize_dashboard_component_type("bad")


def test_dashboard_validators():
    assert validate_string("", "Field") == ""
    assert validate_string("value", "Field") == "value"
    assert validate_non_empty_string(" value ", "Field") == "value"
    assert validate_metadata({"a": 1}) == {"a": 1}
    assert validate_number(1, "Value") == 1.0
    assert validate_number(-1.5, "Value") == -1.5
    assert validate_non_negative_float(0, "Value") == 0.0
    assert validate_positive_float(1, "Value") == 1.0
    assert validate_metric_value(True, "Metric") is True
    assert validate_metric_value("ready", "Metric") == "ready"
    assert validate_metric_value(12.5, "Metric") == 12.5

    with pytest.raises(ValueError):
        validate_string(123, "Field")

    with pytest.raises(ValueError):
        validate_non_empty_string("", "Field")

    with pytest.raises(ValueError):
        validate_metadata([])

    with pytest.raises(ValueError):
        validate_number(True, "Value")

    with pytest.raises(ValueError):
        validate_number("1", "Value")

    with pytest.raises(ValueError):
        validate_non_negative_float(-1, "Value")

    with pytest.raises(ValueError):
        validate_positive_float(0, "Value")

    with pytest.raises(ValueError):
        validate_metric_value([], "Metric")


def test_dashboard_issue_to_dict():
    issue = DashboardIssue(
        code=" data_delay ",
        message=" Market data delayed ",
        severity=" WARNING ",
        source=" provider ",
        metadata={
            "provider_id": "csv-local",
        },
    )

    assert issue.to_dict() == {
        "code": "data_delay",
        "message": "Market data delayed",
        "severity": "warning",
        "source": "provider",
        "metadata": {
            "provider_id": "csv-local",
        },
    }


def test_dashboard_issue_rejects_invalid_values():
    with pytest.raises(ValueError):
        DashboardIssue(code="", message="Message")

    with pytest.raises(ValueError):
        DashboardIssue(code="code", message="")

    with pytest.raises(ValueError):
        DashboardIssue(code="code", message="Message", severity="bad")

    with pytest.raises(ValueError):
        DashboardIssue(code="code", message="Message", source=123)

    with pytest.raises(ValueError):
        DashboardIssue(code="code", message="Message", metadata=[])


def test_build_dashboard_issue():
    issue = build_dashboard_issue(
        code="ok",
        message="Everything is ok.",
        severity="info",
    )

    assert isinstance(issue, DashboardIssue)
    assert issue.code == "ok"


def test_dashboard_metric_to_dict():
    metric = DashboardMetric(
        name=" win_rate ",
        value=62.5,
        label=" Win Rate ",
        unit="%",
        previous_value=60,
        change=2.5,
        change_pct=4.16,
        status=" READY ",
        metadata={
            "source": "evaluation",
        },
    )

    payload = metric.to_dict()

    assert metric.display_label == "Win Rate"
    assert payload == {
        "name": "win_rate",
        "label": "Win Rate",
        "value": 62.5,
        "unit": "%",
        "previous_value": 60,
        "change": 2.5,
        "change_pct": 4.16,
        "status": "ready",
        "metadata": {
            "source": "evaluation",
        },
    }


def test_dashboard_metric_default_label():
    metric = build_dashboard_metric(
        name="total_signals",
        value=12,
    )

    assert metric.display_label == "Total Signals"
    assert metric.to_dict()["label"] == "Total Signals"


def test_dashboard_metric_rejects_invalid_values():
    with pytest.raises(ValueError):
        DashboardMetric(name="", value=1)

    with pytest.raises(ValueError):
        DashboardMetric(name="metric", value=[])

    with pytest.raises(ValueError):
        DashboardMetric(name="metric", value=1, label=123)

    with pytest.raises(ValueError):
        DashboardMetric(name="metric", value=1, unit=123)

    with pytest.raises(ValueError):
        DashboardMetric(name="metric", value=1, previous_value="bad")

    with pytest.raises(ValueError):
        DashboardMetric(name="metric", value=1, change="bad")

    with pytest.raises(ValueError):
        DashboardMetric(name="metric", value=1, change_pct="bad")

    with pytest.raises(ValueError):
        DashboardMetric(name="metric", value=1, status="bad")

    with pytest.raises(ValueError):
        DashboardMetric(name="metric", value=1, metadata=[])


def test_dashboard_time_range_to_dict():
    time_range = DashboardTimeRange(
        label=" last_7_days ",
        start="2026-01-01T00:00:00+00:00",
        end="2026-01-07T00:00:00+00:00",
        timezone=" UTC ",
        metadata={
            "days": 7,
        },
    )

    assert time_range.bounded is True
    assert time_range.to_dict() == {
        "label": "last_7_days",
        "start": "2026-01-01T00:00:00+00:00",
        "end": "2026-01-07T00:00:00+00:00",
        "timezone": "UTC",
        "bounded": True,
        "metadata": {
            "days": 7,
        },
    }


def test_dashboard_time_range_unbounded_and_builder():
    time_range = build_dashboard_time_range(
        label="today",
    )

    assert isinstance(time_range, DashboardTimeRange)
    assert time_range.bounded is False
    assert time_range.timezone == "UTC"


def test_dashboard_time_range_rejects_invalid_values():
    with pytest.raises(ValueError):
        DashboardTimeRange(label="")

    with pytest.raises(ValueError):
        DashboardTimeRange(label="default", start=123)

    with pytest.raises(ValueError):
        DashboardTimeRange(label="default", end=123)

    with pytest.raises(ValueError):
        DashboardTimeRange(label="default", timezone="")

    with pytest.raises(ValueError):
        DashboardTimeRange(label="default", metadata=[])


def test_dashboard_component_to_dict():
    metric = build_dashboard_metric(
        name="signals",
        value=5,
    )
    issue = build_dashboard_issue(
        code="warning",
        message="Low confidence",
        severity="warning",
    )
    component = DashboardComponent(
        component_id=" signal-card ",
        title=" Signal Card ",
        component_type=" CARD ",
        status=" WARNING ",
        description=" Latest signal ",
        data={
            "symbol": "XAUUSD",
        },
        metrics=[metric],
        issues=[issue],
        metadata={
            "order": 1,
        },
    )

    payload = component.to_dict()

    assert component.healthy is False
    assert component.metric_count == 1
    assert component.issue_count == 1
    assert payload["component_id"] == "signal-card"
    assert payload["title"] == "Signal Card"
    assert payload["component_type"] == "card"
    assert payload["status"] == "warning"
    assert payload["healthy"] is False
    assert payload["description"] == "Latest signal"
    assert payload["data"] == {
        "symbol": "XAUUSD",
    }


def test_build_dashboard_component():
    component = build_dashboard_component(
        component_id="market-overview",
        title="Market Overview",
        component_type="section",
    )

    assert isinstance(component, DashboardComponent)
    assert component.healthy is True


def test_dashboard_component_rejects_invalid_values():
    metric = build_dashboard_metric(name="metric", value=1)
    issue = build_dashboard_issue(code="issue", message="Issue")

    with pytest.raises(ValueError):
        DashboardComponent(component_id="", title="Title", component_type="card")

    with pytest.raises(ValueError):
        DashboardComponent(component_id="id", title="", component_type="card")

    with pytest.raises(ValueError):
        DashboardComponent(component_id="id", title="Title", component_type="bad")

    with pytest.raises(ValueError):
        DashboardComponent(component_id="id", title="Title", component_type="card", status="bad")

    with pytest.raises(ValueError):
        DashboardComponent(component_id="id", title="Title", component_type="card", description=123)

    with pytest.raises(ValueError):
        DashboardComponent(component_id="id", title="Title", component_type="card", data=[])

    with pytest.raises(ValueError):
        DashboardComponent(component_id="id", title="Title", component_type="card", metrics="bad")

    with pytest.raises(ValueError):
        DashboardComponent(component_id="id", title="Title", component_type="card", metrics=["bad"])

    with pytest.raises(ValueError):
        DashboardComponent(component_id="id", title="Title", component_type="card", issues="bad")

    with pytest.raises(ValueError):
        DashboardComponent(component_id="id", title="Title", component_type="card", issues=["bad"])

    with pytest.raises(ValueError):
        DashboardComponent(component_id="id", title="Title", component_type="card", metadata=[])

    assert validate_dashboard_metrics([metric]) == [metric]
    assert validate_dashboard_issues([issue]) == [issue]


def test_dashboard_payload_to_dict():
    metric = build_dashboard_metric(
        name="total_signals",
        value=10,
    )
    issue = build_dashboard_issue(
        code="delayed",
        message="Provider delayed",
        severity="warning",
    )
    component = build_dashboard_component(
        component_id="signals",
        title="Signals",
        component_type="card",
        metrics=[metric],
        issues=[issue],
    )
    payload = DashboardPayload(
        payload_id=" main-dashboard ",
        title=" AQOS Dashboard ",
        status=" READY ",
        refresh_mode=" AUTO ",
        generated_at="2026-01-01T00:00:00+00:00",
        time_range=build_dashboard_time_range(label="today"),
        components=[component],
        metrics=[metric],
        data={
            "version": "0.24",
        },
        metadata={
            "source": "test",
        },
    )

    result = payload.to_dict()

    assert payload.healthy is True
    assert payload.component_count == 1
    assert payload.metric_count == 1
    assert payload.issue_count == 1
    assert result["payload_id"] == "main-dashboard"
    assert result["title"] == "AQOS Dashboard"
    assert result["status"] == "ready"
    assert result["refresh_mode"] == "auto"
    assert result["component_count"] == 1
    assert result["metric_count"] == 1
    assert result["issue_count"] == 1


def test_build_dashboard_payload():
    payload = build_dashboard_payload(
        payload_id="dashboard",
        title="Dashboard",
        generated_at="2026-01-01T00:00:00+00:00",
    )

    assert isinstance(payload, DashboardPayload)
    assert payload.status == DashboardStatus.READY


def test_dashboard_payload_rejects_invalid_values():
    with pytest.raises(ValueError):
        DashboardPayload(payload_id="", title="Dashboard")

    with pytest.raises(ValueError):
        DashboardPayload(payload_id="dashboard", title="")

    with pytest.raises(ValueError):
        DashboardPayload(payload_id="dashboard", title="Dashboard", status="bad")

    with pytest.raises(ValueError):
        DashboardPayload(payload_id="dashboard", title="Dashboard", refresh_mode="bad")

    with pytest.raises(ValueError):
        DashboardPayload(payload_id="dashboard", title="Dashboard", generated_at="")

    with pytest.raises(ValueError):
        DashboardPayload(payload_id="dashboard", title="Dashboard", time_range="bad")

    with pytest.raises(ValueError):
        DashboardPayload(payload_id="dashboard", title="Dashboard", components="bad")

    with pytest.raises(ValueError):
        DashboardPayload(payload_id="dashboard", title="Dashboard", components=["bad"])

    with pytest.raises(ValueError):
        DashboardPayload(payload_id="dashboard", title="Dashboard", metrics="bad")

    with pytest.raises(ValueError):
        DashboardPayload(payload_id="dashboard", title="Dashboard", issues="bad")

    with pytest.raises(ValueError):
        DashboardPayload(payload_id="dashboard", title="Dashboard", data=[])

    with pytest.raises(ValueError):
        DashboardPayload(payload_id="dashboard", title="Dashboard", metadata=[])


def test_dashboard_success_and_error_payloads():
    success = dashboard_success_payload(
        payload_id="dashboard",
        title="Dashboard",
        data={
            "ok": True,
        },
    )
    error = dashboard_error_payload(
        payload_id="dashboard",
        title="Dashboard",
        error_code="failed",
        error_message="Dashboard failed",
        source="test",
    )

    assert success.status == DashboardStatus.READY
    assert success.data == {
        "ok": True,
    }

    assert error.status == DashboardStatus.ERROR
    assert error.healthy is False
    assert error.issues[0].code == "failed"
    assert error.issues[0].severity == DashboardSeverity.ERROR


def test_dashboard_exports_are_sorted_and_exist():
    import aqos.dashboard as dashboard

    assert dashboard.__all__ == sorted(dashboard.__all__)

    for export_name in dashboard.__all__:
        assert hasattr(dashboard, export_name), export_name