from __future__ import annotations

from pathlib import Path

import pandas as pd
import pytest

from aqos.backtesting.contracts import BacktestBar
from aqos.model_training.baseline_signal_model import (
    BaselineSignalModel,
    SignalModelTrainingConfig,
)
from aqos.model_training.model_evaluation import ModelPromotionStage
from aqos.model_training.model_promotion import ModelPromotionStatus
from aqos.model_training.model_promotion_registry import (
    ModelPromotionRegistry,
    ModelPromotionRegistryEntry,
    write_model_promotion_registry,
)
from aqos.model_training.model_versioning import (
    build_model_version_metadata,
    write_model_version_metadata,
)
from aqos.model_training.ohlcv_feature_builder import build_ohlcv_ml_features


BACKTEST_MODEL_FEATURE_COLUMNS = (
    "return_1",
    "return_3",
    "sma_distance_5",
    "candle_body_ratio",
)

BACKTEST_MODEL_NAME = "backtest_signal_model"
BACKTEST_MODEL_CREATED_AT = "2026-01-01T00:00:00+00:00"


def build_backtest_model_ohlcv(rows: int = 80) -> pd.DataFrame:
    """
    Deterministic alternating OHLCV series.

    Every even bar rises by 5.0 and every odd bar falls by 3.0, so the direction
    of the next bar is fully learnable from the current bar return.
    """

    records = []
    close = 2000.0

    for index in range(rows):
        step = 5.0 if index % 2 == 0 else -3.0
        open_price = close
        close = open_price + step

        records.append(
            {
                "timestamp": (
                    f"2026-01-{(index // 24) + 1:02d}T{index % 24:02d}:00:00"
                ),
                "symbol": "XAUUSD",
                "timeframe": "H1",
                "open": open_price,
                "high": max(open_price, close) + 1.0,
                "low": min(open_price, close) - 1.0,
                "close": close,
                "volume": 1000.0 + index,
            }
        )

    return pd.DataFrame(records)


def build_backtest_model_training_dataset(ohlcv: pd.DataFrame) -> pd.DataFrame:
    features = build_ohlcv_ml_features(ohlcv)
    next_close = features["close"].shift(-1)

    dataset = features.loc[:, list(BACKTEST_MODEL_FEATURE_COLUMNS)].copy()
    dataset["target"] = (next_close > features["close"]).map(
        {True: "buy", False: "sell"}
    )

    return dataset.iloc[:-1].reset_index(drop=True)


def build_backtest_bars_from_dataframe(
    dataframe: pd.DataFrame,
) -> tuple[BacktestBar, ...]:
    return tuple(
        BacktestBar(
            timestamp=str(row["timestamp"]),
            symbol=str(row["symbol"]),
            timeframe=str(row["timeframe"]),
            open=float(row["open"]),
            high=float(row["high"]),
            low=float(row["low"]),
            close=float(row["close"]),
            volume=float(row["volume"]),
        )
        for _, row in dataframe.iterrows()
    )


@pytest.fixture
def backtest_model_ohlcv() -> pd.DataFrame:
    return build_backtest_model_ohlcv()


@pytest.fixture
def backtest_model_bars(backtest_model_ohlcv: pd.DataFrame) -> tuple[BacktestBar, ...]:
    return build_backtest_bars_from_dataframe(backtest_model_ohlcv)


@pytest.fixture
def backtest_model_data_path(
    tmp_path: Path,
    backtest_model_ohlcv: pd.DataFrame,
) -> Path:
    data_path = tmp_path / "data" / "backtest_model_bars.csv"
    data_path.parent.mkdir(parents=True, exist_ok=True)
    backtest_model_ohlcv.to_csv(data_path, index=False)
    return data_path


@pytest.fixture
def trained_backtest_model(
    backtest_model_ohlcv: pd.DataFrame,
) -> BaselineSignalModel:
    model = BaselineSignalModel(
        config=SignalModelTrainingConfig(
            random_state=42,
            n_estimators=25,
            max_depth=4,
        )
    )
    model.train(
        build_backtest_model_training_dataset(backtest_model_ohlcv),
        feature_columns=BACKTEST_MODEL_FEATURE_COLUMNS,
    )

    return model


@pytest.fixture
def trained_backtest_model_path(
    tmp_path: Path,
    trained_backtest_model: BaselineSignalModel,
) -> Path:
    return trained_backtest_model.save(
        tmp_path / "models" / "backtest_signal_model.joblib"
    )


@pytest.fixture
def promoted_backtest_model_files(
    tmp_path: Path,
    trained_backtest_model_path: Path,
) -> dict[str, object]:
    metadata = build_model_version_metadata(
        model_name=BACKTEST_MODEL_NAME,
        model_path=trained_backtest_model_path,
        created_at_utc=BACKTEST_MODEL_CREATED_AT,
        promotion_stage=ModelPromotionStage.PAPER_TRADING.value,
        is_promotion_ready=True,
    )

    metadata_path = write_model_version_metadata(
        tmp_path / "models" / "model_version_metadata.json",
        metadata,
    )

    entry = ModelPromotionRegistryEntry(
        promotion_id="backtest_signal_model_paper_trading_20260101",
        created_at_utc=BACKTEST_MODEL_CREATED_AT,
        model_name=metadata.model_name,
        model_id=metadata.model_id,
        model_version=metadata.model_version,
        target_stage=ModelPromotionStage.PAPER_TRADING,
        status=ModelPromotionStatus.APPROVED,
        approved=True,
        model_artifact_path=trained_backtest_model_path.as_posix(),
        model_version_metadata_path=metadata_path.as_posix(),
    )

    registry_path = write_model_promotion_registry(
        tmp_path / "models" / "model_promotion_registry.json",
        ModelPromotionRegistry(promotions=(entry,)),
    )

    return {
        "model_path": trained_backtest_model_path,
        "metadata_path": metadata_path,
        "registry_path": registry_path,
        "model_name": metadata.model_name,
        "model_id": metadata.model_id,
        "model_version": metadata.model_version,
    }


@pytest.fixture
def unpromoted_backtest_model_files(
    tmp_path: Path,
    trained_backtest_model_path: Path,
) -> dict[str, object]:
    metadata = build_model_version_metadata(
        model_name=BACKTEST_MODEL_NAME,
        model_path=trained_backtest_model_path,
        created_at_utc=BACKTEST_MODEL_CREATED_AT,
        promotion_stage=ModelPromotionStage.RESEARCH.value,
        is_promotion_ready=False,
    )

    metadata_path = write_model_version_metadata(
        tmp_path / "models" / "unpromoted_model_version_metadata.json",
        metadata,
    )

    registry_path = write_model_promotion_registry(
        tmp_path / "models" / "empty_model_promotion_registry.json",
        ModelPromotionRegistry(),
    )

    return {
        "model_path": trained_backtest_model_path,
        "metadata_path": metadata_path,
        "registry_path": registry_path,
        "model_name": metadata.model_name,
        "model_id": metadata.model_id,
        "model_version": metadata.model_version,
    }
