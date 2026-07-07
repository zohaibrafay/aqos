# AQOS Codebase Documentation

> AI Quant Operating System (AQOS)
>
> This document describes every package and file in the AQOS codebase.
> It serves as the primary reference for developers working on the project.

---

# Current Version

```text
v0.13.0-dev
```

---

# Current Progress

| Sprint | Status |
|---------|--------|
| Sprint 000 | ✅ Complete |
| Sprint 001 | ✅ Complete |
| Sprint 002 | ✅ Complete |
| Sprint 003 | ✅ Complete |
| Sprint 004 | ✅ Complete |
| Sprint 005 | ✅ Complete |
| Sprint 006 | ✅ Complete |
| Sprint 007 | ✅ Complete |
| Sprint 008 | ✅ Complete |
| Sprint 009 | ✅ Complete |
| Sprint 010 | ✅ Complete |
| Sprint 011 | ✅ Complete |
| Sprint 012 | ✅ Complete |
| Sprint 013 | ✅ Complete |
| Sprint 014 | ✅ Complete |
| Sprint 015 | ✅ Complete |

---

# Source Tree

```text
src/
└── aqos/
    ├── agents/
    ├── common/
    ├── core/
    ├── data/
    ├── evaluation/
    ├── features/
    ├── interfaces/
    ├── learning/
    ├── memory/
    ├── models/
    ├── risk/
    ├── services/
    └── strategy/
```

---

# aqos/

Root AQOS package.

| File | Purpose | Status |
|------|---------|--------|
| `__init__.py` | Root package exports | ✅ |
| `version.py` | Version metadata | ✅ |
| `main.py` | Application entry point | ✅ |
| `cli.py` | Command line interface | ✅ |

---

# core/

Responsible for AQOS infrastructure.

| File | Purpose | Status |
|------|---------|--------|
| `__init__.py` | Core package exports | ✅ |
| `version.py` | Version management | ✅ |
| `configuration.py` | Configuration management | ✅ |
| `logger.py` | Logging | ✅ |
| `exceptions.py` | Custom exceptions | ✅ |
| `bootstrap.py` | Bootstrap process | ✅ |
| `health.py` | Health checks | ✅ |

---

# data/

Responsible for market data management.

| File | Purpose | Status |
|------|---------|--------|
| `__init__.py` | Data package exports | ✅ |
| `provider.py` | Data provider interface | ✅ |
| `loader.py` | CSV data loading | ✅ |
| `validator.py` | Data validation | ✅ |
| `cleaner.py` | Data cleaning | ✅ |
| `storage.py` | Data storage | ✅ |
| `catalog.py` | Dataset catalog | ✅ |
| `pipeline.py` | Data pipeline | ✅ |

---

# features/

Responsible for feature engineering.

| File | Purpose | Status |
|------|---------|--------|
| `__init__.py` | Features package exports | ✅ |
| `base.py` | Base feature interface | ✅ |
| `technical.py` | Technical indicators | ✅ |
| `candlestick.py` | Candlestick features | ✅ |
| `price_action.py` | Price action features | ✅ |
| `statistical.py` | Statistical features | ✅ |
| `market_structure.py` | Market structure features | ✅ |
| `pipeline.py` | Feature pipeline | ✅ |

---

# strategy/

Responsible for market intelligence and trading decisions.

| File | Purpose | Status |
|------|---------|--------|
| `__init__.py` | Strategy package exports | ✅ |
| `base.py` | Base strategy interface | ✅ |
| `planner.py` | Strategy orchestrator | ✅ |
| `pattern_detector.py` | Pattern detection | ✅ |
| `market_regime.py` | Market regime detection | ✅ |
| `support_resistance.py` | Support and resistance analysis | ✅ |
| `liquidity.py` | Liquidity analysis | ✅ |
| `trend_structure.py` | Trend structure analysis | ✅ |
| `signal.py` | Signal generation | ✅ |
| `entry.py` | Entry engine | ✅ |
| `exit.py` | Exit engine | ✅ |
| `stop_loss.py` | Strategy-level stop-loss engine | ✅ |
| `take_profit.py` | Strategy-level take-profit engine | ✅ |
| `execution.py` | Execution engine | ⏳ |

---

# models/

Responsible for prediction and market representation.

