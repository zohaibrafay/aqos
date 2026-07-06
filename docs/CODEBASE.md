# AQOS Codebase Documentation

> AI Quant Operating System (AQOS)
>
> This document describes every package and file in the AQOS codebase.
> It serves as the primary reference for developers working on the project.

---

# Current Version

```text
v0.8.0-dev
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
| Sprint 009 | 🚧 In Progress |

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
| `planner.py` | Strategy orchestrator | ⏳ |
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

Responsible for model and strategy evaluation.

| File | Purpose | Status |
|------|---------|--------|
| `__init__.py` | Evaluation package exports | ⏳ |
| `metrics.py` | Evaluation metrics | ⏳ |
| `backtest.py` | Backtesting | ⏳ |
| `walk_forward.py` | Walk-forward validation | ⏳ |
| `paper_trading.py` | Paper trading | ⏳ |
| `report.py` | Evaluation reports | ⏳ |
| `pipeline.py` | Evaluation pipeline | ⏳ |

---

# services/

Responsible for external integrations.

| File | Purpose | Status |
|------|---------|--------|
| `__init__.py` | Services package exports | ⏳ |
| `market_data.py` | Market data services | ⏳ |
| `broker.py` | Broker integrations | ⏳ |
| `news.py` | News services | ⏳ |
| `economic_calendar.py` | Economic calendar | ⏳ |
| `storage.py` | Cloud/local storage | ⏳ |

---

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

---

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
from aqos.risk import RiskPipeline
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

`CODEBASE.md` is the authoritative inventory of the AQOS repository.

The Risk subsystem was completed in Sprint 008. It now includes position sizing, exposure management, drawdown management, risk constraints, risk-level stop-loss management, risk-level take-profit management, portfolio risk management, and a unified risk pipeline.

During Sprint 008, the risk architecture was expanded from the initial foundation to a complete risk-management package. This architecture change is recorded in `ARCHITECTURE.md` and `DECISIONS.md`.

Files such as `continual.py`, `evaluator.py`, `reinforcement.py`, and `self_supervised.py` remain intentionally deferred learning modules. They will be implemented only after their prerequisite systems are available.

Whenever the repository structure changes, this document must be updated before a sprint is considered complete.