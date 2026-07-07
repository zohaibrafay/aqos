# AQOS Architecture

> AI Quant Operating System (AQOS)
>
> This document describes the overall software architecture of AQOS,
> the responsibility of every module,
> system data flow,
> package dependencies,
> and future architectural evolution.

---

# Project Information

| Item | Value |
|------|------|
| Project | AI Quant Operating System (AQOS) |
| Author | Zohaib Hussain |
| Architecture Version | 1.5 |
| Current Phase | Phase 1 – Foundation |
| Status | Active Development |

---

# Architecture Principles

AQOS follows the following engineering principles:

- Clean Architecture
- Modular Design
- Separation of Concerns
- SOLID Principles
- DRY
- KISS
- Domain-Driven Design (DDD)
- Test-Driven Development (where practical)
- Extensibility
- Scalability
- Explainability
- Reproducibility

---

# High-Level Architecture

```text

                    +----------------------+
                    |   External Sources   |
                    +----------+-----------+
                               |
                               |
                    +----------v-----------+
                    |       Services       |
                    +----------+-----------+
                               |
                               |
                    +----------v-----------+
                    |        Data          |
                    +----------+-----------+
                               |
                               |
                    +----------v-----------+
                    |      Features        |
                    +----------+-----------+
                               |
                               |
                    +----------v-----------+
                    |      Strategy        |
                    +----------+-----------+
                               |
                               |
                    +----------v-----------+
                    |       Models         |
                    +----------+-----------+
                               |
                               |
                    +----------v-----------+
                    |      Learning        |
                    +----------+-----------+
                               |
                               |
                    +----------v-----------+
                    |       Memory         |
                    +----------+-----------+
                               |
                               |
                    +----------v-----------+
                    |        Risk          |
                    +----------+-----------+
                               |
                               |
                    +----------v-----------+
                    |     Evaluation       |
                    +----------+-----------+
                               |
                               |
                    +----------v-----------+
                    |       Agents         |
                    +----------+-----------+
                               |
                               |
                    +----------v-----------+
                    |     Broker/API       |
                    +----------------------+

```

---

# Package Structure

