"""
Unit tests for AQOS broker/provider status dashboard payloads.
"""

import pytest

from aqos.brokers import (
    build_broker_config,
    build_broker_registry,
    build_paper_broker_adapter,
    register_paper_broker,
)
from aqos.dashboard import (
    BrokerProviderStatusSnapshot,
    DashboardCard,
    DashboardPayload,
    DashboardStatus,
    DashboardWidget,
    IntegrationHealthState,
    IntegrationStatusItem,
    IntegrationStatusKind,
    broker_config_to_integration_item,
    broker_registry_to_status_items,
    build_broker_provider_status_card,
    build_broker_provider_status_payload,
    build_broker_provider_status_snapshot,
    build_broker_provider_status_snapshot_from_registries,
    build_broker_status_widget,
    build_integration_status_item,
    build_provider_status_widget,
    build_status_summary_widget,
    build_status_table_widget,
    dashboard_status_from_integration_health,
    integration_health_from_status,
    normalize_integration_health_state,
    normalize_integration_status_kind,
    provider_config_to_integration_item,
    provider_registry_to_status_items,
    status_dict_to_integration_item,
    status_snapshot_to_metrics,
    validate_capability_names,
    validate_integration_status_items,
)
from aqos.providers import (
    build_provider_config,
    build_provider_registry,
)


def sample_broker_item():
    return build_integration_status_item(
        status_id="paper-broker",
        name="Paper Broker",
        kind="broker",
        health="online",
        connected=True,
        active=True,
        capabilities=["paper_trading", "market_orders"],
        latency_ms=12.5,
        last_checked_at="2026-01-01T00:00:00+00:00",
        message="Broker healthy.",
        metadata={
            "source": "test",
        },
    )


def sample_provider_item():
    return build_integration_status_item(
        status_id="csv-provider",
        name="CSV Provider",
        kind="provider",
        health="degraded",
        connected=True,
        active=True,
        capabilities=["historical_ohlcv"],
        latency_ms=5.5,
        message="Provider degraded.",
    )


def sample_snapshot():
    return build_broker_provider_status_snapshot(
        broker_items=[sample_broker_item()],
        provider_items=[sample_provider_item()],
        generated_at="2026-01-01T00:00:00+00:00",
    )


def test_status_enum_values():
    assert IntegrationStatusKind.BROKER.value == "broker"
    assert IntegrationStatusKind.PROVIDER.value == "provider"
    assert IntegrationStatusKind.EXCHANGE.value == "exchange"
    assert IntegrationStatusKind.DATA.value == "data"
    assert IntegrationStatusKind.EXECUTION.value == "execution"
    assert IntegrationStatusKind.UNKNOWN.value == "unknown"

    assert IntegrationHealthState.ONLINE.value == "online"
    assert IntegrationHealthState.OFFLINE.value == "offline"
    assert IntegrationHealthState.DEGRADED.value == "degraded"
    assert IntegrationHealthState.ERROR.value == "error"
    assert IntegrationHealthState.UNKNOWN.value == "unknown"


def test_status_normalizers():
    assert normalize_integration_status_kind(IntegrationStatusKind.BROKER) == IntegrationStatusKind.BROKER
    assert normalize_integration_status_kind(" PROVIDER ") == IntegrationStatusKind.PROVIDER
    assert normalize_integration_health_state(IntegrationHealthState.ONLINE) == IntegrationHealthState.ONLINE
    assert normalize_integration_health_state(" DEGRADED ") == IntegrationHealthState.DEGRADED

    with pytest.raises(ValueError):
        normalize_integration_status_kind("bad")

    with pytest.raises(ValueError):
        normalize_integration_health_state("bad")


def test_health_mapping_helpers():
    assert integration_health_from_status("active") == IntegrationHealthState.ONLINE
    assert integration_health_from_status("ready") == IntegrationHealthState.ONLINE
    assert integration_health_from_status("inactive") == IntegrationHealthState.OFFLINE
    assert integration_health_from_status("degraded") == IntegrationHealthState.DEGRADED
    assert integration_health_from_status("error") == IntegrationHealthState.ERROR
    assert integration_health_from_status("something") == IntegrationHealthState.UNKNOWN

    assert dashboard_status_from_integration_health("online") == DashboardStatus.READY
    assert dashboard_status_from_integration_health("degraded") == DashboardStatus.WARNING
    assert dashboard_status_from_integration_health("offline") == DashboardStatus.ERROR
    assert dashboard_status_from_integration_health("unknown") == DashboardStatus.EMPTY


