"""
Unit tests for AQOS product signal API.
"""

import pytest

from aqos.product_api import (
    ProductApiListQuery,
    ProductApiPagination,
    ProductApiStatus,
    ProductSignalDirection,
    ProductSignalPayload,
    ProductSignalRequest,
    ProductSignalStatus,
    ProductSignalStore,
    ProductSignalStrength,
    ProductSignalSummary,
    approve_signal_response,
    build_product_api_context,
    build_product_signal_payload,
    build_product_signal_request,
    build_product_signal_store,
    build_product_signal_summary,
    calculate_signal_risk_reward_ratio,
    create_signal_operation_response,
    filter_product_signals,
    get_signal_response,
    list_signals_response,
    normalize_product_signal_direction,
    normalize_product_signal_status,
    normalize_product_signal_strength,
    paginate_product_signals,
    reject_signal_response,
    resolve_signal_strength,
    signal_payload_to_response,
    update_signal_status,
    validate_product_signal_payloads,
    validate_signal_price,
)


def build_signal(
    signal_id: str = "signal-1",
    direction: str = "buy",
    confidence: float = 82.0,
    status: str = "generated",
) -> ProductSignalPayload:
    return build_product_signal_payload(
        signal_id=signal_id,
        symbol="XAUUSD",
        timeframe="H1",
        direction=direction,
        confidence=confidence,
        status=status,
        entry_price=2000,
        stop_loss=1990 if direction != "sell" else 2010,
        take_profit=2020 if direction != "sell" else 1980,
        explanation="Momentum setup.",
        features={
            "trend": "up",
        },
        created_at="2026-01-01T00:00:00+00:00",
    )


def test_product_signal_enum_values():
    assert ProductSignalDirection.BUY.value == "buy"
    assert ProductSignalDirection.SELL.value == "sell"
    assert ProductSignalDirection.HOLD.value == "hold"

    assert ProductSignalStrength.WEAK.value == "weak"
    assert ProductSignalStrength.MODERATE.value == "moderate"
    assert ProductSignalStrength.STRONG.value == "strong"

    assert ProductSignalStatus.GENERATED.value == "generated"
    assert ProductSignalStatus.APPROVED.value == "approved"
    assert ProductSignalStatus.REJECTED.value == "rejected"
    assert ProductSignalStatus.EXPIRED.value == "expired"


def test_signal_normalizers_accept_enum_and_string():
    assert normalize_product_signal_direction(ProductSignalDirection.BUY) == ProductSignalDirection.BUY
    assert normalize_product_signal_direction(" BUY ") == ProductSignalDirection.BUY
    assert normalize_product_signal_strength(ProductSignalStrength.STRONG) == ProductSignalStrength.STRONG
    assert normalize_product_signal_strength(" MODERATE ") == ProductSignalStrength.MODERATE
    assert normalize_product_signal_status(ProductSignalStatus.GENERATED) == ProductSignalStatus.GENERATED
    assert normalize_product_signal_status(" APPROVED ") == ProductSignalStatus.APPROVED


def test_signal_normalizers_reject_invalid_values():
    with pytest.raises(ValueError):
        normalize_product_signal_direction("bad")

    with pytest.raises(ValueError):
        normalize_product_signal_strength("bad")

    with pytest.raises(ValueError):
        normalize_product_signal_status("bad")


def test_validate_signal_price():
    assert validate_signal_price(0, "Price") == 0.0
    assert validate_signal_price(10.5, "Price") == 10.5

    with pytest.raises(ValueError):
        validate_signal_price(-1, "Price")


def test_resolve_signal_strength():
    assert resolve_signal_strength(80) == ProductSignalStrength.STRONG
    assert resolve_signal_strength(55) == ProductSignalStrength.MODERATE
    assert resolve_signal_strength(30) == ProductSignalStrength.WEAK


