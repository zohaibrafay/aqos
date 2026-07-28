from __future__ import annotations

import pandas as pd
import pytest

from aqos.backtesting import (
    BacktestBar,
    BacktestDataLoadConfig,
    dataframe_to_backtest_bars,
    load_backtest_bars_from_csv,
    prepare_backtest_dataframe,
    read_backtest_csv_dataframe,
    validate_backtest_dataframe,
)


def build_ohlcv_dataframe() -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "timestamp": "2026-01-01T02:00:00",
                "symbol": "XAUUSD",
                "timeframe": "H1",
                "open": 2305.0,
                "high": 2310.0,
                "low": 2300.0,
                "close": 2308.0,
                "volume": 1200,
            },
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
                "high": 2309.0,
                "low": 2301.0,
                "close": 2305.0,
                "volume": 1100,
            },
        ]
    )


def test_read_backtest_csv_dataframe(tmp_path) -> None:
    csv_path = tmp_path / "ohlcv.csv"
    build_ohlcv_dataframe().to_csv(csv_path, index=False)

    dataframe = read_backtest_csv_dataframe(csv_path)

    assert len(dataframe) == 3
    assert "timestamp" in dataframe.columns


def test_read_backtest_csv_dataframe_rejects_missing_file(tmp_path) -> None:
    with pytest.raises(FileNotFoundError):
        read_backtest_csv_dataframe(tmp_path / "missing.csv")


def test_validate_backtest_dataframe_passes_valid_data() -> None:
    config = BacktestDataLoadConfig(csv_path="ohlcv.csv")
    report = validate_backtest_dataframe(build_ohlcv_dataframe(), config)

    assert report.valid is True
    assert report.rows == 3
    assert report.issues == ()


def test_validate_backtest_dataframe_rejects_missing_required_columns() -> None:
    config = BacktestDataLoadConfig(csv_path="ohlcv.csv")
    dataframe = build_ohlcv_dataframe().drop(columns=["high"])

    report = validate_backtest_dataframe(dataframe, config)

    assert report.valid is False
    assert any(issue.column == "high" for issue in report.issues)

    with pytest.raises(ValueError, match="Backtest data validation failed"):
        report.raise_if_invalid()


def test_validate_backtest_dataframe_requires_symbol_when_no_default() -> None:
    config = BacktestDataLoadConfig(csv_path="ohlcv.csv")
    dataframe = build_ohlcv_dataframe().drop(columns=["symbol"])

    report = validate_backtest_dataframe(dataframe, config)

    assert report.valid is False
    assert any(issue.column == "symbol" for issue in report.issues)


def test_validate_backtest_dataframe_allows_default_symbol_and_timeframe() -> None:
    config = BacktestDataLoadConfig(
        csv_path="ohlcv.csv",
        symbol="XAUUSD",
        timeframe="H1",
    )
    dataframe = build_ohlcv_dataframe().drop(columns=["symbol", "timeframe"])

    report = validate_backtest_dataframe(dataframe, config)

    assert report.valid is True


def test_validate_backtest_dataframe_rejects_non_numeric_price() -> None:
    config = BacktestDataLoadConfig(csv_path="ohlcv.csv")
    dataframe = build_ohlcv_dataframe()
    dataframe["close"] = dataframe["close"].astype(object)
    dataframe.loc[0, "close"] = "bad-price"

    report = validate_backtest_dataframe(dataframe, config)

    assert report.valid is False
    assert any(issue.column == "close" for issue in report.issues)


def test_prepare_backtest_dataframe_filters_sorts_and_deduplicates() -> None:
    config = BacktestDataLoadConfig(
        csv_path="ohlcv.csv",
        start_timestamp="2026-01-01T01:00:00",
        end_timestamp="2026-01-01T02:00:00",
    )
    dataframe = pd.concat(
        [build_ohlcv_dataframe(), build_ohlcv_dataframe().iloc[[2]]],
        ignore_index=True,
    )

    prepared = prepare_backtest_dataframe(dataframe, config)

    assert len(prepared) == 2
    assert prepared.iloc[0]["timestamp"] == "2026-01-01T01:00:00"
    assert prepared.iloc[1]["timestamp"] == "2026-01-01T02:00:00"


def test_dataframe_to_backtest_bars_uses_dataframe_symbol_and_timeframe() -> None:
    config = BacktestDataLoadConfig(csv_path="ohlcv.csv")
    bars = dataframe_to_backtest_bars(build_ohlcv_dataframe(), config)

    assert len(bars) == 3
    assert isinstance(bars[0], BacktestBar)
    assert bars[0].symbol == "XAUUSD"
    assert bars[0].timeframe == "H1"


def test_dataframe_to_backtest_bars_uses_default_symbol_and_timeframe() -> None:
    config = BacktestDataLoadConfig(
        csv_path="ohlcv.csv",
        symbol="XAUUSD",
        timeframe="M15",
    )
    dataframe = build_ohlcv_dataframe().drop(columns=["symbol", "timeframe"])

    bars = dataframe_to_backtest_bars(dataframe, config)

    assert bars[0].symbol == "XAUUSD"
    assert bars[0].timeframe == "M15"


def test_load_backtest_bars_from_csv_returns_valid_result(tmp_path) -> None:
    csv_path = tmp_path / "ohlcv.csv"
    build_ohlcv_dataframe().to_csv(csv_path, index=False)

    result = load_backtest_bars_from_csv(
        BacktestDataLoadConfig(csv_path=csv_path)
    )

    payload = result.to_dict()

    assert result.source_rows == 3
    assert result.loaded_rows == 3
    assert result.bars[0].timestamp == "2026-01-01T00:00:00"
    assert result.bars[-1].timestamp == "2026-01-01T02:00:00"
    assert result.metadata["symbol"] == "XAUUSD"
    assert result.metadata["timeframe"] == "H1"
    assert payload["loaded_rows"] == 3
    assert payload["bars"][0]["timestamp"] == "2026-01-01T00:00:00"


def test_load_backtest_bars_from_csv_rejects_invalid_ohlc(tmp_path) -> None:
    csv_path = tmp_path / "ohlcv.csv"
    dataframe = build_ohlcv_dataframe()
    dataframe.loc[0, "high"] = 2200.0
    dataframe.to_csv(csv_path, index=False)

    with pytest.raises(ValueError, match="high"):
        load_backtest_bars_from_csv(BacktestDataLoadConfig(csv_path=csv_path))