def test_integration_status_item_to_dict():
    item = sample_broker_item()
    payload = item.to_dict()

    assert item.healthy is True
    assert item.unhealthy is False
    assert item.degraded is False
    assert payload["status_id"] == "paper-broker"
    assert payload["name"] == "Paper Broker"
    assert payload["kind"] == "broker"
    assert payload["health"] == "online"
    assert payload["connected"] is True
    assert payload["active"] is True
    assert payload["capability_count"] == 2
    assert payload["latency_ms"] == 12.5
    assert payload["metadata"] == {
        "source": "test",
    }


def test_integration_status_item_rejects_invalid_values():
    with pytest.raises(ValueError):
        IntegrationStatusItem(status_id="", name="Item", kind="broker")

    with pytest.raises(ValueError):
        IntegrationStatusItem(status_id="item", name="", kind="broker")

    with pytest.raises(ValueError):
        IntegrationStatusItem(status_id="item", name="Item", kind="bad")

    with pytest.raises(ValueError):
        IntegrationStatusItem(status_id="item", name="Item", kind="broker", health="bad")

    with pytest.raises(ValueError):
        IntegrationStatusItem(status_id="item", name="Item", kind="broker", connected="yes")

    with pytest.raises(ValueError):
        IntegrationStatusItem(status_id="item", name="Item", kind="broker", active="yes")

    with pytest.raises(ValueError):
        IntegrationStatusItem(status_id="item", name="Item", kind="broker", capability_count=-1)

    with pytest.raises(ValueError):
        IntegrationStatusItem(status_id="item", name="Item", kind="broker", capabilities="bad")

    with pytest.raises(ValueError):
        IntegrationStatusItem(status_id="item", name="Item", kind="broker", capabilities=[""])

    with pytest.raises(ValueError):
        IntegrationStatusItem(status_id="item", name="Item", kind="broker", latency_ms=-1)

    with pytest.raises(ValueError):
        IntegrationStatusItem(status_id="item", name="Item", kind="broker", last_checked_at=123)

    with pytest.raises(ValueError):
        IntegrationStatusItem(status_id="item", name="Item", kind="broker", message=123)

    with pytest.raises(ValueError):
        IntegrationStatusItem(status_id="item", name="Item", kind="broker", metadata=[])


def test_status_dict_to_integration_item():
    item = status_dict_to_integration_item(
        {
            "id": "provider-1",
            "name": "Provider 1",
            "kind": "provider",
            "health": "online",
            "connected": True,
            "active": True,
            "capabilities": ["live_quotes"],
            "latency_ms": 3,
        }
    )

    assert item.status_id == "provider-1"
    assert item.name == "Provider 1"
    assert item.kind == "provider"
    assert item.capability_count == 1

    with pytest.raises(ValueError):
        status_dict_to_integration_item([])

    with pytest.raises(ValueError):
        status_dict_to_integration_item({"id": "bad"})


def test_status_validators():
    item = sample_broker_item()

    assert validate_capability_names(["a", "b"]) == ["a", "b"]
    assert validate_integration_status_items([item]) == [item]

    with pytest.raises(ValueError):
        validate_capability_names("bad")

    with pytest.raises(ValueError):
        validate_capability_names([""])

    with pytest.raises(ValueError):
        validate_integration_status_items("bad")

    with pytest.raises(ValueError):
        validate_integration_status_items(["bad"])


def test_snapshot_to_dict_and_counts():
    snapshot = sample_snapshot()
    payload = snapshot.to_dict()

    assert snapshot.item_count == 2
    assert snapshot.broker_count == 1
    assert snapshot.provider_count == 1
    assert snapshot.online_count == 1
    assert snapshot.degraded_count == 1
    assert snapshot.error_count == 0
    assert snapshot.healthy is True
    assert snapshot.status_counts()["online"] == 1
    assert snapshot.status_counts()["degraded"] == 1

    assert payload["snapshot_id"] == "broker-provider-status"
    assert payload["item_count"] == 2
    assert payload["broker_count"] == 1
    assert payload["provider_count"] == 1
    assert payload["generated_at"] == "2026-01-01T00:00:00+00:00"


def test_snapshot_rejects_invalid_values():
    item = sample_broker_item()

    with pytest.raises(ValueError):
        BrokerProviderStatusSnapshot(snapshot_id="")

    with pytest.raises(ValueError):
        BrokerProviderStatusSnapshot(snapshot_id="status", items="bad")

    with pytest.raises(ValueError):
        BrokerProviderStatusSnapshot(snapshot_id="status", items=["bad"])

    with pytest.raises(ValueError):
        BrokerProviderStatusSnapshot(snapshot_id="status", generated_at=123)

    with pytest.raises(ValueError):
        BrokerProviderStatusSnapshot(snapshot_id="status", metadata=[])

    assert validate_integration_status_items([item]) == [item]