def test_calculate_signal_risk_reward_ratio():
    assert calculate_signal_risk_reward_ratio(
        direction="buy",
        entry_price=100,
        stop_loss=90,
        take_profit=120,
    ) == 2.0

    assert calculate_signal_risk_reward_ratio(
        direction="sell",
        entry_price=100,
        stop_loss=110,
        take_profit=80,
    ) == 2.0

    assert calculate_signal_risk_reward_ratio(
        direction="hold",
        entry_price=100,
        stop_loss=90,
        take_profit=120,
    ) == 0.0

    assert calculate_signal_risk_reward_ratio(
        direction="buy",
        entry_price=100,
        stop_loss=110,
        take_profit=120,
    ) == 0.0


def test_product_signal_request_to_dict():
    request = ProductSignalRequest(
        symbol=" xauusd ",
        timeframe=" h1 ",
        entry_price=2000,
        risk_profile=" balanced ",
        include_explanation=True,
        metadata={
            "source": "test",
        },
    )

    assert request.to_dict() == {
        "symbol": "XAUUSD",
        "timeframe": "H1",
        "entry_price": 2000.0,
        "risk_profile": "balanced",
        "include_explanation": True,
        "metadata": {
            "source": "test",
        },
    }


def test_product_signal_request_rejects_invalid_values():
    with pytest.raises(ValueError):
        ProductSignalRequest(symbol="", timeframe="H1")

    with pytest.raises(ValueError):
        ProductSignalRequest(symbol="XAUUSD", timeframe="H2")

    with pytest.raises(ValueError):
        ProductSignalRequest(symbol="XAUUSD", timeframe="H1", entry_price=-1)

    with pytest.raises(ValueError):
        ProductSignalRequest(symbol="XAUUSD", timeframe="H1", risk_profile="")

    with pytest.raises(ValueError):
        ProductSignalRequest(symbol="XAUUSD", timeframe="H1", include_explanation="yes")

    with pytest.raises(ValueError):
        ProductSignalRequest(symbol="XAUUSD", timeframe="H1", metadata=[])


def test_build_product_signal_request():
    request = build_product_signal_request(
        symbol="xauusd",
        timeframe="h1",
        entry_price=2000,
    )

    assert isinstance(request, ProductSignalRequest)
    assert request.to_dict()["symbol"] == "XAUUSD"


def test_product_signal_payload_to_dict():
    signal = build_signal()

    payload = signal.to_dict()

    assert payload["signal_id"] == "signal-1"
    assert payload["symbol"] == "XAUUSD"
    assert payload["timeframe"] == "H1"
    assert payload["direction"] == "buy"
    assert payload["confidence"] == 82.0
    assert payload["strength"] == "strong"
    assert payload["status"] == "generated"
    assert payload["risk_reward_ratio"] == 2.0
    assert payload["actionable"] is True
    assert payload["approved"] is False


def test_product_signal_payload_rejects_invalid_values():
    with pytest.raises(ValueError):
        ProductSignalPayload(
            signal_id="",
            symbol="XAUUSD",
            timeframe="H1",
            direction="buy",
            confidence=80,
            strength="strong",
        )

    with pytest.raises(ValueError):
        ProductSignalPayload(
            signal_id="signal-1",
            symbol="bad symbol",
            timeframe="H1",
            direction="buy",
            confidence=80,
            strength="strong",
        )

    with pytest.raises(ValueError):
        ProductSignalPayload(
            signal_id="signal-1",
            symbol="XAUUSD",
            timeframe="H2",
            direction="buy",
            confidence=80,
            strength="strong",
        )

    with pytest.raises(ValueError):
        ProductSignalPayload(
            signal_id="signal-1",
            symbol="XAUUSD",
            timeframe="H1",
            direction="bad",
            confidence=80,
            strength="strong",
        )

    with pytest.raises(ValueError):
        ProductSignalPayload(
            signal_id="signal-1",
            symbol="XAUUSD",
            timeframe="H1",
            direction="buy",
            confidence=101,
            strength="strong",
        )

    with pytest.raises(ValueError):
        ProductSignalPayload(
            signal_id="signal-1",
            symbol="XAUUSD",
            timeframe="H1",
            direction="buy",
            confidence=80,
            strength="bad",
        )

    with pytest.raises(ValueError):
        ProductSignalPayload(
            signal_id="signal-1",
            symbol="XAUUSD",
            timeframe="H1",
            direction="buy",
            confidence=80,
            strength="strong",
            status="bad",
        )

    with pytest.raises(ValueError):
        ProductSignalPayload(
            signal_id="signal-1",
            symbol="XAUUSD",
            timeframe="H1",
            direction="buy",
            confidence=80,
            strength="strong",
            features=[],
        )


