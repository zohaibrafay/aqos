"""
Unit tests for AQOS product research API.
"""

import pytest

from aqos.product_api import (
    ProductApiListQuery,
    ProductApiPagination,
    ProductApiStatus,
    ProductResearchFinding,
    ProductResearchFindingType,
    ProductResearchPriority,
    ProductResearchReport,
    ProductResearchRequest,
    ProductResearchStatus,
    ProductResearchStore,
    ProductResearchSummary,
    archive_research_finding,
    build_product_api_context,
    build_product_research_finding,
    build_product_research_report,
    build_product_research_request,
    build_product_research_store,
    create_research_operation_response,
    filter_product_research_findings,
    get_research_finding_response,
    list_research_findings_response,
    normalize_product_research_finding_type,
    normalize_product_research_priority,
    normalize_product_research_status,
    paginate_product_research_findings,
    research_finding_to_response,
    research_report_to_response,
    summarize_product_research_findings,
    update_research_status,
    validate_product_research_findings,
    validate_research_tags,
)


def build_finding(
    finding_id: str = "finding-1",
    status: str = "completed",
    priority: str = "high",
    finding_type: str = "hypothesis",
    confidence: float = 78.0,
) -> ProductResearchFinding:
    return build_product_research_finding(
        finding_id=finding_id,
        title="Gold momentum continuation",
        finding_type=finding_type,
        summary="XAUUSD shows strong continuation signs.",
        confidence=confidence,
        priority=priority,
        status=status,
        symbol="XAUUSD",
        timeframe="H1",
        tags=["gold", "momentum"],
        evidence={
            "trend": "up",
        },
        created_at="2026-01-01T00:00:00+00:00",
    )


def test_research_enum_values():
    assert ProductResearchStatus.DRAFT.value == "draft"
    assert ProductResearchStatus.RUNNING.value == "running"
    assert ProductResearchStatus.COMPLETED.value == "completed"
    assert ProductResearchStatus.ARCHIVED.value == "archived"

    assert ProductResearchPriority.LOW.value == "low"
    assert ProductResearchPriority.MEDIUM.value == "medium"
    assert ProductResearchPriority.HIGH.value == "high"
    assert ProductResearchPriority.CRITICAL.value == "critical"

    assert ProductResearchFindingType.OBSERVATION.value == "observation"
    assert ProductResearchFindingType.HYPOTHESIS.value == "hypothesis"
    assert ProductResearchFindingType.BACKTEST.value == "backtest"
    assert ProductResearchFindingType.MARKET_NOTE.value == "market_note"
    assert ProductResearchFindingType.RISK_NOTE.value == "risk_note"


def test_research_normalizers_accept_enum_and_string():
    assert normalize_product_research_status(ProductResearchStatus.COMPLETED) == ProductResearchStatus.COMPLETED
    assert normalize_product_research_status(" COMPLETED ") == ProductResearchStatus.COMPLETED
    assert normalize_product_research_priority(ProductResearchPriority.HIGH) == ProductResearchPriority.HIGH
    assert normalize_product_research_priority(" CRITICAL ") == ProductResearchPriority.CRITICAL
    assert normalize_product_research_finding_type(ProductResearchFindingType.BACKTEST) == ProductResearchFindingType.BACKTEST
    assert normalize_product_research_finding_type(" MARKET_NOTE ") == ProductResearchFindingType.MARKET_NOTE


def test_research_normalizers_reject_invalid_values():
    with pytest.raises(ValueError):
        normalize_product_research_status("bad")

    with pytest.raises(ValueError):
        normalize_product_research_priority("bad")

    with pytest.raises(ValueError):
        normalize_product_research_finding_type("bad")


def test_validate_research_tags():
    assert validate_research_tags(["gold", " momentum "]) == ["gold", " momentum "]

    with pytest.raises(ValueError):
        validate_research_tags("bad")

    with pytest.raises(ValueError):
        validate_research_tags([""])


def test_product_research_request_to_dict():
    request = ProductResearchRequest(
        topic=" Gold breakout research ",
        symbol=" xauusd ",
        timeframe=" h1 ",
        priority="HIGH",
        tags=["gold", "breakout"],
        include_sources=True,
        metadata={
            "source": "test",
        },
    )

    assert request.to_dict() == {
        "topic": "Gold breakout research",
        "symbol": "XAUUSD",
        "timeframe": "H1",
        "priority": "high",
        "tags": ["gold", "breakout"],
        "include_sources": True,
        "metadata": {
            "source": "test",
        },
    }


