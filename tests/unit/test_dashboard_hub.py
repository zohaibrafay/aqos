"""
Unit tests for AQOS dashboard aggregation hub.
"""

import pytest

from aqos.dashboard import (
    DashboardAggregationHub,
    DashboardAggregationMode,
    DashboardAggregationSnapshot,
    DashboardPayload,
    DashboardSection,
    DashboardSectionKind,
    DashboardStatus,
    aggregate_dashboard_payloads,
    build_aggregation_summary_metrics,
    build_dashboard_aggregation_hub,
    build_dashboard_aggregation_snapshot,
    build_dashboard_component,
    build_dashboard_metric,
    build_dashboard_payload,
    build_dashboard_section,
    build_market_overview_payload,
    build_market_overview_snapshot,
    build_section_from_payload,
    build_section_summary_components,
    dashboard_aggregation_error_payload,
    infer_aggregation_status,
    normalize_dashboard_aggregation_mode,
    normalize_dashboard_section_kind,
    validate_dashboard_section_dict,
    validate_dashboard_sections,
    validate_payload_dict,
)


def sample_payload(payload_id="market-overview", title="Market Overview"):
    return build_dashboard_payload(
        payload_id=payload_id,
        title=title,
        status=DashboardStatus.READY,
        generated_at="2026-01-01T00:00:00+00:00",
        components=[
            build_dashboard_component(
                component_id=f"{payload_id}-component",
                title=f"{title} Component",
                component_type="card",
            )
        ],
        metrics=[
            build_dashboard_metric(
                name="count",
                value=1,
            )
        ],
        data={
            "source": payload_id,
        },
    )


def sample_section():
    return build_dashboard_section(
        section_id="market",
        title="Market",
        kind="market",
        payload=sample_payload(),
    )


def test_hub_enum_values():
    assert DashboardSectionKind.MARKET.value == "market"
    assert DashboardSectionKind.SIGNALS.value == "signals"
    assert DashboardSectionKind.PORTFOLIO.value == "portfolio"
    assert DashboardSectionKind.STATUS.value == "status"
    assert DashboardSectionKind.CUSTOM.value == "custom"

    assert DashboardAggregationMode.FULL.value == "full"
    assert DashboardAggregationMode.SUMMARY.value == "summary"
    assert DashboardAggregationMode.COMPACT.value == "compact"


def test_hub_normalizers():
    assert normalize_dashboard_section_kind(DashboardSectionKind.MARKET) == DashboardSectionKind.MARKET
    assert normalize_dashboard_section_kind(" SIGNALS ") == DashboardSectionKind.SIGNALS
    assert normalize_dashboard_aggregation_mode(DashboardAggregationMode.FULL) == DashboardAggregationMode.FULL
    assert normalize_dashboard_aggregation_mode(" COMPACT ") == DashboardAggregationMode.COMPACT

    with pytest.raises(ValueError):
        normalize_dashboard_section_kind("bad")

    with pytest.raises(ValueError):
        normalize_dashboard_aggregation_mode("bad")


def test_dashboard_section_to_dict():
    section = sample_section()
    payload = section.to_dict()

    assert section.healthy is True
    assert section.payload_id == "market-overview"
    assert section.component_count == 1
    assert section.metric_count == 1
    assert section.issue_count == 0
    assert section.resolved_components()[0].component_id == "market-overview-component"
    assert section.resolved_metrics()[0].name == "count"
    assert section.resolved_issues() == []

    assert payload["section_id"] == "market"
    assert payload["title"] == "Market"
    assert payload["kind"] == "market"
    assert payload["status"] == "ready"
    assert payload["healthy"] is True
    assert payload["payload_id"] == "market-overview"
    assert payload["payload"]["payload_id"] == "market-overview"


