# AQOS Codebase Documentation

> AI Quant Operating System (AQOS)
>
> This document describes every package and file in the AQOS codebase.
> It serves as the primary reference for developers working on the project.

---

# Current Version

```
v0.4.0-dev
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
| Sprint 005 | 🚧 In Progress |

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
| cli.py | CLI | ✅ |

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
| market_structure.py | Market structure features | ✅ |
| pipeline.py | Feature engineering pipeline | ✅ |

---

# strategy/

Responsible for market intelligence and trade decision making.

| File | Purpose | Status |
|------|---------|--------|
| base.py | Base strategy interface | ✅ |
| planner.py | Strategy orchestrator | ⏳ |
| pattern_detector.py | Candlestick pattern detection | ✅ |
| market_regime.py | Bull/Bear/Sideways detection | ✅ |
| support_resistance.py | Support & Resistance detection | ✅ |
| liquidity.py | Liquidity zone detection | ✅ |
| trend_structure.py | HH/HL/LH/LL trend detection | ✅ |
| signal.py | Buy/Sell/Hold signal generation | ✅ |
| entry.py | Entry decision engine | ✅ |
| exit.py | Exit decision engine | ✅ |
| stop_loss.py | Stop-loss calculation | ✅ |
| take_profit.py | Take-profit calculation | ✅ |
| execution.py | Trade execution engine | ⏳ |

---

# models/

Prediction models.

| File | Purpose | Status |
|------|---------|--------|
| base.py | Base model | ⏳ |
| dataset.py | Dataset preparation | ⏳ |
| prediction.py | Prediction engine | ⏳ |
| ensemble.py | Ensemble models | ⏳ |
| registry.py | Model registry | ⏳ |
| pipeline.py | Model pipeline | ⏳ |

---

# learning/

Training engine.

| File | Purpose | Status |
|------|---------|--------|
| trainer.py | Model trainer | ⏳ |
| optimizer.py | Optimizer | ⏳ |
| scheduler.py | Learning scheduler | ⏳ |
| loss.py | Loss functions | ⏳ |
| cross_validation.py | Cross validation | ⏳ |
| pipeline.py | Learning pipeline | ⏳ |

---

# memory/

Long-term AI memory.

| File | Purpose | Status |
|------|---------|--------|
| pattern_memory.py | Pattern memory | ⏳ |
| trade_memory.py | Trade memory | ⏳ |
| embedding.py | Embedding generation | ⏳ |
| vector_store.py | Vector database | ⏳ |
| retriever.py | Retrieval engine | ⏳ |
| pipeline.py | Memory pipeline | ⏳ |

---

# risk/

Risk management.

| File | Purpose | Status |
|------|---------|--------|
| position_size.py | Position sizing | ⏳ |
| stop_loss.py | Dynamic stop-loss | ⏳ |
| take_profit.py | Dynamic take-profit | ⏳ |
| drawdown.py | Drawdown control | ⏳ |
| portfolio.py | Portfolio risk | ⏳ |
| pipeline.py | Risk pipeline | ⏳ |

---

# evaluation/

Strategy evaluation.

| File | Purpose | Status |
|------|---------|--------|
| metrics.py | Performance metrics | ⏳ |
| backtest.py | Backtesting | ⏳ |
| walk_forward.py | Walk-forward testing | ⏳ |
| paper_trading.py | Paper trading | ⏳ |
| report.py | Reports | ⏳ |
| pipeline.py | Evaluation pipeline | ⏳ |

---

# services/

External integrations.

| File | Purpose | Status |
|------|---------|--------|
| market_data.py | Market data APIs | ⏳ |
| broker.py | Broker integrations | ⏳ |
| news.py | News providers | ⏳ |
| economic_calendar.py | Economic calendar | ⏳ |
| storage.py | Cloud/local storage | ⏳ |

---

# agents/

Multi-agent orchestration.

| File | Purpose | Status |
|------|---------|--------|
| research_agent.py | Research agent | ⏳ |
| prediction_agent.py | Prediction agent | ⏳ |
| strategy_agent.py | Strategy agent | ⏳ |
| risk_agent.py | Risk agent | ⏳ |
| execution_agent.py | Execution agent | ⏳ |
| coordinator.py | Agent coordinator | ⏳ |

---

# Testing

Current test coverage includes:

### Core

- Version
- Configuration
- Logger
- Exceptions

### Data

- Provider
- Loader
- Validator
- Cleaner
- Storage
- Catalog
- Pipeline

### Features

- Base
- Technical
- Candlestick
- Price Action
- Statistical
- Market Structure
- Pipeline

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

# Status Legend

| Symbol | Meaning |
|---------|---------|
| ✅ | Completed |
| 🚧 | In Progress |
| ⏳ | Planned |

---

# Maintenance Rules

1. Every new source file must be added here.
2. Every renamed file must be updated here.
3. Every removed file must be removed here.
4. Status must always match the repository.
5. This document is updated once per completed sprint.

---

# Notes

`CODEBASE.md` is the authoritative inventory of the AQOS repository.

Whenever the repository structure changes, this document must be updated before the sprint is considered complete.