def test_product_research_request_rejects_invalid_values():
    with pytest.raises(ValueError):
        ProductResearchRequest(topic="")

    with pytest.raises(ValueError):
        ProductResearchRequest(topic="Research", symbol="bad symbol")

    with pytest.raises(ValueError):
        ProductResearchRequest(topic="Research", timeframe="H2")

    with pytest.raises(ValueError):
        ProductResearchRequest(topic="Research", priority="bad")

    with pytest.raises(ValueError):
        ProductResearchRequest(topic="Research", tags=[""])

    with pytest.raises(ValueError):
        ProductResearchRequest(topic="Research", include_sources="yes")

    with pytest.raises(ValueError):
        ProductResearchRequest(topic="Research", metadata=[])


def test_build_product_research_request():
    request = build_product_research_request(
        topic="Gold research",
        symbol="xauusd",
        timeframe="h1",
        priority="high",
    )

    assert isinstance(request, ProductResearchRequest)
    assert request.to_dict()["symbol"] == "XAUUSD"


def test_product_research_finding_to_dict():
    finding = build_finding()

    payload = finding.to_dict()

    assert payload["finding_id"] == "finding-1"
    assert payload["title"] == "Gold momentum continuation"
    assert payload["finding_type"] == "hypothesis"
    assert payload["summary"] == "XAUUSD shows strong continuation signs."
    assert payload["confidence"] == 78.0
    assert payload["priority"] == "high"
    assert payload["status"] == "completed"
    assert payload["symbol"] == "XAUUSD"
    assert payload["timeframe"] == "H1"
    assert payload["completed"] is True
    assert payload["high_priority"] is True
    assert payload["actionable"] is True


def test_product_research_finding_rejects_invalid_values():
    with pytest.raises(ValueError):
        ProductResearchFinding(
            finding_id="",
            title="Title",
            finding_type="hypothesis",
            summary="Summary",
            confidence=80,
        )

    with pytest.raises(ValueError):
        ProductResearchFinding(
            finding_id="finding-1",
            title="",
            finding_type="hypothesis",
            summary="Summary",
            confidence=80,
        )

    with pytest.raises(ValueError):
        ProductResearchFinding(
            finding_id="finding-1",
            title="Title",
            finding_type="bad",
            summary="Summary",
            confidence=80,
        )

    with pytest.raises(ValueError):
        ProductResearchFinding(
            finding_id="finding-1",
            title="Title",
            finding_type="hypothesis",
            summary="",
            confidence=80,
        )

    with pytest.raises(ValueError):
        ProductResearchFinding(
            finding_id="finding-1",
            title="Title",
            finding_type="hypothesis",
            summary="Summary",
            confidence=101,
        )

    with pytest.raises(ValueError):
        ProductResearchFinding(
            finding_id="finding-1",
            title="Title",
            finding_type="hypothesis",
            summary="Summary",
            confidence=80,
            priority="bad",
        )

    with pytest.raises(ValueError):
        ProductResearchFinding(
            finding_id="finding-1",
            title="Title",
            finding_type="hypothesis",
            summary="Summary",
            confidence=80,
            status="bad",
        )

    with pytest.raises(ValueError):
        ProductResearchFinding(
            finding_id="finding-1",
            title="Title",
            finding_type="hypothesis",
            summary="Summary",
            confidence=80,
            symbol="bad symbol",
        )

    with pytest.raises(ValueError):
        ProductResearchFinding(
            finding_id="finding-1",
            title="Title",
            finding_type="hypothesis",
            summary="Summary",
            confidence=80,
            evidence=[],
        )


def test_research_summary():
    findings = [
        build_finding("finding-1", "completed", "high", confidence=80),
        build_finding("finding-2", "draft", "medium", confidence=60),
        build_finding("finding-3", "archived", "critical", confidence=40),
    ]

    summary = summarize_product_research_findings(
        findings,
        metadata={
            "source": "test",
        },
    )

    assert isinstance(summary, ProductResearchSummary)
    assert summary.to_dict() == {
        "total": 3,
        "draft": 1,
        "running": 0,
        "completed": 1,
        "archived": 1,
        "high_priority": 2,
        "average_confidence": 60.0,
        "metadata": {
            "source": "test",
        },
    }


