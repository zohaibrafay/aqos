"""
Unit tests for AQOS real live news ingestion runner.
"""

import pytest

from aqos.news_providers import (
    GdeltNewsQuery,
    HackerNewsQuery,
    LiveConnectorIngestionRequest,
    LiveConnectorIngestionResult,
    LiveIngestionBatchResult,
    LiveIngestionExecutionStatus,
    NewsProviderCredentials,
    NewsProviderResult,
    build_default_news_connector_registry,
    build_default_query_for_live_connector,
    build_gdelt_news_query,
    build_hackernews_query,
    build_ingestion_requests_from_selection,
    build_live_connector_ingestion_request,
    build_live_connector_ingestion_result,
    build_live_ingestion_batch_result,
    build_news_connector_selection_request,
    dispatch_live_connector_loader,
    execute_live_connector_ingestion_request,
    infer_live_ingestion_execution_status,
    normalize_live_ingestion_execution_status,
    run_live_news_ingestion,
    validate_live_connector_ingestion_results,
)


def sample_gdelt_payload():
    return {
        "articles": [
            {
                "url": "https://example.com/gold-cpi",
                "seendate": "2026-07-09T12:00:00Z",
                "title": "Gold falls after hot CPI",
                "domain": "example.com",
                "sourcecountry": "US",
                "language": "English",
            }
        ]
    }


def sample_hackernews_payload():
    return {
        "hits": [
            {
                "objectID": "1001",
                "created_at": "2026-07-09T12:00:00Z",
                "title": "Inflation and markets discussion",
                "url": "https://example.com/inflation-markets",
                "author": "alice",
                "points": 120,
                "num_comments": 33,
                "_tags": ["story"],
            }
        ]
    }


def test_live_ingestion_status_normalizer_and_enum():
    assert LiveIngestionExecutionStatus.SUCCESS.value == "success"
    assert LiveIngestionExecutionStatus.PARTIAL.value == "partial"
    assert LiveIngestionExecutionStatus.FAILED.value == "failed"
    assert LiveIngestionExecutionStatus.EMPTY.value == "empty"

    assert normalize_live_ingestion_execution_status(" SUCCESS ") == LiveIngestionExecutionStatus.SUCCESS

    with pytest.raises(ValueError):
        normalize_live_ingestion_execution_status("bad")


def test_live_connector_ingestion_request_to_dict_and_rejections():
    request = LiveConnectorIngestionRequest(
        connector_id=" gdelt ",
        query=build_gdelt_news_query(query_terms=["gold"]),
        credentials=NewsProviderCredentials(),
        payload=sample_gdelt_payload(),
        fetcher=lambda _request: sample_gdelt_payload(),
        metadata={"source": "test"},
    )
    payload = request.to_dict()
    built = build_live_connector_ingestion_request(connector_id="gdelt")

    assert payload["connector_id"] == "gdelt"
    assert payload["query_type"] == "GdeltNewsQuery"
    assert payload["has_payload"] is True
    assert payload["has_fetcher"] is True
    assert isinstance(built, LiveConnectorIngestionRequest)

    with pytest.raises(ValueError):
        LiveConnectorIngestionRequest(connector_id="")

    with pytest.raises(ValueError):
        LiveConnectorIngestionRequest(connector_id="gdelt", credentials="bad")

    with pytest.raises(ValueError):
        LiveConnectorIngestionRequest(connector_id="gdelt", payload="bad")

    with pytest.raises(ValueError):
        LiveConnectorIngestionRequest(connector_id="gdelt", fetcher="bad")

    with pytest.raises(ValueError):
        LiveConnectorIngestionRequest(connector_id="gdelt", metadata=[])


