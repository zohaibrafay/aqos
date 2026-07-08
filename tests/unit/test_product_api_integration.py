"""
Unit tests for AQOS product API integration helpers.
"""

import pytest

from aqos.product_api import (
    ProductApiGateway,
    ProductApiOperation,
    ProductApiRequestType,
    ProductApiStatus,
    ProductApiStores,
    build_product_api_context,
    build_product_api_gateway,
    build_product_api_request,
    build_product_api_stores,
    product_api_health_response,
    product_api_summary,
    product_api_summary_response,
    route_product_api_request,
    validate_product_api_stores,
)


def build_request(
    request_type: str,
    operation: str,
    payload: dict | None = None,
):
    return build_product_api_request(
        request_type=request_type,
        operation=operation,
        request_id="req-1",
        context=build_product_api_context(
            request_id="req-1",
            user_id="user-1",
            tenant_id="tenant-1",
        ),
        payload=payload or {},
    )


def signal_payload(signal_id: str = "signal-1") -> dict:
    return {
        "signal_id": signal_id,
        "symbol": "XAUUSD",
        "timeframe": "H1",
        "direction": "buy",
        "confidence": 82,
        "entry_price": 2000,
        "stop_loss": 1990,
        "take_profit": 2020,
        "explanation": "Momentum setup.",
        "created_at": "2026-01-01T00:00:00+00:00",
    }


def portfolio_payload(account_id: str = "account-1") -> dict:
    return {
        "account_id": account_id,
        "balance": 10000,
        "equity": 10020,
        "currency": "USD",
        "margin_used": 1000,
        "timestamp": "2026-01-01T00:00:00+00:00",
        "positions": [
            {
                "position_id": "position-1",
                "symbol": "XAUUSD",
                "side": "buy",
                "quantity": 2,
                "entry_price": 2000,
                "current_price": 2010,
                "opened_at": "2026-01-01T00:00:00+00:00",
            }
        ],
    }


def research_payload(finding_id: str = "finding-1") -> dict:
    return {
        "finding_id": finding_id,
        "title": "Gold momentum continuation",
        "finding_type": "hypothesis",
        "summary": "XAUUSD shows continuation signs.",
        "confidence": 78,
        "priority": "high",
        "status": "draft",
        "symbol": "XAUUSD",
        "timeframe": "H1",
        "tags": ["gold"],
        "created_at": "2026-01-01T00:00:00+00:00",
    }


def analytics_payload(dashboard_id: str = "dashboard-1") -> dict:
    return {
        "dashboard_id": dashboard_id,
        "title": "Trading Analytics",
        "period": "daily",
        "generated_at": "2026-01-01T00:00:00+00:00",
        "metrics": [
            {
                "metric_id": "metric-1",
                "metric_type": "return_percent",
                "value": 12.5,
                "label": "Return",
            }
        ],
        "series": [
            {
                "series_id": "series-1",
                "metric_type": "return_percent",
                "period": "daily",
                "label": "Return series",
                "points": [
                    {
                        "timestamp": "2026-01-01T00:00:00+00:00",
                        "value": 10,
                    },
                    {
                        "timestamp": "2026-01-02T00:00:00+00:00",
                        "value": 15,
                    },
                ],
            }
        ],
    }


def test_product_api_stores_summary():
    stores = build_product_api_stores(
        metadata={
            "source": "test",
        },
    )

    assert isinstance(stores, ProductApiStores)
    assert stores.total_records == 0
    assert stores.resource_counts() == {
        "signals": 0,
        "portfolios": 0,
        "research_findings": 0,
        "analytics_dashboards": 0,
        "total_records": 0,
    }
    assert stores.to_dict()["metadata"] == {
        "source": "test",
    }


def test_product_api_stores_reject_invalid_values():
    with pytest.raises(ValueError):
        ProductApiStores(signal_store="bad")

    with pytest.raises(ValueError):
        ProductApiStores(portfolio_store="bad")

    with pytest.raises(ValueError):
        ProductApiStores(research_store="bad")

    with pytest.raises(ValueError):
        ProductApiStores(analytics_store="bad")

    with pytest.raises(ValueError):
        ProductApiStores(metadata=[])

    with pytest.raises(ValueError):
        validate_product_api_stores("bad")


