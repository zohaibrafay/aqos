"""
Unit tests for AQOS product portfolio API.
"""

import pytest

from aqos.product_api import (
    ProductApiListQuery,
    ProductApiPagination,
    ProductApiStatus,
    ProductPortfolioPosition,
    ProductPortfolioSnapshot,
    ProductPortfolioStore,
    ProductPortfolioSummary,
    ProductPositionSide,
    ProductPositionStatus,
    build_product_api_context,
    build_product_portfolio_position,
    build_product_portfolio_snapshot,
    build_product_portfolio_store,
    build_product_portfolio_summary,
    close_portfolio_position,
    create_portfolio_operation_response,
    filter_product_positions,
    get_portfolio_response,
    list_portfolios_response,
    normalize_product_position_side,
    normalize_product_position_status,
    paginate_product_portfolios,
    portfolio_snapshot_to_response,
    validate_currency,
    validate_positive_float,
    validate_product_portfolio_positions,
    validate_product_portfolio_snapshots,
)


def build_position(
    position_id: str = "position-1",
    side: str = "buy",
    status: str = "open",
) -> ProductPortfolioPosition:
    return build_product_portfolio_position(
        position_id=position_id,
        symbol="XAUUSD",
        side=side,
        quantity=2,
        entry_price=2000,
        current_price=2010 if side == "buy" else 1990,
        stop_loss=1990 if side == "buy" else 2010,
        take_profit=2020 if side == "buy" else 1980,
        status=status,
        opened_at="2026-01-01T00:00:00+00:00",
        metadata={
            "strategy": "trend",
        },
    )


def build_snapshot(account_id: str = "account-1") -> ProductPortfolioSnapshot:
    return build_product_portfolio_snapshot(
        account_id=account_id,
        balance=10000,
        equity=10020,
        positions=[
            build_position("position-1", "buy"),
            build_position("position-2", "sell"),
        ],
        currency="USD",
        margin_used=1000,
        timestamp="2026-01-01T00:00:00+00:00",
    )


def test_product_position_enum_values():
    assert ProductPositionSide.BUY.value == "buy"
    assert ProductPositionSide.SELL.value == "sell"
    assert ProductPositionStatus.OPEN.value == "open"
    assert ProductPositionStatus.CLOSED.value == "closed"


def test_position_normalizers_accept_enum_and_string():
    assert normalize_product_position_side(ProductPositionSide.BUY) == ProductPositionSide.BUY
    assert normalize_product_position_side(" BUY ") == ProductPositionSide.BUY
    assert normalize_product_position_status(ProductPositionStatus.OPEN) == ProductPositionStatus.OPEN
    assert normalize_product_position_status(" CLOSED ") == ProductPositionStatus.CLOSED


def test_position_normalizers_reject_invalid_values():
    with pytest.raises(ValueError):
        normalize_product_position_side("bad")

    with pytest.raises(ValueError):
        normalize_product_position_status("bad")


def test_validate_positive_float_and_currency():
    assert validate_positive_float(1, "Value") == 1.0
    assert validate_currency("usd") == "USD"

    with pytest.raises(ValueError):
        validate_positive_float(0, "Value")

    with pytest.raises(ValueError):
        validate_positive_float(True, "Value")

    with pytest.raises(ValueError):
        validate_currency("US")

    with pytest.raises(ValueError):
        validate_currency("US1")


def test_portfolio_position_to_dict_buy_and_sell():
    buy = build_position("position-1", "buy")
    sell = build_position("position-2", "sell")

    buy_payload = buy.to_dict()
    sell_payload = sell.to_dict()

    assert buy_payload["position_id"] == "position-1"
    assert buy_payload["symbol"] == "XAUUSD"
    assert buy_payload["side"] == "buy"
    assert buy_payload["market_price"] == 2010.0
    assert buy_payload["notional_value"] == 4020.0
    assert buy_payload["unrealized_pnl"] == 20.0
    assert buy_payload["open"] is True

    assert sell_payload["side"] == "sell"
    assert sell_payload["unrealized_pnl"] == 20.0


def test_portfolio_position_rejects_invalid_values():
    with pytest.raises(ValueError):
        ProductPortfolioPosition(
            position_id="",
            symbol="XAUUSD",
            side="buy",
            quantity=1,
            entry_price=2000,
        )

    with pytest.raises(ValueError):
        ProductPortfolioPosition(
            position_id="position-1",
            symbol="bad symbol",
            side="buy",
            quantity=1,
            entry_price=2000,
        )

    with pytest.raises(ValueError):
        ProductPortfolioPosition(
            position_id="position-1",
            symbol="XAUUSD",
            side="bad",
            quantity=1,
            entry_price=2000,
        )

    with pytest.raises(ValueError):
        ProductPortfolioPosition(
            position_id="position-1",
            symbol="XAUUSD",
            side="buy",
            quantity=0,
            entry_price=2000,
        )

    with pytest.raises(ValueError):
        ProductPortfolioPosition(
            position_id="position-1",
            symbol="XAUUSD",
            side="buy",
            quantity=1,
            entry_price=0,
        )

    with pytest.raises(ValueError):
        ProductPortfolioPosition(
            position_id="position-1",
            symbol="XAUUSD",
            side="buy",
            quantity=1,
            entry_price=2000,
            current_price=-1,
        )

    with pytest.raises(ValueError):
        ProductPortfolioPosition(
            position_id="position-1",
            symbol="XAUUSD",
            side="buy",
            quantity=1,
            entry_price=2000,
            status="bad",
        )

    with pytest.raises(ValueError):
        ProductPortfolioPosition(
            position_id="position-1",
            symbol="XAUUSD",
            side="buy",
            quantity=1,
            entry_price=2000,
            metadata=[],
        )


