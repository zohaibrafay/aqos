"""
AQOS product API integration helpers.

This module wires product-facing signals, portfolios, research, and analytics
contracts into a lightweight in-memory product API gateway.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from aqos.product_api.analytics import (
    ProductAnalyticsDashboard,
    ProductAnalyticsMetric,
    ProductAnalyticsPoint,
    ProductAnalyticsSeries,
    ProductAnalyticsStore,
    analytics_dashboard_to_response,
    build_product_analytics_dashboard,
    build_product_analytics_metric,
    build_product_analytics_point,
    build_product_analytics_series,
    build_product_analytics_store,
    create_analytics_operation_response,
    get_analytics_dashboard_response,
    list_analytics_dashboards_response,
)
from aqos.product_api.base import (
    ProductApiErrorCode,
    ProductApiRequestContext,
    ProductApiResponse,
    product_api_failure,
    product_api_success,
    validate_metadata,
    validate_non_empty_string,
)
from aqos.product_api.contracts import (
    ProductApiOperation,
    ProductApiOperationResult,
    ProductApiRequest,
    ProductApiRequestType,
    normalize_product_api_operation,
    normalize_product_api_request_type,
    operation_result_to_response,
)
from aqos.product_api.portfolio import (
    ProductPortfolioPosition,
    ProductPortfolioSnapshot,
    ProductPortfolioStore,
    build_product_portfolio_position,
    build_product_portfolio_snapshot,
    build_product_portfolio_store,
    create_portfolio_operation_response,
    get_portfolio_response,
    list_portfolios_response,
    portfolio_snapshot_to_response,
)
from aqos.product_api.research import (
    ProductResearchFinding,
    ProductResearchStore,
    build_product_research_finding,
    build_product_research_store,
    create_research_operation_response,
    get_research_finding_response,
    list_research_findings_response,
    research_finding_to_response,
    update_research_status,
)
from aqos.product_api.signals import (
    ProductSignalPayload,
    ProductSignalStore,
    build_product_signal_payload,
    build_product_signal_store,
    create_signal_operation_response,
    get_signal_response,
    list_signals_response,
    signal_payload_to_response,
    update_signal_status,
)


@dataclass
class ProductApiStores:
    """Container for product API in-memory stores."""

    signal_store: ProductSignalStore = field(default_factory=build_product_signal_store)
    portfolio_store: ProductPortfolioStore = field(default_factory=build_product_portfolio_store)
    research_store: ProductResearchStore = field(default_factory=build_product_research_store)
    analytics_store: ProductAnalyticsStore = field(default_factory=build_product_analytics_store)
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not isinstance(self.signal_store, ProductSignalStore):
            raise ValueError("Signal store must be a ProductSignalStore.")

        if not isinstance(self.portfolio_store, ProductPortfolioStore):
            raise ValueError("Portfolio store must be a ProductPortfolioStore.")

        if not isinstance(self.research_store, ProductResearchStore):
            raise ValueError("Research store must be a ProductResearchStore.")

        if not isinstance(self.analytics_store, ProductAnalyticsStore):
            raise ValueError("Analytics store must be a ProductAnalyticsStore.")

        validate_metadata(self.metadata, "Metadata")

    @property
    def total_records(self) -> int:
        """Return total product API records."""
        return (
            self.signal_store.count()
            + self.portfolio_store.count()
            + self.research_store.count()
            + self.analytics_store.count()
        )

    def resource_counts(self) -> dict[str, int]:
        """Return resource counts."""
        return {
            "signals": self.signal_store.count(),
            "portfolios": self.portfolio_store.count(),
            "research_findings": self.research_store.count(),
            "analytics_dashboards": self.analytics_store.count(),
            "total_records": self.total_records,
        }

    def to_dict(self) -> dict[str, Any]:
        """Convert stores summary into dictionary."""
        return {
            "counts": self.resource_counts(),
            "metadata": dict(self.metadata),
        }


@dataclass
class ProductApiGateway:
    """Product-facing API gateway."""

    stores: ProductApiStores = field(default_factory=lambda: ProductApiStores())
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        validate_product_api_stores(self.stores)
        validate_metadata(self.metadata, "Metadata")

    def summary(self) -> dict[str, Any]:
        """Return gateway summary."""
        return {
            "gateway": "aqos-product-api",
            "stores": self.stores.to_dict(),
            "metadata": dict(self.metadata),
        }

    def handle_request(self, request: ProductApiRequest) -> ProductApiResponse:
        """Handle a product API request."""
        if not isinstance(request, ProductApiRequest):
            raise ValueError("Request must be a ProductApiRequest.")

        try:
            request_type = normalize_product_api_request_type(request.request_type)

            if request_type == ProductApiRequestType.SIGNAL:
                return self.handle_signal_request(request)

            if request_type == ProductApiRequestType.PORTFOLIO:
                return self.handle_portfolio_request(request)

            if request_type == ProductApiRequestType.RESEARCH:
                return self.handle_research_request(request)

            if request_type == ProductApiRequestType.ANALYTICS:
                return self.handle_analytics_request(request)

            if request_type == ProductApiRequestType.WORKFLOW:
                return self.handle_workflow_request(request)

            return unsupported_operation_response(
                request=request,
                details={
                    "request_type": request_type.value,
                },
            )
        except (TypeError, ValueError) as exc:
            return product_api_failure(
                message=str(exc),
                code=ProductApiErrorCode.VALIDATION_ERROR,
                details={
                    "request_type": str(request.request_type),
                    "operation": str(request.operation),
                },
                context=request.context,
            )

    def handle_signal_request(self, request: ProductApiRequest) -> ProductApiResponse:
        """Handle product signal request."""
        operation = normalize_product_api_operation(request.operation)

        if operation == ProductApiOperation.LIST:
            return list_signals_response(
                signals=self.stores.signal_store.list(),
                query=request.query,
                context=request.context,
            )

        if operation == ProductApiOperation.GET:
            return get_signal_response(
                store=self.stores.signal_store,
                signal_id=required_payload_string(request.payload, "signal_id"),
                context=request.context,
            )

        if operation == ProductApiOperation.CREATE:
            signal = build_product_signal_payload(**request.payload)
            self.stores.signal_store.add(signal)
            return create_signal_operation_response(
                signal=signal,
                context=request.context,
            )

        if operation == ProductApiOperation.UPDATE:
            signal_id = required_payload_string(request.payload, "signal_id")
            status = required_payload_string(request.payload, "status")
            signal = self.stores.signal_store.get(signal_id)

            if signal is None:
                return not_found_response(
                    context=request.context,
                    resource_name="Signal",
                    resource_id=signal_id,
                    resource_key="signal_id",
                )

            updated_signal = update_signal_status(
                signal,
                status=status,
                metadata=request.payload.get("metadata", {}),
            )
            self.stores.signal_store.add(updated_signal)
            return signal_payload_to_response(
                signal=updated_signal,
                context=request.context,
                message="Signal updated successfully.",
            )

        if operation == ProductApiOperation.DELETE:
            signal_id = required_payload_string(request.payload, "signal_id")
            removed = self.stores.signal_store.remove(signal_id)

            if removed is None:
                return not_found_response(
                    context=request.context,
                    resource_name="Signal",
                    resource_id=signal_id,
                    resource_key="signal_id",
                )

            return delete_operation_response(
                context=request.context,
                resource_type=ProductApiRequestType.SIGNAL,
                resource_id=signal_id,
            )

        return unsupported_operation_response(request=request)

    def handle_portfolio_request(self, request: ProductApiRequest) -> ProductApiResponse:
        """Handle product portfolio request."""
        operation = normalize_product_api_operation(request.operation)

        if operation == ProductApiOperation.LIST:
            return list_portfolios_response(
                snapshots=self.stores.portfolio_store.list(),
                query=request.query,
                context=request.context,
            )

        if operation == ProductApiOperation.GET:
            return get_portfolio_response(
                store=self.stores.portfolio_store,
                account_id=required_payload_string(request.payload, "account_id"),
                context=request.context,
            )

        if operation == ProductApiOperation.CREATE:
            snapshot = build_portfolio_snapshot_from_payload(request.payload)
            self.stores.portfolio_store.add(snapshot)
            return create_portfolio_operation_response(
                snapshot=snapshot,
                context=request.context,
            )

        if operation == ProductApiOperation.DELETE:
            account_id = required_payload_string(request.payload, "account_id")
            removed = self.stores.portfolio_store.remove(account_id)

            if removed is None:
                return not_found_response(
                    context=request.context,
                    resource_name="Portfolio",
                    resource_id=account_id,
                    resource_key="account_id",
                )

            return delete_operation_response(
                context=request.context,
                resource_type=ProductApiRequestType.PORTFOLIO,
                resource_id=account_id,
            )

        if operation == ProductApiOperation.UPDATE:
            snapshot = build_portfolio_snapshot_from_payload(request.payload)
            self.stores.portfolio_store.add(snapshot)
            return portfolio_snapshot_to_response(
                snapshot=snapshot,
                context=request.context,
                message="Portfolio updated successfully.",
            )

        return unsupported_operation_response(request=request)

    def handle_research_request(self, request: ProductApiRequest) -> ProductApiResponse:
        """Handle product research request."""
        operation = normalize_product_api_operation(request.operation)

        if operation == ProductApiOperation.LIST:
            return list_research_findings_response(
                findings=self.stores.research_store.list(),
                query=request.query,
                context=request.context,
            )

        if operation == ProductApiOperation.GET:
            return get_research_finding_response(
                store=self.stores.research_store,
                finding_id=required_payload_string(request.payload, "finding_id"),
                context=request.context,
            )

        if operation == ProductApiOperation.CREATE:
            finding = build_product_research_finding(**request.payload)
            self.stores.research_store.add(finding)
            return create_research_operation_response(
                finding=finding,
                context=request.context,
            )

        if operation == ProductApiOperation.UPDATE:
            finding_id = required_payload_string(request.payload, "finding_id")
            status = required_payload_string(request.payload, "status")
            finding = self.stores.research_store.get(finding_id)

            if finding is None:
                return not_found_response(
                    context=request.context,
                    resource_name="Research finding",
                    resource_id=finding_id,
                    resource_key="finding_id",
                )

            updated_finding = update_research_status(
                finding,
                status=status,
                metadata=request.payload.get("metadata", {}),
            )
            self.stores.research_store.add(updated_finding)
            return research_finding_to_response(
                finding=updated_finding,
                context=request.context,
                message="Research finding updated successfully.",
            )

        if operation == ProductApiOperation.DELETE:
            finding_id = required_payload_string(request.payload, "finding_id")
            removed = self.stores.research_store.remove(finding_id)

            if removed is None:
                return not_found_response(
                    context=request.context,
                    resource_name="Research finding",
                    resource_id=finding_id,
                    resource_key="finding_id",
                )

            return delete_operation_response(
                context=request.context,
                resource_type=ProductApiRequestType.RESEARCH,
                resource_id=finding_id,
            )

        return unsupported_operation_response(request=request)

    def handle_analytics_request(self, request: ProductApiRequest) -> ProductApiResponse:
        """Handle product analytics request."""
        operation = normalize_product_api_operation(request.operation)

        if operation == ProductApiOperation.LIST:
            return list_analytics_dashboards_response(
                dashboards=self.stores.analytics_store.list(),
                query=request.query,
                context=request.context,
            )

        if operation == ProductApiOperation.GET:
            return get_analytics_dashboard_response(
                store=self.stores.analytics_store,
                dashboard_id=required_payload_string(request.payload, "dashboard_id"),
                context=request.context,
            )

        if operation == ProductApiOperation.CREATE:
            dashboard = build_analytics_dashboard_from_payload(request.payload)
            self.stores.analytics_store.add(dashboard)
            return create_analytics_operation_response(
                dashboard=dashboard,
                context=request.context,
            )

        if operation == ProductApiOperation.UPDATE:
            dashboard = build_analytics_dashboard_from_payload(request.payload)
            self.stores.analytics_store.add(dashboard)
            return analytics_dashboard_to_response(
                dashboard=dashboard,
                context=request.context,
                message="Analytics dashboard updated successfully.",
            )

        if operation == ProductApiOperation.DELETE:
            dashboard_id = required_payload_string(request.payload, "dashboard_id")
            removed = self.stores.analytics_store.remove(dashboard_id)

            if removed is None:
                return not_found_response(
                    context=request.context,
                    resource_name="Analytics dashboard",
                    resource_id=dashboard_id,
                    resource_key="dashboard_id",
                )

            return delete_operation_response(
                context=request.context,
                resource_type=ProductApiRequestType.ANALYTICS,
                resource_id=dashboard_id,
            )

        return unsupported_operation_response(request=request)

    def handle_workflow_request(self, request: ProductApiRequest) -> ProductApiResponse:
        """Handle product workflow request."""
        operation = normalize_product_api_operation(request.operation)

        if operation in {ProductApiOperation.GET, ProductApiOperation.EXECUTE}:
            workflow = request.payload.get("workflow", "summary")

            if workflow != "summary":
                return product_api_failure(
                    message="Unsupported product workflow.",
                    code=ProductApiErrorCode.VALIDATION_ERROR,
                    details={
                        "workflow": workflow,
                    },
                    context=request.context,
                )

            return product_api_summary_response(
                stores=self.stores,
                context=request.context,
            )

        return unsupported_operation_response(request=request)


def validate_product_api_stores(stores: ProductApiStores) -> ProductApiStores:
    """Validate product API stores."""
    if not isinstance(stores, ProductApiStores):
        raise ValueError("Stores must be ProductApiStores.")

    return stores


def required_payload_string(payload: dict[str, Any], key: str) -> str:
    """Get required payload string."""
    validate_metadata(payload, "Payload")
    validate_non_empty_string(key, "Payload key")

    if key not in payload:
        raise ValueError(f"Payload field '{key}' is required.")

    return validate_non_empty_string(str(payload[key]), key)


def build_portfolio_snapshot_from_payload(payload: dict[str, Any]) -> ProductPortfolioSnapshot:
    """Build portfolio snapshot from request payload."""
    validate_metadata(payload, "Payload")

    positions = [
        build_portfolio_position_from_payload(item)
        for item in payload.get("positions", [])
    ]

    snapshot_payload = {
        **payload,
        "positions": positions,
    }

    return build_product_portfolio_snapshot(**snapshot_payload)


def build_portfolio_position_from_payload(
    payload: ProductPortfolioPosition | dict[str, Any],
) -> ProductPortfolioPosition:
    """Build portfolio position from payload."""
    if isinstance(payload, ProductPortfolioPosition):
        return payload

    validate_metadata(payload, "Position payload")
    return build_product_portfolio_position(**payload)


def build_analytics_dashboard_from_payload(payload: dict[str, Any]) -> ProductAnalyticsDashboard:
    """Build analytics dashboard from request payload."""
    validate_metadata(payload, "Payload")

    metrics = [
        build_analytics_metric_from_payload(item)
        for item in payload.get("metrics", [])
    ]
    series = [
        build_analytics_series_from_payload(item)
        for item in payload.get("series", [])
    ]

    dashboard_payload = {
        **payload,
        "metrics": metrics,
        "series": series,
    }

    return build_product_analytics_dashboard(**dashboard_payload)


def build_analytics_metric_from_payload(
    payload: ProductAnalyticsMetric | dict[str, Any],
) -> ProductAnalyticsMetric:
    """Build analytics metric from payload."""
    if isinstance(payload, ProductAnalyticsMetric):
        return payload

    validate_metadata(payload, "Metric payload")
    return build_product_analytics_metric(**payload)


def build_analytics_series_from_payload(
    payload: ProductAnalyticsSeries | dict[str, Any],
) -> ProductAnalyticsSeries:
    """Build analytics series from payload."""
    if isinstance(payload, ProductAnalyticsSeries):
        return payload

    validate_metadata(payload, "Series payload")

    points = [
        build_analytics_point_from_payload(item)
        for item in payload.get("points", [])
    ]

    series_payload = {
        **payload,
        "points": points,
    }

    return build_product_analytics_series(**series_payload)


def build_analytics_point_from_payload(
    payload: ProductAnalyticsPoint | dict[str, Any],
) -> ProductAnalyticsPoint:
    """Build analytics point from payload."""
    if isinstance(payload, ProductAnalyticsPoint):
        return payload

    validate_metadata(payload, "Point payload")
    return build_product_analytics_point(**payload)


def delete_operation_response(
    *,
    context: ProductApiRequestContext | None,
    resource_type: ProductApiRequestType,
    resource_id: str,
) -> ProductApiResponse:
    """Build delete operation response."""
    return operation_result_to_response(
        result=ProductApiOperationResult(
            operation=ProductApiOperation.DELETE,
            resource_type=resource_type,
            resource_id=resource_id,
            accepted=True,
            result={
                "deleted": True,
            },
        ),
        context=context,
        message="Resource deleted successfully.",
    )


def not_found_response(
    *,
    context: ProductApiRequestContext | None,
    resource_name: str,
    resource_id: str,
    resource_key: str,
) -> ProductApiResponse:
    """Build not found response."""
    return product_api_failure(
        message=f"{resource_name} not found.",
        code=ProductApiErrorCode.NOT_FOUND,
        details={
            resource_key: resource_id,
        },
        context=context,
    )


def unsupported_operation_response(
    *,
    request: ProductApiRequest,
    details: dict[str, Any] | None = None,
) -> ProductApiResponse:
    """Build unsupported operation response."""
    return product_api_failure(
        message="Unsupported product API operation.",
        code=ProductApiErrorCode.VALIDATION_ERROR,
        details={
            "request_type": normalize_product_api_request_type(request.request_type).value,
            "operation": normalize_product_api_operation(request.operation).value,
            **(details or {}),
        },
        context=request.context,
    )


def product_api_summary(stores: ProductApiStores) -> dict[str, Any]:
    """Build product API summary."""
    validate_product_api_stores(stores)

    return {
        "product_api": "AQOS Product API",
        "resources": stores.resource_counts(),
        "ready": True,
    }


def product_api_health_response(
    *,
    stores: ProductApiStores | None = None,
    context: ProductApiRequestContext | None = None,
) -> ProductApiResponse:
    """Build product API health response."""
    resolved_stores = stores or build_product_api_stores()

    return product_api_success(
        data={
            "status": "healthy",
            "summary": product_api_summary(resolved_stores),
        },
        message="Product API is healthy.",
        context=context,
    )


def product_api_summary_response(
    *,
    stores: ProductApiStores,
    context: ProductApiRequestContext | None = None,
) -> ProductApiResponse:
    """Build product API summary response."""
    return product_api_success(
        data={
            "summary": product_api_summary(stores),
        },
        message="Product API summary generated successfully.",
        context=context,
    )


def build_product_api_stores(
    *,
    signal_store: ProductSignalStore | None = None,
    portfolio_store: ProductPortfolioStore | None = None,
    research_store: ProductResearchStore | None = None,
    analytics_store: ProductAnalyticsStore | None = None,
    metadata: dict[str, Any] | None = None,
) -> ProductApiStores:
    """Build product API stores."""
    return ProductApiStores(
        signal_store=signal_store or build_product_signal_store(),
        portfolio_store=portfolio_store or build_product_portfolio_store(),
        research_store=research_store or build_product_research_store(),
        analytics_store=analytics_store or build_product_analytics_store(),
        metadata=metadata or {},
    )


def build_product_api_gateway(
    *,
    stores: ProductApiStores | None = None,
    metadata: dict[str, Any] | None = None,
) -> ProductApiGateway:
    """Build product API gateway."""
    return ProductApiGateway(
        stores=stores or build_product_api_stores(),
        metadata=metadata or {},
    )


def route_product_api_request(
    *,
    request: ProductApiRequest,
    gateway: ProductApiGateway | None = None,
    stores: ProductApiStores | None = None,
) -> ProductApiResponse:
    """Route product API request through gateway."""
    resolved_gateway = gateway or build_product_api_gateway(
        stores=stores,
    )

    return resolved_gateway.handle_request(request)