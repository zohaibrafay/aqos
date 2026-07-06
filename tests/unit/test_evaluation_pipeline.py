"""
Unit tests for EvaluationPipeline.
"""

import pytest

from aqos.evaluation import (
    Backtester,
    BacktestResult,
    EvaluationMetrics,
    EvaluationPipeline,
    EvaluationReport,
    PaperTradingEngine,
    ReportGenerator,
    WalkForwardValidator,
)


def create_pipeline() -> EvaluationPipeline:
    return EvaluationPipeline(
        metrics=EvaluationMetrics(),
        backtester=Backtester(),
        report_generator=ReportGenerator(),
        walk_forward_validator=WalkForwardValidator(
            train_size=3,
            test_size=2,
        ),
        paper_trading_engine=PaperTradingEngine(
            initial_balance=10_000.0,
        ),
    )


def test_evaluate_classification():
    pipeline = create_pipeline()

    result = pipeline.evaluate_classification(
        actual=["buy", "sell", "hold", "buy"],
        predicted=["buy", "sell", "buy", "buy"],
    )

    assert result["accuracy"] == 0.75


def test_evaluate_regression():
    pipeline = create_pipeline()

    result = pipeline.evaluate_regression(
        actual=[1.0, 2.0, 3.0],
        predicted=[1.0, 2.5, 2.0],
    )

    assert result["mae"] == pytest.approx(0.5)
    assert result["mse"] == pytest.approx(0.4166666667)
    assert result["rmse"] == pytest.approx(0.6454972244)


def test_evaluate_trades():
    pipeline = create_pipeline()

    result = pipeline.evaluate_trades(
        profits=[100.0, -50.0, 25.0],
    )

    assert result["total_profit"] == 75.0
    assert result["average_profit"] == 25.0
    assert result["win_rate"] == pytest.approx(2 / 3)
    assert result["profit_factor"] == 2.5


def test_run_backtest():
    pipeline = create_pipeline()

    result = pipeline.run_backtest(
        profits=[100.0, -50.0, 25.0],
        initial_balance=10_000.0,
    )

    assert isinstance(result, BacktestResult)
    assert result.final_balance == 10_075.0
    assert result.total_profit == 75.0


def test_generate_backtest_report():
    pipeline = create_pipeline()

    report = pipeline.generate_backtest_report(
        profits=[100.0, -50.0, 25.0],
        initial_balance=10_000.0,
        title="AQOS Backtest",
    )

    assert isinstance(report, EvaluationReport)
    assert report.title == "AQOS Backtest"
    assert report.summary["total_profit"] == 75.0
    assert report.summary["total_trades"] == 3


def test_generate_backtest_text_summary():
    pipeline = create_pipeline()

    summary = pipeline.generate_backtest_text_summary(
        profits=[100.0, -50.0, 25.0],
        initial_balance=10_000.0,
        title="AQOS Backtest",
    )

    assert "AQOS Backtest" in summary
    assert "Total Profit: 75.0" in summary


def test_walk_forward_split():
    pipeline = create_pipeline()

    splits = pipeline.walk_forward_split(
        data=[
            1,
            2,
            3,
            4,
            5,
            6,
        ]
    )

    assert len(splits) == 1
    assert splits[0].train_data == [1, 2, 3]
    assert splits[0].test_data == [4, 5]


def test_walk_forward_without_validator():
    pipeline = EvaluationPipeline(
        metrics=EvaluationMetrics(),
        backtester=Backtester(),
        report_generator=ReportGenerator(),
    )

    with pytest.raises(ValueError):
        pipeline.walk_forward_split(
            data=[
                1,
                2,
                3,
                4,
                5,
            ]
        )


def test_paper_trading_engine():
    pipeline = create_pipeline()

    engine = pipeline.paper_trading()

    trade = engine.open_trade(
        trade_id="trade-1",
        symbol="XAUUSD",
        side="buy",
        quantity=1.0,
        entry_price=2000.0,
    )

    assert trade.trade_id == "trade-1"


def test_paper_trading_without_engine():
    pipeline = EvaluationPipeline(
        metrics=EvaluationMetrics(),
        backtester=Backtester(),
        report_generator=ReportGenerator(),
    )

    with pytest.raises(ValueError):
        pipeline.paper_trading()