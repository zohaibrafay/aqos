# AQOS Codebase Documentation

> AI Quant Operating System (AQOS)
>
> This document describes every package and file in the AQOS codebase.
> It serves as the primary reference for developers working on the project.

---

# Current Version

```
v0.5.0-dev
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
| Sprint 006 | 🚧 In Progress |

---

# Source Tree

```
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

# core/

Responsible for AQOS infrastructure.

| File | Purpose | Status |
|------|---------|--------|
| version.py | Version management | ✅ |
| configuration.py | Configuration | ✅ |
| logger.py | Logging | ✅ |
| exceptions.py | Custom exceptions | ✅ |
| bootstrap.py | Bootstrap | ✅ |
| health.py | Health checks | ✅ |
| cli.py | Command Line Interface | ✅ |

---

# data/

Responsible for market data management.

| File | Purpose | Status |
|------|---------|--------|
| provider.py | Data provider | ✅ |
| loader.py | Data loader | ✅ |
| validator.py | Data validation | ✅ |
| cleaner.py | Data cleaning | ✅ |
| storage.py | Data storage | ✅ |
| catalog.py | Dataset catalog | ✅ |
| pipeline.py | Data pipeline | ✅ |

---

# features/

Responsible for feature engineering.

| File | Purpose | Status |
|------|---------|--------|
| base.py | Base feature interface | ✅ |
| technical.py | Technical indicators | ✅ |
| candlestick.py | Candlestick features | ✅ |
| price_action.py | Price Action features | ✅ |
| statistical.py | Statistical features | ✅ |
| market_structure.py | Market Structure features | ✅ |
| pipeline.py | Feature pipeline | ✅ |

---

# strategy/

Responsible for market intelligence and trading decisions.

| File | Purpose | Status |
|------|---------|--------|
| base.py | Base strategy | ✅ |
| planner.py | Strategy orchestrator | ⏳ |
| pattern_detector.py | Pattern detection | ✅ |
| market_regime.py | Market regime detection | ✅ |
| support_resistance.py | Support & resistance | ✅ |
| liquidity.py | Liquidity analysis | ✅ |
| trend_structure.py | Trend structure analysis | ✅ |
| signal.py | Signal generation | ✅ |
| entry.py | Entry engine | ✅ |
| exit.py | Exit engine | ✅ |
| stop_loss.py | Stop-loss engine | ✅ |
| take_profit.py | Take-profit engine | ✅ |
| execution.py | Execution engine | ⏳ |

---

# models/

Responsible for prediction and market representation.

| File | Purpose | Status |
|------|---------|--------|
| base.py | Base model interface | ✅ |
| dataset.py | Dataset preparation | ✅ |
| predictor.py | Prediction engine | ✅ |
| encoder.py | Feature encoder | ✅ |
| transformer.py | Feature transformer | ✅ |
| similarity.py | Similarity engine | ✅ |
| uncertainty.py | Prediction uncertainty estimation | ✅ |
| world_model.py | Market world-state representation | ✅ |

---

# learning/

Responsible for model training.

| File | Purpose | Status |
|------|---------|--------|
| trainer.py | Training engine | ⏳ |
| optimizer.py | Optimizer | ⏳ |
| scheduler.py | Learning-rate scheduler | ⏳ |
| loss.py | Loss functions | ⏳ |
| cross_validation.py | Cross validation | ⏳ |
| pipeline.py | Learning pipeline | ⏳ |

---

# memory/

Responsible for long-term AI memory.

| File | Purpose | Status |
|------|---------|--------|
| pattern_memory.py | Pattern memory | ⏳ |
| trade_memory.py | Trade memory | ⏳ |
| embedding.py | Embedding generation | ⏳ |
| vector_store.py | Vector storage | ⏳ |
| retriever.py | Memory retrieval | ⏳ |
| pipeline.py | Memory pipeline | ⏳ |

---

# risk/

Responsible for risk management.

| File | Purpose | Status |
|------|---------|--------|
| position_size.py | Position sizing | ⏳ |
| stop_loss.py | Dynamic stop loss | ⏳ |
| take_profit.py | Dynamic take profit | ⏳ |
| drawdown.py | Drawdown management | ⏳ |
| portfolio.py | Portfolio risk | ⏳ |
| pipeline.py | Risk pipeline | ⏳ |

---

# evaluation/

Responsible for model and strategy evaluation.

| File | Purpose | Status |
|------|---------|--------|
| metrics.py | Evaluation metrics | ⏳ |
| backtest.py | Backtesting | ⏳ |
| walk_forward.py | Walk-forward validation | ⏳ |
| paper_trading.py | Paper trading | ⏳ |
| report.py | Evaluation reports | ⏳ |
| pipeline.py | Evaluation pipeline | ⏳ |

---

# services/

Responsible for external integrations.

| File | Purpose | Status |
|------|---------|--------|
| market_data.py | Market data services | ⏳ |
| broker.py | Broker integrations | ⏳ |
| news.py | News services | ⏳ |
| economic_calendar.py | Economic calendar | ⏳ |
| storage.py | Cloud/local storage | ⏳ |

---

# agents/

Responsible for multi-agent orchestration.

| File | Purpose | Status |
|------|---------|--------|
| research_agent.py | Research agent | ⏳ |
| prediction_agent.py | Prediction agent | ⏳ |
| strategy_agent.py | Strategy agent | ⏳ |
| risk_agent.py | Risk agent | ⏳ |
| execution_agent.py | Execution agent | ⏳ |
| coordinator.py | Agent coordinator | ⏳ |

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

- Base
- Technical
- Candlestick
- Price Action
- Statistical
- Market Structure
- Pipeline

## Strategy

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

## Models

- Base Model
- Dataset
- Predictor
- Encoder
- Transformer
- Similarity Engine
- Uncertainty Engine
- World Model

---

# Status Legend

| Symbol | Meaning |
|---------|---------|
| ✅ | Completed |
| 🚧 | In Progress |
| ⏳ | Planned |

---

# Maintenance Rules

1. Every new source file must be added to this document.
2. Every renamed file must be updated here.
3. Every deleted file must be removed here.
4. Status must always match the repository.
5. Update this document once per completed sprint.

---

# Notes

`CODEBASE.md` is the authoritative inventory of the AQOS repository.

Whenever the repository structure changes, this document must be updated before a sprint is considered complete.