def test_default_queries_for_connectors():
    assert isinstance(build_default_query_for_live_connector("gdelt"), GdeltNewsQuery)
    assert isinstance(build_default_query_for_live_connector("hacker_news"), HackerNewsQuery)

    assert build_default_query_for_live_connector("news_api").page_size == 5
    assert build_default_query_for_live_connector("marketaux").symbol == "XAUUSD"
    assert build_default_query_for_live_connector("finnhub").category == "general"
    assert build_default_query_for_live_connector("trading_economics").limit == 5
    assert build_default_query_for_live_connector("cryptopanic").page == 1

    with pytest.raises(ValueError):
        build_default_query_for_live_connector("bad")


def test_dispatch_live_connector_loader_success_and_rejections():
    gdelt_result = dispatch_live_connector_loader(
        connector_id="gdelt",
        query=build_gdelt_news_query(query_terms=["gold"]),
        payload=sample_gdelt_payload(),
    )
    hn_result = dispatch_live_connector_loader(
        connector_id="hacker_news",
        query=build_hackernews_query(query_terms=["inflation"]),
        payload=sample_hackernews_payload(),
    )

    assert isinstance(gdelt_result, NewsProviderResult)
    assert gdelt_result.success is True
    assert gdelt_result.record_count == 1

    assert hn_result.success is True
    assert hn_result.record_count == 1

    with pytest.raises(ValueError):
        dispatch_live_connector_loader(
            connector_id="gdelt",
            query=build_hackernews_query(query_terms=["wrong"]),
            payload=sample_gdelt_payload(),
        )

    with pytest.raises(ValueError):
        dispatch_live_connector_loader(
            connector_id="bad",
            query=build_gdelt_news_query(query_terms=["gold"]),
        )


def test_execute_live_connector_ingestion_request_success_and_failure():
    request = build_live_connector_ingestion_request(
        connector_id="gdelt",
        query=build_gdelt_news_query(query_terms=["gold"]),
        payload=sample_gdelt_payload(),
    )
    result = execute_live_connector_ingestion_request(request)

    bad_request = build_live_connector_ingestion_request(
        connector_id="bad",
    )
    bad_result = execute_live_connector_ingestion_request(bad_request)

    assert isinstance(result, LiveConnectorIngestionResult)
    assert result.success is True
    assert result.record_count == 1
    assert result.provider_result.success is True

    assert bad_result.success is False
    assert bad_result.provider_result.success is False

    with pytest.raises(ValueError):
        execute_live_connector_ingestion_request("bad")


def test_live_connector_ingestion_result_and_batch_result():
    provider_result = dispatch_live_connector_loader(
        connector_id="gdelt",
        query=build_gdelt_news_query(query_terms=["gold"]),
        payload=sample_gdelt_payload(),
    )
    result = build_live_connector_ingestion_result(
        connector_id="gdelt",
        success=True,
        provider_result=provider_result,
        message="ok",
    )
    batch = build_live_ingestion_batch_result(
        results=[result],
        message="done",
    )

    assert result.record_count == 1
    assert result.to_dict()["connector_id"] == "gdelt"
    assert isinstance(batch, LiveIngestionBatchResult)
    assert batch.status == LiveIngestionExecutionStatus.SUCCESS
    assert batch.success is True
    assert batch.connector_count == 1
    assert batch.success_count == 1
    assert batch.failed_count == 0
    assert batch.total_record_count == 1

    with pytest.raises(ValueError):
        LiveConnectorIngestionResult(
            connector_id="gdelt",
            success=True,
            provider_result="bad",
        )

    with pytest.raises(ValueError):
        LiveIngestionBatchResult(
            status="success",
            results="bad",
        )


