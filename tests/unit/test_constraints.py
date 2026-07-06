"""
Unit tests for RiskConstraints.
"""

import pytest

from aqos.risk import RiskConstraints, RiskDecision


def test_validate_trade_allowed():
    constraints = RiskConstraints(
        max_risk_percent=0.02,
        max_exposure_percent=0.5,
        max_drawdown_percent=0.2,
    )

    decision = constraints.validate_trade(
        account_balance=10_000.0,
        risk_amount=100.0,
        exposure=4_000.0,
        peak_equity=10_000.0,
        current_equity=9_500.0,
    )

    assert isinstance(decision, RiskDecision)
    assert decision.allowed is True
    assert decision.reasons == []


def test_validate_trade_risk_violation():
    constraints = RiskConstraints(max_risk_percent=0.01)

    decision = constraints.validate_trade(
        account_balance=10_000.0,
        risk_amount=200.0,
        exposure=1_000.0,
        peak_equity=10_000.0,
        current_equity=9_900.0,
    )

    assert decision.allowed is False
    assert "Risk amount exceeds maximum risk limit." in decision.reasons


def test_validate_trade_exposure_violation():
    constraints = RiskConstraints(max_exposure_percent=0.3)

    decision = constraints.validate_trade(
        account_balance=10_000.0,
        risk_amount=50.0,
        exposure=4_000.0,
        peak_equity=10_000.0,
        current_equity=9_900.0,
    )

    assert decision.allowed is False
    assert "Exposure exceeds maximum exposure limit." in decision.reasons


def test_validate_trade_drawdown_violation():
    constraints = RiskConstraints(max_drawdown_percent=0.05)

    decision = constraints.validate_trade(
        account_balance=10_000.0,
        risk_amount=50.0,
        exposure=1_000.0,
        peak_equity=10_000.0,
        current_equity=9_000.0,
    )

    assert decision.allowed is False
    assert "Drawdown exceeds maximum drawdown limit." in decision.reasons


def test_validate_trade_multiple_violations():
    constraints = RiskConstraints(
        max_risk_percent=0.01,
        max_exposure_percent=0.2,
        max_drawdown_percent=0.05,
    )

    decision = constraints.validate_trade(
        account_balance=10_000.0,
        risk_amount=200.0,
        exposure=5_000.0,
        peak_equity=10_000.0,
        current_equity=9_000.0,
    )

    assert decision.allowed is False
    assert len(decision.reasons) == 3


def test_is_risk_within_limit_true():
    constraints = RiskConstraints(max_risk_percent=0.02)

    result = constraints.is_risk_within_limit(
        risk_amount=100.0,
        account_balance=10_000.0,
    )

    assert result is True


def test_is_risk_within_limit_false():
    constraints = RiskConstraints(max_risk_percent=0.005)

    result = constraints.is_risk_within_limit(
        risk_amount=100.0,
        account_balance=10_000.0,
    )

    assert result is False


def test_is_exposure_within_limit_true():
    constraints = RiskConstraints(max_exposure_percent=0.5)

    result = constraints.is_exposure_within_limit(
        exposure=4_000.0,
        account_balance=10_000.0,
    )

    assert result is True


def test_is_exposure_within_limit_false():
    constraints = RiskConstraints(max_exposure_percent=0.3)

    result = constraints.is_exposure_within_limit(
        exposure=4_000.0,
        account_balance=10_000.0,
    )

    assert result is False


def test_is_drawdown_within_limit_true():
    constraints = RiskConstraints(max_drawdown_percent=0.2)

    result = constraints.is_drawdown_within_limit(
        peak_equity=10_000.0,
        current_equity=9_000.0,
    )

    assert result is True


def test_is_drawdown_within_limit_false():
    constraints = RiskConstraints(max_drawdown_percent=0.05)

    result = constraints.is_drawdown_within_limit(
        peak_equity=10_000.0,
        current_equity=9_000.0,
    )

    assert result is False


def test_invalid_max_risk_percent_zero():
    with pytest.raises(ValueError):
        RiskConstraints(max_risk_percent=0)


def test_invalid_max_exposure_percent_zero():
    with pytest.raises(ValueError):
        RiskConstraints(max_exposure_percent=0)


def test_invalid_max_drawdown_percent_zero():
    with pytest.raises(ValueError):
        RiskConstraints(max_drawdown_percent=0)


def test_invalid_percent_above_one():
    with pytest.raises(ValueError):
        RiskConstraints(max_risk_percent=1.5)


def test_negative_risk_amount():
    constraints = RiskConstraints()

    with pytest.raises(ValueError):
        constraints.is_risk_within_limit(
            risk_amount=-1.0,
            account_balance=10_000.0,
        )


def test_negative_exposure():
    constraints = RiskConstraints()

    with pytest.raises(ValueError):
        constraints.is_exposure_within_limit(
            exposure=-1.0,
            account_balance=10_000.0,
        )


def test_invalid_account_balance():
    constraints = RiskConstraints()

    with pytest.raises(ValueError):
        constraints.is_risk_within_limit(
            risk_amount=100.0,
            account_balance=0,
        )


def test_invalid_peak_equity():
    constraints = RiskConstraints()

    with pytest.raises(ValueError):
        constraints.is_drawdown_within_limit(
            peak_equity=0,
            current_equity=9_000.0,
        )


def test_invalid_current_equity():
    constraints = RiskConstraints()

    with pytest.raises(ValueError):
        constraints.is_drawdown_within_limit(
            peak_equity=10_000.0,
            current_equity=-1.0,
        )