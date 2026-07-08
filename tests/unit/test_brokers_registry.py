"""
Unit tests for AQOS broker registry.
"""

import pytest

from aqos.brokers import (
    BrokerCapability,
    BrokerConfig,
    BrokerRegistry,
    BrokerRegistryEntry,
    BrokerRegistrySummary,
    BrokerStatus,
    PaperBrokerAdapter,
    PositionAccountAdapter,
    broker_registry_error_result,
    broker_registry_to_result,
    build_broker_config,
    build_broker_registry,
    build_broker_registry_entry,
    build_paper_broker_adapter,
    build_position_account_adapter,
    register_broker_adapter,
    register_broker_config,
    register_paper_broker,
    resolve_paper_broker_adapter,
    resolve_position_account_adapter,
    summarize_broker_registry_entries,
    validate_broker_config_object,
    validate_broker_registry,
    validate_broker_registry_entries,
)


def build_paper_adapter(broker_id="paper-1"):
    return build_paper_broker_adapter(
        broker_id=broker_id,
        cash_balance=100000,
    )


def build_account_adapter(adapter):
    return build_position_account_adapter(
        broker_config=adapter.broker_config,
        account_id=f"{adapter.broker_id}-account",
        cash_balance=adapter.cash_balance,
    )


def build_exchange_config():
    return build_broker_config(
        broker_id="exchange-1",
        name="Exchange",
        broker_type="exchange",
        base_url="https://example.com",
        capabilities=["live_trading", "market_orders", "account_info"],
        paper_mode=False,
    )


def test_broker_registry_entry_to_dict():
    adapter = build_paper_adapter()
    account_adapter = build_account_adapter(adapter)

    entry = BrokerRegistryEntry(
        config=adapter.broker_config,
        adapter=adapter,
        account_adapter=account_adapter,
        metadata={
            "source": "test",
        },
    )

    payload = entry.to_dict()

    assert entry.broker_id == "paper-1"
    assert entry.active is True
    assert entry.has_adapter is True
    assert entry.has_account_adapter is True
    assert entry.supports("paper_trading") is True
    assert payload["broker_id"] == "paper-1"
    assert payload["broker_type"] == "paper"
    assert payload["status"] == "active"
    assert payload["adapter_type"] == "PaperBrokerAdapter"
    assert payload["account_adapter_type"] == "PositionAccountAdapter"
    assert payload["metadata"] == {
        "source": "test",
    }


def test_broker_registry_entry_rejects_invalid_values():
    adapter = build_paper_adapter()

    with pytest.raises(ValueError):
        BrokerRegistryEntry(config="bad")

    with pytest.raises(ValueError):
        BrokerRegistryEntry(config=adapter.broker_config, account_adapter="bad")

    with pytest.raises(ValueError):
        BrokerRegistryEntry(config=adapter.broker_config, metadata=[])


def test_broker_registry_summary_to_dict():
    summary = BrokerRegistrySummary(
        total=2,
        active=1,
        inactive=1,
        paper=1,
        exchange=1,
        with_adapters=1,
        with_account_adapters=1,
        metadata={
            "source": "test",
        },
    )

    assert summary.to_dict() == {
        "total": 2,
        "active": 1,
        "inactive": 1,
        "degraded": 0,
        "error": 0,
        "paper": 1,
        "exchange": 1,
        "with_adapters": 1,
        "with_account_adapters": 1,
        "metadata": {
            "source": "test",
        },
    }


def test_broker_registry_summary_rejects_invalid_values():
    with pytest.raises(ValueError):
        BrokerRegistrySummary(total=-1)

    with pytest.raises(ValueError):
        BrokerRegistrySummary(total=1, active=-1)

    with pytest.raises(ValueError):
        BrokerRegistrySummary(total=1, metadata=[])


def test_build_broker_registry_entry_and_registry():
    adapter = build_paper_adapter()

    entry = build_broker_registry_entry(
        config=adapter.broker_config,
        adapter=adapter,
    )
    registry = build_broker_registry(
        entries={
            "paper-1": entry,
        },
        metadata={
            "source": "test",
        },
    )

    assert isinstance(entry, BrokerRegistryEntry)
    assert isinstance(registry, BrokerRegistry)
    assert registry.count() == 1
    assert registry.metadata == {
        "source": "test",
    }


def test_validate_registry_helpers():
    adapter = build_paper_adapter()
    entry = build_broker_registry_entry(config=adapter.broker_config)

    registry = build_broker_registry(
        entries={
            "paper-1": entry,
        },
    )

    assert validate_broker_config_object(adapter.broker_config) == adapter.broker_config
    assert validate_broker_registry_entries({"paper-1": entry}) == {"paper-1": entry}
    assert validate_broker_registry(registry) == registry

    with pytest.raises(ValueError):
        validate_broker_config_object("bad")

    with pytest.raises(ValueError):
        validate_broker_registry_entries("bad")

    with pytest.raises(ValueError):
        validate_broker_registry_entries({"": entry})

    with pytest.raises(ValueError):
        validate_broker_registry_entries({"paper-1": "bad"})

    with pytest.raises(ValueError):
        validate_broker_registry("bad")


