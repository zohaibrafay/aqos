from aqos.core import (
    AQOSException,
    ConfigurationError,
    ValidationError,
    DataError,
    FeatureError,
    ModelError,
    MemoryError,
    StrategyError,
    RiskError,
    AgentError,
    InfrastructureError,
)


def test_base_exception():

    error = AQOSException("AQOS Error")

    assert str(error) == "AQOS Error"


def test_configuration_error():

    error = ConfigurationError("Configuration failed")

    assert isinstance(error, AQOSException)


def test_validation_error():

    error = ValidationError("Validation failed")

    assert isinstance(error, AQOSException)


def test_data_error():

    error = DataError("Data failed")

    assert isinstance(error, AQOSException)


def test_feature_error():

    error = FeatureError("Feature failed")

    assert isinstance(error, AQOSException)


def test_model_error():

    error = ModelError("Model failed")

    assert isinstance(error, AQOSException)


def test_memory_error():

    error = MemoryError("Memory failed")

    assert isinstance(error, AQOSException)


def test_strategy_error():

    error = StrategyError("Strategy failed")

    assert isinstance(error, AQOSException)


def test_risk_error():

    error = RiskError("Risk failed")

    assert isinstance(error, AQOSException)


def test_agent_error():

    error = AgentError("Agent failed")

    assert isinstance(error, AQOSException)


def test_infrastructure_error():

    error = InfrastructureError("Infrastructure failed")

    assert isinstance(error, AQOSException)