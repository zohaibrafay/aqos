"""
Data → Features integration tests.

Validates that market data prepared by AQOS data services can flow into
the feature engineering pipeline.
"""

import pandas as pd

from aqos.features import (
    CandlestickFeatures,
    FeaturePipeline,
    MarketStructureFeatures,
    PriceActionFeatures,
    StatisticalFeatures,
    TechnicalIndicators,
)
from aqos.services import MarketDataService


def create_feature_pipeline() -> FeaturePipeline:
    """
    Create the full feature engineering pipeline.
    """

    pipeline = FeaturePipeline()

    pipeline.add(TechnicalIndicators())
    pipeline.add(CandlestickFeatures())
    pipeline.add(PriceActionFeatures())
    pipeline.add(StatisticalFeatures())
    pipeline.add(MarketStructureFeatures())

    return pipeline


def test_market_data_service_to_feature_pipeline(
    market_data_service: MarketDataService,
    integration_symbol: str,
    integration_timeframe: str,
):
    dataframe = market_data_service.to_dataframe(
        symbol=integration_symbol,
        timeframe=integration_timeframe,
    )

    pipeline = create_feature_pipeline()

    result = pipeline.run(dataframe)

    expected_columns = [
        "sma_10",
        "ema_10",
        "returns",
        "body",
        "body_size",
        "upper_wick",
        "lower_wick",
        "price_range",
        "rolling_mean_10",
        "rolling_std_10",
        "rolling_min_10",
        "rolling_max_10",
        "z_score",
        "swing_high",
        "swing_low",
        "trend",
    ]

    for column in expected_columns:
        assert column in result.columns

    assert len(result) == len(dataframe)
    assert result["close"].tolist() == [
        2005.0,
        2015.0,
        2025.0,
    ]


def test_data_agent_prepared_ohlcv_to_feature_pipeline(
    data_agent,
    integration_symbol: str,
    integration_timeframe: str,
):
    prepared_result = data_agent.execute(
        action="prepare-ohlcv",
        payload={
            "symbol": integration_symbol,
            "timeframe": integration_timeframe,
        },
    )

    assert prepared_result.success is True

    dataframe = pd.DataFrame(prepared_result.data["records"])

    pipeline = create_feature_pipeline()

    result = pipeline.run(dataframe)

    assert "sma_10" in result.columns
    assert "body" in result.columns
    assert "price_range" in result.columns
    assert "rolling_mean_10" in result.columns
    assert "trend" in result.columns
    assert len(result) == 3


def test_feature_pipeline_preserves_market_data_rows(
    market_data_service: MarketDataService,
    integration_symbol: str,
    integration_timeframe: str,
):
    dataframe = market_data_service.to_dataframe(
        symbol=integration_symbol,
        timeframe=integration_timeframe,
    )

    pipeline = create_feature_pipeline()

    result = pipeline.run(dataframe)

    assert len(result) == 3
    assert result.iloc[0]["open"] == 2000.0
    assert result.iloc[1]["close"] == 2015.0
    assert result.iloc[2]["volume"] == 1500.0


def test_feature_pipeline_output_can_be_used_as_market_context(
    market_data_service: MarketDataService,
    integration_symbol: str,
    integration_timeframe: str,
):
    dataframe = market_data_service.to_dataframe(
        symbol=integration_symbol,
        timeframe=integration_timeframe,
    )

    pipeline = create_feature_pipeline()

    result = pipeline.run(dataframe)

    latest_row = result.iloc[-1].to_dict()

    assert latest_row["close"] == 2025.0
    assert "sma_10" in latest_row
    assert "ema_10" in latest_row
    assert "returns" in latest_row
    assert "trend" in latest_row


def test_data_quality_check_before_feature_pipeline(
    data_agent,
    integration_symbol: str,
    integration_timeframe: str,
):
    quality_result = data_agent.execute(
        action="quality-check",
        payload={
            "symbol": integration_symbol,
            "timeframe": integration_timeframe,
        },
    )

    assert quality_result.success is True
    assert quality_result.data["valid"] is True
    assert quality_result.data.get("valid") is True

    prepared_result = data_agent.execute(
        action="prepare-ohlcv",
        payload={
            "symbol": integration_symbol,
            "timeframe": integration_timeframe,
        },
    )

    dataframe = pd.DataFrame(prepared_result.data["records"])

    pipeline = create_feature_pipeline()
    result = pipeline.run(dataframe)

    assert len(result) == 3
    assert "price_range" in result.columns