def test_dashboard_section_rejects_invalid_values():
    component = build_dashboard_component(
        component_id="component",
        title="Component",
        component_type="card",
    )
    metric = build_dashboard_metric(name="metric", value=1)

    with pytest.raises(ValueError):
        DashboardSection(section_id="", title="Section", kind="market")

    with pytest.raises(ValueError):
        DashboardSection(section_id="section", title="", kind="market")

    with pytest.raises(ValueError):
        DashboardSection(section_id="section", title="Section", kind="bad")

    with pytest.raises(ValueError):
        DashboardSection(section_id="section", title="Section", kind="market", status="bad")

    with pytest.raises(ValueError):
        DashboardSection(section_id="section", title="Section", kind="market", payload="bad")

    with pytest.raises(ValueError):
        DashboardSection(section_id="section", title="Section", kind="market", components="bad")

    with pytest.raises(ValueError):
        DashboardSection(section_id="section", title="Section", kind="market", components=["bad"])

    with pytest.raises(ValueError):
        DashboardSection(section_id="section", title="Section", kind="market", metrics="bad")

    with pytest.raises(ValueError):
        DashboardSection(section_id="section", title="Section", kind="market", metrics=["bad"])

    with pytest.raises(ValueError):
        DashboardSection(section_id="section", title="Section", kind="market", issues="bad")

    with pytest.raises(ValueError):
        DashboardSection(section_id="section", title="Section", kind="market", data=[])

    with pytest.raises(ValueError):
        DashboardSection(section_id="section", title="Section", kind="market", metadata=[])

    assert build_dashboard_section(
        section_id="section",
        title="Section",
        kind="custom",
        components=[component],
        metrics=[metric],
    ).component_count == 1


def test_build_section_from_payload():
    payload = sample_payload()
    section = build_section_from_payload(
        section_id="market",
        title="Market",
        kind="market",
        payload=payload,
    )

    assert isinstance(section, DashboardSection)
    assert section.status == DashboardStatus.READY
    assert section.payload == payload

    with pytest.raises(ValueError):
        build_section_from_payload(
            section_id="market",
            title="Market",
            kind="market",
            payload="bad",
        )


def test_dashboard_aggregation_snapshot_to_dict():
    snapshot = build_dashboard_aggregation_snapshot(
        snapshot_id="aqos-dashboard",
        title="AQOS Dashboard",
        sections=[sample_section()],
        generated_at="2026-01-01T00:00:00+00:00",
    )

    payload = snapshot.to_dict()

    assert isinstance(snapshot, DashboardAggregationSnapshot)
    assert snapshot.section_count == 1
    assert snapshot.payload_count == 1
    assert snapshot.component_count == 1
    assert snapshot.metric_count == 1
    assert snapshot.issue_count == 0
    assert snapshot.healthy is True
    assert payload["snapshot_id"] == "aqos-dashboard"
    assert payload["section_count"] == 1
    assert payload["payload_count"] == 1
    assert payload["component_count"] == 1


def test_dashboard_aggregation_snapshot_to_payload_modes():
    snapshot = build_dashboard_aggregation_snapshot(
        snapshot_id="aqos-dashboard",
        title="AQOS Dashboard",
        sections=[sample_section()],
        generated_at="2026-01-01T00:00:00+00:00",
    )

    full_payload = snapshot.to_dashboard_payload(mode="full")
    summary_payload = snapshot.to_dashboard_payload(mode="summary")
    compact_payload = snapshot.to_dashboard_payload(mode="compact")

    assert isinstance(full_payload, DashboardPayload)
    assert full_payload.payload_id == "aqos-dashboard"
    assert full_payload.component_count == 2
    assert full_payload.metric_count == 6
    assert full_payload.data["aggregation_mode"] == "full"

    assert summary_payload.component_count == 1
    assert summary_payload.metric_count == 5
    assert summary_payload.data["aggregation_mode"] == "summary"

    assert compact_payload.component_count == 0
    assert compact_payload.metric_count == 5
    assert compact_payload.data["aggregation_mode"] == "compact"


def test_dashboard_aggregation_snapshot_empty_payload():
    snapshot = build_dashboard_aggregation_snapshot(
        snapshot_id="aqos-dashboard",
        title="AQOS Dashboard",
        sections=[],
        generated_at="2026-01-01T00:00:00+00:00",
    )
    payload = snapshot.to_dashboard_payload()

    assert payload.status == DashboardStatus.EMPTY
    assert payload.component_count == 0
    assert payload.metric_count == 5


