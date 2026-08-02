"""Unit tests for the persisted paper trading models."""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal

import pytest

from aqos.paper_trading.contracts import (
    PaperAction,
    PaperFill,
    PaperOrder,
    PaperOrderStatus,
    PaperOrderType,
    PaperPosition,
    PaperPositionStatus,
    PaperRejectionReason,
    PaperSide,
    PaperTrade,
    PaperTradingError,
)
from aqos.paper_trading.models import (
    AQOS_PAPER_MODELS_VERSION,
    PaperAccountSnapshotRecord,
    PaperFillRecord,
    PaperOrderRecord,
    PaperPositionRecord,
    PaperTradeRecord,
    as_amount,
)
from aqos.paper_trading.simulator import PaperExitReason


FIXED_NOW = datetime(2026, 1, 1, 0, 0, 0)


def build_order_contract(**overrides) -> PaperOrder:
    payload = {
        "order_id": "order_1",
        "account_id": "account_1",
        "user_id": "user_1",
        "symbol": "XAUUSD",
        "action": PaperAction.BUY,
        "order_type": PaperOrderType.MARKET,
        "quantity": 2.0,
        "status": PaperOrderStatus.ACCEPTED,
        "created_at_utc": FIXED_NOW,
        "updated_at_utc": FIXED_NOW,
    }
    payload.update(overrides)

    return PaperOrder(**payload)


def build_position_contract(**overrides) -> PaperPosition:
    payload = {
        "position_id": "position_1",
        "account_id": "account_1",
        "symbol": "XAUUSD",
        "side": PaperSide.LONG,
        "quantity": 2.0,
        "entry_price": 100.0,
        "opened_at_utc": FIXED_NOW,
    }
    payload.update(overrides)

    return PaperPosition(**payload)


def build_trade_contract(**overrides) -> PaperTrade:
    payload = {
        "trade_id": "trade_1",
        "position_id": "position_1",
        "account_id": "account_1",
        "symbol": "XAUUSD",
        "side": PaperSide.LONG,
        "quantity": 2.0,
        "entry_price": 100.0,
        "exit_price": 110.0,
        "opened_at_utc": FIXED_NOW,
        "closed_at_utc": FIXED_NOW,
        "gross_pnl": 20.0,
        "commission": 2.0,
    }
    payload.update(overrides)

    return PaperTrade(**payload)


def test_module_version_is_declared() -> None:
    assert AQOS_PAPER_MODELS_VERSION == "1.0"


def test_as_amount_accepts_decimals_from_mysql() -> None:
    assert as_amount(Decimal("10.50")) == pytest.approx(10.5)
    assert as_amount(3) == pytest.approx(3.0)


class TestPaperOrderRecord:
    def test_a_contract_round_trips_through_the_record(self) -> None:
        order = build_order_contract(
            signal_id="signal_1",
            stop_loss=96.0,
            take_profit=110.0,
            extra_metadata={"strategy": "baseline"},
        )

        restored = PaperOrderRecord.from_contract(order).to_contract()

        assert restored.order_id == order.order_id
        assert restored.action == PaperAction.BUY
        assert restored.order_type == PaperOrderType.MARKET
        assert restored.status == PaperOrderStatus.ACCEPTED
        assert restored.quantity == pytest.approx(2.0)
        assert restored.stop_loss == pytest.approx(96.0)
        assert restored.signal_id == "signal_1"
        assert restored.extra_metadata == {"strategy": "baseline"}

    def test_defaults_are_applied_before_any_flush(self) -> None:
        """A transient record must not read as None where zero is meant."""

        record = PaperOrderRecord(
            order_id="order_1",
            user_id="user_1",
            account_id="account_1",
            symbol="XAUUSD",
            action=PaperAction.BUY,
            order_type=PaperOrderType.MARKET,
            quantity=1.0,
            created_at_utc=FIXED_NOW,
            updated_at_utc=FIXED_NOW,
        )

        assert record.status == PaperOrderStatus.CREATED
        assert record.filled_quantity == 0
        assert record.extra_metadata == {}

    def test_a_rejected_order_must_explain_itself(self) -> None:
        record = PaperOrderRecord(
            order_id="order_1",
            user_id="user_1",
            account_id="account_1",
            symbol="XAUUSD",
            action=PaperAction.BUY,
            order_type=PaperOrderType.MARKET,
            quantity=1.0,
            status=PaperOrderStatus.REJECTED,
            created_at_utc=FIXED_NOW,
            updated_at_utc=FIXED_NOW,
        )

        with pytest.raises(PaperTradingError, match="rejection reason"):
            record.assert_rejection_is_explained()

    def test_a_rejected_order_with_a_reason_is_accepted(self) -> None:
        record = PaperOrderRecord.from_contract(
            build_order_contract(
                status=PaperOrderStatus.REJECTED,
                rejection_reason=PaperRejectionReason.DUPLICATE_EXECUTION,
                rejection_message="Signal already executed.",
            )
        )

        record.assert_rejection_is_explained()

        assert record.to_contract().rejection_reason == (
            PaperRejectionReason.DUPLICATE_EXECUTION
        )

    def test_to_dict_matches_the_contract(self) -> None:
        record = PaperOrderRecord.from_contract(build_order_contract())

        assert record.to_dict()["order_id"] == "order_1"
        assert record.to_dict()["status"] == "accepted"

    def test_repr_names_the_order(self) -> None:
        record = PaperOrderRecord.from_contract(build_order_contract())

        assert "order_1" in repr(record)

    def test_a_metadata_kwarg_is_refused(self) -> None:
        """``metadata`` is SQLAlchemy's; silently dropping it would lose data."""

        with pytest.raises(TypeError, match="extra_metadata"):
            PaperOrderRecord(
                order_id="order_1",
                user_id="user_1",
                account_id="account_1",
                symbol="XAUUSD",
                action=PaperAction.BUY,
                order_type=PaperOrderType.MARKET,
                quantity=1.0,
                created_at_utc=FIXED_NOW,
                updated_at_utc=FIXED_NOW,
                metadata={"strategy": "baseline"},
            )


