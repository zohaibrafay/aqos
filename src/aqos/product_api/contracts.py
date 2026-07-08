"""
AQOS product API request and response contracts.

This module provides dependency-free product-facing contracts for requests,
pagination, filtering, sorting, list responses, and operation results.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from math import ceil
from typing import Any

from aqos.product_api.base import (
    ProductApiRequestContext,
    ProductApiResponse,
    ProductApiStatus,
    build_product_api_context,
    product_api_success,
    validate_metadata,
    validate_non_empty_string,
    validate_string,
)


class ProductApiRequestType(str, Enum):
    """Supported product API request types."""

    SIGNAL = "signal"
    PORTFOLIO = "portfolio"
    RESEARCH = "research"
    ANALYTICS = "analytics"
    WORKFLOW = "workflow"


class ProductApiOperation(str, Enum):
    """Supported product API operations."""

    LIST = "list"
    GET = "get"
    CREATE = "create"
    UPDATE = "update"
    DELETE = "delete"
    EXECUTE = "execute"


class ProductSortDirection(str, Enum):
    """Supported product API sort directions."""

    ASC = "asc"
    DESC = "desc"


class ProductFilterOperator(str, Enum):
    """Supported product API filter operators."""

    EQ = "eq"
    NE = "ne"
    GT = "gt"
    GTE = "gte"
    LT = "lt"
    LTE = "lte"
    IN = "in"
    CONTAINS = "contains"


@dataclass(frozen=True)
class ProductApiPagination:
    """Product API pagination contract."""

    page: int = 1
    page_size: int = 20

    def __post_init__(self) -> None:
        validate_positive_integer(self.page, "Page")
        validate_positive_integer(self.page_size, "Page size")

        if self.page_size > 500:
            raise ValueError("Page size cannot exceed 500.")

    @property
    def offset(self) -> int:
        """Return pagination offset."""
        return (self.page - 1) * self.page_size

    def total_pages(self, total_items: int) -> int:
        """Calculate total pages."""
        validate_non_negative_integer(total_items, "Total items")

        if total_items == 0:
            return 0

        return ceil(total_items / self.page_size)

    def to_dict(self, *, total_items: int | None = None) -> dict[str, Any]:
        """Convert pagination into dictionary."""
        payload: dict[str, Any] = {
            "page": self.page,
            "page_size": self.page_size,
            "offset": self.offset,
        }

        if total_items is not None:
            validate_non_negative_integer(total_items, "Total items")
            payload["total_items"] = total_items
            payload["total_pages"] = self.total_pages(total_items)
            payload["has_next"] = self.page < self.total_pages(total_items)
            payload["has_previous"] = self.page > 1

        return payload


@dataclass(frozen=True)
class ProductApiSort:
    """Product API sort contract."""

    field: str
    direction: ProductSortDirection | str = ProductSortDirection.ASC

    def __post_init__(self) -> None:
        validate_field_name(self.field)
        normalize_product_sort_direction(self.direction)

    def to_dict(self) -> dict[str, Any]:
        """Convert sort into dictionary."""
        return {
            "field": self.field.strip(),
            "direction": normalize_product_sort_direction(self.direction).value,
        }


@dataclass(frozen=True)
class ProductApiFilter:
    """Product API filter contract."""

    field: str
    operator: ProductFilterOperator | str
    value: Any

    def __post_init__(self) -> None:
        validate_field_name(self.field)
        normalized_operator = normalize_product_filter_operator(self.operator)

        if normalized_operator == ProductFilterOperator.IN and not isinstance(self.value, list):
            raise ValueError("IN filter value must be a list.")

        if normalized_operator == ProductFilterOperator.CONTAINS and not isinstance(self.value, str):
            raise ValueError("CONTAINS filter value must be a string.")

    def to_dict(self) -> dict[str, Any]:
        """Convert filter into dictionary."""
        return {
            "field": self.field.strip(),
            "operator": normalize_product_filter_operator(self.operator).value,
            "value": self.value,
        }


@dataclass(frozen=True)
class ProductApiListQuery:
    """Product API list query contract."""

    pagination: ProductApiPagination = field(default_factory=ProductApiPagination)
    filters: list[ProductApiFilter] = field(default_factory=list)
    sort: list[ProductApiSort] = field(default_factory=list)
    search: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not isinstance(self.pagination, ProductApiPagination):
            raise ValueError("Pagination must be a ProductApiPagination.")

        validate_product_filters(self.filters)
        validate_product_sorts(self.sort)
        validate_string(self.search, "Search")
        validate_metadata(self.metadata, "Metadata")

    def to_dict(self) -> dict[str, Any]:
        """Convert list query into dictionary."""
        return {
            "pagination": self.pagination.to_dict(),
            "filters": [
                item.to_dict()
                for item in self.filters
            ],
            "sort": [
                item.to_dict()
                for item in self.sort
            ],
            "search": self.search.strip(),
            "metadata": dict(self.metadata),
        }


@dataclass(frozen=True)
class ProductApiRequest:
    """Product API request contract."""

    request_type: ProductApiRequestType | str
    operation: ProductApiOperation | str
    context: ProductApiRequestContext
    payload: dict[str, Any] = field(default_factory=dict)
    query: ProductApiListQuery | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        normalize_product_api_request_type(self.request_type)
        normalize_product_api_operation(self.operation)

        if not isinstance(self.context, ProductApiRequestContext):
            raise ValueError("Context must be a ProductApiRequestContext.")

        validate_metadata(self.payload, "Payload")

        if self.query is not None and not isinstance(self.query, ProductApiListQuery):
            raise ValueError("Query must be a ProductApiListQuery.")

        validate_metadata(self.metadata, "Metadata")

    @property
    def is_list(self) -> bool:
        """Return whether request is a list request."""
        return normalize_product_api_operation(self.operation) == ProductApiOperation.LIST

    @property
    def is_execute(self) -> bool:
        """Return whether request is an execute request."""
        return normalize_product_api_operation(self.operation) == ProductApiOperation.EXECUTE

    def to_dict(self) -> dict[str, Any]:
        """Convert request into dictionary."""
        return {
            "request_type": normalize_product_api_request_type(self.request_type).value,
            "operation": normalize_product_api_operation(self.operation).value,
            "context": self.context.to_dict(),
            "payload": dict(self.payload),
            "query": self.query.to_dict() if self.query else None,
            "metadata": dict(self.metadata),
        }


@dataclass(frozen=True)
class ProductApiListResult:
    """Product API list result contract."""

    items: list[dict[str, Any]] = field(default_factory=list)
    pagination: ProductApiPagination = field(default_factory=ProductApiPagination)
    total_items: int = 0
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        validate_list_items(self.items)

        if not isinstance(self.pagination, ProductApiPagination):
            raise ValueError("Pagination must be a ProductApiPagination.")

        validate_non_negative_integer(self.total_items, "Total items")
        validate_metadata(self.metadata, "Metadata")

    def to_dict(self) -> dict[str, Any]:
        """Convert list result into dictionary."""
        return {
            "items": [
                dict(item)
                for item in self.items
            ],
            "pagination": self.pagination.to_dict(total_items=self.total_items),
            "total_items": self.total_items,
            "metadata": dict(self.metadata),
        }


@dataclass(frozen=True)
class ProductApiOperationResult:
    """Product API operation result contract."""

    operation: ProductApiOperation | str
    resource_type: ProductApiRequestType | str
    resource_id: str = ""
    accepted: bool = True
    result: dict[str, Any] = field(default_factory=dict)
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        normalize_product_api_operation(self.operation)
        normalize_product_api_request_type(self.resource_type)
        validate_string(self.resource_id, "Resource ID")

        if not isinstance(self.accepted, bool):
            raise ValueError("Accepted must be a boolean.")

        validate_metadata(self.result, "Result")
        validate_metadata(self.metadata, "Metadata")

    def to_dict(self) -> dict[str, Any]:
        """Convert operation result into dictionary."""
        return {
            "operation": normalize_product_api_operation(self.operation).value,
            "resource_type": normalize_product_api_request_type(self.resource_type).value,
            "resource_id": self.resource_id.strip(),
            "accepted": self.accepted,
            "result": dict(self.result),
            "metadata": dict(self.metadata),
        }


def validate_positive_integer(value: int, field_name: str) -> int:
    """Validate positive integer."""
    if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
        raise ValueError(f"{field_name} must be a positive integer.")

    return value


def validate_non_negative_integer(value: int, field_name: str) -> int:
    """Validate non-negative integer."""
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise ValueError(f"{field_name} must be a non-negative integer.")

    return value


def validate_field_name(field: str) -> str:
    """Validate product API field name."""
    normalized = validate_non_empty_string(field, "Field")

    if not normalized.replace("_", "").replace(".", "").isalnum():
        raise ValueError("Field must be alphanumeric and may include '_' or '.'.")

    return normalized


def validate_product_filters(filters: list[ProductApiFilter]) -> list[ProductApiFilter]:
    """Validate product API filters."""
    if not isinstance(filters, list):
        raise ValueError("Filters must be a list.")

    for item in filters:
        if not isinstance(item, ProductApiFilter):
            raise ValueError("Filters must contain ProductApiFilter objects.")

    return filters


def validate_product_sorts(sort: list[ProductApiSort]) -> list[ProductApiSort]:
    """Validate product API sorts."""
    if not isinstance(sort, list):
        raise ValueError("Sort must be a list.")

    for item in sort:
        if not isinstance(item, ProductApiSort):
            raise ValueError("Sort must contain ProductApiSort objects.")

    return sort


def validate_list_items(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Validate list result items."""
    if not isinstance(items, list):
        raise ValueError("Items must be a list.")

    for item in items:
        if not isinstance(item, dict):
            raise ValueError("Items must contain dictionaries.")

    return items