def test_product_api_gateway_summary_and_health_response():
    stores = build_product_api_stores()
    gateway = build_product_api_gateway(
        stores=stores,
        metadata={
            "source": "test",
        },
    )

    assert isinstance(gateway, ProductApiGateway)
    assert gateway.summary()["gateway"] == "aqos-product-api"
    assert gateway.summary()["metadata"] == {
        "source": "test",
    }

    response = product_api_health_response(
        stores=stores,
        context=build_product_api_context(request_id="req-1"),
    )

    assert response.status == ProductApiStatus.SUCCESS
    assert response.data["status"] == "healthy"
    assert response.data["summary"]["ready"] is True


def test_product_api_summary_response():
    stores = build_product_api_stores()

    response = product_api_summary_response(
        stores=stores,
        context=build_product_api_context(request_id="req-1"),
    )

    assert response.status == ProductApiStatus.SUCCESS
    assert response.data["summary"] == product_api_summary(stores)


def test_signal_create_list_get_update_delete_flow():
    gateway = build_product_api_gateway()

    create_response = gateway.handle_request(
        build_request("signal", "create", signal_payload()),
    )

    assert create_response.status == ProductApiStatus.SUCCESS
    assert create_response.data["operation"] == ProductApiOperation.CREATE.value
    assert gateway.stores.signal_store.count() == 1

    list_response = gateway.handle_request(
        build_request("signal", "list"),
    )

    assert list_response.status == ProductApiStatus.SUCCESS
    assert list_response.data["total_items"] == 1

    get_response = gateway.handle_request(
        build_request("signal", "get", {"signal_id": "signal-1"}),
    )

    assert get_response.status == ProductApiStatus.SUCCESS
    assert get_response.data["signal"]["signal_id"] == "signal-1"

    update_response = gateway.handle_request(
        build_request(
            "signal",
            "update",
            {
                "signal_id": "signal-1",
                "status": "approved",
                "metadata": {
                    "approved_by": "qa",
                },
            },
        ),
    )

    assert update_response.status == ProductApiStatus.SUCCESS
    assert update_response.data["signal"]["status"] == "approved"

    delete_response = gateway.handle_request(
        build_request("signal", "delete", {"signal_id": "signal-1"}),
    )

    assert delete_response.status == ProductApiStatus.SUCCESS
    assert delete_response.data["resource_type"] == ProductApiRequestType.SIGNAL.value
    assert delete_response.data["result"]["deleted"] is True
    assert gateway.stores.signal_store.count() == 0


def test_portfolio_create_list_get_update_delete_flow():
    gateway = build_product_api_gateway()

    create_response = gateway.handle_request(
        build_request("portfolio", "create", portfolio_payload()),
    )

    assert create_response.status == ProductApiStatus.SUCCESS
    assert gateway.stores.portfolio_store.count() == 1

    list_response = gateway.handle_request(
        build_request("portfolio", "list"),
    )

    assert list_response.status == ProductApiStatus.SUCCESS
    assert list_response.data["total_items"] == 1

    get_response = gateway.handle_request(
        build_request("portfolio", "get", {"account_id": "account-1"}),
    )

    assert get_response.status == ProductApiStatus.SUCCESS
    assert get_response.data["portfolio"]["account_id"] == "account-1"

    updated_payload = portfolio_payload()
    updated_payload["equity"] = 10100

    update_response = gateway.handle_request(
        build_request("portfolio", "update", updated_payload),
    )

    assert update_response.status == ProductApiStatus.SUCCESS
    assert update_response.data["portfolio"]["equity"] == 10100.0

    delete_response = gateway.handle_request(
        build_request("portfolio", "delete", {"account_id": "account-1"}),
    )

    assert delete_response.status == ProductApiStatus.SUCCESS
    assert gateway.stores.portfolio_store.count() == 0


def test_research_create_list_get_update_delete_flow():
    gateway = build_product_api_gateway()

    create_response = gateway.handle_request(
        build_request("research", "create", research_payload()),
    )

    assert create_response.status == ProductApiStatus.SUCCESS
    assert gateway.stores.research_store.count() == 1

    list_response = gateway.handle_request(
        build_request("research", "list"),
    )

    assert list_response.status == ProductApiStatus.SUCCESS
    assert list_response.data["total_items"] == 1

    get_response = gateway.handle_request(
        build_request("research", "get", {"finding_id": "finding-1"}),
    )

    assert get_response.status == ProductApiStatus.SUCCESS
    assert get_response.data["finding"]["finding_id"] == "finding-1"

    update_response = gateway.handle_request(
        build_request(
            "research",
            "update",
            {
                "finding_id": "finding-1",
                "status": "completed",
                "metadata": {
                    "reviewed": True,
                },
            },
        ),
    )

    assert update_response.status == ProductApiStatus.SUCCESS
    assert update_response.data["finding"]["status"] == "completed"

    delete_response = gateway.handle_request(
        build_request("research", "delete", {"finding_id": "finding-1"}),
    )

    assert delete_response.status == ProductApiStatus.SUCCESS
    assert gateway.stores.research_store.count() == 0


