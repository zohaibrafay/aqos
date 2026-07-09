"""
Unit tests for AQOS live news connector registry.
"""

import pytest

from aqos.news_providers import (
    LiveNewsConnectorDefinition,
    LiveNewsConnectorSelectionMode,
    LiveNewsConnectorStatus,
    NewsConnectorRegistry,
    NewsConnectorRegistryEntry,
    NewsConnectorSelectionRequest,
    NewsConnectorSelectionResult,
    NewsProviderCredentials,
    build_default_news_connector_registry,
    build_gdelt_connector_definition,
    build_news_connector_registry,
    build_news_connector_registry_entry,
    build_news_connector_selection_request,
    build_news_connector_selection_result,
    connector_entry_has_capabilities,
    connector_entry_has_tags,
    connector_entry_matches_selection_request,
    get_live_news_connector_definition,
    list_connectors_by_capability,
    list_connectors_by_category,
    list_connectors_by_status,
    list_live_news_connector_definitions,
    normalize_capability_value,
    normalize_live_news_connector_selection_mode,
    register_news_connector_definition,
    select_connector_runtime_configs,
    select_live_news_connectors,
    validate_connector_capability_list,
    validate_connector_category_list,
    validate_connector_id_list,
    validate_connector_status_list,
    validate_credentials_mapping,
    validate_registry_entries,
    validate_registry_string_list,
)


def sample_entry():
    return build_news_connector_registry_entry(
        definition=build_gdelt_connector_definition(),
        priority=10,
        enabled=True,
        tags=["global", "public"],
        metadata={"source": "test"},
    )


def test_selection_mode_normalizer_and_enum():
    assert LiveNewsConnectorSelectionMode.ALL.value == "all"
    assert LiveNewsConnectorSelectionMode.FIRST_READY.value == "first_ready"
    assert LiveNewsConnectorSelectionMode.PREFERRED_ONLY.value == "preferred_only"
    assert LiveNewsConnectorSelectionMode.FALLBACK_CHAIN.value == "fallback_chain"

    assert (
        normalize_live_news_connector_selection_mode(" ALL ")
        == LiveNewsConnectorSelectionMode.ALL
    )
    assert (
        normalize_live_news_connector_selection_mode(" FIRST_READY ")
        == LiveNewsConnectorSelectionMode.FIRST_READY
    )

    with pytest.raises(ValueError):
        normalize_live_news_connector_selection_mode("bad")


def test_registry_entry_to_dict_and_rejections():
    entry = NewsConnectorRegistryEntry(
        definition=build_gdelt_connector_definition(),
        priority=5,
        enabled=True,
        tags=[" Global "],
        metadata={"source": "test"},
    )
    payload = entry.to_dict()
    built = sample_entry()

    assert payload["connector_id"] == "gdelt"
    assert payload["category"] == "global_news"
    assert payload["status"] == "ready"
    assert payload["priority"] == 5
    assert payload["enabled"] is True
    assert payload["ready"] is True
    assert payload["tags"] == ["global"]
    assert isinstance(built, NewsConnectorRegistryEntry)

    with pytest.raises(ValueError):
        NewsConnectorRegistryEntry(definition="bad")

    with pytest.raises(ValueError):
        NewsConnectorRegistryEntry(definition=build_gdelt_connector_definition(), priority=-1)

    with pytest.raises(ValueError):
        NewsConnectorRegistryEntry(definition=build_gdelt_connector_definition(), enabled="yes")

    with pytest.raises(ValueError):
        NewsConnectorRegistryEntry(definition=build_gdelt_connector_definition(), tags="bad")

    with pytest.raises(ValueError):
        NewsConnectorRegistryEntry(definition=build_gdelt_connector_definition(), metadata=[])