def test_build_product_portfolio_position():
    position = build_product_portfolio_position(
        position_id="position-1",
        symbol="xauusd",
        side="buy",
        quantity=1,
        entry_price=2000,
    )

    assert isinstance(position, ProductPortfolioPosition)
    assert position.symbol == "xauusd"
    assert position.market_price == 2000.0


def test_portfolio_snapshot_to_dict():
    snapshot = build_snapshot()

    payload = snapshot.to_dict()

    assert payload["account_id"] == "account-1"
    assert payload["balance"] == 10000.0
    assert payload["equity"] == 10020.0
    assert payload["currency"] == "USD"
    assert payload["margin_used"] == 1000.0
    assert payload["free_margin"] == 9020.0
    assert payload["total_exposure"] == 8000.0
    assert payload["unrealized_pnl"] == 40.0
    assert payload["open_positions"] == 2


def test_portfolio_snapshot_rejects_invalid_values():
    position = build_position()

    with pytest.raises(ValueError):
        ProductPortfolioSnapshot(account_id="", balance=100, equity=100)

    with pytest.raises(ValueError):
        ProductPortfolioSnapshot(account_id="account-1", balance=-1, equity=100)

    with pytest.raises(ValueError):
        ProductPortfolioSnapshot(account_id="account-1", balance=100, equity=-1)

    with pytest.raises(ValueError):
        ProductPortfolioSnapshot(account_id="account-1", balance=100, equity=100, positions=["bad"])

    with pytest.raises(ValueError):
        ProductPortfolioSnapshot(account_id="account-1", balance=100, equity=100, currency="BAD1")

    with pytest.raises(ValueError):
        ProductPortfolioSnapshot(account_id="account-1", balance=100, equity=100, margin_used=-1)

    with pytest.raises(ValueError):
        ProductPortfolioSnapshot(account_id="account-1", balance=100, equity=100, metadata=[])

    with pytest.raises(ValueError):
        ProductPortfolioSnapshot(
            account_id="account-1",
            balance=100,
            equity=100,
            positions=[position],
            timestamp="",
        )


def test_build_product_portfolio_snapshot():
    snapshot = build_product_portfolio_snapshot(
        account_id="account-1",
        balance=1000,
        equity=1000,
        timestamp="2026-01-01T00:00:00+00:00",
    )

    assert isinstance(snapshot, ProductPortfolioSnapshot)
    assert snapshot.account_id == "account-1"


def test_portfolio_summary():
    snapshot = build_snapshot()
    summary = build_product_portfolio_summary(
        snapshot=snapshot,
        metadata={
            "source": "test",
        },
    )

    assert isinstance(summary, ProductPortfolioSummary)
    assert summary.to_dict() == {
        "total_positions": 2,
        "open_positions": 2,
        "closed_positions": 0,
        "buy_positions": 1,
        "sell_positions": 1,
        "total_exposure": 8000.0,
        "unrealized_pnl": 40.0,
        "metadata": {
            "source": "test",
        },
    }


def test_portfolio_summary_rejects_invalid_values():
    with pytest.raises(ValueError):
        build_product_portfolio_summary(snapshot="bad")

    with pytest.raises(ValueError):
        ProductPortfolioSummary(total_positions=-1)

    with pytest.raises(ValueError):
        ProductPortfolioSummary(unrealized_pnl="bad")

    with pytest.raises(ValueError):
        ProductPortfolioSummary(metadata=[])


def test_validate_portfolio_lists():
    position = build_position()
    snapshot = build_snapshot()

    assert validate_product_portfolio_positions([position]) == [position]
    assert validate_product_portfolio_snapshots([snapshot]) == [snapshot]

    with pytest.raises(ValueError):
        validate_product_portfolio_positions("bad")

    with pytest.raises(ValueError):
        validate_product_portfolio_positions(["bad"])

    with pytest.raises(ValueError):
        validate_product_portfolio_snapshots("bad")

    with pytest.raises(ValueError):
        validate_product_portfolio_snapshots(["bad"])


def test_portfolio_store():
    snapshot = build_snapshot()
    store = build_product_portfolio_store()

    assert isinstance(store, ProductPortfolioStore)
    assert store.count() == 0

    store.add(snapshot)

    assert store.count() == 1
    assert store.get("account-1") == snapshot
    assert store.list() == [snapshot]
    assert store.remove("account-1") == snapshot
    assert store.count() == 0

    store.add(snapshot)
    store.clear()

    assert store.count() == 0