| File | Purpose | Status |
|------|---------|--------|
| `__init__.py` | Models package exports | ✅ |
| `base.py` | Base model interface | ✅ |
| `dataset.py` | Dataset preparation | ✅ |
| `predictor.py` | Prediction engine | ✅ |
| `encoder.py` | Feature encoder | ✅ |
| `transformer.py` | Feature transformer | ✅ |
| `similarity.py` | Similarity engine | ✅ |
| `uncertainty.py` | Prediction uncertainty estimation | ✅ |
| `world_model.py` | Market world-state representation | ✅ |

---

# learning/

Responsible for model training and optimization.

| File | Purpose | Status |
|------|---------|--------|
| `__init__.py` | Learning package exports | ✅ |
| `trainer.py` | Model training engine | ✅ |
| `optimizer.py` | Optimizer configuration | ✅ |
| `scheduler.py` | Learning-rate scheduler | ✅ |
| `loss.py` | Loss function configuration | ✅ |
| `cross_validation.py` | Cross-validation configuration | ✅ |
| `pipeline.py` | Learning pipeline | ✅ |
| `continual.py` | Continual learning | ⏳ |
| `evaluator.py` | Training evaluation | ⏳ |
| `reinforcement.py` | Reinforcement learning | ⏳ |
| `self_supervised.py` | Self-supervised learning | ⏳ |

---

# memory/

Responsible for long-term AI memory.

| File | Purpose | Status |
|------|---------|--------|
| `__init__.py` | Memory package exports | ✅ |
| `pattern_memory.py` | Pattern memory | ✅ |
| `trade_memory.py` | Trade memory | ✅ |
| `embedding.py` | Embedding generation | ✅ |
| `vector_store.py` | Vector storage and similarity search | ✅ |
| `retriever.py` | Memory retrieval | ✅ |
| `pipeline.py` | Memory pipeline | ✅ |

---

# risk/

Responsible for risk management.

| File | Purpose | Status |
|------|---------|--------|
| `__init__.py` | Risk package exports | ✅ |
| `sizing.py` | Position sizing | ✅ |
| `exposure.py` | Exposure management | ✅ |
| `drawdown.py` | Drawdown management | ✅ |
| `constraints.py` | Risk constraints | ✅ |
| `stop_loss.py` | Risk-level stop-loss management | ✅ |
| `take_profit.py` | Risk-level take-profit management | ✅ |
| `portfolio.py` | Portfolio risk management | ✅ |
| `pipeline.py` | Risk pipeline | ✅ |

---

# evaluation/

Responsible for model, strategy, and trading evaluation.

| File | Purpose | Status |
|------|---------|--------|
| `__init__.py` | Evaluation package exports | ✅ |
| `metrics.py` | Evaluation metrics | ✅ |
| `backtest.py` | Backtesting | ✅ |
| `walk_forward.py` | Walk-forward validation | ✅ |
| `paper_trading.py` | Paper trading simulation | ✅ |
| `report.py` | Evaluation reports | ✅ |
| `pipeline.py` | Evaluation pipeline | ✅ |

---

# services/

Responsible for external integrations.

| File | Purpose | Status |
|------|---------|--------|
| `__init__.py` | Services package exports | ✅ |
| `market_data.py` | Market data services | ✅ |
| `broker.py` | Broker integrations | ✅ |
| `news.py` | News services | ✅|
| `economic_calendar.py` | Economic calendar | ✅ |
| `storage.py` | Cloud/local storage | ✅ |
| `backtest_Service.py` | backtest Service | ✅ |
| `data_Service.py` | Data Service | ✅ |
| `experiment_service` | Experiment Service | ✅ |
| `model_service` | Modal Service | ✅ |
| `strategy_service` | Strategy Service | ✅ |

---
# interfaces/

Responsible for external integrations.

| File | Purpose | Status |
|------|---------|--------|
| `__init__.py` | interfaces package exports | ✅ |
| `agent_interface.py` | Agent Interface | ✅ |
| `api_interface.py` | API Interface | ✅ |
| `cli_interface.py` | CLI Interface | ✅|
| `dashboard_interface.py` | Dashboard Interface | ✅ |
| `data_provider.py` | Data Provider Interface | ✅ |
| `memory.py` | Memory Interface | ✅ |
| `data_Service.py` | Data Interface | ✅ |
| `model.py` | Model Interface | ✅ |
| `risk.py` | Risk Interface | ✅ |
| `schemas.py` | Schema Interface | ✅ |
| `strategy` | Strategy Interface | ✅ |

