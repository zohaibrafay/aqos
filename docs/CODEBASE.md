# AQOS Codebase Documentation

> AI Quant Operating System (AQOS)
>
> This document describes every package and file in the AQOS codebase.
> It serves as the primary reference for developers working on the project.

---

# Current Version

```
v0.7.0-dev
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
| Sprint 008 | 🚧 In Progress |

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
| `stop_loss.py` | Stop-loss engine | ✅ |
| `take_profit.py` | Take-profit engine | ✅ |
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
| `__init__.py` | Risk package exports | ⏳ |
| `position_size.py` | Position sizing | ⏳ |
| `stop_loss.py` | Dynamic stop loss | ⏳ |
| `take_profit.py` | Dynamic take profit | ⏳ |
| `drawdown.py` | Drawdown management | ⏳ |
| `portfolio.py` | Portfolio risk | ⏳ |
| `pipeline.py` | Risk pipeline | ⏳ |

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
- Stop Loss Engine
- Take Profit Engine

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
from aqos.memory import MemoryPipeline
```

This keeps imports clean, consistent, and stable across the codebase.

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

The Memory subsystem was completed in Sprint 007. It currently uses lightweight in-memory storage and deterministic hash-based embeddings. This gives AQOS a testable foundation for pattern memory, trade memory, vector search, and retrieval before persistent vector databases and real embedding models are integrated later.

Files such as `continual.py`, `evaluator.py`, `reinforcement.py`, and `self_supervised.py` remain intentionally deferred learning modules. They will be implemented only after their prerequisite systems are available.

Whenever the repository structure changes, this document must be updated before a sprint is considered complete.