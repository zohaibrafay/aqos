"""
Unit tests for RiskInterface.
"""

from typing import Any

import pytest

from aqos.interfaces import (
    RiskInterface,
    RiskInterfaceDecision,
)


class DummyRiskManager(RiskInterface):
    """
    Test implementation of RiskInterface.
    """

    @property
    def name(self) -> str:
        return "dummy-risk-manager"

    def validate_trade(
        self,
        trade_request: dict[str, Any],
    ) -> bool:
        self.validate_trade_request(trade_request)

        side = self.get_required_trade_value(
            trade_request=trade_request,
            key="side",
        )
        account_balance = float(
            self.get_required_trade_value(
                trade_request=trade_request,
                key="account_balance",
            )
        )
        risk_percent = float(
            self.get_required_trade_value(
                trade_request=trade_request,
                key="risk_percent",
            )
        )
        entry_price = float(
            self.get_required_trade_value(
                trade_request=trade_request,
                key="entry_price",
            )
        )
        stop_loss_price = float(
            self.get_required_trade_value(
                trade_request=trade_request,
                key="stop_loss_price",
            )
        )

        self.validate_side(side)
        self.validate_account_balance(account_balance)
        self.validate_risk_percent(risk_percent)
        self.validate_price(entry_price)
        self.validate_price(stop_loss_price)

        if side == "buy" and stop_loss_price >= entry_price:
            return False

        if side == "sell" and stop_loss_price <= entry_price:
            return False

        return True

    def rejection_reason(
        self,
        trade_request: dict[str, Any],
    ) -> str:
        side = self.get_required_trade_value(
            trade_request=trade_request,
            key="side",
        )
        entry_price = float(
            self.get_required_trade_value(
                trade_request=trade_request,
                key="entry_price",
            )
        )
        stop_loss_price = float(
            self.get_required_trade_value(
                trade_request=trade_request,
                key="stop_loss_price",
            )
        )

        if side == "buy" and stop_loss_price >= entry_price:
            return "Buy stop loss must be below entry price."

        if side == "sell" and stop_loss_price <= entry_price:
            return "Sell stop loss must be above entry price."

        return "Trade rejected."

    def calculate_position_size(
        self,
        account_balance: float,
        risk_percent: float,
        entry_price: float,
        stop_loss_price: float,
    ) -> float:
        self.validate_account_balance(account_balance)
        self.validate_risk_percent(risk_percent)
        self.validate_price(entry_price)
        self.validate_price(stop_loss_price)

        risk_amount = account_balance * risk_percent
        risk_per_unit = abs(entry_price - stop_loss_price)

        if risk_per_unit == 0:
            raise ValueError("Risk per unit cannot be zero.")

        position_size = risk_amount / risk_per_unit

        self.validate_position_size(position_size)

        return position_size


def create_buy_trade_request() -> dict[str, Any]:
    return {
        "symbol": "XAUUSD",
        "side": "buy",
        "account_balance": 10_000.0,
        "risk_percent": 0.01,
        "entry_price": 2000.0,
        "stop_loss_price": 1990.0,
    }


def create_invalid_buy_trade_request() -> dict[str, Any]:
    return {
        "symbol": "XAUUSD",
        "side": "buy",
        "account_balance": 10_000.0,
        "risk_percent": 0.01,
        "entry_price": 2000.0,
        "stop_loss_price": 2010.0,
    }


def test_risk_interface_cannot_be_instantiated():
    with pytest.raises(TypeError):
        RiskInterface()


def test_dummy_risk_manager_is_interface_instance():
    manager = DummyRiskManager()

    assert isinstance(manager, RiskInterface)


def test_risk_manager_name():
    manager = DummyRiskManager()

    assert manager.name == "dummy-risk-manager"


def test_validate_trade_allowed():
    manager = DummyRiskManager()

    allowed = manager.validate_trade(
        create_buy_trade_request()
    )

    assert allowed is True


def test_validate_trade_rejected():
    manager = DummyRiskManager()

    allowed = manager.validate_trade(
        create_invalid_buy_trade_request()
    )

    assert allowed is False


def test_rejection_reason():
    manager = DummyRiskManager()

    reason = manager.rejection_reason(
        create_invalid_buy_trade_request()
    )

    assert reason == "Buy stop loss must be below entry price."