def test_portfolio_store_rejects_invalid_values():
    snapshot = build_snapshot()

    with pytest.raises(ValueError):
        ProductPortfolioStore(snapshots=[])

    with pytest.raises(ValueError):
        ProductPortfolioStore(snapshots={"account-1": "bad"})

    store = build_product_portfolio_store()

    with pytest.raises(ValueError):
        store.add("bad")

    with pytest.raises(ValueError):
        store.get("")

    with pytest.raises(ValueError):
        store.remove("")


def test_portfolio_snapshot_to_response():
    context = build_product_api_context(request_id="req-1")
    snapshot = build_snapshot()

    response = portfolio_snapshot_to_response(
        snapshot=snapshot,
        context=context,
    )

    assert response.status == ProductApiStatus.SUCCESS
    assert response.data["portfolio"]["account_id"] == "account-1"
    assert response.data["summary"]["open_positions"] == 2
    assert response.meta is not None
    assert response.meta.request_id == "req-1"

    with pytest.raises(ValueError):
        portfolio_snapshot_to_response(snapshot="bad")


def test_list_portfolios_response_and_pagination():
    context = build_product_api_context(request_id="req-1")
    snapshots = [
        build_snapshot("account-1"),
        build_snapshot("account-2"),
    ]
    query = ProductApiListQuery(
        pagination=ProductApiPagination(page=1, page_size=1),
    )

    response = list_portfolios_response(
        snapshots=snapshots,
        query=query,
        context=context,
    )

    assert response.status == ProductApiStatus.SUCCESS
    assert len(response.data["items"]) == 1
    assert response.data["total_items"] == 2
    assert response.data["metadata"]["accounts"] == ["account-1", "account-2"]


def test_create_portfolio_operation_response():
    response = create_portfolio_operation_response(
        snapshot=build_snapshot(),
        context=build_product_api_context(request_id="req-1"),
    )

    assert response.status == ProductApiStatus.SUCCESS
    assert response.data["operation"] == "create"
    assert response.data["resource_type"] == "portfolio"
    assert response.data["resource_id"] == "account-1"

    with pytest.raises(ValueError):
        create_portfolio_operation_response(snapshot="bad")


def test_get_portfolio_response():
    snapshot = build_snapshot()
    store = build_product_portfolio_store()
    store.add(snapshot)

    found = get_portfolio_response(
        store=store,
        account_id="account-1",
    )

    missing = get_portfolio_response(
        store=store,
        account_id="missing",
    )

    assert found.status == ProductApiStatus.SUCCESS
    assert found.data["portfolio"]["account_id"] == "account-1"
    assert missing.status == ProductApiStatus.FAILURE
    assert missing.error is not None
    assert missing.error.code == "not_found"

    with pytest.raises(ValueError):
        get_portfolio_response(
            store="bad",
            account_id="account-1",
        )


def test_close_portfolio_position():
    position = build_position()

    closed = close_portfolio_position(
        position,
        closed_at="2026-01-01T01:00:00+00:00",
        metadata={
            "reason": "manual",
        },
    )

    assert closed.status == ProductPositionStatus.CLOSED
    assert closed.closed is True
    assert closed.closed_at == "2026-01-01T01:00:00+00:00"
    assert closed.metadata["reason"] == "manual"

    with pytest.raises(ValueError):
        close_portfolio_position("bad")


def test_paginate_portfolios_and_filter_positions():
    snapshots = [
        build_snapshot("account-1"),
        build_snapshot("account-2"),
        build_snapshot("account-3"),
    ]

    paged = paginate_product_portfolios(
        snapshots=snapshots,
        pagination=ProductApiPagination(page=2, page_size=1),
    )

    assert [snapshot.account_id for snapshot in paged] == ["account-2"]

    positions = build_snapshot().positions

    buy_positions = filter_product_positions(
        positions=positions,
        side="buy",
    )

    assert len(buy_positions) == 1
    assert buy_positions[0].side == "buy"

    xau_positions = filter_product_positions(
        positions=positions,
        symbol="xauusd",
        status="open",
    )

    assert len(xau_positions) == 2

    with pytest.raises(ValueError):
        paginate_product_portfolios(
            snapshots=snapshots,
            pagination="bad",
        )


def test_product_portfolio_exports_exist():
    import aqos.product_api as product_api

    expected_exports = [
        "ProductPortfolioPosition",
        "ProductPortfolioSnapshot",
        "ProductPortfolioStore",
        "ProductPortfolioSummary",
        "ProductPositionSide",
        "ProductPositionStatus",
        "build_product_portfolio_position",
        "build_product_portfolio_snapshot",
        "build_product_portfolio_store",
        "build_product_portfolio_summary",
        "close_portfolio_position",
        "create_portfolio_operation_response",
        "filter_product_positions",
        "get_portfolio_response",
        "list_portfolios_response",
        "normalize_product_position_side",
        "normalize_product_position_status",
        "paginate_product_portfolios",
        "portfolio_snapshot_to_response",
        "validate_currency",
        "validate_positive_float",
        "validate_product_portfolio_positions",
        "validate_product_portfolio_snapshots",
    ]

    for export_name in expected_exports:
        assert hasattr(product_api, export_name), export_name