def test_selection_request_to_dict_and_rejections():
    credentials = NewsProviderCredentials(
        auth_type="api_key",
        api_key="secret",
    )
    request = NewsConnectorSelectionRequest(
        connector_ids=["gdelt"],
        categories=["global_news"],
        capabilities=["live_news"],
        statuses=["ready"],
        tags=["public"],
        mode="all",
        include_disabled=False,
        require_credentials=False,
        credentials_by_connector_id={"gdelt": credentials},
        limit=1,
        metadata={"source": "test"},
    )
    payload = request.to_dict()
    built = build_news_connector_selection_request(connector_ids=["gdelt"])

    assert payload["connector_ids"] == ["gdelt"]
    assert payload["categories"] == ["global_news"]
    assert payload["capabilities"] == ["live_news"]
    assert payload["statuses"] == ["ready"]
    assert payload["tags"] == ["public"]
    assert payload["mode"] == "all"
    assert payload["credential_connector_ids"] == ["gdelt"]
    assert payload["limit"] == 1
    assert isinstance(built, NewsConnectorSelectionRequest)

    with pytest.raises(ValueError):
        NewsConnectorSelectionRequest(connector_ids="bad")

    with pytest.raises(ValueError):
        NewsConnectorSelectionRequest(connector_ids=["bad"])

    with pytest.raises(ValueError):
        NewsConnectorSelectionRequest(categories="bad")

    with pytest.raises(ValueError):
        NewsConnectorSelectionRequest(categories=["bad"])

    with pytest.raises(ValueError):
        NewsConnectorSelectionRequest(capabilities=["bad"])

    with pytest.raises(ValueError):
        NewsConnectorSelectionRequest(statuses=["bad"])

    with pytest.raises(ValueError):
        NewsConnectorSelectionRequest(tags="bad")

    with pytest.raises(ValueError):
        NewsConnectorSelectionRequest(mode="bad")

    with pytest.raises(ValueError):
        NewsConnectorSelectionRequest(include_disabled="bad")

    with pytest.raises(ValueError):
        NewsConnectorSelectionRequest(require_credentials="bad")

    with pytest.raises(ValueError):
        NewsConnectorSelectionRequest(credentials_by_connector_id=[])

    with pytest.raises(ValueError):
        NewsConnectorSelectionRequest(
            credentials_by_connector_id={"gdelt": "bad"},
        )

    with pytest.raises(ValueError):
        NewsConnectorSelectionRequest(limit=-1)

    with pytest.raises(ValueError):
        NewsConnectorSelectionRequest(metadata=[])


def test_selection_result_to_dict_and_rejections():
    request = build_news_connector_selection_request(connector_ids=["gdelt"])
    result = build_news_connector_selection_result(
        success=True,
        entries=[sample_entry()],
        message="Selected.",
        request=request,
        metadata={"source": "test"},
    )

    payload = result.to_dict()

    assert isinstance(result, NewsConnectorSelectionResult)
    assert result.connector_count == 1
    assert len(result.definitions) == 1
    assert payload["success"] is True
    assert payload["connector_count"] == 1
    assert payload["connector_ids"] == ["gdelt"]
    assert payload["request"]["connector_ids"] == ["gdelt"]

    with pytest.raises(ValueError):
        NewsConnectorSelectionResult(success="yes")

    with pytest.raises(ValueError):
        NewsConnectorSelectionResult(success=True, entries="bad")

    with pytest.raises(ValueError):
        NewsConnectorSelectionResult(success=True, entries=["bad"])

    with pytest.raises(ValueError):
        NewsConnectorSelectionResult(success=True, request="bad")

    with pytest.raises(ValueError):
        NewsConnectorSelectionResult(success=True, metadata=[])


def test_registry_to_dict_and_lookup():
    registry = build_news_connector_registry(
        entries=[sample_entry()],
        metadata={"source": "test"},
    )

    payload = registry.to_dict()

    assert isinstance(registry, NewsConnectorRegistry)
    assert registry.connector_count == 1
    assert registry.has_connector("gdelt") is True
    assert registry.get_connector("gdelt").connector_id.value == "gdelt"
    assert payload["connector_count"] == 1
    assert "gdelt" in payload["entries"]

    with pytest.raises(KeyError):
        registry.get_connector("news_api")

    with pytest.raises(ValueError):
        NewsConnectorRegistry(entries=[])

    with pytest.raises(ValueError):
        NewsConnectorRegistry(entries={"wrong": sample_entry()})

    with pytest.raises(ValueError):
        NewsConnectorRegistry(entries={"gdelt": "bad"})

    with pytest.raises(ValueError):
        NewsConnectorRegistry(metadata=[])


