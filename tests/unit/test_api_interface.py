"""
Unit tests for APIInterface.
"""

from typing import Any

import pandas as pd
import pytest

from aqos.interfaces import (
    APIInterface,
    BacktestRequest,
    ExperimentRequest,
    MarketDataRequest,
    PredictionRequest,
    RiskInterface,
    RiskRequest,
    StrategyRequest,
)
from aqos.models import BaseModel
from aqos.services import MarketDataService


class DummyModel(BaseModel):

    @property
    def name(self) -> str:
        return "dummy-model"

    def fit(
        self,
        features: pd.DataFrame,
        target: pd.Series,
    ) -> None:
        return None

    def predict(
        self,
        features: pd.DataFrame,
    ) -> pd.Series:
        return pd.Series(
            [
                "buy"
                for _index in range(len(features))
            ]
        )

    def save(
        self,
        path: str,
    ) -> None:
        return None

    @classmethod
    def load(
        cls,
        path: str,
    ):
        return cls()


class DummyRiskManager(RiskInterface):

    @property
    def name(self) -> str:
        return "dummy-risk-manager"

    def validate_trade(
        self,
        trade_request: dict[str, Any],
    ) -> bool:
        return trade_request["side"] in {"buy", "sell"}

    def rejection_reason(
        self,
        trade_request: dict[str, Any],
    ) -> str:
        return "Trade rejected."

    def calculate_position_size(
        self,
        account_balance: float,
        risk_percent: float,
        entry_price: float,
        stop_loss_price: float,
    ) -> float:
        return 10.0


def create_market_data_service() -> MarketDataService:
    service = MarketDataService()

    candle_1 = service.create_candle(
        timestamp="2026-01-01",
        open_price=2000.0,
        high_price=2010.0,
        low_price=1990.0,
        close_price=2005.0,
        volume=1000.0,
    )
    candle_2 = service.create_candle(
        timestamp="2026-01-02",
        open_price=2010.0,
        high_price=2020.0,
        low_price=2005.0,
        close_price=2015.0,
        volume=1500.0,
    )

    service.register_feed(
        symbol="XAUUSD",
        timeframe="H1",
        candles=[
            candle_1,
            candle_2,
        ],
    )

    return service


def test_health():
    api = APIInterface()

    response = api.health()

    assert response.success is True
    assert response.message == "API interface is healthy."
    assert response.payload["status"] == "ok"


def test_get_market_data():
    api = APIInterface(
        market_data_service=create_market_data_service(),
    )

    response = api.get_market_data(
        MarketDataRequest(
            symbol="XAUUSD",
            timeframe="H1",
        )
    )

    assert response.success is True
    assert response.message == "Market data retrieved."
    assert len(response.payload["records"]) == 2


def test_get_market_data_with_limit():
    api = APIInterface(
        market_data_service=create_market_data_service(),
    )

    response = api.get_market_data(
        MarketDataRequest(
            symbol="XAUUSD",
            timeframe="H1",
            limit=1,
        )
    )

    assert response.success is True
    assert len(response.payload["records"]) == 1
    assert response.payload["records"][0]["timestamp"] == "2026-01-02"


def test_get_missing_market_data_returns_failure():
    api = APIInterface()

    response = api.get_market_data(
        MarketDataRequest(
            symbol="XAUUSD",
            timeframe="H1",
        )
    )

    assert response.success is False
    assert response.message == "Market data feed does not exist."


def test_run_prediction():
    api = APIInterface()

    api._model_service.register(
        name="dummy-model",
        model=DummyModel(),
    )

    response = api.run_prediction(
        PredictionRequest(
            model_name="dummy-model",
            features=[
                {
                    "open": 2000.0,
                    "close": 2005.0,
                },
                {
                    "open": 2010.0,
                    "close": 2015.0,
                },
            ],
        )
    )

    assert response.success is True
    assert response.message == "Prediction completed."
    assert response.payload["model_name"] == "dummy-model"
    assert response.payload["predictions"] == [
        "buy",
        "buy",
    ]


def test_run_prediction_missing_model_returns_failure():
    api = APIInterface()

    response = api.run_prediction(
        PredictionRequest(
            model_name="missing",
            features=[
                {
                    "open": 2000.0,
                    "close": 2005.0,
                }
            ],
        )
    )

    assert response.success is False
    assert response.message == "Model does not exist."


def test_generate_strategy_decision():
    api = APIInterface()

    response = api.generate_strategy_decision(
        StrategyRequest(
            market_state={
                "regime": "bullish",
                "trend": "uptrend",
                "entry_price": 2000.0,
            },
            metadata={
                "symbol": "XAUUSD",
            },
        )
    )

    assert response.success is True
    assert response.message == "Strategy decision generated."
    assert response.payload["signal"] == "buy"
    assert response.payload["should_enter"] is True
    assert response.metadata["symbol"] == "XAUUSD"


def test_generate_strategy_decision_missing_key_returns_failure():
    api = APIInterface()

    response = api.generate_strategy_decision(
        StrategyRequest(
            market_state={
                "trend": "uptrend",
            }
        )
    )

    assert response.success is False
    assert response.message == "Missing required key: regime"


def test_assess_risk_without_manager_returns_failure():
    api = APIInterface()

    response = api.assess_risk(
        RiskRequest(
            trade_request={
                "symbol": "XAUUSD",
                "side": "buy",
            }
        )
    )

    assert response.success is False
    assert response.message == "Risk manager is not configured."


def test_assess_risk_with_manager():
    api = APIInterface(
        risk_manager=DummyRiskManager(),
    )

    response = api.assess_risk(
        RiskRequest(
            trade_request={
                "symbol": "XAUUSD",
                "side": "buy",
                "account_balance": 10_000.0,
                "risk_percent": 0.01,
                "entry_price": 2000.0,
                "stop_loss_price": 1990.0,
            }
        )
    )

    assert response.success is True
    assert response.message == "Risk assessment completed."
    assert response.payload["allowed"] is True
    assert response.payload["position_size"] == 10.0


def test_run_backtest():
    api = APIInterface()

    response = api.run_backtest(
        BacktestRequest(
            name="run-1",
            profits=[
                100.0,
                -50.0,
                25.0,
            ],
            initial_balance=10_000.0,
        )
    )

    assert response.success is True
    assert response.message == "Backtest completed."
    assert response.payload["name"] == "run-1"
    assert response.payload["total_profit"] == 75.0
    assert response.payload["final_balance"] == 10_075.0


def test_create_experiment():
    api = APIInterface()

    response = api.create_experiment(
        ExperimentRequest(
            name="experiment-1",
            description="Baseline experiment",
            metadata={
                "symbol": "XAUUSD",
            },
        )
    )

    assert response.success is True
    assert response.message == "Experiment created."
    assert response.payload["name"] == "experiment-1"
    assert response.payload["status"] == "created"
    assert response.metadata["symbol"] == "XAUUSD"


def test_create_duplicate_experiment_returns_failure():
    api = APIInterface()

    request = ExperimentRequest(
        name="experiment-1",
    )

    api.create_experiment(request)
    response = api.create_experiment(request)

    assert response.success is False
    assert response.message == "Experiment already exists."


def test_invalid_request_type():
    api = APIInterface()

    with pytest.raises(TypeError):
        api.get_market_data("not-a-request")