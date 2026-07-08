"""
Unit tests for AQOS provider registry.
"""

import pytest

from aqos.providers import (
    HistoricalOhlcvAdapter,
    LiveMarketDataAdapter,
    ProviderCapability,
    ProviderConfig,
    ProviderRegistry,
    ProviderRegistryEntry,
    ProviderRegistrySummary,
    ProviderStatus,
    ProviderType,
    build_historical_ohlcv_adapter,
    build_live_market_data_adapter,
    build_provider_config,
    build_provider_registry,
    build_provider_registry_entry,
    normalize_provider_status_value,
    normalize_provider_type_value,
    provider_registry_error_result,
    provider_registry_to_result,
    register_market_data_provider,
    resolve_historical_adapter,
    resolve_live_adapter,
    summarize_provider_registry_entries,
    validate_provider_config_object,
    validate_provider_registry,
    validate_provider_registry_entries,
)


def historical_config(provider_id: str = "historical-1") -> ProviderConfig:
    return build_provider_config(
        provider_id=provider_id,
        name="Historical Provider",
        provider_type="market_data",
        capabilities=["historical_ohlcv"],
    )


def live_config(provider_id: str = "live-1") -> ProviderConfig:
    return build_provider_config(
        provider_id=provider_id,
        name="Live Provider",
        provider_type="market_data",
        capabilities=["live_quotes", "ticks"],
    )


def test_registry_normalizers_accept_enum_and_string():
    assert normalize_provider_type_value(ProviderType.MARKET_DATA) == ProviderType.MARKET_DATA
    assert normalize_provider_type_value(" MARKET_DATA ") == ProviderType.MARKET_DATA
    assert normalize_provider_status_value(ProviderStatus.ACTIVE) == ProviderStatus.ACTIVE
    assert normalize_provider_status_value(" DEGRADED ") == ProviderStatus.DEGRADED


def test_registry_normalizers_reject_invalid_values():
    with pytest.raises(ValueError):
        normalize_provider_type_value("bad")

    with pytest.raises(ValueError):
        normalize_provider_status_value("bad")


def test_provider_registry_entry_to_dict():
    config = historical_config()
    adapter = build_historical_ohlcv_adapter(provider_config=config)
    entry = ProviderRegistryEntry(
        config=config,
        adapter=adapter,
        metadata={
            "source": "test",
        },
    )

    payload = entry.to_dict()

    assert entry.provider_id == "historical-1"
    assert entry.active is True
    assert entry.has_adapter is True
    assert entry.supports("historical_ohlcv") is True
    assert payload["provider_id"] == "historical-1"
    assert payload["has_adapter"] is True
    assert payload["adapter_type"] == "HistoricalOhlcvAdapter"
    assert payload["metadata"] == {
        "source": "test",
    }


def test_provider_registry_entry_rejects_invalid_values():
    with pytest.raises(ValueError):
        ProviderRegistryEntry(config="bad")

    with pytest.raises(ValueError):
        ProviderRegistryEntry(config=historical_config(), metadata=[])


def test_build_provider_registry_entry():
    entry = build_provider_registry_entry(
        config=historical_config(),
    )

    assert isinstance(entry, ProviderRegistryEntry)
    assert entry.provider_id == "historical-1"


def test_registry_summary_to_dict():
    summary = ProviderRegistrySummary(
        total=4,
        active=1,
        inactive=1,
        degraded=1,
        error=1,
        with_adapters=2,
        metadata={
            "source": "test",
        },
    )

    assert summary.to_dict() == {
        "total": 4,
        "active": 1,
        "inactive": 1,
        "degraded": 1,
        "error": 1,
        "with_adapters": 2,
        "metadata": {
            "source": "test",
        },
    }


def test_registry_summary_rejects_invalid_values():
    with pytest.raises(ValueError):
        ProviderRegistrySummary(total=-1)

    with pytest.raises(ValueError):
        ProviderRegistrySummary(metadata=[])


