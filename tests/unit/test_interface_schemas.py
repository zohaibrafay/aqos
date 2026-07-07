"""
Unit tests for interface schemas.
"""

import pytest

from aqos.interfaces import (
    BacktestRequest,
    BacktestResponse,
    ExperimentRequest,
    ExperimentResponse,
    InterfaceEnvelope,
    MarketDataRequest,
    PredictionRequest,
    PredictionResponse,
    RiskRequest,
    RiskResponse,
    StrategyRequest,
    StrategyResponse,
)


def test_market_data_request():
    request = MarketDataRequest(
        symbol="XAUUSD",
        timeframe="H1",
        limit=100,
        metadata={"source": "local"},
    )

    assert request.symbol == "XAUUSD"
    assert request.timeframe == "H1"
    assert request.limit == 100
    assert request.metadata["source"] == "local"


def test_market_data_request_rejects_empty_symbol():
    with pytest.raises(ValueError):
        MarketDataRequest(
            symbol="",
            timeframe="H1",
        )


def test_market_data_request_rejects_empty_timeframe():
    with pytest.raises(ValueError):
        MarketDataRequest(
            symbol="XAUUSD",
            timeframe="",
        )


def test_market_data_request_rejects_invalid_limit():
    with pytest.raises(ValueError):
        MarketDataRequest(
            symbol="XAUUSD",
            timeframe="H1",
            limit=0,
        )


def test_prediction_request():
    request = PredictionRequest(
        model_name="model-1",
        features=[
            {
                "open": 2000.0,
                "close": 2005.0,
            }
        ],
    )

    assert request.model_name == "model-1"
    assert request.features[0]["close"] == 2005.0


def test_prediction_request_rejects_empty_model_name():
    with pytest.raises(ValueError):
        PredictionRequest(
            model_name="",
            features=[
                {
                    "close": 2005.0,
                }
            ],
        )


def test_prediction_request_rejects_empty_features():
    with pytest.raises(ValueError):
        PredictionRequest(
            model_name="model-1",
            features=[],
        )


def test_prediction_response():
    response = PredictionResponse(
        model_name="model-1",
        predictions=[
            "buy",
        ],
    )

    assert response.model_name == "model-1"
    assert response.predictions == ["buy"]


def test_prediction_response_rejects_empty_predictions():
    with pytest.raises(ValueError):
        PredictionResponse(
            model_name="model-1",
            predictions=[],
        )


def test_strategy_request():
    request = StrategyRequest(
        market_state={
            "trend": "uptrend",
        }
    )

    assert request.market_state["trend"] == "uptrend"


def test_strategy_request_rejects_empty_market_state():
    with pytest.raises(ValueError):
        StrategyRequest(
            market_state={},
        )


def test_strategy_response():
    response = StrategyResponse(
        signal="buy",
        should_enter=True,
        should_exit=False,
        metadata={
            "symbol": "XAUUSD",
        },
    )

    assert response.signal == "buy"
    assert response.should_enter is True
    assert response.should_exit is False
    assert response.metadata["symbol"] == "XAUUSD"


def test_strategy_response_rejects_invalid_signal():
    with pytest.raises(ValueError):
        StrategyResponse(
            signal="invalid",
            should_enter=False,
            should_exit=False,
        )


def test_strategy_response_rejects_invalid_boolean():
    with pytest.raises(TypeError):
        StrategyResponse(
            signal="buy",
            should_enter="yes",
            should_exit=False,
        )


def test_risk_request():
    request = RiskRequest(
        trade_request={
            "symbol": "XAUUSD",
            "side": "buy",
        }
    )

    assert request.trade_request["symbol"] == "XAUUSD"


def test_risk_request_rejects_empty_trade_request():
    with pytest.raises(ValueError):
        RiskRequest(
            trade_request={},
        )


def test_risk_response_allowed():
    response = RiskResponse(
        allowed=True,
        reason="Trade allowed.",
        position_size=10.0,
    )

    assert response.allowed is True
    assert response.reason == "Trade allowed."
    assert response.position_size == 10.0


def test_risk_response_rejected():
    response = RiskResponse(
        allowed=False,
        reason="Risk too high.",
    )

    assert response.allowed is False
    assert response.reason == "Risk too high."
    assert response.position_size is None


def test_risk_response_rejects_empty_reason():
    with pytest.raises(ValueError):
        RiskResponse(
            allowed=False,
            reason="",
        )


def test_risk_response_rejects_invalid_position_size():
    with pytest.raises(ValueError):
        RiskResponse(
            allowed=True,
            reason="Trade allowed.",
            position_size=0,
        )


def test_backtest_request():
    request = BacktestRequest(
        name="run-1",
        profits=[
            100.0,
            -50.0,
        ],
        initial_balance=10_000.0,
    )

    assert request.name == "run-1"
    assert request.profits == [
        100.0,
        -50.0,
    ]
    assert request.initial_balance == 10_000.0


def test_backtest_request_rejects_empty_name():
    with pytest.raises(ValueError):
        BacktestRequest(
            name="",
            profits=[
                100.0,
            ],
            initial_balance=10_000.0,
        )


def test_backtest_request_rejects_empty_profits():
    with pytest.raises(ValueError):
        BacktestRequest(
            name="run-1",
            profits=[],
            initial_balance=10_000.0,
        )


def test_backtest_request_rejects_invalid_initial_balance():
    with pytest.raises(ValueError):
        BacktestRequest(
            name="run-1",
            profits=[
                100.0,
            ],
            initial_balance=0,
        )


def test_backtest_response():
    response = BacktestResponse(
        name="run-1",
        total_profit=150.0,
        final_balance=10_150.0,
        win_rate=0.75,
    )

    assert response.name == "run-1"
    assert response.total_profit == 150.0
    assert response.final_balance == 10_150.0
    assert response.win_rate == 0.75


def test_backtest_response_rejects_invalid_win_rate():
    with pytest.raises(ValueError):
        BacktestResponse(
            name="run-1",
            total_profit=150.0,
            final_balance=10_150.0,
            win_rate=1.1,
        )


def test_experiment_request():
    request = ExperimentRequest(
        name="experiment-1",
        description="Baseline experiment",
        metadata={
            "symbol": "XAUUSD",
        },
    )

    assert request.name == "experiment-1"
    assert request.description == "Baseline experiment"
    assert request.metadata["symbol"] == "XAUUSD"


def test_experiment_request_rejects_empty_name():
    with pytest.raises(ValueError):
        ExperimentRequest(
            name="",
        )


def test_experiment_response():
    response = ExperimentResponse(
        name="experiment-1",
        status="completed",
        results={
            "total_profit": 100.0,
        },
    )

    assert response.name == "experiment-1"
    assert response.status == "completed"
    assert response.results["total_profit"] == 100.0


def test_experiment_response_rejects_invalid_status():
    with pytest.raises(ValueError):
        ExperimentResponse(
            name="experiment-1",
            status="invalid",
        )


def test_interface_envelope():
    envelope = InterfaceEnvelope(
        success=True,
        message="Request completed.",
        payload={
            "signal": "buy",
        },
        metadata={
            "source": "api",
        },
    )

    assert envelope.success is True
    assert envelope.message == "Request completed."
    assert envelope.payload["signal"] == "buy"
    assert envelope.metadata["source"] == "api"


def test_interface_envelope_rejects_invalid_success():
    with pytest.raises(TypeError):
        InterfaceEnvelope(
            success="true",
            message="Request completed.",
        )


def test_interface_envelope_rejects_empty_message():
    with pytest.raises(ValueError):
        InterfaceEnvelope(
            success=True,
            message="",
        )