def test_product_signal_summary():
    signals = [
        build_signal("signal-1", "buy", 80),
        build_signal("signal-2", "sell", 60),
        build_signal("signal-3", "hold", 40),
    ]

    summary = build_product_signal_summary(
        signals=signals,
        metadata={
            "source": "test",
        },
    )

    assert isinstance(summary, ProductSignalSummary)
    assert summary.to_dict() == {
        "total": 3,
        "buy": 1,
        "sell": 1,
        "hold": 1,
        "average_confidence": 60.0,
        "metadata": {
            "source": "test",
        },
    }


def test_product_signal_summary_rejects_invalid_values():
    with pytest.raises(ValueError):
        ProductSignalSummary(total=-1)

    with pytest.raises(ValueError):
        ProductSignalSummary(total=1, average_confidence=101)

    with pytest.raises(ValueError):
        ProductSignalSummary(metadata=[])


def test_validate_product_signal_payloads():
    signal = build_signal()

    assert validate_product_signal_payloads([signal]) == [signal]

    with pytest.raises(ValueError):
        validate_product_signal_payloads("bad")

    with pytest.raises(ValueError):
        validate_product_signal_payloads(["bad"])


def test_product_signal_store():
    signal = build_signal()
    store = build_product_signal_store()

    assert isinstance(store, ProductSignalStore)
    assert store.count() == 0

    store.add(signal)

    assert store.count() == 1
    assert store.get("signal-1") == signal
    assert store.list() == [signal]
    assert store.remove("signal-1") == signal
    assert store.count() == 0

    store.add(signal)
    store.clear()

    assert store.count() == 0


def test_product_signal_store_rejects_invalid_values():
    signal = build_signal()

    with pytest.raises(ValueError):
        ProductSignalStore(signals=[])

    with pytest.raises(ValueError):
        ProductSignalStore(signals={"signal-1": "bad"})

    store = build_product_signal_store()

    with pytest.raises(ValueError):
        store.add("bad")

    with pytest.raises(ValueError):
        store.get("")

    with pytest.raises(ValueError):
        store.remove("")


def test_signal_payload_to_response():
    context = build_product_api_context(request_id="req-1")
    signal = build_signal()

    response = signal_payload_to_response(
        signal=signal,
        context=context,
    )

    assert response.status == ProductApiStatus.SUCCESS
    assert response.data["signal"]["signal_id"] == "signal-1"
    assert response.meta is not None
    assert response.meta.request_id == "req-1"

    with pytest.raises(ValueError):
        signal_payload_to_response(signal="bad")


def test_list_signals_response_and_pagination():
    context = build_product_api_context(request_id="req-1")
    signals = [
        build_signal("signal-1", "buy", 80),
        build_signal("signal-2", "sell", 60),
    ]
    query = ProductApiListQuery(
        pagination=ProductApiPagination(page=1, page_size=1),
    )

    response = list_signals_response(
        signals=signals,
        query=query,
        context=context,
    )

    assert response.status == ProductApiStatus.SUCCESS
    assert len(response.data["items"]) == 1
    assert response.data["total_items"] == 2
    assert response.data["metadata"]["summary"]["total"] == 2