```text

src/
└── aqos/
│
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

# Package Responsibilities

---

## core/

Responsible for application lifecycle.

Contains

- Version
- Configuration
- Logger
- Exceptions
- Bootstrap
- CLI
- Health Check

Status

✅ Completed

---

## common/

Reusable utilities shared across AQOS.

Examples

- Constants
- Enums
- Helpers
- Validators
- Utilities

Status

Planned

---

## interfaces/

Contains abstract interfaces used throughout AQOS.

Examples

- BaseModel
- BaseStrategy
- BaseTrainer
- BaseService

Status

Planned

---

## services/

Responsible for external integrations.

Examples

- Market Data APIs
- Broker APIs
- News APIs
- Economic Calendar
- Storage Services

Status

Planned

---

## data/

Responsible for market data.

Includes

- Provider
- Loader
- Validator
- Cleaner
- Storage
- Catalog
- Pipeline

Status

✅ Completed

---

## features/

Responsible for feature engineering.

Includes

- Base Feature
- Technical Indicators
- Candlestick Features
- Price Action
- Statistical Features
- Market Structure
- Feature Pipeline

Status

✅ Completed

---

## strategy/

Responsible for market intelligence and trading logic.

Current Modules

- base.py
- planner.py
- pattern_detector.py
- market_regime.py
- support_resistance.py
- liquidity.py
- trend_structure.py
- signal.py
- entry.py
- exit.py
- stop_loss.py
- take_profit.py
- execution.py

Completed

- Base Strategy
- Pattern Detector
- Market Regime
- Support & Resistance
- Liquidity
- Trend Structure
- Signal Engine
- Entry Engine
- Exit Engine
- Strategy Stop Loss Engine
- Strategy Take Profit Engine

Remaining / Deferred

- Strategy Planner
- Execution Engine

Current Status

✅ Foundation Completed

Future Expansion

- Smart Money Concepts
- ICT
- BOS
- CHOCH
- Order Blocks
- Fair Value Gaps
- Equal Highs
- Equal Lows
- Multi-Timeframe Bias
- Liquidity Sweeps

---

## models/

Prediction models and market representation.

Current Modules

- base.py
- dataset.py
- encoder.py
- predictor.py
- similarity.py
- transformer.py
- uncertainty.py
- world_model.py

Completed

- Base Model
- Dataset
- Encoder
- Predictor
- Similarity Engine
- Transformer
- Uncertainty Engine
- World Model

Status

✅ Completed

Future Expansion

- LSTM
- Transformer
- Temporal Fusion Transformer
- XGBoost
- LightGBM
- CatBoost
- Ensemble Models
- ONNX Export
- Model Registry
- GPU Inference

---

## learning/

Training engine.

Current Modules

- trainer.py
- optimizer.py
- scheduler.py
- loss.py
- cross_validation.py
- pipeline.py
- continual.py
- evaluator.py
- reinforcement.py
- self_supervised.py

Completed

- Trainer
- Optimizer
- Scheduler
- Loss
- Cross Validation
- Learning Pipeline

Deferred

- Continual Learning
- Training Evaluator
- Reinforcement Learning
- Self-Supervised Learning

Status

✅ Foundation Completed

Future Expansion

- Online Learning
- Incremental Learning
- Reinforcement Learning
- Self-Supervised Pretraining
- Hyperparameter Search
- Experiment Tracking
- Distributed Training

---

## memory/

Knowledge and pattern memory.

Current Modules

- pattern_memory.py
- trade_memory.py
- embedding.py
- vector_store.py
- retriever.py
- pipeline.py

Completed

- Pattern Memory
- Trade Memory
- Embedding Engine
- Vector Store
- Memory Retriever
- Memory Pipeline

Status

✅ Completed

Future Expansion

- Persistent Pattern Memory
- Persistent Trade Memory
- Real Embedding Models
- Vector Database
- FAISS
- Chroma
- Qdrant
- pgvector
- Experience Replay
- Strategy Memory
- Agent Memory

---

## risk/

Risk management.

Current Modules

- sizing.py
- exposure.py
- drawdown.py
- constraints.py
- stop_loss.py
- take_profit.py
- portfolio.py
- pipeline.py

Completed

- Position Sizing
- Exposure Management
- Drawdown Management
- Risk Constraints
- Risk-Level Stop Loss Management
- Risk-Level Take Profit Management
- Portfolio Risk Management
- Risk Pipeline

Status

✅ Completed

---

# Risk Architecture

The Risk subsystem is responsible for deciding whether a trade or portfolio state is acceptable under configured risk rules.

The Risk subsystem does not generate trade signals.

The Risk subsystem does not predict market direction.

The Risk subsystem only protects capital.

---

## Risk Module Responsibilities

| Module | Responsibility |
|--------|---------------|
| sizing.py | Calculates position size from account balance, risk percentage, entry price, and stop-loss price |
| exposure.py | Calculates trade exposure and validates exposure limits |
| drawdown.py | Calculates drawdown and validates drawdown limits |
| constraints.py | Combines risk, exposure, and drawdown checks into a risk decision |
| stop_loss.py | Handles risk-level stop-loss calculation and trigger checks |
| take_profit.py | Handles risk-adjusted take-profit calculation and hit checks |
| portfolio.py | Handles portfolio-level value, exposure, and unrealized PnL |
| pipeline.py | Coordinates the full risk assessment flow |

---

## Risk Flow

```text

Trade Request

↓

Position Sizing

↓

Exposure Calculation

↓

Drawdown Check

↓

Risk Constraints

↓

Stop Loss Check

↓

Take Profit Check

↓

Portfolio Risk Check

↓

Risk Assessment

```

---

## Risk Pipeline

```text

RiskPipeline

├── PositionSizer
├── ExposureManager
├── DrawdownManager
├── RiskConstraints
├── StopLossManager
├── TakeProfitManager
└── PortfolioRiskManager