class TestPaperPositionRecord:
    def test_a_contract_round_trips_through_the_record(self) -> None:
        position = build_position_contract(
            stop_loss=96.0,
            take_profit=110.0,
            order_id="order_1",
            signal_id="signal_1",
        )

        restored = PaperPositionRecord.from_contract(position).to_contract()

        assert restored.position_id == "position_1"
        assert restored.side == PaperSide.LONG
        assert restored.status == PaperPositionStatus.OPEN
        assert restored.entry_price == pytest.approx(100.0)
        assert restored.open_quantity == pytest.approx(2.0)
        assert restored.order_id == "order_1"

    def test_defaults_are_applied_before_any_flush(self) -> None:
        record = PaperPositionRecord(
            position_id="position_1",
            account_id="account_1",
            symbol="XAUUSD",
            side=PaperSide.LONG,
            quantity=1.0,
            entry_price=100.0,
            opened_at_utc=FIXED_NOW,
        )

        assert record.status == PaperPositionStatus.OPEN
        assert record.closed_quantity == 0
        assert record.realized_pnl == 0
        assert record.extra_metadata == {}

    def test_a_closed_position_must_be_timestamped(self) -> None:
        record = PaperPositionRecord(
            position_id="position_1",
            account_id="account_1",
            symbol="XAUUSD",
            side=PaperSide.LONG,
            quantity=1.0,
            entry_price=100.0,
            opened_at_utc=FIXED_NOW,
            status=PaperPositionStatus.CLOSED,
        )

        with pytest.raises(PaperTradingError, match="close time"):
            record.assert_close_is_timestamped()

    def test_a_timestamped_close_is_accepted(self) -> None:
        record = PaperPositionRecord.from_contract(
            build_position_contract(
                status=PaperPositionStatus.CLOSED,
                closed_quantity=2.0,
                closed_at_utc=FIXED_NOW,
                realized_pnl=20.0,
            )
        )

        record.assert_close_is_timestamped()

        assert record.to_contract().is_open is False

    def test_repr_names_the_position(self) -> None:
        record = PaperPositionRecord.from_contract(build_position_contract())

        assert "position_1" in repr(record)


class TestPaperFillRecord:
    def test_a_contract_round_trips_through_the_record(self) -> None:
        fill = PaperFill(
            fill_id="fill_1",
            order_id="order_1",
            quantity=2.0,
            price=100.5,
            filled_at_utc=FIXED_NOW,
            commission=1.5,
        )

        record = PaperFillRecord.from_contract(
            fill,
            account_id="account_1",
            position_id="position_1",
        )
        restored = record.to_contract()

        assert record.account_id == "account_1"
        assert record.position_id == "position_1"
        assert restored.price == pytest.approx(100.5)
        assert restored.commission == pytest.approx(1.5)
        assert restored.notional == pytest.approx(201.0)

    def test_commission_defaults_to_zero(self) -> None:
        record = PaperFillRecord(
            fill_id="fill_1",
            order_id="order_1",
            account_id="account_1",
            quantity=1.0,
            price=100.0,
            filled_at_utc=FIXED_NOW,
        )

        assert record.commission == 0
        assert record.to_dict()["commission"] == pytest.approx(0.0)

    def test_repr_names_the_fill(self) -> None:
        record = PaperFillRecord(
            fill_id="fill_1",
            order_id="order_1",
            account_id="account_1",
            quantity=1.0,
            price=100.0,
            filled_at_utc=FIXED_NOW,
        )

        assert "fill_1" in repr(record)