def normalize_product_api_request_type(
    request_type: ProductApiRequestType | str,
) -> ProductApiRequestType:
    """Normalize product API request type."""
    if isinstance(request_type, ProductApiRequestType):
        return request_type

    normalized = validate_non_empty_string(request_type, "Product API request type").lower()

    try:
        return ProductApiRequestType(normalized)
    except ValueError as exc:
        valid = ", ".join(item.value for item in ProductApiRequestType)
        raise ValueError(
            f"Invalid product API request type '{request_type}'. Valid request types: {valid}.",
        ) from exc


def normalize_product_api_operation(
    operation: ProductApiOperation | str,
) -> ProductApiOperation:
    """Normalize product API operation."""
    if isinstance(operation, ProductApiOperation):
        return operation

    normalized = validate_non_empty_string(operation, "Product API operation").lower()

    try:
        return ProductApiOperation(normalized)
    except ValueError as exc:
        valid = ", ".join(item.value for item in ProductApiOperation)
        raise ValueError(
            f"Invalid product API operation '{operation}'. Valid operations: {valid}.",
        ) from exc


def normalize_product_sort_direction(
    direction: ProductSortDirection | str,
) -> ProductSortDirection:
    """Normalize product API sort direction."""
    if isinstance(direction, ProductSortDirection):
        return direction

    normalized = validate_non_empty_string(direction, "Product sort direction").lower()

    try:
        return ProductSortDirection(normalized)
    except ValueError as exc:
        valid = ", ".join(item.value for item in ProductSortDirection)
        raise ValueError(
            f"Invalid product sort direction '{direction}'. Valid directions: {valid}.",
        ) from exc