```

The `RiskPipeline` returns a `RiskAssessment`.

RiskAssessment contains

- allowed
- position_size
- risk_amount
- exposure
- drawdown_percent
- stop_loss_price
- take_profit_price
- stop_loss_triggered
- take_profit_hit
- reasons

---

## Strategy Stop Loss vs Risk Stop Loss

AQOS intentionally separates strategy-level stop-loss planning from risk-level stop-loss control.

| Module | Purpose |
|--------|---------|
| strategy/stop_loss.py | Strategy-level stop-loss planning |
| risk/stop_loss.py | Account-level stop-loss validation and risk control |

Strategy stop loss answers:

```text
Where does the strategy want the stop loss?
```

Risk stop loss answers:

```text
Is the stop loss safe for the account?
```

---

## Strategy Take Profit vs Risk Take Profit

AQOS intentionally separates strategy-level take-profit planning from risk-level take-profit validation.

| Module | Purpose |
|--------|---------|
| strategy/take_profit.py | Strategy-level take-profit planning |
| risk/take_profit.py | Risk-adjusted take-profit calculation and validation |

Strategy take profit answers:

```text
Where does the strategy want to take profit?
```

Risk take profit answers:

```text
Is the reward-risk structure acceptable?
```

---

## evaluation/

Strategy, model, and trading evaluation.

Current Modules

- metrics.py
- backtest.py
- walk_forward.py
- paper_trading.py
- report.py
- pipeline.py

Completed

- Evaluation Metrics
- Backtesting
- Walk-Forward Validation
- Paper Trading
- Evaluation Reports
- Evaluation Pipeline

Status

✅ Completed

Future Expansion

- Sharpe Ratio
- Sortino Ratio
- Calmar Ratio
- Advanced Performance Metrics
- Candle-by-Candle Backtesting
- Slippage Simulation
- Commission Simulation
- Spread Simulation
- Multi-Symbol Backtesting
- Multi-Timeframe Backtesting
- Portfolio Backtesting
- HTML Reports
- PDF Reports
- Equity Curve Charts
- Drawdown Charts
- Evaluation Dashboard

## agents/

Multi-agent orchestration.

Future

- Research Agent
- Prediction Agent
- Strategy Agent
- Risk Agent
- Execution Agent
- Coordinator

Status

Planned

---

# System Data Flow

```text

External APIs

↓

Services

↓

Data Layer

↓

Feature Engineering

↓

Strategy Engine

↓

Prediction Models

↓

Learning Engine

↓

Memory System

↓

Risk Engine

↓

Evaluation

↓

Execution Agent

↓

Broker

```

---

# Dependency Flow

```text

core
│
├── common
│
├── services
│
├── data
│
├── features
│
├── strategy
│
├── models
│
├── learning
│
├── memory
│
├── risk
│
├── evaluation
│
└── agents

```

Higher-level modules should depend only on lower-level modules where possible.

Circular dependencies are not allowed.

---

# Current Development Status

# Current Development Status

| Sprint | Module | Status |
|---------|---------|--------|
| Sprint 000 | Project Setup | ✅ |
| Sprint 001 | Core Infrastructure | ✅ |
| Sprint 002 | Data Layer | ✅ |
| Sprint 003 | Feature Engineering | ✅ |
| Sprint 004 | Strategy Engine | ✅ |
| Sprint 005 | Models | ✅ |
| Sprint 006 | Learning | ✅ |
| Sprint 007 | Memory | ✅ |
| Sprint 008 | Risk | ✅ |
| Sprint 009 | Evaluation | ✅ |
| Sprint 010 | Services | ✅ |
| Sprint 011 | Interfaces | ✅  |
| Sprint 012 | Agents | ✅ |
| Sprint 013 | Common Utilities |✅ |
| Sprint 014 | Full Integration | ⏳ |

---

# Future Architecture Evolution

Phase 2

Institutional Intelligence

Includes

- Smart Money Concepts
- ICT
- Order Blocks
- Fair Value Gaps
- BOS
- CHOCH
- Liquidity Sweeps
- Multi-Timeframe Analysis
- Hidden Markov Models
- Transformer Market State Encoder
- Market Regime Intelligence
- Market DNA
- Experience Memory
- Strategy Generation

---

Phase 3

Production Platform

Includes

- Data Lake
- DuckDB
- Polars
- Distributed Training
- GPU Computing
- Experiment Tracking
- Monitoring
- Paper Trading
- Live Trading
- MLOps
- Kubernetes Deployment
- Broker Integrations
- Risk Monitoring
- Agent Orchestration

---

# Architecture Rules

1. Top-level packages are frozen.

2. No architecture changes without an ADR.

3. Every module must have a single responsibility.

4. Every public component must be documented.

5. Every module must have unit tests.

6. Integration tests are required where applicable.

7. Circular dependencies are prohibited.

8. Documentation is part of the Definition of Done.

9. Completed public classes must be exported through package-level `__init__.py`.

10. Strategy logic and risk logic must remain separated.

---

# Architecture Version History

| Version | Description |
|----------|-------------|
| 1.0 | Initial frozen architecture after Sprint 003 |
| 1.1 | Expanded Risk subsystem during Sprint 008 |

---
## Common Utilities Subsystem

Status: Completed in Sprint 013

The Common Utilities subsystem defines shared utility primitives for AQOS.

Path:

```text
src/aqos/common/
```

Common Utilities are used to reduce duplication and create stable shared behavior across AQOS modules.

### Common Layer Position

```text
all AQOS subsystems
    ↓
