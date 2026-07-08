"""
Unit tests for AQOS product API contracts.
"""

import pytest

from aqos.product_api import (
    ProductApiFilter,
    ProductApiListQuery,
    ProductApiListResult,
    ProductApiOperation,
    ProductApiOperationResult,
    ProductApiPagination,
    ProductApiRequest,
    ProductApiRequestContext,
    ProductApiRequestType,
    ProductApiResponse,
    ProductApiSort,
    ProductApiStatus,
    ProductFilterOperator,
    ProductSortDirection,
    build_product_api_context,
    build_product_api_filter,
    build_product_api_list_query,
    build_product_api_list_result,
    build_product_api_operation_result,
    build_product_api_pagination,
    build_product_api_request,
    build_product_api_sort,
    empty_list_response,
    list_result_to_response,
    normalize_product_api_operation,
    normalize_product_api_request_type,
    normalize_product_filter_operator,
    normalize_product_sort_direction,
    operation_result_to_response,
    validate_field_name,
    validate_list_items,
    validate_non_negative_integer,
    validate_positive_integer,
    validate_product_filters,
    validate_product_sorts,
)


def test_product_api_request_type_values():
    assert ProductApiRequestType.SIGNAL.value == "signal"
    assert ProductApiRequestType.PORTFOLIO.value == "portfolio"
    assert ProductApiRequestType.RESEARCH.value == "research"
    assert ProductApiRequestType.ANALYTICS.value == "analytics"
    assert ProductApiRequestType.WORKFLOW.value == "workflow"


def test_product_api_operation_values():
    assert ProductApiOperation.LIST.value == "list"
    assert ProductApiOperation.GET.value == "get"
    assert ProductApiOperation.CREATE.value == "create"
    assert ProductApiOperation.UPDATE.value == "update"
    assert ProductApiOperation.DELETE.value == "delete"
    assert ProductApiOperation.EXECUTE.value == "execute"


def test_product_sort_direction_values():
    assert ProductSortDirection.ASC.value == "asc"
    assert ProductSortDirection.DESC.value == "desc"


def test_product_filter_operator_values():
    assert ProductFilterOperator.EQ.value == "eq"
    assert ProductFilterOperator.NE.value == "ne"
    assert ProductFilterOperator.GT.value == "gt"
    assert ProductFilterOperator.GTE.value == "gte"
    assert ProductFilterOperator.LT.value == "lt"
    assert ProductFilterOperator.LTE.value == "lte"
    assert ProductFilterOperator.IN.value == "in"
    assert ProductFilterOperator.CONTAINS.value == "contains"


def test_normalizers_accept_enum_and_string():
    assert normalize_product_api_request_type(ProductApiRequestType.SIGNAL) == ProductApiRequestType.SIGNAL
    assert normalize_product_api_request_type(" SIGNAL ") == ProductApiRequestType.SIGNAL
    assert normalize_product_api_operation(ProductApiOperation.LIST) == ProductApiOperation.LIST
    assert normalize_product_api_operation(" EXECUTE ") == ProductApiOperation.EXECUTE
    assert normalize_product_sort_direction(ProductSortDirection.ASC) == ProductSortDirection.ASC
    assert normalize_product_sort_direction(" DESC ") == ProductSortDirection.DESC
    assert normalize_product_filter_operator(ProductFilterOperator.EQ) == ProductFilterOperator.EQ
    assert normalize_product_filter_operator(" CONTAINS ") == ProductFilterOperator.CONTAINS


def test_normalizers_reject_invalid_values():
    with pytest.raises(ValueError):
        normalize_product_api_request_type("bad")

    with pytest.raises(ValueError):
        normalize_product_api_operation("bad")

    with pytest.raises(ValueError):
        normalize_product_sort_direction("bad")

    with pytest.raises(ValueError):
        normalize_product_filter_operator("bad")


def test_integer_validators():
    assert validate_positive_integer(1, "Value") == 1
    assert validate_non_negative_integer(0, "Value") == 0

    with pytest.raises(ValueError):
        validate_positive_integer(0, "Value")

    with pytest.raises(ValueError):
        validate_positive_integer(True, "Value")

    with pytest.raises(ValueError):
        validate_non_negative_integer(-1, "Value")

    with pytest.raises(ValueError):
        validate_non_negative_integer(True, "Value")