---

# agents/

Responsible for external integrations.

| File | Purpose | Status |
|------|---------|--------|
| `__init__.py` | Agents package exports | ✅ |
| `base.py` | Base Agent | ✅ |
| `data_agent.py` | Data Agent | ✅ |
| `evaluation_agent.py` | Evaluation Agent | ✅|
| `execution_agent.py` | Execution Agent| ✅ |
| `market_agent.py` | Market Agent| ✅ |
| `memory_agent.py` | Memory Agent | ✅ |
| `orchestrator.py` | Orchestrator Agent | ✅ |
| `research_agent.py` | Research Agent | ✅ |
| `risk_agent.py` | Risk Agent | ✅ |
| `strategy_agent` | Strategy Agent | ✅ |

---
# common/

Responsible for external integrations.

| File | Purpose | Status |
|------|---------|--------|
| `__init__.py` | Common package exports | ✅ |
| `constants.py` | Constants | ✅ |
| `decorators.py` | Decorator | ✅ |
| `error_helpers.py` | Error Helpers | ✅|
| `helpers.py` | Helpers| ✅ |
| `id_helpers.py` | id Helper| ✅ |
| `math_utils.py` | Math Utils | ✅ |
| `serialization.py` | serialization | ✅ |
| `time_utils.py` | Time Utils | ✅ |
| `types.py` | Types | ✅ |
| `validators` | Validators | ✅ |

---


Completed modules:

```text
constants.py
validators.py
id_helpers.py
time_utils.py
serialization.py
math_utils.py
error_helpers.py
```

Reserved placeholder modules:

```text
decorators.py
enums.py
helpers.py
types.py
```

### `constants.py`

Responsibilities:

- Project constants
- Default AQOS trading constants
- Valid signal constants
- Valid side constants
- Valid order type constants
- Valid order status constants
- Valid position status constants
- Valid experiment status constants
- Valid sentiment constants
- Valid impact constants
- Valid memory type constants
- Valid timeframe constants
- OHLCV column constants
- Price column constants
- Namespace constants
- Common status constants
- Common message constants

### `validators.py`

Responsibilities:

- Validate non-empty strings
- Validate non-empty lists
- Validate non-empty dictionaries
- Validate payload dictionaries
- Validate metadata dictionaries
- Validate positive numbers
- Validate non-negative numbers
- Validate positive integers
- Validate ratios
- Validate allowed values
- Validate required keys
- Validate required columns
- Validate OHLCV columns
- Validate symbols
- Validate timeframes
- Validate signals
- Validate sides
- Validate order types
- Validate sentiments
- Validate impacts
- Validate memory types
- Validate account balances
- Validate risk percent values
- Validate prices
- Validate quantities
- Validate OHLCV records

### `id_helpers.py`

Responsibilities:

- Generate UUIDs
- Generate short IDs
- Generate prefixed IDs
- Generate compound IDs
- Generate timestamp IDs
- Normalize ID parts
- Normalize complete IDs
- Validate IDs
- Validate prefixes
- Validate separators
- Ensure unique IDs
- Check ID validity

### `time_utils.py`

Responsibilities:

- Return current UTC datetime
- Return current UTC datetime as ISO string
- Return current UTC date
- Parse datetime values
- Parse date values
- Convert datetimes to UTC
- Format datetimes
- Format dates
- Convert datetimes to timestamps
- Convert timestamps to datetimes
- Add seconds, minutes, hours, and days
- Calculate seconds, minutes, hours, and days between datetimes
- Check whether a datetime is in the past
- Check whether a datetime is in the future
- Check whether a datetime is inside a time window
- Normalize datetime values from payload dictionaries

### `serialization.py`

Responsibilities:

- Convert values to JSON-safe values
- Serialize dictionaries
- Serialize lists
- Convert values to JSON strings
- Parse JSON strings
- Safely access dictionary values
- Remove `None` values from dictionaries
- Compact dictionaries
- Flatten nested dictionaries
- Unflatten dictionaries
- Merge dictionaries
- Deep merge dictionaries