common/
```

The Common Utilities subsystem can be used by:

- core
- data
- features
- strategy
- models
- learning
- memory
- risk
- evaluation
- services
- interfaces
- agents

### Common Modules

```text
common/
├── constants.py
├── validators.py
├── id_helpers.py
├── time_utils.py
├── serialization.py
├── math_utils.py
└── error_helpers.py
```

Reserved future modules:

```text
common/
├── decorators.py
├── enums.py
├── helpers.py
└── types.py
```

### Design Responsibility

Common Utilities are responsible for:

- shared constants
- shared validation
- shared ID handling
- shared datetime handling
- shared serialization
- shared math helpers
- shared error formatting

Common Utilities are not responsible for:

- trading strategy decisions
- model predictions
- service orchestration
- agent workflows
- live broker execution
- API routing
- dashboard rendering

### Shared Constants

`constants.py` defines stable shared values such as:

- AQOS project names
- default symbol
- default timeframe
- default risk percent
- valid signals
- valid sides
- valid order types
- valid statuses
- valid sentiments
- valid impacts
- valid memory types
- valid timeframes
- OHLCV columns
- namespaces
- common messages

### Shared Validators

`validators.py` defines reusable validation helpers for:

- strings
- lists
- dictionaries
- payloads
- metadata
- numbers
- ratios
- required keys
- required columns
- OHLCV records
- symbols
- timeframes
- signals
- sides
- order types
- sentiments
- impacts
- memory types
- account balances
- risk percent values
- prices
- quantities

### ID Helpers

`id_helpers.py` defines reusable ID helpers for:

- UUIDs
- short IDs
- prefixed IDs
- compound IDs
- timestamp IDs
- ID normalization
- ID validation
- uniqueness checks

### Time Utilities

`time_utils.py` defines reusable UTC-first time helpers for:

- current UTC datetime
- current UTC date
- datetime parsing
- date parsing
- UTC conversion
- datetime formatting
- date formatting
- timestamp conversion
- time arithmetic
- time differences
- past/future checks
- time-window checks

### Serialization Helpers

`serialization.py` defines JSON-safe serialization helpers for:

- primitive values
- dataclasses
- dictionaries
- lists
- tuples
- sets
- decimals
- dates
- datetimes
- enums
- paths
- objects with `to_dict`
- objects with `__dict__`

It also includes helpers for:

- JSON conversion
- dictionary compaction
- dictionary flattening
- dictionary unflattening
- shallow merging
- deep merging

### Math Utilities

`math_utils.py` defines reusable numeric helpers for:

- safe division
- percentage change
- percentage return
- clamping
- rounding
- mean
- median
- variance
- standard deviation
- min-max normalization
- weighted average
- rolling mean
- cumulative sum
- maximum drawdown
- profit factor
- win rate

### Error Helpers

`error_helpers.py` defines structured error helpers.

Public class:

```text
ErrorInfo
```

Responsibilities:

- normalize error codes
- normalize error messages
- build error info
- build error dictionaries
- build not-found errors
- build validation errors
- build type errors
- convert exceptions to structured errors
- collect errors
- combine errors
- raise conditionally
- safely execute callables

### Design Boundary

The Common Utilities subsystem provides generic reusable primitives.

It must remain lightweight and dependency-minimal.

It should not depend on high-level AQOS subsystems such as:

- agents
- services
- interfaces
- strategy
- risk
- models
- learning
- evaluation

This keeps common utilities safe to import from anywhere in AQOS.
# Architecture Decision Records

Architecture decisions are recorded in:

```text
docs/DECISIONS.md
```

Current ADRs

| ADR | Decision |
|------|----------|
| ADR-001 | Freeze top-level AQOS architecture |
| ADR-002 | Dedicated strategy modules |
| ADR-003 | Documentation-first sprint completion workflow |
| ADR-004 | Expanded Risk subsystem architecture |

---
### Agent Layer Position

```text
external users / apps / agents
    ↓