def test_validate_field_name():
    assert validate_field_name("symbol") == "symbol"
    assert validate_field_name("market.symbol") == "market.symbol"
    assert validate_field_name("created_at") == "created_at"

    with pytest.raises(ValueError):
        validate_field_name("")

    with pytest.raises(ValueError):
        validate_field_name("bad field")

    with pytest.raises(ValueError):
        validate_field_name("bad-field")


def test_product_api_pagination_to_dict():
    pagination = ProductApiPagination(
        page=2,
        page_size=10,
    )

    assert pagination.offset == 10
    assert pagination.total_pages(95) == 10

    assert pagination.to_dict(total_items=95) == {
        "page": 2,
        "page_size": 10,
        "offset": 10,
        "total_items": 95,
        "total_pages": 10,
        "has_next": True,
        "has_previous": True,
    }


def test_product_api_pagination_rejects_invalid_values():
    with pytest.raises(ValueError):
        ProductApiPagination(page=0)

    with pytest.raises(ValueError):
        ProductApiPagination(page=True)

    with pytest.raises(ValueError):
        ProductApiPagination(page_size=0)

    with pytest.raises(ValueError):
        ProductApiPagination(page_size=501)

    with pytest.raises(ValueError):
        ProductApiPagination().total_pages(-1)


def test_build_product_api_pagination():
    pagination = build_product_api_pagination(
        page=3,
        page_size=50,
    )

    assert isinstance(pagination, ProductApiPagination)
    assert pagination.offset == 100


def test_product_api_sort_to_dict():
    sort = ProductApiSort(
        field=" created_at ",
        direction="DESC",
    )

    assert sort.to_dict() == {
        "field": "created_at",
        "direction": "desc",
    }


def test_product_api_sort_rejects_invalid_values():
    with pytest.raises(ValueError):
        ProductApiSort(field="", direction="asc")

    with pytest.raises(ValueError):
        ProductApiSort(field="created-at", direction="asc")

    with pytest.raises(ValueError):
        ProductApiSort(field="created_at", direction="bad")


def test_build_product_api_sort():
    sort = build_product_api_sort(
        field="confidence",
        direction="desc",
    )

    assert isinstance(sort, ProductApiSort)
    assert sort.direction == "desc"


def test_product_api_filter_to_dict():
    item = ProductApiFilter(
        field="symbol",
        operator="EQ",
        value="XAUUSD",
    )

    assert item.to_dict() == {
        "field": "symbol",
        "operator": "eq",
        "value": "XAUUSD",
    }


def test_product_api_filter_rejects_invalid_values():
    with pytest.raises(ValueError):
        ProductApiFilter(field="", operator="eq", value="XAUUSD")

    with pytest.raises(ValueError):
        ProductApiFilter(field="symbol", operator="bad", value="XAUUSD")

    with pytest.raises(ValueError):
        ProductApiFilter(field="symbol", operator="in", value="XAUUSD")

    with pytest.raises(ValueError):
        ProductApiFilter(field="symbol", operator="contains", value=["XAUUSD"])


def test_build_product_api_filter():
    item = build_product_api_filter(
        field="symbol",
        operator="in",
        value=["XAUUSD", "BTCUSDT"],
    )

    assert isinstance(item, ProductApiFilter)
    assert item.value == ["XAUUSD", "BTCUSDT"]


def test_validate_filter_sort_and_item_lists():
    filter_item = build_product_api_filter(
        field="symbol",
        operator="eq",
        value="XAUUSD",
    )
    sort_item = build_product_api_sort(
        field="created_at",
    )

    assert validate_product_filters([filter_item]) == [filter_item]
    assert validate_product_sorts([sort_item]) == [sort_item]
    assert validate_list_items([{"id": "1"}]) == [{"id": "1"}]

    with pytest.raises(ValueError):
        validate_product_filters("bad")

    with pytest.raises(ValueError):
        validate_product_filters(["bad"])

    with pytest.raises(ValueError):
        validate_product_sorts("bad")

    with pytest.raises(ValueError):
        validate_product_sorts(["bad"])

    with pytest.raises(ValueError):
        validate_list_items("bad")

    with pytest.raises(ValueError):
        validate_list_items(["bad"])


