"""
AQOS Interfaces Package.
"""

from aqos.interfaces.agent_interface import AgentInterface
from aqos.interfaces.api_interface import APIInterface
from aqos.interfaces.cli_interface import CLIInterface
from aqos.interfaces.dashboard_interface import DashboardInterface
from aqos.interfaces.data_provider import DataProviderInterface
from aqos.interfaces.memory import (
    MemoryInterface,
    MemoryInterfaceRecord,
    MemoryInterfaceSearchResult,
)
from aqos.interfaces.model import ModelInterface
from aqos.interfaces.risk import (
    RiskInterface,
    RiskInterfaceDecision,
)
from aqos.interfaces.schemas import (
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
from aqos.interfaces.strategy import (
    StrategyInterface,
    StrategyInterfaceDecision,
)

__all__ = [
    "APIInterface",
    "AgentInterface",
    "BacktestRequest",
    "BacktestResponse",
    "CLIInterface",
    "DashboardInterface",
    "DataProviderInterface",
    "ExperimentRequest",
    "ExperimentResponse",
    "InterfaceEnvelope",
    "MarketDataRequest",
    "MemoryInterface",
    "MemoryInterfaceRecord",
    "MemoryInterfaceSearchResult",
    "ModelInterface",
    "PredictionRequest",
    "PredictionResponse",
    "RiskInterface",
    "RiskInterfaceDecision",
    "RiskRequest",
    "RiskResponse",
    "StrategyInterface",
    "StrategyInterfaceDecision",
    "StrategyRequest",
    "StrategyResponse",
]