### `math_utils.py`

Responsibilities:

- Validate numeric values
- Validate numeric iterables
- Safely divide numbers
- Calculate percentage change
- Calculate percentage return
- Clamp values
- Round values
- Calculate mean
- Calculate median
- Calculate variance
- Calculate standard deviation
- Normalize values using min-max normalization
- Calculate weighted averages
- Calculate rolling means
- Calculate cumulative sums
- Calculate maximum drawdown
- Calculate profit factor
- Calculate win rate

### `error_helpers.py`

Public classes:

- `ErrorInfo`

Responsibilities:

- Normalize error codes
- Normalize error messages
- Build structured error info
- Build structured error dictionaries
- Build not-found errors
- Build validation errors
- Build type errors
- Extract exception names
- Convert exceptions to `ErrorInfo`
- Convert exceptions to dictionaries
- Format error messages
- Collect errors
- Check if errors exist
- Return first error
- Combine error messages
- Raise conditionally
- Raise if value is `None`
- Execute callables safely

### Common Package Exports

All completed common utilities are exported from:

```text
src/aqos/common/__init__.py
```


### Domain Interface Contracts

#### `data_provider.py`

Public classes:

- `DataProviderInterface`

Responsibilities:

- Define market data provider contract
- Fetch OHLCV data
- Check provider support for symbol/timeframe
- Return latest candle
- Return close prices
- Validate required OHLCV columns

#### `model.py`

Public classes:

- `ModelInterface`

Responsibilities:

- Define model contract
- Train model
- Run predictions
- Predict one row
- Save model
- Load model
- Validate features and targets

#### `strategy.py`

Public classes:

- `StrategyInterface`
- `StrategyInterfaceDecision`

Responsibilities:

- Define strategy contract
- Generate buy/sell/hold signal
- Decide entry
- Decide exit
- Build full strategy decision
- Validate market state
- Validate signal

#### `risk.py`

Public classes:

- `RiskInterface`
- `RiskInterfaceDecision`

Responsibilities:

- Define risk system contract
- Validate trade request
- Explain rejection reason
- Calculate position size
- Build full risk decision
- Validate account balance, risk percent, prices, and position size

#### `memory.py`

Public classes:

- `MemoryInterface`
- `MemoryInterfaceRecord`
- `MemoryInterfaceSearchResult`

Responsibilities:

- Define memory system contract
- Store memory records
- Retrieve memory records
- Search memory records
- Remove memory records
- Store multiple records
- Validate memory records and search results

### Interface Schemas

#### `schemas.py`

Public classes:

- `MarketDataRequest`
- `PredictionRequest`
- `PredictionResponse`
- `StrategyRequest`
- `StrategyResponse`
- `RiskRequest`
- `RiskResponse`
- `BacktestRequest`
- `BacktestResponse`
- `ExperimentRequest`
- `ExperimentResponse`
- `InterfaceEnvelope`

Responsibilities:

- Define lightweight request/response shapes
- Validate interface inputs
- Standardize interface outputs
- Provide shared schemas for API, CLI, dashboard, and agent layers

### Application-Facing Interfaces

#### `api_interface.py`

Public classes:

- `APIInterface`

Responsibilities:

- Provide API-style access to AQOS services
- Return standardized `InterfaceEnvelope` responses
- Retrieve market data
- Run predictions
- Generate strategy decisions
- Assess risk through an injected risk manager
- Run backtests
- Create experiments

#### `cli_interface.py`

Public classes:

- `CLIInterface`

Responsibilities:

- Provide CLI-style command execution
- Normalize command names
- Execute health, market-data, predict, strategy, risk, backtest, and experiment-create commands
- Return standardized `InterfaceEnvelope` responses

#### `dashboard_interface.py`

Public classes:

- `DashboardInterface`

Responsibilities:

- Provide dashboard-style read access
- Return system overview
- Return market data summary
- Return backtest summary
- Return experiment summary
- Return broker summary
- Return news summary
- Return economic calendar summary
- Return storage summary

#### `agent_interface.py`

Public classes:

- `AgentInterface`

Responsibilities:

- Provide AI-agent-style action access
- Execute health action
- Retrieve dashboard overview
- Retrieve market summary
- Generate strategy decision
- Run risk assessment
- Run backtest
- Store memory
- Recall memory

### Interfaces Package Exports

All public interface classes are exported from:



### Service Directory

```text
services/
├── __init__.py
├── backtest_service.py
├── broker.py
├── data_service.py
├── economic_calendar.py
├── experiment_service.py
├── market_data.py
├── model_service.py
├── news.py
├── storage.py
└── strategy_service.py
```

### Internal Orchestration Services

#### `data_service.py`

Provides dataset-level service operations.

Public classes:

- `DataService`
- `DatasetSnapshot`

Responsibilities:

- Register market datasets
- Validate required OHLCV columns
- Sort data by timestamp
- Retrieve datasets
- List dataset names, symbols, and timeframes
- Return latest row
- Return close prices

#### `model_service.py`

Provides model-level service operations.

Public classes:

- `ModelService`
- `ModelSnapshot`
- `PredictionSnapshot`

Responsibilities:

- Register models
- Retrieve models
- Run predictions
- Calculate confidence
- Build world state outputs

#### `strategy_service.py`

Provides strategy-level service operations.

Public classes:

- `StrategyService`
- `StrategyDecision`

Responsibilities:

- Generate buy/sell/hold signals
- Determine entry decisions
- Determine exit decisions
- Calculate strategy-level stop-loss
- Calculate strategy-level take-profit
- Build complete strategy decisions

#### `backtest_service.py`

Provides backtesting service operations.

Public classes:

- `BacktestService`
- `BacktestRun`

Responsibilities:

- Run backtests
- Store backtest results
- Retrieve backtest runs
- Generate reports
- Generate text summaries
- Select best run by profit

#### `experiment_service.py`

Provides experiment management operations.

Public classes:

- `ExperimentService`
- `ExperimentRun`

Responsibilities:

- Create experiments
- Start experiments
- Complete experiments
- Fail experiments
- Add experiment results
- Compare experiments by metrics

### External Integration-Style Services

These services are lightweight, in-memory abstractions for future real integrations.

#### `market_data.py`

Public classes:

- `MarketDataService`
- `MarketCandle`
- `MarketDataFeed`

Responsibilities:

- Store OHLCV candles
- Register symbol/timeframe feeds
- Retrieve candles
- Convert feeds to pandas DataFrames
- Return close prices
- Return latest candle

Future integrations:

- Binance
- OANDA
- MetaTrader
- Polygon
- Alpha Vantage
- Twelve Data
- Yahoo Finance

#### `broker.py`

Public classes:

- `BrokerService`
- `BrokerOrder`
- `BrokerPosition`

Responsibilities:

- Place simulated orders
- Cancel orders
- Fill orders
- Create positions
- Close positions
- Calculate realized profit

Future integrations:

- MetaTrader 5
- OANDA
- Alpaca
- Binance
- Interactive Brokers

#### `news.py`

Public classes:

- `NewsService`
- `NewsItem`

Responsibilities:

- Store financial news
- Filter news by symbol
- Filter news by source
- Filter news by sentiment
- Track impact score
- Calculate average impact score

Future integrations:

- Finnhub
- NewsAPI
- Reuters-style feeds
- Investing.com-style feeds
- ForexFactory-style feeds

#### `economic_calendar.py`

Public classes:

- `EconomicCalendarService`
- `EconomicCalendarEvent`

Responsibilities:

- Store economic events
- Filter by currency
- Filter by country
- Filter by impact
- Find upcoming events
- Find past events
- Check high-impact events inside a time window

Future integrations:

- Trading Economics
- ForexFactory-style calendar
- Investing.com-style calendar

#### `storage.py`

Public classes:

- `StorageService`
- `StorageRecord`

Responsibilities:

- Save records by namespace
- Load records
- Update metadata
- List records
- List namespaces
- Clear namespace
- Clear storage

Future integrations:

- Local filesystem
- SQLite
- PostgreSQL
- DuckDB
- Parquet
- S3
- Azure Blob Storage

### Services Package Exports

All public service classes are exported from:

```text
src/aqos/services/__init__.py
```

# agents/

Responsible for multi-agent orchestration.