def test_product_api_list_query_to_dict():
    pagination = build_product_api_pagination(page=1, page_size=25)
    filter_item = build_product_api_filter(
        field="symbol",
        operator="eq",
        value="XAUUSD",
    )
    sort_item = build_product_api_sort(
        field="created_at",
        direction="desc",
    )

    query = ProductApiListQuery(
        pagination=pagination,
        filters=[filter_item],
        sort=[sort_item],
        search=" gold ",
        metadata={
            "source": "test",
        },
    )

    payload = query.to_dict()

    assert payload["pagination"]["page_size"] == 25
    assert payload["filters"] == [filter_item.to_dict()]
    assert payload["sort"] == [sort_item.to_dict()]
    assert payload["search"] == "gold"
    assert payload["metadata"] == {
        "source": "test",
    }


def test_product_api_list_query_rejects_invalid_values():
    with pytest.raises(ValueError):
        ProductApiListQuery(pagination="bad")

    with pytest.raises(ValueError):
        ProductApiListQuery(filters=["bad"])

    with pytest.raises(ValueError):
        ProductApiListQuery(sort=["bad"])

    with pytest.raises(ValueError):
        ProductApiListQuery(search=123)

    with pytest.raises(ValueError):
        ProductApiListQuery(metadata=[])


def test_build_product_api_list_query():
    query = build_product_api_list_query(
        search="signal",
        metadata={
            "source": "test",
        },
    )

    assert isinstance(query, ProductApiListQuery)
    assert query.search == "signal"
    assert query.metadata == {
        "source": "test",
    }


def test_product_api_request_to_dict():
    context = build_product_api_context(
        request_id="req-1",
        user_id="user-1",
    )
    query = build_product_api_list_query(search="xau")

    request = ProductApiRequest(
        request_type="SIGNAL",
        operation="LIST",
        context=context,
        payload={
            "symbol": "XAUUSD",
        },
        query=query,
        metadata={
            "source": "test",
        },
    )

    payload = request.to_dict()

    assert request.is_list is True
    assert request.is_execute is False
    assert payload["request_type"] == "signal"
    assert payload["operation"] == "list"
    assert payload["context"]["request_id"] == "req-1"
    assert payload["payload"] == {
        "symbol": "XAUUSD",
    }
    assert payload["query"] == query.to_dict()


def test_product_api_request_rejects_invalid_values():
    context = build_product_api_context(request_id="req-1")

    with pytest.raises(ValueError):
        ProductApiRequest(
            request_type="bad",
            operation="list",
            context=context,
        )

    with pytest.raises(ValueError):
        ProductApiRequest(
            request_type="signal",
            operation="bad",
            context=context,
        )

    with pytest.raises(ValueError):
        ProductApiRequest(
            request_type="signal",
            operation="list",
            context="bad",
        )

    with pytest.raises(ValueError):
        ProductApiRequest(
            request_type="signal",
            operation="list",
            context=context,
            payload=[],
        )

    with pytest.raises(ValueError):
        ProductApiRequest(
            request_type="signal",
            operation="list",
            context=context,
            query="bad",
        )

    with pytest.raises(ValueError):
        ProductApiRequest(
            request_type="signal",
            operation="list",
            context=context,
            metadata=[],
        )


def test_build_product_api_request():
    request = build_product_api_request(
        request_type="signal",
        operation="execute",
        request_id="req-1",
        payload={
            "symbol": "XAUUSD",
        },
    )

    assert isinstance(request, ProductApiRequest)
    assert request.is_execute is True
    assert request.context.request_id == "req-1"


def test_product_api_list_result_to_dict():
    pagination = build_product_api_pagination(page=1, page_size=10)
    result = ProductApiListResult(
        items=[
            {
                "id": "signal-1",
            },
        ],
        pagination=pagination,
        total_items=1,
        metadata={
            "source": "test",
        },
    )

    payload = result.to_dict()

    assert payload["items"] == [{"id": "signal-1"}]
    assert payload["pagination"]["total_items"] == 1
    assert payload["pagination"]["total_pages"] == 1
    assert payload["metadata"] == {
        "source": "test",
    }


def test_product_api_list_result_rejects_invalid_values():
    with pytest.raises(ValueError):
        ProductApiListResult(items=["bad"])

    with pytest.raises(ValueError):
        ProductApiListResult(pagination="bad")

    with pytest.raises(ValueError):
        ProductApiListResult(total_items=-1)

    with pytest.raises(ValueError):
        ProductApiListResult(metadata=[])