def test_dashboard_aggregation_snapshot_rejects_invalid_values():
    with pytest.raises(ValueError):
        DashboardAggregationSnapshot(snapshot_id="", title="Dashboard")

    with pytest.raises(ValueError):
        DashboardAggregationSnapshot(snapshot_id="dashboard", title="")

    with pytest.raises(ValueError):
        DashboardAggregationSnapshot(snapshot_id="dashboard", title="Dashboard", sections="bad")

    with pytest.raises(ValueError):
        DashboardAggregationSnapshot(snapshot_id="dashboard", title="Dashboard", sections=["bad"])

    with pytest.raises(ValueError):
        DashboardAggregationSnapshot(snapshot_id="dashboard", title="Dashboard", status="bad")

    with pytest.raises(ValueError):
        DashboardAggregationSnapshot(snapshot_id="dashboard", title="Dashboard", refresh_mode="bad")

    with pytest.raises(ValueError):
        DashboardAggregationSnapshot(snapshot_id="dashboard", title="Dashboard", generated_at="")

    with pytest.raises(ValueError):
        DashboardAggregationSnapshot(snapshot_id="dashboard", title="Dashboard", data=[])

    with pytest.raises(ValueError):
        DashboardAggregationSnapshot(snapshot_id="dashboard", title="Dashboard", metadata=[])


def test_dashboard_aggregation_hub_register_and_build():
    hub = build_dashboard_aggregation_hub(
        metadata={
            "env": "test",
        },
    )
    section = sample_section()

    registered = hub.register_section(section)
    same_section = hub.get_section("market")
    required_section = hub.require_section("market")
    snapshot = hub.build_snapshot(
        snapshot_id="aqos-dashboard",
        title="AQOS Dashboard",
        generated_at="2026-01-01T00:00:00+00:00",
    )
    payload = hub.build_payload(
        snapshot_id="aqos-dashboard",
        title="AQOS Dashboard",
        mode="summary",
    )

    assert isinstance(hub, DashboardAggregationHub)
    assert registered == section
    assert same_section == section
    assert required_section == section
    assert hub.section_count == 1
    assert snapshot.section_count == 1
    assert snapshot.metadata["env"] == "test"
    assert payload.payload_id == "aqos-dashboard"
    assert payload.data["aggregation_mode"] == "summary"
    assert hub.summary()["section_count"] == 1

    removed = hub.remove_section("market")
    assert removed == section
    assert hub.section_count == 0

    hub.register_section(section)
    hub.clear()
    assert hub.section_count == 0


def test_dashboard_aggregation_hub_register_payload():
    hub = build_dashboard_aggregation_hub()
    payload = sample_payload()

    section = hub.register_payload(
        section_id="market",
        title="Market",
        kind="market",
        payload=payload,
    )

    assert section.payload == payload
    assert hub.section_count == 1

    with pytest.raises(ValueError):
        hub.register_payload(
            section_id="market",
            title="Market",
            kind="market",
            payload="bad",
        )


def test_dashboard_aggregation_hub_rejects_invalid_values():
    section = sample_section()

    with pytest.raises(ValueError):
        DashboardAggregationHub(sections=[])

    with pytest.raises(ValueError):
        DashboardAggregationHub(sections={"": section})

    with pytest.raises(ValueError):
        DashboardAggregationHub(sections={"section": "bad"})

    with pytest.raises(ValueError):
        DashboardAggregationHub(metadata=[])

    hub = build_dashboard_aggregation_hub()

    with pytest.raises(ValueError):
        hub.register_section("bad")

    with pytest.raises(ValueError):
        hub.get_section("")

    with pytest.raises(KeyError):
        hub.require_section("missing")

    with pytest.raises(ValueError):
        hub.remove_section("")


def test_validate_helpers():
    section = sample_section()
    payload = sample_payload()

    assert validate_dashboard_sections([section]) == [section]
    assert validate_dashboard_section_dict({"section": section}) == {"section": section}
    assert validate_payload_dict({"payload": payload}) == {"payload": payload}

    with pytest.raises(ValueError):
        validate_dashboard_sections("bad")

    with pytest.raises(ValueError):
        validate_dashboard_sections(["bad"])

    with pytest.raises(ValueError):
        validate_dashboard_section_dict("bad")

    with pytest.raises(ValueError):
        validate_dashboard_section_dict({"": section})

    with pytest.raises(ValueError):
        validate_dashboard_section_dict({"section": "bad"})

    with pytest.raises(ValueError):
        validate_payload_dict("bad")

    with pytest.raises(ValueError):
        validate_payload_dict({"": payload})

    with pytest.raises(ValueError):
        validate_payload_dict({"payload": "bad"})