def test_summarize_provider_registry_entries():
    active_entry = build_provider_registry_entry(
        config=build_provider_config(
            provider_id="active",
            name="Active",
            provider_type="market_data",
            status="active",
            capabilities=["historical_ohlcv"],
        ),
        adapter=object(),
    )
    inactive_entry = build_provider_registry_entry(
        config=build_provider_config(
            provider_id="inactive",
            name="Inactive",
            provider_type="market_data",
            status="inactive",
            capabilities=["live_quotes"],
        ),
    )
    degraded_entry = build_provider_registry_entry(
        config=build_provider_config(
            provider_id="degraded",
            name="Degraded",
            provider_type="market_data",
            status="degraded",
            capabilities=["ticks"],
        ),
    )
    error_entry = build_provider_registry_entry(
        config=build_provider_config(
            provider_id="error",
            name="Error",
            provider_type="market_data",
            status="error",
            capabilities=["ticks"],
        ),
    )

    summary = summarize_provider_registry_entries(
        [active_entry, inactive_entry, degraded_entry, error_entry],
        metadata={
            "source": "test",
        },
    )

    assert summary.to_dict() == {
        "total": 4,
        "active": 1,
        "inactive": 1,
        "degraded": 1,
        "error": 1,
        "with_adapters": 1,
        "metadata": {
            "source": "test",
        },
    }

    with pytest.raises(ValueError):
        summarize_provider_registry_entries("bad")

    with pytest.raises(ValueError):
        summarize_provider_registry_entries(["bad"])


def test_validate_registry_helpers():
    entry = build_provider_registry_entry(config=historical_config())
    registry = build_provider_registry(
        entries={
            "historical-1": entry,
        },
    )

    assert validate_provider_config_object(historical_config()) == historical_config()
    assert validate_provider_registry_entries({"historical-1": entry}) == {"historical-1": entry}
    assert validate_provider_registry(registry) == registry

    with pytest.raises(ValueError):
        validate_provider_config_object("bad")

    with pytest.raises(ValueError):
        validate_provider_registry_entries("bad")

    with pytest.raises(ValueError):
        validate_provider_registry_entries({"": entry})

    with pytest.raises(ValueError):
        validate_provider_registry_entries({"historical-1": "bad"})

    with pytest.raises(ValueError):
        validate_provider_registry("bad")


def test_provider_registry_register_get_remove_clear():
    registry = build_provider_registry(
        metadata={
            "source": "test",
        },
    )
    config = historical_config()
    adapter = build_historical_ohlcv_adapter(provider_config=config)

    entry = registry.register_adapter(
        config=config,
        adapter=adapter,
        metadata={
            "kind": "historical",
        },
    )

    assert isinstance(registry, ProviderRegistry)
    assert isinstance(entry, ProviderRegistryEntry)
    assert registry.count() == 1
    assert registry.has("historical-1") is True
    assert registry.get("historical-1") == entry
    assert registry.require("historical-1") == entry
    assert registry.get_config("historical-1") == config
    assert registry.get_adapter("historical-1") == adapter
    assert registry.provider_ids() == ["historical-1"]
    assert registry.list_entries() == [entry]
    assert registry.list_configs() == [config]
    assert registry.list_adapters() == [adapter]

    removed = registry.remove("historical-1")

    assert removed == entry
    assert registry.count() == 0

    registry.register_config(config)
    registry.clear()

    assert registry.count() == 0


def test_provider_registry_rejects_invalid_values():
    with pytest.raises(ValueError):
        ProviderRegistry(entries=[])

    with pytest.raises(ValueError):
        ProviderRegistry(metadata=[])

    registry = build_provider_registry()

    with pytest.raises(ValueError):
        registry.register_entry("bad")

    with pytest.raises(ValueError):
        registry.require("missing")

    with pytest.raises(ValueError):
        registry.get("")

    with pytest.raises(ValueError):
        registry.remove("")


