"""
Unit tests for CLIInterface.
"""

from typing import Any

import pandas as pd

from aqos.interfaces import (
    APIInterface,
    CLIInterface,
    RiskInterface,
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


def test_available_commands():
    cli = CLIInterface()

    assert cli.available_commands() == [
        "backtest",
        "experiment-create",
        "health",
        "market-data",
        "predict",
        "risk",
        "strategy",
    ]


def test_execute_health():
    cli = CLIInterface()

    response = cli.execute("health")

    assert response.success is True
    assert response.message == "API interface is healthy."
    assert response.payload["status"] == "ok"


def test_execute_normalizes_command():
    cli = CLIInterface()

    response = cli.execute("MARKET_DATA")

    assert response.success is False
    assert response.message == "Symbol cannot be empty."


def test_execute_unsupported_command():
    cli = CLIInterface()

    response = cli.execute("unknown")

    assert response.success is False
    assert response.message == "Unsupported CLI command: unknown"


def test_execute_empty_command():
    cli = CLIInterface()

    response = cli.execute("")

    assert response.success is False
    assert response.message == "CLI command cannot be empty."


def test_execute_non_string_command():
    cli = CLIInterface()

    response = cli.execute(123)

    assert response.success is False
    assert response.message == "CLI command must be a string."


def test_market_data_command():
    api = APIInterface(
        market_data_service=create_market_data_service(),
    )
    cli = CLIInterface(api)

    response = cli.execute(
        command="market-data",
        arguments={
            "symbol": "XAUUSD",
            "timeframe": "H1",
        },
    )

    assert response.success is True
    assert response.message == "Market data retrieved."
    assert len(response.payload["records"]) == 2


def test_market_data_command_with_limit():
    api = APIInterface(
        market_data_service=create_market_data_service(),
    )
    cli = CLIInterface(api)

    response = cli.execute(
        command="market-data",
        arguments={
            "symbol": "XAUUSD",
            "timeframe": "H1",
            "limit": 1,
        },
    )

    assert response.success is True
    assert len(response.payload["records"]) == 1
    assert response.payload["records"][0]["timestamp"] == "2026-01-02"


def test_predict_command():
    api = APIInterface()
    api._model_service.register(
        name="dummy-model",
        model=DummyModel(),
    )

    cli = CLIInterface(api)

    response = cli.execute(
        command="predict",
        arguments={
            "model_name": "dummy-model",
            "features": [
                {
                    "open": 2000.0,
                    "close": 2005.0,
                }
            ],
        },
    )

    assert response.success is True
    assert response.message == "Prediction completed."
    assert response.payload["predictions"] == [
        "buy",
    ]


def test_predict_command_missing_model():
    cli = CLIInterface()

    response = cli.execute(
        command="predict",
        arguments={
            "model_name": "missing",
            "features": [
                {
                    "open": 2000.0,
                    "close": 2005.0,
                }
            ],
        },
    )

    assert response.success is False
    assert response.message == "Model does not exist."


def test_strategy_command():
    cli = CLIInterface()

    response = cli.execute(
        command="strategy",
        arguments={
            "market_state": {
                "regime": "bullish",
                "trend": "uptrend",
                "entry_price": 2000.0,
            },
            "metadata": {
                "symbol": "XAUUSD",
            },
        },
    )

    assert response.success is True
    assert response.message == "Strategy decision generated."
    assert response.payload["signal"] == "buy"
    assert response.metadata["symbol"] == "XAUUSD"


def test_strategy_command_missing_market_state():
    cli = CLIInterface()

    response = cli.execute(
        command="strategy",
        arguments={},
    )

    assert response.success is False
    assert response.message == "Market state cannot be empty."


def test_risk_command_without_manager():
    cli = CLIInterface()

    response = cli.execute(
        command="risk",
        arguments={
            "trade_request": {
                "symbol": "XAUUSD",
                "side": "buy",
            }
        },
    )

    assert response.success is False
    assert response.message == "Risk manager is not configured."


def test_risk_command_with_manager():
    api = APIInterface(
        risk_manager=DummyRiskManager(),
    )
    cli = CLIInterface(api)

    response = cli.execute(
        command="risk",
        arguments={
            "trade_request": {
                "symbol": "XAUUSD",
                "side": "buy",
                "account_balance": 10_000.0,
                "risk_percent": 0.01,
                "entry_price": 2000.0,
                "stop_loss_price": 1990.0,
            }
        },
    )

    assert response.success is True
    assert response.message == "Risk assessment completed."
    assert response.payload["position_size"] == 10.0


def test_backtest_command():
    cli = CLIInterface()

    response = cli.execute(
        command="backtest",
        arguments={
            "name": "run-1",
            "profits": [
                100.0,
                -50.0,
                25.0,
            ],
            "initial_balance": 10_000.0,
        },
    )

    assert response.success is True
    assert response.message == "Backtest completed."
    assert response.payload["total_profit"] == 75.0
    assert response.payload["final_balance"] == 10_075.0


def test_backtest_command_missing_name():
    cli = CLIInterface()

    response = cli.execute(
        command="backtest",
        arguments={
            "profits": [
                100.0,
            ],
            "initial_balance": 10_000.0,
        },
    )

    assert response.success is False
    assert response.message == "Backtest name cannot be empty."


def test_experiment_create_command():
    cli = CLIInterface()

    response = cli.execute(
        command="experiment-create",
        arguments={
            "name": "experiment-1",
            "description": "Baseline experiment",
            "metadata": {
                "symbol": "XAUUSD",
            },
        },
    )

    assert response.success is True
    assert response.message == "Experiment created."
    assert response.payload["name"] == "experiment-1"
    assert response.payload["status"] == "created"
    assert response.metadata["symbol"] == "XAUUSD"


def test_direct_market_data_method():
    api = APIInterface(
        market_data_service=create_market_data_service(),
    )
    cli = CLIInterface(api)

    response = cli.market_data(
        {
            "symbol": "XAUUSD",
            "timeframe": "H1",
        }
    )

    assert response.success is True
    assert len(response.payload["records"]) == 2