def test_infer_aggregation_status():
    ready = build_dashboard_section(section_id="ready", title="Ready", kind="custom", status="ready")
    warning = build_dashboard_section(section_id="warning", title="Warning", kind="custom", status="warning")
    error = build_dashboard_section(section_id="error", title="Error", kind="custom", status="error")
    empty = build_dashboard_section(section_id="empty", title="Empty", kind="custom", status="empty")

    assert infer_aggregation_status([]) == DashboardStatus.EMPTY
    assert infer_aggregation_status([ready]) == DashboardStatus.READY
    assert infer_aggregation_status([ready, warning]) == DashboardStatus.WARNING
    assert infer_aggregation_status([ready, empty]) == DashboardStatus.WARNING
    assert infer_aggregation_status([empty]) == DashboardStatus.EMPTY
    assert infer_aggregation_status([ready, error]) == DashboardStatus.ERROR

    with pytest.raises(ValueError):
        infer_aggregation_status(["bad"])


def test_summary_builders():
    snapshot = build_dashboard_aggregation_snapshot(
        snapshot_id="aqos-dashboard",
        title="AQOS Dashboard",
        sections=[sample_section()],
    )
    metrics = build_aggregation_summary_metrics(snapshot)
    components = build_section_summary_components([sample_section()])

    assert len(metrics) == 5
    assert metrics[0].name == "section_count"
    assert metrics[0].value == 1
    assert len(components) == 1
    assert components[0].component_id == "section-summary-market"

    with pytest.raises(ValueError):
        build_aggregation_summary_metrics("bad")

    with pytest.raises(ValueError):
        build_section_summary_components(["bad"])


def test_aggregate_dashboard_payloads():
    market_payload = build_market_overview_payload(
        snapshots=[
            build_market_overview_snapshot(
                symbol="XAUUSD",
                latest_price=2020,
                previous_price=2000,
            )
        ],
    )
    status_payload = sample_payload(
        payload_id="status",
        title="Status",
    )

    payload = aggregate_dashboard_payloads(
        payloads={
            "market": market_payload,
            "status": status_payload,
        },
        section_kinds={
            "market": "market",
            "status": "status",
        },
        snapshot_id="aqos-dashboard",
        title="AQOS Dashboard",
        mode="summary",
    )

    assert isinstance(payload, DashboardPayload)
    assert payload.payload_id == "aqos-dashboard"
    assert payload.status == DashboardStatus.READY
    assert payload.component_count == 2
    assert payload.metric_count == 5
    assert payload.data["section_count"] == 2
    assert payload.data["aggregation_mode"] == "summary"


def test_dashboard_aggregation_error_payload():
    payload = dashboard_aggregation_error_payload(
        error_code="dashboard_failed",
        error_message="Dashboard aggregation failed.",
    )

    assert payload.status == DashboardStatus.ERROR
    assert payload.issue_count == 1
    assert payload.issues[0].code == "dashboard_failed"

    with pytest.raises(ValueError):
        dashboard_aggregation_error_payload(
            error_code="",
            error_message="Failed.",
        )

    with pytest.raises(ValueError):
        dashboard_aggregation_error_payload(
            error_code="failed",
            error_message="",
        )


def test_dashboard_hub_exports_exist():
    import aqos.dashboard as dashboard

    expected_exports = [
        "DashboardAggregationHub",
        "DashboardAggregationMode",
        "DashboardAggregationSnapshot",
        "DashboardSection",
        "DashboardSectionKind",
        "aggregate_dashboard_payloads",
        "build_aggregation_summary_metrics",
        "build_dashboard_aggregation_hub",
        "build_dashboard_aggregation_snapshot",
        "build_dashboard_section",
        "build_section_from_payload",
        "build_section_summary_components",
        "dashboard_aggregation_error_payload",
        "infer_aggregation_status",
        "normalize_dashboard_aggregation_mode",
        "normalize_dashboard_section_kind",
        "validate_dashboard_section_dict",
        "validate_dashboard_sections",
        "validate_payload_dict",
    ]

    for export_name in expected_exports:
        assert hasattr(dashboard, export_name), export_name