def test_infer_live_ingestion_execution_status():
    provider_result = dispatch_live_connector_loader(
        connector_id="gdelt",
        query=build_gdelt_news_query(query_terms=["gold"]),
        payload=sample_gdelt_payload(),
    )
    good = build_live_connector_ingestion_result(
        connector_id="gdelt",
        success=True,
        provider_result=provider_result,
    )
    bad_provider = execute_live_connector_ingestion_request(
        build_live_connector_ingestion_request(connector_id="bad"),
    )

    assert infer_live_ingestion_execution_status([]) == LiveIngestionExecutionStatus.EMPTY
    assert infer_live_ingestion_execution_status([good]) == LiveIngestionExecutionStatus.SUCCESS
    assert infer_live_ingestion_execution_status([good, bad_provider]) == LiveIngestionExecutionStatus.PARTIAL
    assert infer_live_ingestion_execution_status([bad_provider]) == LiveIngestionExecutionStatus.FAILED

    with pytest.raises(ValueError):
        validate_live_connector_ingestion_results("bad")

    with pytest.raises(ValueError):
        validate_live_connector_ingestion_results(["bad"])


def test_build_ingestion_requests_from_selection():
    registry = build_default_news_connector_registry()
    requests = build_ingestion_requests_from_selection(
        registry,
        build_news_connector_selection_request(
            connector_ids=["gdelt", "hacker_news"],
        ),
        payloads_by_connector_id={
            "gdelt": sample_gdelt_payload(),
            "hacker_news": sample_hackernews_payload(),
        },
    )

    assert len(requests) == 2
    assert [request.connector_id for request in requests] == ["gdelt", "hacker_news"]
    assert all(isinstance(request, LiveConnectorIngestionRequest) for request in requests)

    with pytest.raises(ValueError):
        build_ingestion_requests_from_selection("bad")


def test_run_live_news_ingestion_with_explicit_requests():
    requests = [
        build_live_connector_ingestion_request(
            connector_id="gdelt",
            query=build_gdelt_news_query(query_terms=["gold"]),
            payload=sample_gdelt_payload(),
        ),
        build_live_connector_ingestion_request(
            connector_id="hacker_news",
            query=build_hackernews_query(query_terms=["inflation"]),
            payload=sample_hackernews_payload(),
        ),
    ]

    batch = run_live_news_ingestion(requests=requests)

    assert batch.success is True
    assert batch.connector_count == 2
    assert batch.success_count == 2
    assert batch.total_record_count == 2
    assert batch.status == LiveIngestionExecutionStatus.SUCCESS

    with pytest.raises(ValueError):
        run_live_news_ingestion(registry="bad")

    with pytest.raises(ValueError):
        run_live_news_ingestion(requests="bad")

    with pytest.raises(ValueError):
        run_live_news_ingestion(requests=["bad"])


def test_run_live_news_ingestion_from_registry_selection():
    registry = build_default_news_connector_registry()
    batch = run_live_news_ingestion(
        registry=registry,
        selection_request=build_news_connector_selection_request(
            connector_ids=["gdelt", "hacker_news"],
        ),
        payloads_by_connector_id={
            "gdelt": sample_gdelt_payload(),
            "hacker_news": sample_hackernews_payload(),
        },
    )

    assert batch.success is True
    assert batch.connector_count == 2
    assert batch.success_count == 2
    assert batch.total_record_count == 2
    assert batch.to_dict()["connector_ids"] == ["gdelt", "hacker_news"]


def test_real_ingestion_exports_exist():
    import aqos.news_providers as news_providers

    expected_exports = [
        "LiveConnectorIngestionRequest",
        "LiveConnectorIngestionResult",
        "LiveIngestionBatchResult",
        "LiveIngestionExecutionStatus",
        "build_default_query_for_live_connector",
        "build_ingestion_requests_from_selection",
        "build_live_connector_ingestion_request",
        "build_live_connector_ingestion_result",
        "build_live_ingestion_batch_result",
        "dispatch_live_connector_loader",
        "execute_live_connector_ingestion_request",
        "infer_live_ingestion_execution_status",
        "normalize_live_ingestion_execution_status",
        "run_live_news_ingestion",
        "validate_live_connector_ingestion_results",
    ]

    for export_name in expected_exports:
        assert hasattr(news_providers, export_name), export_name