def test_analytics_create_list_get_update_delete_flow():
    gateway = build_product_api_gateway()

    create_response = gateway.handle_request(
        build_request("analytics", "create", analytics_payload()),
    )

    assert create_response.status == ProductApiStatus.SUCCESS
    assert gateway.stores.analytics_store.count() == 1

    list_response = gateway.handle_request(
        build_request("analytics", "list"),
    )

    assert list_response.status == ProductApiStatus.SUCCESS
    assert list_response.data["total_items"] == 1

    get_response = gateway.handle_request(
        build_request("analytics", "get", {"dashboard_id": "dashboard-1"}),
    )

    assert get_response.status == ProductApiStatus.SUCCESS
    assert get_response.data["dashboard"]["dashboard_id"] == "dashboard-1"

    updated_payload = analytics_payload()
    updated_payload["title"] = "Updated Analytics"

    update_response = gateway.handle_request(
        build_request("analytics", "update", updated_payload),
    )

    assert update_response.status == ProductApiStatus.SUCCESS
    assert update_response.data["dashboard"]["title"] == "Updated Analytics"

    delete_response = gateway.handle_request(
        build_request("analytics", "delete", {"dashboard_id": "dashboard-1"}),
    )

    assert delete_response.status == ProductApiStatus.SUCCESS
    assert gateway.stores.analytics_store.count() == 0


def test_workflow_summary_route():
    gateway = build_product_api_gateway()

    gateway.handle_request(
        build_request("signal", "create", signal_payload()),
    )

    response = gateway.handle_request(
        build_request(
            "workflow",
            "execute",
            {
                "workflow": "summary",
            },
        ),
    )

    assert response.status == ProductApiStatus.SUCCESS
    assert response.data["summary"]["resources"]["signals"] == 1


def test_route_product_api_request_helper():
    stores = build_product_api_stores()
    request = build_request("signal", "create", signal_payload())

    response = route_product_api_request(
        request=request,
        stores=stores,
    )

    assert response.status == ProductApiStatus.SUCCESS
    assert stores.signal_store.count() == 1


def test_missing_resources_return_not_found():
    gateway = build_product_api_gateway()

    signal_response = gateway.handle_request(
        build_request("signal", "get", {"signal_id": "missing"}),
    )
    portfolio_response = gateway.handle_request(
        build_request("portfolio", "get", {"account_id": "missing"}),
    )
    research_response = gateway.handle_request(
        build_request("research", "get", {"finding_id": "missing"}),
    )
    analytics_response = gateway.handle_request(
        build_request("analytics", "get", {"dashboard_id": "missing"}),
    )

    assert signal_response.status == ProductApiStatus.FAILURE
    assert portfolio_response.status == ProductApiStatus.FAILURE
    assert research_response.status == ProductApiStatus.FAILURE
    assert analytics_response.status == ProductApiStatus.FAILURE

    assert signal_response.error is not None
    assert signal_response.error.code == "not_found"


def test_validation_failures_return_failure_response():
    gateway = build_product_api_gateway()

    response = gateway.handle_request(
        build_request("signal", "get", {}),
    )

    assert response.status == ProductApiStatus.FAILURE
    assert response.error is not None
    assert response.error.code == "validation_error"


def test_unsupported_operation_returns_failure_response():
    gateway = build_product_api_gateway()

    response = gateway.handle_request(
        build_request("workflow", "list"),
    )

    assert response.status == ProductApiStatus.FAILURE
    assert response.error is not None
    assert response.error.code == "validation_error"


def test_gateway_rejects_invalid_request():
    gateway = build_product_api_gateway()

    with pytest.raises(ValueError):
        gateway.handle_request("bad")


def test_product_api_integration_exports_exist():
    import aqos.product_api as product_api

    expected_exports = [
        "ProductApiGateway",
        "ProductApiStores",
        "build_product_api_gateway",
        "build_product_api_stores",
        "product_api_health_response",
        "product_api_summary",
        "product_api_summary_response",
        "route_product_api_request",
        "validate_product_api_stores",
    ]

    for export_name in expected_exports:
        assert hasattr(product_api, export_name), export_name