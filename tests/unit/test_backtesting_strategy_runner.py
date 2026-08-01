from __future__ import annotations

import json

import pandas as pd

from aqos.backtesting import (
    BACKTEST_STRATEGY_RUNNER_VERSION,
    BacktestSignalAction,
    BacktestSignalAdapterStatus,
    NoOpBacktestSignalAdapter,
    RuleBasedBacktestSignalAdapter,
    RuleBasedSignalAdapterConfig,
    StrategyBacktestRunnerConfig,
    build_strategy_adapter_context,
    load_backtest_bars_from_csv,
    BacktestDataLoadConfig,
    run_backtest_with_signal_adapter,
)


def build_strategy_backtest_dataframe() -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "timestamp": "2026-01-01T00:00:00",
                "symbol": "XAUUSD",
                "timeframe": "H1",
                "open": 2300.0,
                "high": 2306.0,
                "low": 2298.0,
                "close": 2304.0,
                "volume": 1000,
            },
            {
                "timestamp": "2026-01-01T01:00:00",
                "symbol": "XAUUSD",
                "timeframe": "H1",
                "open": 2304.0,
                "high": 2312.0,
                "low": 2301.0,
                "close": 2310.0,
                "volume": 1100,
            },
            {
                "timestamp": "2026-01-01T02:00:00",
                "symbol": "XAUUSD",
                "timeframe": "H1",
                "open": 2310.0,
                "high": 2315.0,
                "low": 2308.0,
                "close": 2312.0,
                "volume": 1200,
            },
        ]
    )


def first_bar_buy_strategy(bar, history, metadata=None):
    if metadata is not None and metadata.get("bar_index") == 0:
        return {
            "action": "buy",
            "confidence": 0.8,
            "stop_loss": 2290.0,
            "take_profit": 2310.0,
            "metadata": {"reason": "first bar buy"},
        }

    return "hold"


def test_build_strategy_adapter_context_uses_history_and_metadata(tmp_path) -> None:
    data_path = tmp_path / "bars.csv"
    build_strategy_backtest_dataframe().to_csv(data_path, index=False)

    result = load_backtest_bars_from_csv(
        BacktestDataLoadConfig(csv_path=data_path)
    )

    config = StrategyBacktestRunnerConfig(
        data_path=data_path,
        strategy_name="context_test_strategy",
        metadata={"profile": "unit"},
    )

    context = build_strategy_adapter_context(
        bar=result.bars[1],
        history=(result.bars[0],),
        index=1,
        config=config,
    )

    assert context.bar.timestamp == "2026-01-01T01:00:00"
    assert context.previous_bar == result.bars[0]
    assert context.metadata["strategy_name"] == "context_test_strategy"
    assert context.metadata["bar_index"] == 1
    assert context.metadata["profile"] == "unit"


def test_run_backtest_with_signal_adapter_writes_outputs(tmp_path) -> None:
    data_path = tmp_path / "bars.csv"
    output_dir = tmp_path / "strategy_backtest"

    build_strategy_backtest_dataframe().to_csv(data_path, index=False)

    adapter = RuleBasedBacktestSignalAdapter(
        strategy=first_bar_buy_strategy,
        config=RuleBasedSignalAdapterConfig(
            adapter_name="first_bar_buy_adapter",
        ),
    )

    output = run_backtest_with_signal_adapter(
        config=StrategyBacktestRunnerConfig(
            data_path=data_path,
            output_dir=output_dir,
            symbol="XAUUSD",
            timeframe="H1",
            strategy_name="first_bar_buy_strategy",
            fixed_quantity=1.0,
        ),
        adapter=adapter,
    )

    assert output.report_path.exists()
    assert output.trades_path.exists()
    assert output.equity_curve_path.exists()
    assert output.orders_path.exists()
    assert output.signals_path.exists()
    assert output.adapter_results_path.exists()

    assert output.metrics.total_trades == 1
    assert output.metrics.winning_trades == 1
    assert output.metrics.net_profit == 10.0
    assert output.final_state.open_position_count == 0

    assert len(output.adapter_results) == 3
    assert output.adapter_results[0].status == BacktestSignalAdapterStatus.GENERATED
    assert output.adapter_results[0].signal.action == BacktestSignalAction.BUY
    assert output.adapter_results[1].signal.action == BacktestSignalAction.HOLD

    report = json.loads(output.report_path.read_text(encoding="utf-8"))
    adapter_results = json.loads(
        output.adapter_results_path.read_text(encoding="utf-8")
    )
    signals = pd.read_csv(output.signals_path)
    trades = pd.read_csv(output.trades_path)

    assert report["metrics"]["total_trades"] == 1
    assert report["metrics"]["net_profit"] == 10.0
    assert report["metrics"]["metadata"]["adapter_name"] == "first_bar_buy_adapter"

    assert len(adapter_results) == 3
    assert adapter_results[0]["signal"]["action"] == "buy"

    assert len(signals) == 3
    assert signals.iloc[0]["action"] == "buy"

    assert len(trades) == 1
    assert trades.iloc[0]["exit_reason"] == "take_profit"


def test_run_backtest_with_noop_adapter_generates_no_trades(tmp_path) -> None:
    data_path = tmp_path / "bars.csv"
    output_dir = tmp_path / "noop_backtest"

    build_strategy_backtest_dataframe().to_csv(data_path, index=False)

    output = run_backtest_with_signal_adapter(
        config=StrategyBacktestRunnerConfig(
            data_path=data_path,
            output_dir=output_dir,
            symbol="XAUUSD",
            timeframe="H1",
            strategy_name="noop_strategy",
        ),
        adapter=NoOpBacktestSignalAdapter(),
    )

    assert output.metrics.total_trades == 0
    assert output.metrics.net_profit == 0.0
    assert output.final_state.open_position_count == 0
    assert len(output.adapter_results) == 3
    assert all(
        adapter_result.signal.action == BacktestSignalAction.HOLD
        for adapter_result in output.adapter_results
    )


def test_strategy_backtest_runner_version_exported() -> None:
    assert BACKTEST_STRATEGY_RUNNER_VERSION == "1.0"