def test_research_summary_rejects_invalid_values():
    with pytest.raises(ValueError):
        ProductResearchSummary(total=-1)

    with pytest.raises(ValueError):
        ProductResearchSummary(average_confidence=101)

    with pytest.raises(ValueError):
        ProductResearchSummary(metadata=[])


def test_research_report_to_dict():
    findings = [build_finding()]
    report = build_product_research_report(
        report_id="report-1",
        title="Gold research report",
        findings=findings,
        summary="Research summary.",
        generated_at="2026-01-01T01:00:00+00:00",
    )

    payload = report.to_dict()

    assert payload["report_id"] == "report-1"
    assert payload["title"] == "Gold research report"
    assert payload["summary"] == "Research summary."
    assert payload["status"] == "completed"
    assert payload["research_summary"]["total"] == 1
    assert payload["generated_at"] == "2026-01-01T01:00:00+00:00"


def test_research_report_rejects_invalid_values():
    with pytest.raises(ValueError):
        ProductResearchReport(report_id="", title="Report")

    with pytest.raises(ValueError):
        ProductResearchReport(report_id="report-1", title="")

    with pytest.raises(ValueError):
        ProductResearchReport(report_id="report-1", title="Report", findings=["bad"])

    with pytest.raises(ValueError):
        ProductResearchReport(report_id="report-1", title="Report", summary=123)

    with pytest.raises(ValueError):
        ProductResearchReport(report_id="report-1", title="Report", status="bad")

    with pytest.raises(ValueError):
        ProductResearchReport(report_id="report-1", title="Report", metadata=[])

    with pytest.raises(ValueError):
        ProductResearchReport(report_id="report-1", title="Report", generated_at="")


def test_validate_product_research_findings():
    finding = build_finding()

    assert validate_product_research_findings([finding]) == [finding]

    with pytest.raises(ValueError):
        validate_product_research_findings("bad")

    with pytest.raises(ValueError):
        validate_product_research_findings(["bad"])


def test_research_store():
    finding = build_finding()
    store = build_product_research_store()

    assert isinstance(store, ProductResearchStore)
    assert store.count() == 0

    store.add(finding)

    assert store.count() == 1
    assert store.get("finding-1") == finding
    assert store.list() == [finding]
    assert store.remove("finding-1") == finding
    assert store.count() == 0

    store.add(finding)
    store.clear()

    assert store.count() == 0


def test_research_store_rejects_invalid_values():
    with pytest.raises(ValueError):
        ProductResearchStore(findings=[])

    with pytest.raises(ValueError):
        ProductResearchStore(findings={"finding-1": "bad"})

    store = build_product_research_store()

    with pytest.raises(ValueError):
        store.add("bad")

    with pytest.raises(ValueError):
        store.get("")

    with pytest.raises(ValueError):
        store.remove("")


def test_research_finding_to_response():
    context = build_product_api_context(request_id="req-1")
    finding = build_finding()

    response = research_finding_to_response(
        finding=finding,
        context=context,
    )

    assert response.status == ProductApiStatus.SUCCESS
    assert response.data["finding"]["finding_id"] == "finding-1"
    assert response.meta is not None
    assert response.meta.request_id == "req-1"

    with pytest.raises(ValueError):
        research_finding_to_response(finding="bad")


def test_research_report_to_response():
    context = build_product_api_context(request_id="req-1")
    report = build_product_research_report(
        report_id="report-1",
        title="Research report",
        findings=[build_finding()],
    )

    response = research_report_to_response(
        report=report,
        context=context,
    )

    assert response.status == ProductApiStatus.SUCCESS
    assert response.data["report"]["report_id"] == "report-1"
    assert response.meta is not None

    with pytest.raises(ValueError):
        research_report_to_response(report="bad")


def test_list_research_findings_response_and_pagination():
    context = build_product_api_context(request_id="req-1")
    findings = [
        build_finding("finding-1"),
        build_finding("finding-2", status="draft", priority="medium"),
    ]
    query = ProductApiListQuery(
        pagination=ProductApiPagination(page=1, page_size=1),
    )

    response = list_research_findings_response(
        findings=findings,
        query=query,
        context=context,
    )

    assert response.status == ProductApiStatus.SUCCESS
    assert len(response.data["items"]) == 1
    assert response.data["total_items"] == 2
    assert response.data["metadata"]["summary"]["total"] == 2