| File | Purpose | Status |
|------|---------|--------|
| `__init__.py` | Agents package exports | ⏳ |
| `research_agent.py` | Research agent | ⏳ |
| `prediction_agent.py` | Prediction agent | ⏳ |
| `strategy_agent.py` | Strategy agent | ⏳ |
| `risk_agent.py` | Risk agent | ⏳ |
| `execution_agent.py` | Execution agent | ⏳ |
| `coordinator.py` | Agent coordinator | ⏳ |

---

# common/

Responsible for shared utilities.

| File | Purpose | Status |
|------|---------|--------|
| `__init__.py` | Common package exports | ⏳ |

---

# interfaces/

Responsible for system interfaces.

| File | Purpose | Status |
|------|---------|--------|
| `__init__.py` | Interfaces package exports | ⏳ |

---

# Testing Coverage

## Core

- Version
- Configuration
- Logger
- Exceptions
- Bootstrap
- Health
- CLI

## Data

- Provider
- Loader
- Validator
- Cleaner
- Storage
- Catalog
- Pipeline

## Features

- Base Feature
- Technical Indicators
- Candlestick Features
- Price Action
- Statistical Features
- Market Structure
- Feature Pipeline

## Strategy

- Base Strategy
- Pattern Detector
- Market Regime
- Support and Resistance
- Liquidity
- Trend Structure
- Signal Engine
- Entry Engine
- Exit Engine
- Strategy Stop Loss Engine
- Strategy Take Profit Engine

## Models

- Base Model
- Dataset
- Predictor
- Encoder
- Transformer
- Similarity Engine
- Uncertainty Engine
- World Model

## Learning

- Trainer
- Optimizer
- Scheduler
- Loss
- Cross Validation
- Learning Pipeline

## Memory

- Pattern Memory
- Trade Memory
- Embedding Engine
- Vector Store
- Memory Retriever
- Memory Pipeline

## Risk

- Position Sizer
- Exposure Manager
- Drawdown Manager
- Risk Constraints
- Stop Loss Manager
- Take Profit Manager
- Portfolio Risk Manager
- Risk Pipeline

## Evaluation

- Evaluation Metrics
- Backtester
- Walk-Forward Validator
- Paper Trading Engine
- Report Generator
- Evaluation Pipeline

---

## Agent Directory

```text
agents/
├── __init__.py
├── base.py
├── data_agent.py
├── evaluation_agent.py
├── execution_agent.py
├── market_agent.py
├── memory_agent.py
├── orchestrator.py
├── research_agent.py
├── risk_agent.py
└── strategy_agent.py
```

### `base.py`

Public classes:

- `AgentBase`
- `AgentTask`
- `AgentResult`

Responsibilities:

- Define shared agent task schema
- Define shared agent result schema
- Normalize agent actions
- Validate supported actions
- Provide success/failure result helpers
- Provide payload validation helpers

### `data_agent.py`

Public classes:

- `DataAgent`

Responsibilities:

- Check market data availability
- Return market data summaries
- Return latest candle
- Return close prices
- Prepare OHLCV records
- Run basic data quality checks

Supported actions:

- `health`
- `availability`
- `summary`
- `latest-candle`
- `close-prices`
- `prepare-ohlcv`
- `quality-check`

### `market_agent.py`

Public classes:

- `MarketAgent`

Responsibilities:

- Generate market snapshots
- Generate trend summaries
- Generate regime summaries
- Generate news context
- Generate economic calendar context
- Build market state payloads for downstream agents

Supported actions:

- `health`
- `snapshot`
- `trend-summary`
- `regime-summary`
- `news-context`
- `calendar-context`
- `market-state`

### `research_agent.py`

Public classes:

- `ResearchAgent`

Responsibilities:

- Generate research hypotheses
- Generate experiment plans
- Create research experiments
- Record research findings
- Generate research summaries

Supported actions:

- `health`
- `hypothesis`
- `experiment-plan`
- `create-experiment`
- `record-finding`
- `research-summary`

### `strategy_agent.py`

Public classes:

- `StrategyAgent`

Responsibilities:

- Generate strategy signals
- Generate strategy decisions
- Explain signals
- Check entries
- Check exits
- Generate strategy handoff payloads

Supported actions:

- `health`
- `signal`
- `decision`
- `explain-signal`
- `entry-check`
- `exit-check`
- `handoff`