class TestPaperTradeRecord:
    def test_a_contract_round_trips_through_the_record(self) -> None:
        trade = build_trade_contract(
            risk_amount=8.0,
            reward_amount=20.0,
            balance_after=10_018.0,
            signal_id="signal_1",
        )

        record = PaperTradeRecord.from_contract(
            trade,
            exit_reason=PaperExitReason.TAKE_PROFIT,
        )
        restored = record.to_contract()

        assert restored.gross_pnl == pytest.approx(20.0)
        assert restored.commission == pytest.approx(2.0)
        assert restored.net_pnl == pytest.approx(18.0)
        assert restored.risk_amount == pytest.approx(8.0)
        assert record.exit_reason == PaperExitReason.TAKE_PROFIT

    def test_net_pnl_must_be_derived_from_its_inputs(self) -> None:
        record = PaperTradeRecord.from_contract(build_trade_contract())
        record.net_pnl = 20.0

        with pytest.raises(PaperTradingError, match="gross_pnl minus commission"):
            record.assert_net_pnl_is_derived()

    def test_a_consistent_net_pnl_is_accepted(self) -> None:
        """``from_contract`` derives net_pnl, so the record starts honest."""

        record = PaperTradeRecord.from_contract(build_trade_contract())

        assert as_amount(record.net_pnl) == pytest.approx(18.0)

        record.assert_net_pnl_is_derived()

    def test_a_losing_trade_is_consistent_too(self) -> None:
        record = PaperTradeRecord.from_contract(
            build_trade_contract(exit_price=95.0, gross_pnl=-10.0)
        )

        assert as_amount(record.net_pnl) == pytest.approx(-12.0)

        record.assert_net_pnl_is_derived()

    def test_the_record_feeds_the_analytics_contract(self) -> None:
        record = PaperTradeRecord.from_contract(
            build_trade_contract(balance_after=10_018.0)
        )

        analytics_record = record.to_account_trade_record()

        assert analytics_record.trade_id == "trade_1"
        assert analytics_record.net_pnl == pytest.approx(18.0)
        assert analytics_record.symbol == "XAUUSD"
        assert analytics_record.balance_after == pytest.approx(10_018.0)

    def test_to_dict_includes_the_exit_reason(self) -> None:
        record = PaperTradeRecord.from_contract(
            build_trade_contract(),
            exit_reason=PaperExitReason.STOP_LOSS,
        )

        assert record.to_dict()["exit_reason"] == "stop_loss"

    def test_the_exit_reason_defaults_to_a_manual_close(self) -> None:
        record = PaperTradeRecord.from_contract(build_trade_contract())

        assert record.exit_reason == PaperExitReason.MANUAL_CLOSE

    def test_repr_names_the_trade(self) -> None:
        record = PaperTradeRecord.from_contract(build_trade_contract())

        assert "trade_1" in repr(record)


class TestPaperAccountSnapshotRecord:
    def build(self, **overrides) -> PaperAccountSnapshotRecord:
        payload = {
            "snapshot_id": "snapshot_1",
            "account_id": "account_1",
            "starting_balance": 10_000.0,
            "current_balance": 10_050.0,
            "equity": 10_050.0,
            "captured_at_utc": FIXED_NOW,
        }
        payload.update(overrides)

        return PaperAccountSnapshotRecord(**payload)

    def test_defaults_are_applied_before_any_flush(self) -> None:
        record = self.build()

        assert record.currency == "USD"
        assert record.margin_used == 0
        assert record.open_position_count == 0
        assert record.open_order_count == 0
        assert record.closed_trade_count == 0

    def test_the_currency_is_normalised(self) -> None:
        assert self.build(currency="eur").currency == "EUR"

    @pytest.mark.parametrize("currency", ["US", "USDD", "12A", ""])
    def test_an_invalid_currency_is_rejected(self, currency: str) -> None:
        with pytest.raises(PaperTradingError, match="3 letter code"):
            self.build(currency=currency)

    def test_to_dict_reports_every_field(self) -> None:
        payload = self.build(open_position_count=2).to_dict()

        assert payload["snapshot_id"] == "snapshot_1"
        assert payload["starting_balance"] == pytest.approx(10_000.0)
        assert payload["open_position_count"] == 2
        assert payload["captured_at_utc"] == FIXED_NOW.isoformat()
        assert payload["metadata"] == {}

    def test_repr_names_the_snapshot(self) -> None:
        assert "snapshot_1" in repr(self.build())
