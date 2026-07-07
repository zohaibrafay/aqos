# AQOS Development Roadmap

> AI Quant Operating System (AQOS)
>
> Master implementation roadmap.

---

# Current Status

**Current Version**

```text
v0.13.0-dev
```

**Current Phase**

```text
Phase 1 — Foundation
```

**Current Sprint**

```text
Sprint 014 — System Integration
```

**Current Task**

```text
Task 14.1
```

---

# Sprint Progress

| Sprint | Module | Status |
|---------|--------|--------|
| Sprint 000 | Project Setup | ✅ Complete |
| Sprint 001 | Core Infrastructure | ✅ Complete |
| Sprint 002 | Data Layer | ✅ Complete |
| Sprint 003 | Feature Engineering | ✅ Complete |
| Sprint 004 | Strategy Engine | ✅ Complete |
| Sprint 005 | Models | ✅ Complete |
| Sprint 006 | Learning Engine | ✅ Complete |
| Sprint 007 | Memory | ✅ Complete |
| Sprint 008 | Risk | ✅ Complete |
| Sprint 009 | Evaluation | ✅ Complete |
| Sprint 010 | Services | ✅ Complete |
| Sprint 011 | Interfaces | ✅ Complete  |
| Sprint 012 | Agents | ✅ Complete |
| Sprint 013 | Common Utilities | ✅ Complete|
| Sprint 014 | System Integration | 🚧 In Progress |

---

# Completed Modules

## Sprint 000

- Project Setup
- Repository Structure
- Packaging
- Development Environment

---

## Sprint 001

- Version
- Configuration
- Logger
- Exceptions
- Bootstrap
- Health Check
- CLI

---

## Sprint 002

- Provider
- Loader
- Validator
- Cleaner
- Storage
- Catalog
- Pipeline

---

## Sprint 003

- Base Feature
- Technical Indicators
- Candlestick Features
- Price Action
- Statistical Features
- Market Structure
- Feature Pipeline

---

## Sprint 004

### Strategy

- Base Strategy
- Pattern Detector
- Market Regime
- Support & Resistance
- Liquidity
- Trend Structure
- Signal Engine
- Entry Engine
- Exit Engine
- Stop Loss Engine
- Take Profit Engine

---

## Sprint 005

### Models

- Base Model
- Dataset
- Predictor
- Encoder
- Transformer
- Similarity Engine
- Uncertainty Engine
- World Model

---

## Sprint 006

### Learning

- Trainer
- Optimizer
- Scheduler
- Loss
- Cross Validation
- Learning Pipeline

---

## Sprint 007

### Memory

- Pattern Memory
- Trade Memory
- Embedding Engine
- Vector Store
- Memory Retriever
- Memory Pipeline

---

## Sprint 008

### Risk

- Position Sizing
- Exposure Management
- Drawdown Management
- Risk Constraints
- Stop Loss Management
- Take Profit Management
- Portfolio Risk Management
- Risk Pipeline

---

## Sprint 009

### Evaluation

- Evaluation Metrics
- Backtesting
- Walk-Forward Validation
- Paper Trading
- Evaluation Reports
- Evaluation Pipeline

---

## Sprint 010 — Services


Status: Completed

Sprint 010 completed the AQOS service layer.

The service layer now provides clean orchestration wrappers around the internal AQOS subsystems and lightweight external integration-style services for future API, broker, market data, news, calendar, and storage integrations.

Completed service modules:

- `data_service.py`
- `model_service.py`
- `strategy_service.py`
- `backtest_service.py`
- `experiment_service.py`
- `market_data.py`
- `broker.py`
- `news.py`
- `economic_calendar.py`
- `storage.py`

Completed capabilities:

- Register and manage market datasets
- Register and run models
- Generate strategy decisions
- Run and store backtests
- Track experiment runs
- Store external-style OHLCV candle feeds
- Simulate broker orders and positions
- Store and filter market news
- Store and filter economic calendar events
- Save and load generic records by namespace
- Export all public service classes through `aqos.services`
## Sprint 011 — Interfaces

Status: Completed

Sprint 011 completed the AQOS Interfaces subsystem.

The Interfaces subsystem now contains both domain-level interface contracts and application-facing interfaces.

Completed interface modules:

- `data_provider.py`
- `model.py`
- `strategy.py`
- `risk.py`
- `memory.py`
- `schemas.py`
- `api_interface.py`
- `cli_interface.py`
- `dashboard_interface.py`
- `agent_interface.py`

Completed capabilities:

- Define market data provider contracts
- Define model contracts
- Define strategy contracts
- Define risk contracts
- Define memory contracts
- Define request/response schemas
- Provide API-facing access to AQOS services
- Provide CLI-style command access
- Provide dashboard-style read access
- Provide agent-style action access
- Export all public interface classes through `aqos.interfaces`

## Sprint 012 — Agents

Status: Completed

Sprint 012 completed the AQOS Agents subsystem.

Completed agent modules:

- `base.py`
- `data_agent.py`
- `market_agent.py`
- `research_agent.py`
- `strategy_agent.py`
- `risk_agent.py`
- `execution_agent.py`
- `evaluation_agent.py`
- `memory_agent.py`
- `orchestrator.py`

Completed capabilities:

- Define shared agent task/result contracts
- Provide data availability and OHLCV preparation workflows
- Provide market snapshot, trend, regime, news, and calendar workflows
- Provide research hypothesis and experiment planning workflows
- Provide strategy signal, decision, explanation, and handoff workflows
- Provide risk assessment, position sizing, and approval workflows
- Provide simulated execution, order, fill, cancel, close, and summary workflows
- Provide backtest, evaluation, report, and comparison workflows
- Provide memory storage, recall, pattern memory, trade memory, and summary workflows
- Provide multi-agent orchestration workflows
- Export all public agent classes through `aqos.agents`

## Sprint 013 — Common Utilities

Status: Completed

Sprint 013 completed the AQOS Common Utilities subsystem.

Completed common utility modules:

- `constants.py`
- `validators.py`
- `id_helpers.py`
- `time_utils.py`
- `serialization.py`
- `math_utils.py`
- `error_helpers.py`

Completed capabilities:

- Shared AQOS constants
- Shared validation helpers
- Symbol, timeframe, signal, side, order type, sentiment, impact, and memory type validation
- OHLCV record and column validation
- ID generation, normalization, and uniqueness helpers
- UTC datetime parsing, formatting, conversion, and window checks
- JSON-safe serialization helpers
- Dictionary flattening, unflattening, merging, and compaction
- Numeric helpers for division, returns, drawdown, win rate, profit factor, variance, standard deviation, and rolling means
- Structured error helpers
- Exception-to-dictionary conversion
- Safe execution helpers
- Public exports through `aqos.common`
## Sprint 014 — System Integration

Status: Next

Planned focus:

- Cross-subsystem integration tests
- End-to-end AQOS workflow tests
- Agent-to-service workflow validation
- Common utilities adoption in selected modules
- System-level workflow examples
- Integration documentation

# Long-Term Goal

Build an institutional-grade AI Quant Research Platform capable of:

- Market Intelligence
- Machine Learning
- Deep Learning
- Reinforcement Learning
- Pattern Memory
- World Models
- Risk Management
- Backtesting
- Paper Trading
- Live Trading
- Multi-Agent AI