def normalize_product_filter_operator(
    operator: ProductFilterOperator | str,
) -> ProductFilterOperator:
    """Normalize product API filter operator."""
    if isinstance(operator, ProductFilterOperator):
        return operator

    normalized = validate_non_empty_string(operator, "Product filter operator").lower()

    try:
        return ProductFilterOperator(normalized)
    except ValueError as exc:
        valid = ", ".join(item.value for item in ProductFilterOperator)
        raise ValueError(
            f"Invalid product filter operator '{operator}'. Valid operators: {valid}.",
        ) from exc


def build_product_api_pagination(
    *,
    page: int = 1,
    page_size: int = 20,
) -> ProductApiPagination:
    """Build product API pagination."""
    return ProductApiPagination(
        page=page,
        page_size=page_size,
    )


def build_product_api_sort(
    *,
    field: str,
    direction: ProductSortDirection | str = ProductSortDirection.ASC,
) -> ProductApiSort:
    """Build product API sort."""
    return ProductApiSort(
        field=field,
        direction=direction,
    )


def build_product_api_filter(
    *,
    field: str,
    operator: ProductFilterOperator | str,
    value: Any,
) -> ProductApiFilter:
    """Build product API filter."""
    return ProductApiFilter(
        field=field,
        operator=operator,
        value=value,
    )