def test_default_registry_contains_named_connectors():
    registry = build_default_news_connector_registry()

    assert registry.connector_count == 7
    assert registry.has_connector("gdelt") is True
    assert registry.has_connector("hacker_news") is True
    assert registry.has_connector("news_api") is True
    assert registry.has_connector("marketaux") is True
    assert registry.has_connector("finnhub") is True
    assert registry.has_connector("trading_economics") is True
    assert registry.has_connector("cryptopanic") is True

    definitions = list_live_news_connector_definitions(registry)

    assert len(definitions) == 7
    assert all(isinstance(definition, LiveNewsConnectorDefinition) for definition in definitions)

    with pytest.raises(ValueError):
        list_live_news_connector_definitions("bad")


def test_register_connector_definition_and_duplicate_handling():
    registry = build_news_connector_registry()

    updated = register_news_connector_definition(
        registry,
        definition=build_gdelt_connector_definition(),
        priority=5,
        tags=["global"],
    )

    assert updated.connector_count == 1
    assert updated.has_connector("gdelt") is True

    with pytest.raises(ValueError):
        register_news_connector_definition(
            updated,
            definition=build_gdelt_connector_definition(),
        )

    overwritten = register_news_connector_definition(
        updated,
        definition=build_gdelt_connector_definition(),
        priority=1,
        overwrite=True,
    )

    assert overwritten.get_connector("gdelt").priority == 1

    with pytest.raises(ValueError):
        register_news_connector_definition("bad", definition=build_gdelt_connector_definition())


def test_get_live_connector_definition():
    registry = build_default_news_connector_registry()
    definition = get_live_news_connector_definition(registry, "gdelt")

    assert isinstance(definition, LiveNewsConnectorDefinition)
    assert definition.to_dict()["connector_id"] == "gdelt"

    with pytest.raises(ValueError):
        get_live_news_connector_definition("bad", "gdelt")


def test_entry_match_helpers():
    entry = sample_entry()

    assert connector_entry_has_capabilities(entry, ["live_news"]) is True
    assert connector_entry_has_tags(entry, ["public"]) is True

    request = build_news_connector_selection_request(
        connector_ids=["gdelt"],
        categories=["global_news"],
        capabilities=["live_news"],
        statuses=["ready"],
        tags=["public"],
    )

    assert connector_entry_matches_selection_request(entry, request) is True

    miss_request = build_news_connector_selection_request(connector_ids=["news_api"])

    assert connector_entry_matches_selection_request(entry, miss_request) is False

    with pytest.raises(ValueError):
        connector_entry_has_capabilities("bad", ["live_news"])

    with pytest.raises(ValueError):
        connector_entry_has_tags("bad", ["public"])

    with pytest.raises(ValueError):
        connector_entry_matches_selection_request("bad", request)

    with pytest.raises(ValueError):
        connector_entry_matches_selection_request(entry, "bad")


def test_select_connectors_by_filters_modes_and_limit():
    registry = build_default_news_connector_registry()

    public_result = select_live_news_connectors(
        registry,
        build_news_connector_selection_request(tags=["no_key"]),
    )

    assert public_result.success is True
    assert public_result.connector_count == 2
    assert public_result.to_dict()["connector_ids"] == ["gdelt", "hacker_news"]

    first_ready = select_live_news_connectors(
        registry,
        build_news_connector_selection_request(mode="first_ready"),
    )

    assert first_ready.success is True
    assert first_ready.connector_count == 1
    assert first_ready.entries[0].connector_id.value == "gdelt"

    preferred = select_live_news_connectors(
        registry,
        build_news_connector_selection_request(
            connector_ids=["cryptopanic", "finnhub"],
            mode="preferred_only",
        ),
    )

    assert preferred.success is True
    assert preferred.to_dict()["connector_ids"] == ["finnhub", "cryptopanic"]

    limited = select_live_news_connectors(
        registry,
        build_news_connector_selection_request(limit=3),
    )

    assert limited.connector_count == 3

    no_match = select_live_news_connectors(
        registry,
        build_news_connector_selection_request(tags=["does-not-exist"]),
    )

    assert no_match.success is False
    assert no_match.connector_count == 0

    with pytest.raises(ValueError):
        select_live_news_connectors("bad")

    with pytest.raises(ValueError):
        select_live_news_connectors(registry, "bad")