interfaces/
    ↓
agents/
    ↓
services/
    ↓
core AQOS subsystems
```

Agents are not responsible for low-level domain logic.

They are responsible for:

- workflow execution
- task routing
- handoff generation
- agent-level summaries
- multi-step coordination
- deterministic workflow orchestration

### Agent Modules

```text
agents/
├── base.py
├── data_agent.py
├── market_agent.py
├── research_agent.py
├── strategy_agent.py
├── risk_agent.py
├── execution_agent.py
├── evaluation_agent.py
├── memory_agent.py
└── orchestrator.py
```

### Shared Agent Contract

All agents use:

```text
AgentTask
AgentResult
AgentBase
```

`AgentTask` defines:

- action
- payload
- metadata

`AgentResult` defines:

- success
- message
- data
- metadata

`AgentBase` provides:

- action normalization
- action validation
- payload helpers
- success helper
- failure helper

### Agent Responsibilities

#### DataAgent

Handles market data availability, OHLCV preparation, close prices, summaries, and quality checks.

#### MarketAgent

Builds market snapshots, trend summaries, regime summaries, news context, calendar context, and market state payloads.

#### ResearchAgent

Generates hypotheses, experiment plans, research experiments, findings, and research summaries.

#### StrategyAgent

Generates signals, decisions, explanations, entry checks, exit checks, and strategy handoff payloads.

#### RiskAgent

Calculates position size, assesses trades, approves/rejects trades, generates rejection reasons, and produces risk handoff payloads.

#### ExecutionAgent

Places simulated orders, executes risk-approved trades, fills orders, cancels orders, closes positions, and summarizes execution state.

#### EvaluationAgent

Runs backtests, summarizes backtests, compares backtests, grades performance, and generates evaluation reports.

#### MemoryAgent

Stores, recalls, retrieves, forgets, and summarizes memory records.

#### AgentOrchestrator

Coordinates all agents and runs multi-agent workflows.

### Completed Multi-Agent Workflows

```text
MarketAgent → StrategyAgent
StrategyAgent → RiskAgent
RiskAgent → ExecutionAgent
MarketAgent → StrategyAgent → RiskAgent → ExecutionAgent
ResearchAgent
EvaluationAgent
MemoryAgent
```

### Example Trade Workflow

```text
AgentOrchestrator.trade-workflow
    ↓
MarketAgent.market-state
    ↓
StrategyAgent.handoff
    ↓
RiskAgent.risk-handoff
    ↓
ExecutionAgent.execute-trade
```

### Design Boundary

The Agents subsystem does not replace Services.

Services remain responsible for subsystem orchestration.

Agents are responsible for task-level workflow composition.

The current Agents subsystem is deterministic and does not require:

- external APIs
- live brokers
- real-time feeds
- LLM calls
- autonomous runtimes
# Final Note

AQOS is being developed as a modular, scalable, and institutional-grade AI Quant Research Platform.

This architecture document serves as the single source of truth for the system structure.

The top-level AQOS architecture remains frozen.

Sprint 008 expanded only the internal `risk/` subsystem by adding:

- risk/stop_loss.py
- risk/take_profit.py
- risk/portfolio.py
- risk/pipeline.py

Sprint 009 completed the existing `evaluation/` subsystem by adding:

- evaluation/metrics.py
- evaluation/backtest.py
- evaluation/walk_forward.py
- evaluation/paper_trading.py
- evaluation/report.py
- evaluation/pipeline.py

No new architecture decision was required for Sprint 009 because Evaluation was already part of the frozen top-level AQOS architecture.

Any architectural modification must be documented in `docs/DECISIONS.md` before implementation.