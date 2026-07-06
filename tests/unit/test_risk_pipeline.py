"""
Unit tests for RiskPipeline.
"""

import pytest

from aqos.risk import (
    DrawdownManager,
    ExposureManager,
    PortfolioRiskManager,
    PositionSizer,
    RiskAssessment,
    RiskConstraints,
    RiskDecision,
    RiskPipeline,
    StopLossManager,
    TakeProfitManager,
)


def create_pipeline() -> RiskPipeline:
    return RiskPipeline(
        position_sizer=PositionSizer(risk_percent=0.01),
        exposure_manager=ExposureManager(max_exposure_percent=1.0),
        drawdown_manager=DrawdownManager(max_drawdown_percent=0.2),
        constraints=RiskConstraints(
            max_risk_percent=0.02,
            max_exposure_percent=1.0,
            max_drawdown_percent=0.2,
        ),
        stop_loss_manager=StopLossManager(),
        take_profit_manager=TakeProfitManager(reward_risk_ratio=2.0),
        portfolio_manager=PortfolioRiskManager(),
    )


def test_assess_buy_trade_allowed():
    pipeline = create_pipeline()

    assessment = pipeline.assess_trade(
        account_balance=10_000.0,
        peak_equity=10_000.0,
        current_equity=9_800.0,
        entry_price=1000.0,
        stop_loss_price=990.0,
        current_price=1005.0,
        side="buy",
    )

    assert isinstance(assessment, RiskAssessment)
    assert assessment.allowed is True
    assert assessment.position_size == 10.0
    assert assessment.risk_amount == 100.0
    assert assessment.exposure == 10_000.0
    assert assessment.drawdown_percent == 0.02
    assert assessment.take_profit_price == 1020.0
    assert assessment.stop_loss_triggered is False
    assert assessment.take_profit_hit is False


def test_assess_sell_trade_allowed():
    pipeline = create_pipeline()

    assessment = pipeline.assess_trade(
        account_balance=10_000.0,
        peak_equity=10_000.0,
        current_equity=9_800.0,
        entry_price=1000.0,
        stop_loss_price=1010.0,
        current_price=995.0,
        side="sell",
    )

    assert assessment.allowed is True
    assert assessment.position_size == 10.0
    assert assessment.risk_amount == 100.0
    assert assessment.exposure == 10_000.0
    assert assessment.take_profit_price == 980.0


def test_assess_trade_with_stop_loss_triggered():
    pipeline = create_pipeline()

    assessment = pipeline.assess_trade(
        account_balance=10_000.0,
        peak_equity=10_000.0,
        current_equity=9_800.0,
        entry_price=1000.0,
        stop_loss_price=990.0,
        current_price=990.0,
        side="buy",
    )

    assert assessment.stop_loss_triggered is True


def test_assess_trade_with_take_profit_hit():
    pipeline = create_pipeline()

    assessment = pipeline.assess_trade(
        account_balance=10_000.0,
        peak_equity=10_000.0,
        current_equity=9_800.0,
        entry_price=1000.0,
        stop_loss_price=990.0,
        current_price=1020.0,
        side="buy",
    )

    assert assessment.take_profit_hit is True


def test_assess_trade_not_allowed_by_exposure():
    pipeline = create_pipeline()

    assessment = pipeline.assess_trade(
        account_balance=10_000.0,
        peak_equity=10_000.0,
        current_equity=9_800.0,
        entry_price=2000.0,
        stop_loss_price=1990.0,
        current_price=2000.0,
        side="buy",
    )

    assert assessment.allowed is False
    assert "Exposure exceeds maximum exposure limit." in assessment.reasons


def test_assess_trade_not_allowed_by_drawdown():
    pipeline = create_pipeline()

    assessment = pipeline.assess_trade(
        account_balance=10_000.0,
        peak_equity=10_000.0,
        current_equity=7_000.0,
        entry_price=1000.0,
        stop_loss_price=990.0,
        current_price=1000.0,
        side="buy",
    )

    assert assessment.allowed is False
    assert "Drawdown exceeds maximum drawdown limit." in assessment.reasons


def test_validate_decision():
    pipeline = create_pipeline()

    decision = RiskDecision(
        allowed=True,
        reasons=[],
    )

    assert pipeline.validate_decision(decision) is True


def test_invalid_side():
    pipeline = create_pipeline()

    with pytest.raises(ValueError):
        pipeline.assess_trade(
            account_balance=10_000.0,
            peak_equity=10_000.0,
            current_equity=9_800.0,
            entry_price=1000.0,
            stop_loss_price=990.0,
            current_price=1000.0,
            side="hold",
        )