def test_broker_config_to_integration_item():
    config = build_broker_config(
        broker_id="broker-1",
        name="Broker 1",
        broker_type="paper",
        capabilities=["paper_trading", "market_orders"],
        paper_mode=True,
    )

    item = broker_config_to_integration_item(config)

    assert item.status_id == "broker-1"
    assert item.name == "Broker 1"
    assert item.kind == IntegrationStatusKind.BROKER
    assert item.health == IntegrationHealthState.ONLINE
    assert item.capability_count == 2
    assert item.metadata["broker_type"] == "paper"

    with pytest.raises(ValueError):
        broker_config_to_integration_item(None)


def test_provider_config_to_integration_item():
    config = build_provider_config(
        provider_id="provider-1",
        name="Provider 1",
        provider_type="market_data",
        capabilities=["historical_ohlcv"],
    )

    item = provider_config_to_integration_item(config)

    assert item.status_id == "provider-1"
    assert item.name == "Provider 1"
    assert item.kind == IntegrationStatusKind.DATA
    assert item.health == IntegrationHealthState.ONLINE
    assert item.capability_count == 1
    assert item.metadata["provider_type"] == "market_data"

    with pytest.raises(ValueError):
        provider_config_to_integration_item(None)


def test_registry_to_status_items():
    broker_registry = build_broker_registry()
    paper_adapter = build_paper_broker_adapter(broker_id="paper-broker")
    register_paper_broker(
        registry=broker_registry,
        adapter=paper_adapter,
    )

    provider_registry = build_provider_registry()
    provider_config = build_provider_config(
        provider_id="csv-provider",
        name="CSV Provider",
        provider_type="market_data",
        capabilities=["historical_ohlcv"],
    )
    provider_registry.register_config(provider_config)

    broker_items = broker_registry_to_status_items(broker_registry)
    provider_items = provider_registry_to_status_items(provider_registry)

    assert len(broker_items) == 1
    assert broker_items[0].status_id == "paper-broker"
    assert broker_items[0].connected is True
    assert broker_items[0].metadata["has_adapter"] is True

    assert len(provider_items) == 1
    assert provider_items[0].status_id == "csv-provider"
    assert provider_items[0].connected is False
    assert provider_items[0].metadata["has_adapter"] is False

    with pytest.raises(ValueError):
        broker_registry_to_status_items(None)

    with pytest.raises(ValueError):
        provider_registry_to_status_items(None)


def test_build_snapshot_from_registries():
    broker_registry = build_broker_registry()
    paper_adapter = build_paper_broker_adapter(broker_id="paper-broker")
    register_paper_broker(
        registry=broker_registry,
        adapter=paper_adapter,
    )

    provider_registry = build_provider_registry()
    provider_registry.register_config(
    build_provider_config(
        provider_id="csv-provider",
        name="CSV Provider",
        provider_type="market_data",
        capabilities=["historical_ohlcv"],
        )
    )

    snapshot = build_broker_provider_status_snapshot_from_registries(
        broker_registry=broker_registry,
        provider_registry=provider_registry,
    )

    assert snapshot.item_count == 2
    assert snapshot.broker_count == 1
    assert snapshot.provider_count == 1


def test_status_snapshot_to_metrics():
    metrics = status_snapshot_to_metrics(sample_snapshot())

    assert len(metrics) == 6
    assert metrics[0].name == "integration_count"
    assert metrics[0].value == 2
    assert metrics[3].name == "online_count"
    assert metrics[3].value == 1

    with pytest.raises(ValueError):
        status_snapshot_to_metrics("bad")


def test_build_status_summary_widget():
    widget = build_status_summary_widget(sample_snapshot())

    assert isinstance(widget, DashboardWidget)
    assert widget.widget_id == "broker-provider-status-summary"
    assert widget.status == DashboardStatus.READY
    assert widget.metric_count == 6
    assert widget.action_count == 1
    assert widget.series_count == 1
    assert widget.data["item_count"] == 2

    error_snapshot = build_broker_provider_status_snapshot(
        broker_items=[
            build_integration_status_item(
                status_id="bad-broker",
                name="Bad Broker",
                kind="broker",
                health="error",
            )
        ],
    )
    error_widget = build_status_summary_widget(error_snapshot)

    assert error_widget.status == DashboardStatus.ERROR
    assert error_widget.issue_count == 1

    with pytest.raises(ValueError):
        build_status_summary_widget("bad")