def test_provider_registry_filters_and_selection():
    registry = build_provider_registry()
    historical_adapter = build_historical_ohlcv_adapter(provider_config=historical_config())
    live_adapter = build_live_market_data_adapter(provider_config=live_config())

    registry.register_adapter(
        config=historical_config(),
        adapter=historical_adapter,
    )
    registry.register_adapter(
        config=live_config(),
        adapter=live_adapter,
    )
    registry.register_config(
        build_provider_config(
            provider_id="inactive-live",
            name="Inactive Live",
            provider_type="market_data",
            status="inactive",
            capabilities=["live_quotes"],
        ),
    )

    assert len(registry.active_entries()) == 2
    assert len(registry.entries_by_type("market_data")) == 3
    assert len(registry.entries_by_type("market_data", active_only=True)) == 2
    assert len(registry.entries_supporting("live_quotes")) == 2
    assert len(registry.entries_supporting("live_quotes", active_only=True)) == 1

    selected_historical = registry.select_provider(
        provider_type="market_data",
        capability="historical_ohlcv",
    )
    selected_live = registry.select_provider(
        provider_type="market_data",
        capability="live_quotes",
    )

    assert selected_historical.provider_id == "historical-1"
    assert selected_live.provider_id == "live-1"
    assert registry.resolve_adapter(capability="historical_ohlcv") == historical_adapter
    assert registry.resolve_adapter(capability="news_feed") is None


def test_provider_registry_to_dict_and_result_helpers():
    registry = build_provider_registry()
    registry.register_config(historical_config())

    payload = registry.to_dict()
    result = provider_registry_to_result(registry)
    error = provider_registry_error_result(error="failed")

    assert payload["summary"]["total"] == 1
    assert payload["providers"][0]["provider_id"] == "historical-1"
    assert result.success is True
    assert result.data["registry"]["summary"]["total"] == 1
    assert error.success is False
    assert error.error == "failed"

    with pytest.raises(ValueError):
        provider_registry_to_result("bad")


def test_register_market_data_provider():
    registry = build_provider_registry()
    adapter = object()

    entry = register_market_data_provider(
        registry=registry,
        provider_id="provider-1",
        name="Provider 1",
        capabilities=["live_quotes"],
        adapter=adapter,
    )

    assert entry.provider_id == "provider-1"
    assert entry.adapter == adapter
    assert registry.count() == 1

    with pytest.raises(ValueError):
        register_market_data_provider(
            registry="bad",
            provider_id="provider-2",
            name="Provider 2",
            capabilities=["live_quotes"],
        )

    with pytest.raises(ValueError):
        register_market_data_provider(
            registry=registry,
            provider_id="provider-2",
            name="Provider 2",
            capabilities=["bad"],
        )


def test_resolve_historical_and_live_adapters():
    registry = build_provider_registry()
    historical_adapter = build_historical_ohlcv_adapter(provider_config=historical_config())
    live_adapter = build_live_market_data_adapter(provider_config=live_config())

    registry.register_adapter(
        config=historical_config(),
        adapter=historical_adapter,
    )
    registry.register_adapter(
        config=live_config(),
        adapter=live_adapter,
    )

    assert isinstance(resolve_historical_adapter(registry), HistoricalOhlcvAdapter)
    assert isinstance(resolve_live_adapter(registry), LiveMarketDataAdapter)

    empty_registry = build_provider_registry()

    assert resolve_historical_adapter(empty_registry) is None
    assert resolve_live_adapter(empty_registry) is None

    bad_historical_registry = build_provider_registry()
    bad_historical_registry.register_adapter(
        config=historical_config(),
        adapter=object(),
    )

    with pytest.raises(ValueError):
        resolve_historical_adapter(bad_historical_registry)

    bad_live_registry = build_provider_registry()
    bad_live_registry.register_adapter(
        config=live_config(),
        adapter=object(),
    )

    with pytest.raises(ValueError):
        resolve_live_adapter(bad_live_registry)


def test_registry_exports_exist():
    import aqos.providers as providers

    expected_exports = [
        "ProviderRegistry",
        "ProviderRegistryEntry",
        "ProviderRegistrySummary",
        "build_provider_registry",
        "build_provider_registry_entry",
        "normalize_provider_status_value",
        "normalize_provider_type_value",
        "provider_registry_error_result",
        "provider_registry_to_result",
        "register_market_data_provider",
        "resolve_historical_adapter",
        "resolve_live_adapter",
        "summarize_provider_registry_entries",
        "validate_provider_config_object",
        "validate_provider_registry",
        "validate_provider_registry_entries",
    ]

    for export_name in expected_exports:
        assert hasattr(providers, export_name), export_name