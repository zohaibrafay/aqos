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
| Architecture Version | 1.0 |
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

```

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

```

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

Current Status

🟡 In Progress

Completed

- Base Strategy
- Pattern Detector
- Market Regime
- Support & Resistance
- Liquidity

Remaining

- Trend Structure
- Signal
- Entry
- Exit
- Stop Loss
- Take Profit
- Execution

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

Prediction models.

Future

- LSTM
- Transformer
- TFT
- XGBoost
- LightGBM
- CatBoost
- Ensemble Models

Status

Planned

---

## learning/

Training engine.

Future

- Trainer
- Optimizer
- Scheduler
- Hyperparameter Search
- Cross Validation

Status

Planned

---

## memory/

Knowledge and pattern memory.

Future

- Pattern Memory
- Trade Memory
- Embeddings
- Vector Database
- Retrieval

Status

Planned

---

## risk/

Risk management.

Future

- Position Sizing
- Stop Loss
- Take Profit
- Drawdown
- Portfolio Risk

Status

Planned

---

## evaluation/

Strategy evaluation.

Future

- Metrics
- Backtesting
- Walk Forward
- Paper Trading
- Reports

Status

Planned

---

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

```

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

```

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

| Sprint | Module | Status |
|---------|---------|--------|
| Sprint 000 | Project Setup | ✅ |
| Sprint 001 | Core Infrastructure | ✅ |
| Sprint 002 | Data Layer | ✅ |
| Sprint 003 | Feature Engineering | ✅ |
| Sprint 004 | Strategy Engine | 🟡 |
| Sprint 005 | Models | ⏳ |
| Sprint 006 | Learning | ⏳ |
| Sprint 007 | Memory | ⏳ |
| Sprint 008 | Risk | ⏳ |
| Sprint 009 | Evaluation | ⏳ |
| Sprint 010 | Services | ⏳ |
| Sprint 011 | Agents | ⏳ |
| Sprint 012 | Full Integration | ⏳ |

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
- Live Trading
- MLOps
- Kubernetes Deployment

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

---

# Architecture Version History

| Version | Description |
|----------|-------------|
| 1.0 | Initial frozen architecture after Sprint 003 |
| Future | Updated only through Architecture Decision Records (ADR) |

---

# Final Note

AQOS is being developed as a modular, scalable, and institutional-grade AI Quant Research Platform.

This architecture document serves as the single source of truth for the system structure.

Any architectural modification must be documented in `docs/DECISIONS.md` before implementation.