def test_create_signal_operation_response():
    response = create_signal_operation_response(
        signal=build_signal(),
        context=build_product_api_context(request_id="req-1"),
    )

    assert response.status == ProductApiStatus.SUCCESS
    assert response.data["operation"] == "create"
    assert response.data["resource_type"] == "signal"
    assert response.data["resource_id"] == "signal-1"

    with pytest.raises(ValueError):
        create_signal_operation_response(signal="bad")


def test_update_approve_and_reject_signal():
    signal = build_signal()

    approved = update_signal_status(
        signal,
        status="approved",
    )

    assert approved.status == "approved"
    assert approved.approved is True

    approved_response = approve_signal_response(signal=signal)

    assert approved_response.data["signal"]["status"] == "approved"

    rejected_response = reject_signal_response(
        signal=signal,
        reason="Low confidence.",
    )

    assert rejected_response.data["signal"]["status"] == "rejected"
    assert rejected_response.data["signal"]["metadata"]["rejection_reason"] == "Low confidence."

    with pytest.raises(ValueError):
        update_signal_status("bad", status="approved")

    with pytest.raises(ValueError):
        reject_signal_response(signal=signal, reason=123)


def test_get_signal_response():
    signal = build_signal()
    store = build_product_signal_store()
    store.add(signal)

    found = get_signal_response(
        store=store,
        signal_id="signal-1",
    )

    missing = get_signal_response(
        store=store,
        signal_id="missing",
    )

    assert found.status == ProductApiStatus.SUCCESS
    assert found.data["signal"]["signal_id"] == "signal-1"
    assert missing.status == ProductApiStatus.FAILURE
    assert missing.error is not None
    assert missing.error.code == "not_found"

    with pytest.raises(ValueError):
        get_signal_response(
            store="bad",
            signal_id="signal-1",
        )


def test_paginate_and_filter_product_signals():
    signals = [
        build_signal("signal-1", "buy", 80),
        build_signal("signal-2", "sell", 60),
        build_signal("signal-3", "hold", 40),
    ]

    paged = paginate_product_signals(
        signals=signals,
        pagination=ProductApiPagination(page=2, page_size=1),
    )

    assert [signal.signal_id for signal in paged] == ["signal-2"]

    buy_signals = filter_product_signals(
        signals=signals,
        direction="buy",
    )

    assert len(buy_signals) == 1
    assert buy_signals[0].direction == "buy"

    h1_signals = filter_product_signals(
        signals=signals,
        symbol="xauusd",
        timeframe="h1",
    )

    assert len(h1_signals) == 3

    generated_signals = filter_product_signals(
        signals=signals,
        status="generated",
    )

    assert len(generated_signals) == 3

    with pytest.raises(ValueError):
        paginate_product_signals(
            signals=signals,
            pagination="bad",
        )


def test_product_signal_exports_exist():
    import aqos.product_api as product_api

    expected_exports = [
        "ProductSignalDirection",
        "ProductSignalPayload",
        "ProductSignalRequest",
        "ProductSignalStatus",
        "ProductSignalStore",
        "ProductSignalStrength",
        "ProductSignalSummary",
        "approve_signal_response",
        "build_product_signal_payload",
        "build_product_signal_request",
        "build_product_signal_store",
        "build_product_signal_summary",
        "calculate_signal_risk_reward_ratio",
        "create_signal_operation_response",
        "filter_product_signals",
        "get_signal_response",
        "list_signals_response",
        "normalize_product_signal_direction",
        "normalize_product_signal_status",
        "normalize_product_signal_strength",
        "paginate_product_signals",
        "reject_signal_response",
        "resolve_signal_strength",
        "signal_payload_to_response",
        "update_signal_status",
        "validate_product_signal_payloads",
        "validate_signal_price",
    ]

    for export_name in expected_exports:
        assert hasattr(product_api, export_name), export_name