### `risk_agent.py`

Public classes:

- `RiskAgent`

Responsibilities:

- Calculate position size
- Assess trade risk
- Approve or reject trades
- Generate rejection reasons
- Generate risk handoff payloads for execution

Supported actions:

- `health`
- `position-size`
- `assess-trade`
- `approve-trade`
- `reject-reason`
- `risk-handoff`

### `execution_agent.py`

Public classes:

- `ExecutionAgent`

Responsibilities:

- Place simulated orders
- Execute risk-approved trades
- Fill orders
- Cancel orders
- Close positions
- Retrieve order status
- Generate execution summaries

Supported actions:

- `health`
- `execute-trade`
- `place-order`
- `fill-order`
- `cancel-order`
- `close-position`
- `order-status`
- `execution-summary`

### `evaluation_agent.py`

Public classes:

- `EvaluationAgent`

Responsibilities:

- Run backtests
- Generate backtest summaries
- Compare backtests
- Grade performance
- Generate evaluation reports

Supported actions:

- `health`
- `run-backtest`
- `backtest-summary`
- `compare-backtests`
- `performance-grade`
- `evaluation-report`

### `memory_agent.py`

Public classes:

- `MemoryAgent`

Responsibilities:

- Store observations
- Recall memory records
- Retrieve memory by ID
- Forget memory records
- Generate memory summaries
- Store pattern memory
- Store trade memory

Supported actions:

- `health`
- `remember`
- `recall`
- `get-memory`
- `forget`
- `memory-summary`
- `pattern-memory`
- `trade-memory`

### `orchestrator.py`

Public classes:

- `AgentOrchestrator`

Responsibilities:

- Route tasks to agents
- Check agent health
- Run market-strategy workflow
- Run strategy-risk workflow
- Run risk-execution workflow
- Run full trade workflow
- Run research workflow
- Run backtest workflow
- Run memory workflow

Supported actions:

- `health`
- `route`
- `market-strategy-workflow`
- `strategy-risk-workflow`
- `risk-execution-workflow`
- `trade-workflow`
- `research-workflow`
- `backtest-workflow`
- `memory-workflow`

### Agents Package Exports

All public agent classes are exported from:

```text
src/aqos/agents/__init__.py
```
# Status Legend

| Symbol | Meaning |
|---------|---------|
| ✅ | Completed |
| 🚧 | In Progress |
| ⏳ | Planned |

---

# Package Export Rule

Every completed AQOS package should expose its completed public classes through its package-level `__init__.py`.

Example:

```python
from aqos.evaluation import EvaluationPipeline
```

This keeps imports clean, consistent, and stable across the codebase.

---

# Architecture Notes

## Strategy stop-loss vs Risk stop-loss

AQOS has two different stop-loss concepts:

| Module | Purpose |
|--------|---------|
| `strategy/stop_loss.py` | Strategy-level stop-loss planning |
| `risk/stop_loss.py` | Account-level stop-loss validation and risk control |

## Strategy take-profit vs Risk take-profit

AQOS has two different take-profit concepts:

| Module | Purpose |
|--------|---------|
| `strategy/take_profit.py` | Strategy-level take-profit planning |
| `risk/take_profit.py` | Risk-adjusted take-profit calculation and validation |

This separation prevents strategy logic from being mixed with portfolio/account risk controls.

---

# Maintenance Rules

1. Every new source file must be added to this document.
2. Every renamed file must be updated here.
3. Every deleted file must be removed here.
4. Package-level `__init__.py` files must export completed public classes.
5. Status must always match the repository.
6. Update this document once per completed sprint.

---

# Notes

Sprint 014 introduced a dedicated system integration testing layer.

This layer validates how completed AQOS subsystems work together.

It does not introduce a new production runtime package.

### Integration Directory

```text
tests/integration/
├── conftest.py
├── test_backtest_evaluation_integration.py
├── test_common_utilities_adoption.py
├── test_core.py
├── test_data_to_features_integration.py
├── test_feature_pipeline.py
├── test_features.py
├── test_full_trade_workflow_integration.py
├── test_market_strategy_risk_integration.py
├── test_research_memory_integration.py
├── test_services_to_agents_integration.py
└── test_system_integration_scaffold.py
```

### `conftest.py`