def test_calculate_position_size():
    manager = DummyRiskManager()

    position_size = manager.calculate_position_size(
        account_balance=10_000.0,
        risk_percent=0.01,
        entry_price=2000.0,
        stop_loss_price=1990.0,
    )

    assert position_size == 10.0


def test_assess_allowed_trade():
    manager = DummyRiskManager()

    decision = manager.assess(
        trade_request=create_buy_trade_request(),
        metadata={
            "strategy": "trend",
        },
    )

    assert isinstance(decision, RiskInterfaceDecision)
    assert decision.allowed is True
    assert decision.reason == "Trade allowed."
    assert decision.position_size == 10.0
    assert decision.metadata["strategy"] == "trend"


def test_assess_rejected_trade():
    manager = DummyRiskManager()

    decision = manager.assess(
        trade_request=create_invalid_buy_trade_request(),
    )

    assert decision.allowed is False
    assert decision.reason == "Buy stop loss must be below entry price."
    assert decision.position_size is None


def test_validate_trade_request():
    manager = DummyRiskManager()

    manager.validate_trade_request(
        create_buy_trade_request()
    )


def test_validate_trade_request_rejects_non_dict():
    manager = DummyRiskManager()

    with pytest.raises(TypeError):
        manager.validate_trade_request(["not", "a", "dict"])


def test_validate_trade_request_rejects_empty_dict():
    manager = DummyRiskManager()

    with pytest.raises(ValueError):
        manager.validate_trade_request({})


def test_validate_side():
    manager = DummyRiskManager()

    manager.validate_side("buy")
    manager.validate_side("sell")


def test_validate_side_rejects_invalid_side():
    manager = DummyRiskManager()

    with pytest.raises(ValueError):
        manager.validate_side("hold")


def test_validate_account_balance():
    manager = DummyRiskManager()

    manager.validate_account_balance(10_000.0)


def test_validate_account_balance_rejects_invalid_balance():
    manager = DummyRiskManager()

    with pytest.raises(ValueError):
        manager.validate_account_balance(0)


def test_validate_risk_percent():
    manager = DummyRiskManager()

    manager.validate_risk_percent(0.01)


def test_validate_risk_percent_rejects_invalid_low_value():
    manager = DummyRiskManager()

    with pytest.raises(ValueError):
        manager.validate_risk_percent(0)


def test_validate_risk_percent_rejects_invalid_high_value():
    manager = DummyRiskManager()

    with pytest.raises(ValueError):
        manager.validate_risk_percent(1.1)


def test_validate_price():
    manager = DummyRiskManager()

    manager.validate_price(2000.0)


def test_validate_price_rejects_invalid_price():
    manager = DummyRiskManager()

    with pytest.raises(ValueError):
        manager.validate_price(0)


def test_validate_position_size():
    manager = DummyRiskManager()

    manager.validate_position_size(1.0)


def test_validate_position_size_rejects_invalid_position_size():
    manager = DummyRiskManager()

    with pytest.raises(ValueError):
        manager.validate_position_size(0)


def test_get_required_trade_value():
    manager = DummyRiskManager()

    value = manager.get_required_trade_value(
        trade_request=create_buy_trade_request(),
        key="symbol",
    )

    assert value == "XAUUSD"


def test_get_required_trade_value_rejects_empty_key():
    manager = DummyRiskManager()

    with pytest.raises(ValueError):
        manager.get_required_trade_value(
            trade_request=create_buy_trade_request(),
            key="",
        )


def test_get_required_trade_value_rejects_missing_key():
    manager = DummyRiskManager()

    with pytest.raises(ValueError):
        manager.get_required_trade_value(
            trade_request=create_buy_trade_request(),
            key="missing",
        )


def test_validate_trade_missing_required_key():
    manager = DummyRiskManager()

    request = create_buy_trade_request()
    request.pop("side")

    with pytest.raises(ValueError):
        manager.validate_trade(request)


def test_validate_trade_invalid_side():
    manager = DummyRiskManager()

    request = create_buy_trade_request()
    request["side"] = "hold"

    with pytest.raises(ValueError):
        manager.validate_trade(request)


def test_position_size_rejects_zero_risk_per_unit():
    manager = DummyRiskManager()

    with pytest.raises(ValueError):
        manager.calculate_position_size(
            account_balance=10_000.0,
            risk_percent=0.01,
            entry_price=2000.0,
            stop_loss_price=2000.0,
        )