def test_select_requires_credentials():
    registry = build_default_news_connector_registry()

    no_credentials = select_live_news_connectors(
        registry,
        build_news_connector_selection_request(
            connector_ids=["news_api"],
            require_credentials=True,
        ),
    )

    with_credentials = select_live_news_connectors(
        registry,
        build_news_connector_selection_request(
            connector_ids=["news_api"],
            require_credentials=True,
            credentials_by_connector_id={
                "news_api": NewsProviderCredentials(
                    auth_type="api_key",
                    api_key="secret",
                ),
            },
        ),
    )

    assert no_credentials.success is False
    assert with_credentials.success is True
    assert with_credentials.connector_count == 1


def test_select_runtime_configs():
    registry = build_default_news_connector_registry()
    runtime_configs = select_connector_runtime_configs(
        registry,
        build_news_connector_selection_request(
            connector_ids=["gdelt", "hacker_news"],
        ),
    )

    assert len(runtime_configs) == 2
    assert all(hasattr(runtime_config, "connector") for runtime_config in runtime_configs)

    with pytest.raises(ValueError):
        select_connector_runtime_configs("bad")


def test_category_status_and_capability_shortcuts():
    registry = build_default_news_connector_registry()

    global_news = list_connectors_by_category(registry, "global_news")
    ready = list_connectors_by_status(registry, "ready")
    live_news = list_connectors_by_capability(registry, "live_news")

    assert [entry.connector_id.value for entry in global_news] == ["gdelt"]
    assert [entry.connector_id.value for entry in ready] == ["gdelt", "hacker_news"]
    assert len(live_news) == 7


def test_registry_validators_and_exports_exist():
    credentials = NewsProviderCredentials(
        auth_type="api_key",
        api_key="secret",
    )

    assert validate_registry_string_list(["tag"]) == ["tag"]
    assert validate_connector_id_list(["gdelt"]) == ["gdelt"]
    assert validate_connector_category_list(["global_news"]) == ["global_news"]
    assert validate_connector_capability_list(["live_news"]) == ["live_news"]
    assert validate_connector_status_list(["ready"]) == ["ready"]
    assert validate_credentials_mapping({"news_api": credentials}) == {"news_api": credentials}
    assert validate_registry_entries([sample_entry()]) == [sample_entry()]
    assert normalize_capability_value("live_news").value == "live_news"

    with pytest.raises(ValueError):
        validate_registry_string_list("bad", "Tags")

    with pytest.raises(ValueError):
        validate_registry_string_list([""], "Tags")

    with pytest.raises(ValueError):
        validate_connector_id_list("bad")

    with pytest.raises(ValueError):
        validate_connector_category_list("bad")

    with pytest.raises(ValueError):
        validate_connector_capability_list("bad")

    with pytest.raises(ValueError):
        validate_connector_status_list("bad")

    with pytest.raises(ValueError):
        validate_credentials_mapping("bad")

    with pytest.raises(ValueError):
        validate_registry_entries("bad")

    with pytest.raises(ValueError):
        normalize_capability_value("bad")

    import aqos.news_providers as news_providers

    expected_exports = [
        "LiveNewsConnectorSelectionMode",
        "NewsConnectorRegistry",
        "NewsConnectorRegistryEntry",
        "NewsConnectorSelectionRequest",
        "NewsConnectorSelectionResult",
        "build_default_news_connector_registry",
        "build_news_connector_registry",
        "build_news_connector_registry_entry",
        "build_news_connector_selection_request",
        "build_news_connector_selection_result",
        "connector_entry_has_capabilities",
        "connector_entry_has_tags",
        "connector_entry_matches_selection_request",
        "get_live_news_connector_definition",
        "list_connectors_by_capability",
        "list_connectors_by_category",
        "list_connectors_by_status",
        "list_live_news_connector_definitions",
        "normalize_capability_value",
        "normalize_live_news_connector_selection_mode",
        "register_news_connector_definition",
        "select_connector_runtime_configs",
        "select_live_news_connectors",
        "validate_connector_capability_list",
        "validate_connector_category_list",
        "validate_connector_id_list",
        "validate_connector_status_list",
        "validate_credentials_mapping",
        "validate_registry_entries",
        "validate_registry_string_list",
    ]

    for export_name in expected_exports:
        assert hasattr(news_providers, export_name), export_name