def build_product_api_list_query(
    *,
    pagination: ProductApiPagination | None = None,
    filters: list[ProductApiFilter] | None = None,
    sort: list[ProductApiSort] | None = None,
    search: str = "",
    metadata: dict[str, Any] | None = None,
) -> ProductApiListQuery:
    """Build product API list query."""
    return ProductApiListQuery(
        pagination=pagination or ProductApiPagination(),
        filters=filters or [],
        sort=sort or [],
        search=search,
        metadata=metadata or {},
    )


def build_product_api_request(
    *,
    request_type: ProductApiRequestType | str,
    operation: ProductApiOperation | str,
    request_id: str,
    context: ProductApiRequestContext | None = None,
    payload: dict[str, Any] | None = None,
    query: ProductApiListQuery | None = None,
    metadata: dict[str, Any] | None = None,
) -> ProductApiRequest:
    """Build product API request."""
    return ProductApiRequest(
        request_type=request_type,
        operation=operation,
        context=context or build_product_api_context(request_id=request_id),
        payload=payload or {},
        query=query,
        metadata=metadata or {},
    )


def build_product_api_list_result(
    *,
    items: list[dict[str, Any]] | None = None,
    pagination: ProductApiPagination | None = None,
    total_items: int = 0,
    metadata: dict[str, Any] | None = None,
) -> ProductApiListResult:
    """Build product API list result."""
    return ProductApiListResult(
        items=items or [],
        pagination=pagination or ProductApiPagination(),
        total_items=total_items,
        metadata=metadata or {},
    )


def build_product_api_operation_result(
    *,
    operation: ProductApiOperation | str,
    resource_type: ProductApiRequestType | str,
    resource_id: str = "",
    accepted: bool = True,
    result: dict[str, Any] | None = None,
    metadata: dict[str, Any] | None = None,
) -> ProductApiOperationResult:
    """Build product API operation result."""
    return ProductApiOperationResult(
        operation=operation,
        resource_type=resource_type,
        resource_id=resource_id,
        accepted=accepted,
        result=result or {},
        metadata=metadata or {},
    )


def list_result_to_response(
    *,
    result: ProductApiListResult,
    context: ProductApiRequestContext | None = None,
    message: str = "List request completed.",
) -> ProductApiResponse:
    """Convert product API list result into response."""
    if not isinstance(result, ProductApiListResult):
        raise ValueError("Result must be a ProductApiListResult.")

    return product_api_success(
        data=result.to_dict(),
        message=message,
        context=context,
    )


def operation_result_to_response(
    *,
    result: ProductApiOperationResult,
    context: ProductApiRequestContext | None = None,
    message: str = "Operation completed.",
) -> ProductApiResponse:
    """Convert product API operation result into response."""
    if not isinstance(result, ProductApiOperationResult):
        raise ValueError("Result must be a ProductApiOperationResult.")

    return product_api_success(
        data=result.to_dict(),
        message=message,
        context=context,
    )


def empty_list_response(
    *,
    context: ProductApiRequestContext | None = None,
    message: str = "No records found.",
) -> ProductApiResponse:
    """Build empty list response."""
    return list_result_to_response(
        result=ProductApiListResult(),
        context=context,
        message=message,
    )