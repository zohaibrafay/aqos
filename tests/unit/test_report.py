"""
Unit tests for ReportGenerator.
"""

import pytest

from aqos.evaluation import Backtester, EvaluationReport, ReportGenerator


def create_backtest_result():
    backtester = Backtester()

    return backtester.run(
        profits=[100.0, -50.0, 25.0],
        initial_balance=10_000.0,
    )


def test_generate_backtest_report():
    result = create_backtest_result()

    generator = ReportGenerator()

    report = generator.generate_backtest_report(result)

    assert isinstance(report, EvaluationReport)
    assert report.title == "Backtest Report"
    assert report.summary["initial_balance"] == 10_000.0
    assert report.summary["final_balance"] == 10_075.0
    assert report.summary["total_profit"] == 75.0
    assert report.summary["total_trades"] == 3


def test_generate_backtest_report_with_custom_title():
    result = create_backtest_result()

    generator = ReportGenerator()

    report = generator.generate_backtest_report(
        result=result,
        title="XAUUSD Strategy Report",
    )

    assert report.title == "XAUUSD Strategy Report"


def test_generate_backtest_report_details():
    result = create_backtest_result()

    generator = ReportGenerator()

    report = generator.generate_backtest_report(result)

    trades = report.details["trades"]

    assert len(trades) == 3
    assert trades[0]["index"] == 0
    assert trades[0]["profit"] == 100.0
    assert trades[0]["balance"] == 10_100.0


def test_generate_text_summary():
    result = create_backtest_result()

    generator = ReportGenerator()

    report = generator.generate_backtest_report(result)

    summary = generator.generate_text_summary(report)

    assert "Backtest Report" in summary
    assert "Initial Balance: 10000.0" in summary
    assert "Final Balance: 10075.0" in summary
    assert "Total Profit: 75.0" in summary
    assert "Total Trades: 3" in summary


def test_empty_report_title():
    result = create_backtest_result()

    generator = ReportGenerator()

    with pytest.raises(ValueError):
        generator.generate_backtest_report(
            result=result,
            title="",
        )


def test_generate_text_summary_with_empty_title():
    generator = ReportGenerator()

    report = EvaluationReport(
        title="",
        summary={
            "initial_balance": 10_000.0,
            "final_balance": 10_100.0,
            "total_profit": 100.0,
            "return_percent": 0.01,
            "win_rate": 1.0,
            "max_drawdown": 0.0,
            "total_trades": 1,
        },
        details={},
    )

    with pytest.raises(ValueError):
        generator.generate_text_summary(report)