def test_create_research_operation_response():
    response = create_research_operation_response(
        finding=build_finding(),
        context=build_product_api_context(request_id="req-1"),
    )

    assert response.status == ProductApiStatus.SUCCESS
    assert response.data["operation"] == "create"
    assert response.data["resource_type"] == "research"
    assert response.data["resource_id"] == "finding-1"

    with pytest.raises(ValueError):
        create_research_operation_response(finding="bad")


def test_get_research_finding_response():
    finding = build_finding()
    store = build_product_research_store()
    store.add(finding)

    found = get_research_finding_response(
        store=store,
        finding_id="finding-1",
    )

    missing = get_research_finding_response(
        store=store,
        finding_id="missing",
    )

    assert found.status == ProductApiStatus.SUCCESS
    assert found.data["finding"]["finding_id"] == "finding-1"
    assert missing.status == ProductApiStatus.FAILURE
    assert missing.error is not None
    assert missing.error.code == "not_found"

    with pytest.raises(ValueError):
        get_research_finding_response(
            store="bad",
            finding_id="finding-1",
        )


def test_update_and_archive_research_status():
    finding = build_finding(status="draft", priority="high")

    completed = update_research_status(
        finding,
        status="completed",
        metadata={
            "reviewed_by": "qa",
        },
    )

    assert completed.status == "completed"
    assert completed.completed is True
    assert completed.metadata["reviewed_by"] == "qa"

    archived = archive_research_finding(
        completed,
        reason="superseded",
    )

    assert archived.status == ProductResearchStatus.ARCHIVED
    assert archived.metadata["archive_reason"] == "superseded"

    with pytest.raises(ValueError):
        update_research_status("bad", status="completed")

    with pytest.raises(ValueError):
        archive_research_finding(completed, reason=123)


def test_paginate_and_filter_product_research_findings():
    findings = [
        build_finding("finding-1", status="completed", priority="high", finding_type="hypothesis"),
        build_finding("finding-2", status="draft", priority="medium", finding_type="observation"),
        build_finding("finding-3", status="archived", priority="critical", finding_type="risk_note"),
    ]

    paged = paginate_product_research_findings(
        findings=findings,
        pagination=ProductApiPagination(page=2, page_size=1),
    )

    assert [finding.finding_id for finding in paged] == ["finding-2"]

    completed = filter_product_research_findings(
        findings=findings,
        status="completed",
    )

    assert len(completed) == 1
    assert completed[0].finding_id == "finding-1"

    high = filter_product_research_findings(
        findings=findings,
        priority="high",
    )

    assert len(high) == 1

    risk_notes = filter_product_research_findings(
        findings=findings,
        finding_type="risk_note",
    )

    assert len(risk_notes) == 1

    gold = filter_product_research_findings(
        findings=findings,
        symbol="xauusd",
        timeframe="h1",
        tag="gold",
    )

    assert len(gold) == 3

    with pytest.raises(ValueError):
        paginate_product_research_findings(
            findings=findings,
            pagination="bad",
        )


def test_product_research_exports_exist():
    import aqos.product_api as product_api

    expected_exports = [
        "ProductResearchFinding",
        "ProductResearchFindingType",
        "ProductResearchPriority",
        "ProductResearchReport",
        "ProductResearchRequest",
        "ProductResearchStatus",
        "ProductResearchStore",
        "ProductResearchSummary",
        "archive_research_finding",
        "build_product_research_finding",
        "build_product_research_report",
        "build_product_research_request",
        "build_product_research_store",
        "create_research_operation_response",
        "filter_product_research_findings",
        "get_research_finding_response",
        "list_research_findings_response",
        "normalize_product_research_finding_type",
        "normalize_product_research_priority",
        "normalize_product_research_status",
        "paginate_product_research_findings",
        "research_finding_to_response",
        "research_report_to_response",
        "summarize_product_research_findings",
        "update_research_status",
        "validate_product_research_findings",
        "validate_research_tags",
    ]

    for export_name in expected_exports:
        assert hasattr(product_api, export_name), export_name