def test_build_status_table_widget():
    widget = build_status_table_widget(sample_snapshot())

    assert isinstance(widget, DashboardWidget)
    assert widget.widget_id == "broker-provider-status-table"
    assert widget.status == DashboardStatus.READY
    assert widget.row_count == 2
    assert widget.table_rows[0]["status_id"] == "paper-broker"

    empty_widget = build_status_table_widget(
        build_broker_provider_status_snapshot(),
    )

    assert empty_widget.status == DashboardStatus.EMPTY

    with pytest.raises(ValueError):
        build_status_table_widget("bad")


def test_build_broker_and_provider_widgets():
    snapshot = sample_snapshot()
    broker_widget = build_broker_status_widget(snapshot)
    provider_widget = build_provider_status_widget(snapshot)

    assert isinstance(broker_widget, DashboardWidget)
    assert broker_widget.widget_id == "broker-status"
    assert broker_widget.status == DashboardStatus.READY
    assert broker_widget.metric_count == 3

    assert isinstance(provider_widget, DashboardWidget)
    assert provider_widget.widget_id == "provider-status"
    assert provider_widget.status == DashboardStatus.READY
    assert provider_widget.metric_count == 3

    empty_snapshot = build_broker_provider_status_snapshot()
    assert build_broker_status_widget(empty_snapshot).status == DashboardStatus.EMPTY
    assert build_provider_status_widget(empty_snapshot).status == DashboardStatus.EMPTY

    with pytest.raises(ValueError):
        build_broker_status_widget("bad")

    with pytest.raises(ValueError):
        build_provider_status_widget("bad")


def test_build_broker_provider_status_card():
    card = build_broker_provider_status_card(sample_snapshot())

    assert isinstance(card, DashboardCard)
    assert card.card_id == "broker-provider-status-card"
    assert card.status == DashboardStatus.READY
    assert card.primary_metric.name == "integration_count"
    assert card.widget_count == 4
    assert card.data["item_count"] == 2

    error_card = build_broker_provider_status_card(
        build_broker_provider_status_snapshot(
            broker_items=[
                build_integration_status_item(
                    status_id="bad-broker",
                    name="Bad Broker",
                    kind="broker",
                    health="error",
                )
            ],
        )
    )

    assert error_card.status == DashboardStatus.ERROR

    with pytest.raises(ValueError):
        build_broker_provider_status_card("bad")


def test_build_broker_provider_status_payload():
    snapshot = sample_snapshot()
    payload = build_broker_provider_status_payload(
        snapshot=snapshot,
    )

    assert isinstance(payload, DashboardPayload)
    assert payload.payload_id == "broker-provider-status-dashboard"
    assert payload.status == DashboardStatus.READY
    assert payload.component_count == 3
    assert payload.metric_count == 6
    assert payload.data["item_count"] == 2

    empty_payload = build_broker_provider_status_payload(
        snapshot=build_broker_provider_status_snapshot(),
    )

    assert empty_payload.status == DashboardStatus.EMPTY
    assert empty_payload.component_count == 1

    error_payload = build_broker_provider_status_payload(
        snapshot=build_broker_provider_status_snapshot(
            broker_items=[
                build_integration_status_item(
                    status_id="bad-broker",
                    name="Bad Broker",
                    kind="broker",
                    health="error",
                )
            ],
        ),
    )

    assert error_payload.status == DashboardStatus.ERROR

    with pytest.raises(ValueError):
        build_broker_provider_status_payload(snapshot="bad")


def test_dashboard_status_exports_exist():
    import aqos.dashboard as dashboard

    expected_exports = [
        "BrokerProviderStatusSnapshot",
        "IntegrationHealthState",
        "IntegrationStatusItem",
        "IntegrationStatusKind",
        "broker_config_to_integration_item",
        "broker_registry_to_status_items",
        "build_broker_provider_status_card",
        "build_broker_provider_status_payload",
        "build_broker_provider_status_snapshot",
        "build_broker_provider_status_snapshot_from_registries",
        "build_broker_status_widget",
        "build_integration_status_item",
        "build_provider_status_widget",
        "build_status_summary_widget",
        "build_status_table_widget",
        "dashboard_status_from_integration_health",
        "integration_health_from_status",
        "normalize_integration_health_state",
        "normalize_integration_status_kind",
        "provider_config_to_integration_item",
        "provider_registry_to_status_items",
        "status_dict_to_integration_item",
        "status_snapshot_to_metrics",
        "validate_capability_names",
        "validate_integration_status_items",
    ]

    for export_name in expected_exports:
        assert hasattr(dashboard, export_name), export_name