def test_registry_register_config_adapter_and_account_adapter():
    registry = build_broker_registry()
    adapter = build_paper_adapter()
    account_adapter = build_account_adapter(adapter)

    config_entry = registry.register_config(
        adapter.broker_config,
        metadata={
            "config_only": True,
        },
    )

    assert config_entry.broker_id == "paper-1"
    assert config_entry.has_adapter is False
    assert registry.count() == 1

    adapter_entry = registry.register_adapter(
        config=adapter.broker_config,
        adapter=adapter,
        metadata={
            "adapter": True,
        },
    )

    assert adapter_entry.has_adapter is True
    assert registry.get_adapter("paper-1") == adapter

    account_entry = registry.attach_account_adapter(
        broker_id="paper-1",
        account_adapter=account_adapter,
        metadata={
            "account": True,
        },
    )

    assert account_entry.has_account_adapter is True
    assert registry.get_account_adapter("paper-1") == account_adapter
    assert registry.require("paper-1").metadata["account"] is True

    with pytest.raises(ValueError):
        registry.register_entry("bad")

    with pytest.raises(ValueError):
        registry.register_adapter(config=adapter.broker_config, adapter=None)

    with pytest.raises(ValueError):
        registry.attach_account_adapter(broker_id="paper-1", account_adapter="bad")

    with pytest.raises(KeyError):
        registry.attach_account_adapter(broker_id="missing", account_adapter=account_adapter)


def test_registry_get_list_remove_clear():
    registry = build_broker_registry()
    adapter = build_paper_adapter()
    account_adapter = build_account_adapter(adapter)

    register_paper_broker(
        registry=registry,
        adapter=adapter,
        account_adapter=account_adapter,
    )

    assert registry.has("paper-1") is True
    assert registry.has("missing") is False
    assert registry.get("paper-1").broker_id == "paper-1"
    assert registry.get("missing") is None
    assert registry.get_config("paper-1") == adapter.broker_config
    assert registry.get_adapter("paper-1") == adapter
    assert registry.get_account_adapter("paper-1") == account_adapter
    assert registry.broker_ids() == ["paper-1"]
    assert registry.list_entries()[0].broker_id == "paper-1"
    assert registry.list_configs()[0] == adapter.broker_config
    assert registry.list_adapters()[0] == adapter
    assert registry.list_account_adapters()[0] == account_adapter

    removed = registry.remove("paper-1")

    assert removed.broker_id == "paper-1"
    assert registry.count() == 0
    assert registry.remove("missing") is None

    register_paper_broker(registry=registry, adapter=adapter)
    assert registry.count() == 1
    registry.clear()
    assert registry.count() == 0

    with pytest.raises(KeyError):
        registry.require("missing")


def test_registry_filters_and_selection():
    registry = build_broker_registry()
    paper_adapter = build_paper_adapter()
    exchange_config = build_exchange_config()

    register_paper_broker(
        registry=registry,
        adapter=paper_adapter,
    )
    registry.register_config(exchange_config)

    assert len(registry.active_entries()) == 2
    assert len(registry.entries_by_type("paper")) == 1
    assert len(registry.entries_by_type("exchange")) == 1
    assert len(registry.entries_supporting("market_orders")) == 2
    assert len(registry.paper_entries()) == 1
    assert len(registry.live_entries()) == 1

    selected = registry.select_broker(
        broker_type="paper",
        capability="paper_trading",
        require_adapter=True,
    )

    assert selected.broker_id == "paper-1"

    selected_preferred = registry.select_broker(
        preferred_broker_id="exchange-1",
        broker_type="exchange",
    )

    assert selected_preferred.broker_id == "exchange-1"

    assert registry.select_broker(preferred_broker_id="missing") is None
    assert registry.select_broker(preferred_broker_id="exchange-1", require_adapter=True) is None
    assert registry.select_broker(broker_type="crypto") is None


def test_registry_resolve_adapters():
    registry = build_broker_registry()
    paper_adapter = build_paper_adapter()
    account_adapter = build_account_adapter(paper_adapter)

    register_paper_broker(
        registry=registry,
        adapter=paper_adapter,
        account_adapter=account_adapter,
    )

    resolved_adapter = registry.resolve_adapter(
        broker_type="paper",
        capability="paper_trading",
    )
    resolved_account_adapter = registry.resolve_account_adapter()

    assert resolved_adapter == paper_adapter
    assert resolved_account_adapter == account_adapter
    assert registry.resolve_adapter(preferred_broker_id="missing") is None
    assert registry.resolve_account_adapter(preferred_broker_id="missing") is None