def test_build_product_api_list_result():
    result = build_product_api_list_result(
        items=[
            {
                "id": "1",
            },
        ],
        total_items=1,
    )

    assert isinstance(result, ProductApiListResult)
    assert result.total_items == 1


def test_product_api_operation_result_to_dict():
    result = ProductApiOperationResult(
        operation="EXECUTE",
        resource_type="SIGNAL",
        resource_id=" signal-1 ",
        accepted=True,
        result={
            "status": "queued",
        },
        metadata={
            "source": "test",
        },
    )

    assert result.to_dict() == {
        "operation": "execute",
        "resource_type": "signal",
        "resource_id": "signal-1",
        "accepted": True,
        "result": {
            "status": "queued",
        },
        "metadata": {
            "source": "test",
        },
    }


def test_product_api_operation_result_rejects_invalid_values():
    with pytest.raises(ValueError):
        ProductApiOperationResult(operation="bad", resource_type="signal")

    with pytest.raises(ValueError):
        ProductApiOperationResult(operation="execute", resource_type="bad")

    with pytest.raises(ValueError):
        ProductApiOperationResult(operation="execute", resource_type="signal", resource_id=123)

    with pytest.raises(ValueError):
        ProductApiOperationResult(operation="execute", resource_type="signal", accepted="yes")

    with pytest.raises(ValueError):
        ProductApiOperationResult(operation="execute", resource_type="signal", result=[])

    with pytest.raises(ValueError):
        ProductApiOperationResult(operation="execute", resource_type="signal", metadata=[])


def test_build_product_api_operation_result():
    result = build_product_api_operation_result(
        operation="execute",
        resource_type="signal",
        resource_id="signal-1",
        result={
            "queued": True,
        },
    )

    assert isinstance(result, ProductApiOperationResult)
    assert result.accepted is True
    assert result.result == {
        "queued": True,
    }


def test_list_result_to_response():
    context = build_product_api_context(request_id="req-1")
    result = build_product_api_list_result(
        items=[
            {
                "id": "1",
            },
        ],
        total_items=1,
    )

    response = list_result_to_response(
        result=result,
        context=context,
    )

    assert isinstance(response, ProductApiResponse)
    assert response.status == ProductApiStatus.SUCCESS
    assert response.data["total_items"] == 1
    assert response.meta is not None
    assert response.meta.request_id == "req-1"

    with pytest.raises(ValueError):
        list_result_to_response(result="bad")


def test_operation_result_to_response():
    context = build_product_api_context(request_id="req-1")
    result = build_product_api_operation_result(
        operation="execute",
        resource_type="signal",
        resource_id="signal-1",
    )

    response = operation_result_to_response(
        result=result,
        context=context,
    )

    assert response.status == ProductApiStatus.SUCCESS
    assert response.data["resource_id"] == "signal-1"
    assert response.meta is not None

    with pytest.raises(ValueError):
        operation_result_to_response(result="bad")


def test_empty_list_response():
    response = empty_list_response(
        context=build_product_api_context(request_id="req-1"),
    )

    assert response.status == ProductApiStatus.SUCCESS
    assert response.data["items"] == []
    assert response.data["total_items"] == 0


def test_product_api_contract_exports_exist():
    import aqos.product_api as product_api

    expected_exports = [
        "ProductApiFilter",
        "ProductApiListQuery",
        "ProductApiListResult",
        "ProductApiOperation",
        "ProductApiOperationResult",
        "ProductApiPagination",
        "ProductApiRequest",
        "ProductApiRequestType",
        "ProductApiSort",
        "ProductFilterOperator",
        "ProductSortDirection",
        "build_product_api_filter",
        "build_product_api_list_query",
        "build_product_api_list_result",
        "build_product_api_operation_result",
        "build_product_api_pagination",
        "build_product_api_request",
        "build_product_api_sort",
        "empty_list_response",
        "list_result_to_response",
        "normalize_product_api_operation",
        "normalize_product_api_request_type",
        "normalize_product_filter_operator",
        "normalize_product_sort_direction",
        "operation_result_to_response",
        "validate_field_name",
        "validate_list_items",
        "validate_non_negative_integer",
        "validate_positive_integer",
        "validate_product_filters",
        "validate_product_sorts",
    ]

    for export_name in expected_exports:
        assert hasattr(product_api, export_name), export_name