Responsibilities:

- Provide integration default values
- Provide sample OHLCV records
- Provide shared service fixtures
- Provide populated MarketDataService fixture
- Provide populated NewsService fixture
- Provide populated EconomicCalendarService fixture
- Provide shared agent fixtures
- Provide shared AgentOrchestrator fixture

### `test_system_integration_scaffold.py`

Responsibilities:

- Validate integration defaults
- Validate OHLCV fixtures
- Validate service fixtures
- Validate market data fixture population
- Validate news fixture population
- Validate economic calendar fixture population
- Validate agent fixtures
- Validate agent health
- Validate orchestrator health
- Validate orchestrator routing

### `test_data_to_features_integration.py`

Responsibilities:

- Validate MarketDataService output can feed FeaturePipeline
- Validate DataAgent prepared OHLCV records can feed FeaturePipeline
- Validate feature pipeline preserves market data rows
- Validate feature output can be used as market context
- Validate DataAgent quality checks before feature pipeline execution

### `test_services_to_agents_integration.py`

Responsibilities:

- Validate services are visible through agents
- Validate MarketDataService through DataAgent
- Validate NewsService through MarketAgent
- Validate EconomicCalendarService through MarketAgent
- Validate ExperimentService through ResearchAgent
- Validate StorageService through ResearchAgent
- Validate BrokerService through ExecutionAgent
- Validate BacktestService through EvaluationAgent
- Validate MemoryAgent stateful behavior

### `test_market_strategy_risk_integration.py`

Responsibilities:

- Validate MarketAgent output feeds StrategyAgent
- Validate StrategyAgent handoff feeds RiskAgent
- Validate manual Market → Strategy → Risk workflow
- Validate orchestrator market-strategy workflow
- Validate orchestrator strategy-risk workflow
- Validate hold-signal risk workflow stop
- Validate invalid risk handoff rejection behavior

### `test_full_trade_workflow_integration.py`

Responsibilities:

- Validate manual Market → Strategy → Risk → Execution workflow
- Validate orchestrator trade workflow
- Validate orchestrator risk-execution workflow
- Validate trade workflow failure when market data is missing
- Validate rejected risk handoff does not execute
- Validate trade workflow output can be stored in memory

### `test_backtest_evaluation_integration.py`

Responsibilities:

- Validate EvaluationAgent runs backtests
- Validate EvaluationAgent stores backtest results in BacktestService
- Validate EvaluationAgent summaries
- Validate EvaluationAgent reports
- Validate EvaluationAgent comparison workflow
- Validate duplicate backtest handling
- Validate orchestrator backtest workflow
- Validate evaluation output can be stored in memory

### `test_research_memory_integration.py`

Responsibilities:

- Validate research hypotheses can be stored in memory
- Validate experiment plans can be stored in memory
- Validate research findings can feed memory
- Validate research summaries can be stored in memory
- Validate orchestrator research workflow can feed memory
- Validate orchestrator memory workflow can store research content
- Validate memory type filtering

### `test_common_utilities_adoption.py`

Responsibilities:

- Validate common constants match integration defaults
- Validate common validators accept real OHLCV fixtures
- Validate common validators accept market, strategy, and risk outputs
- Validate ID helpers can build workflow IDs
- Validate time utilities parse fixture datetimes
- Validate serialization helpers process agent and orchestrator outputs
- Validate math helpers process backtest-like values
- Validate error helpers format agent failures
- Validate safe execution helpers
- Validate common utilities can serialize full trade workflow output

`CODEBASE.md` is the authoritative inventory of the AQOS repository.

The Evaluation subsystem was completed in Sprint 009. It now includes evaluation metrics, lightweight backtesting, walk-forward validation, paper trading simulation, evaluation reports, and a unified evaluation pipeline.

The current Evaluation implementation is intentionally lightweight and deterministic. Later phases will add realistic backtesting features such as slippage, commissions, broker fill simulation, benchmark comparison, Monte Carlo analysis, advanced performance metrics, and visual reporting.

Files such as `continual.py`, `evaluator.py`, `reinforcement.py`, and `self_supervised.py` remain intentionally deferred learning modules. They will be implemented only after their prerequisite systems are available.

Whenever the repository structure changes, this document must be updated before a sprint is considered complete.