def test_registry_summary_and_to_dict():
    registry = build_broker_registry(
        metadata={
            "source": "test",
        },
    )
    paper_adapter = build_paper_adapter()
    account_adapter = build_account_adapter(paper_adapter)

    inactive_config = build_broker_config(
        broker_id="inactive",
        name="Inactive",
        broker_type="paper",
        status=BrokerStatus.INACTIVE,
        capabilities=["paper_trading"],
        paper_mode=True,
    )

    register_paper_broker(
        registry=registry,
        adapter=paper_adapter,
        account_adapter=account_adapter,
    )
    registry.register_config(inactive_config)

    summary = registry.summary()
    payload = registry.to_dict()

    assert summary.total == 2
    assert summary.active == 1
    assert summary.inactive == 1
    assert summary.paper == 2
    assert summary.with_adapters == 1
    assert summary.with_account_adapters == 1
    assert payload["summary"]["total"] == 2
    assert len(payload["entries"]) == 2
    assert payload["metadata"] == {
        "source": "test",
    }


def test_summarize_broker_registry_entries():
    adapter = build_paper_adapter()
    entry = build_broker_registry_entry(
        config=adapter.broker_config,
        adapter=adapter,
    )

    summary = summarize_broker_registry_entries(
        [entry],
        metadata={
            "source": "test",
        },
    )

    assert summary.total == 1
    assert summary.active == 1
    assert summary.paper == 1
    assert summary.with_adapters == 1
    assert summary.metadata == {
        "source": "test",
    }

    with pytest.raises(ValueError):
        summarize_broker_registry_entries("bad")

    with pytest.raises(ValueError):
        summarize_broker_registry_entries(["bad"])


def test_registry_result_helpers():
    registry = build_broker_registry()
    adapter = build_paper_adapter()
    register_paper_broker(registry=registry, adapter=adapter)

    result = broker_registry_to_result(registry)
    error = broker_registry_error_result(
        error="failed",
        operation="register",
    )

    assert result.success is True
    assert result.data["registry"]["summary"]["total"] == 1
    assert error.success is False
    assert error.error == "failed"
    assert error.metadata["operation"] == "register"

    with pytest.raises(ValueError):
        broker_registry_to_result("bad")

    with pytest.raises(ValueError):
        broker_registry_error_result(error="failed", operation="")


def test_register_helper_functions():
    registry = build_broker_registry()
    adapter = build_paper_adapter()
    account_adapter = build_account_adapter(adapter)
    exchange_config = build_exchange_config()

    config_entry = register_broker_config(
        registry=registry,
        config=exchange_config,
    )
    adapter_entry = register_broker_adapter(
        registry=registry,
        config=adapter.broker_config,
        adapter=adapter,
        account_adapter=account_adapter,
    )

    assert config_entry.broker_id == "exchange-1"
    assert adapter_entry.broker_id == "paper-1"

    with pytest.raises(ValueError):
        register_broker_config(registry="bad", config=exchange_config)

    with pytest.raises(ValueError):
        register_broker_adapter(registry="bad", config=adapter.broker_config, adapter=adapter)


def test_register_and_resolve_paper_broker():
    registry = build_broker_registry()
    adapter = build_paper_adapter()
    account_adapter = build_account_adapter(adapter)

    entry = register_paper_broker(
        registry=registry,
        adapter=adapter,
        account_adapter=account_adapter,
        metadata={
            "source": "paper",
        },
    )

    resolved_paper = resolve_paper_broker_adapter(registry)
    resolved_account = resolve_position_account_adapter(registry)

    assert entry.broker_id == "paper-1"
    assert entry.metadata == {
        "source": "paper",
    }
    assert isinstance(resolved_paper, PaperBrokerAdapter)
    assert isinstance(resolved_account, PositionAccountAdapter)

    assert resolve_paper_broker_adapter(registry, preferred_broker_id="missing") is None
    assert resolve_position_account_adapter(registry, preferred_broker_id="missing") is None

    with pytest.raises(ValueError):
        register_paper_broker(registry="bad", adapter=adapter)

    with pytest.raises(ValueError):
        register_paper_broker(registry=registry, adapter="bad")

    with pytest.raises(ValueError):
        resolve_paper_broker_adapter("bad")

    with pytest.raises(ValueError):
        resolve_position_account_adapter("bad")


def test_resolve_paper_broker_adapter_rejects_wrong_adapter_type():
    registry = build_broker_registry()
    config = build_broker_config(
        broker_id="paper-wrong",
        name="Paper Wrong",
        broker_type="paper",
        capabilities=["paper_trading"],
        paper_mode=True,
    )

    registry.register_adapter(
        config=config,
        adapter=object(),
    )

    with pytest.raises(ValueError):
        resolve_paper_broker_adapter(registry)


def test_broker_registry_exports_exist():
    import aqos.brokers as brokers

    expected_exports = [
        "BrokerRegistry",
        "BrokerRegistryEntry",
        "BrokerRegistrySummary",
        "broker_registry_error_result",
        "broker_registry_to_result",
        "build_broker_registry",
        "build_broker_registry_entry",
        "register_broker_adapter",
        "register_broker_config",
        "register_paper_broker",
        "resolve_paper_broker_adapter",
        "resolve_position_account_adapter",
        "summarize_broker_registry_entries",
        "validate_broker_config_object",
        "validate_broker_registry",
        "validate_broker_registry_entries",
    ]

    for export_name in expected_exports:
        assert hasattr(brokers, export_name), export_name