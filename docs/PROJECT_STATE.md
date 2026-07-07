# AQOS Project State

> AI Quant Operating System (AQOS)
>
> This document represents the current development state of AQOS.
> It is the primary resume point for development.
>
> Whenever development resumes, this document should be read first.

---

# Project Information

| Item | Value |
|------|-------|
| Project | AI Quant Operating System (AQOS) |
| Current Version | v0.13.0-dev |
| Current Phase | Phase 1 – Foundation |
| Status | Active Development |

---

# Current Development State

## Current Sprint

```text
Sprint 014 — System Integration
```

## Current Task

```text
Task 14.1
```

## Previous Sprint

```text
Sprint 013 — Common Utilities
```


# Overall Progress

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
| Sprint 010 | Services |  ✅ Complete |
| Sprint 011 | Interfaces |  ✅ Complete |
| Sprint 012 | Agents | ✅ Complete|
| Sprint 013 | Common Utilities | ✅ Complete |
| Sprint 014 | Full System Integration | 🚧 In Progress |

---

## Completed Subsystems

- Core Infrastructure
- Data Layer
- Feature Engineering
- Strategy Engine
- Models
- Learning Engine
- Memory
- Risk
- Evaluation
- Services
- Interfaces
- Agents
- Common Utilities

## Sprint 013 Summary

Sprint 013 completed the AQOS Common Utilities subsystem.

The Common Utilities subsystem provides reusable constants, validators, ID helpers, time helpers, serialization helpers, math helpers, and error helpers.

These utilities are designed to reduce duplication across AQOS and provide stable shared primitives for future integration, APIs, dashboards, agents, and orchestration workflows.

## Completed Common Modules

```text
src/aqos/common/
├── __init__.py
├── constants.py
├── error_helpers.py
├── id_helpers.py
├── math_utils.py
├── serialization.py
├── time_utils.py
└── validators.py
```

Existing placeholder modules remain reserved for future use:

```text
src/aqos/common/
├── decorators.py
├── enums.py
├── helpers.py
└── types.py
```

## Public Common Capabilities

AQOS now includes reusable helpers for:

- Project constants
- Trading constants
- Valid signal values
- Valid side values
- Valid order types
- Valid statuses
- Valid sentiments
- Valid impacts
- Valid memory types
- Valid timeframes
- OHLCV column constants
- Payload validation
- Metadata validation
- Required key validation
- Required column validation
- OHLCV record validation
- Symbol normalization
- Timeframe validation
- Signal validation
- Risk percent validation
- Price and quantity validation
- UUID generation
- Short ID generation
- Prefixed ID generation
- Compound ID generation
- Timestamp ID generation
- ID normalization
- Unique ID generation
- UTC datetime parsing
- UTC datetime formatting
- Timestamp conversion
- Date parsing
- Date formatting
- Time window checks
- JSON-safe serialization
- Dictionary flattening
- Dictionary unflattening
- Deep dictionary merging
- Safe dictionary access
- Numeric validation
- Safe division
- Percentage change
- Percentage return
- Mean and median
- Variance and standard deviation
- Min-max normalization
- Weighted average
- Rolling mean
- Cumulative sum
- Maximum drawdown
- Profit factor
- Win rate
- Structured error objects
- Exception conversion
- Error collection
- Safe function execution

## Current Architecture Status

AQOS now has completed foundational subsystems from core infrastructure through common utilities and agent orchestration.

The system can currently:

- Register and manage datasets
- Manage OHLCV market data
- Prepare close prices and OHLCV records
- Generate market snapshots
- Analyze simple trend and regime context
- Store and summarize news items
- Store and summarize economic calendar events
- Run model predictions
- Build world state outputs
- Generate strategy signals
- Generate strategy decisions
- Create strategy handoff payloads
- Assess trade risk
- Calculate position sizing
- Generate risk handoff payloads
- Place simulated broker orders
- Fill orders
- Cancel orders
- Close positions
- Summarize execution state
- Run backtests
- Generate evaluation reports
- Compare backtests
- Track experiments
- Generate research hypotheses
- Generate experiment plans
- Store and recall agent memory
- Run orchestrated workflows across market, strategy, risk, execution, evaluation, research, and memory agents
- Use common utilities for constants, validation, IDs, time handling, serialization, math, and error formatting

## Next Step

Sprint 014 will focus on System Integration.
## Sprint 010 Summary

Sprint 010 completed the AQOS service layer.

The service layer now exposes stable orchestration classes for AQOS internal modules and lightweight integration-style abstractions for future market data, broker, news, calendar, and storage connections.

## Completed Service Modules

```text
src/aqos/services/
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

# Sprint 009 Summary

Completed Components

## Evaluation

- Evaluation Metrics
- Backtesting
- Walk-Forward Validation
- Paper Trading
- Evaluation Reports
- Evaluation Pipeline

All unit tests passed successfully.

---

# Current Codebase Status

Completed

- Core Infrastructure
- Data Layer
- Feature Engineering
- Strategy Engine
- Models
- Learning Engine
- Memory
- Risk
- Evaluation

Next

- Services

---

# Immediate Next Tasks

Sprint 010

Services

Task Order

- Task 10.1 Market Data Service

## Completed Subsystems

- Core Infrastructure
- Data Layer
- Feature Engineering
- Strategy Engine
- Models
- Learning Engine
- Memory
- Risk
- Evaluation
- Services
- Interfaces

## Sprint 011 Summary

Sprint 011 completed the AQOS Interfaces subsystem.

The Interfaces subsystem now includes both:

1. Domain interface contracts
2. Application-facing interfaces

Domain contracts define how AQOS components should behave.

Application-facing interfaces define how APIs, CLI tools, dashboards, and agents can interact with AQOS.

## Completed Interface Modules

```text
src/aqos/interfaces/
├── __init__.py
├── agent_interface.py
├── api_interface.py
├── cli_interface.py
├── dashboard_interface.py
├── data_provider.py
├── memory.py
├── model.py
├── risk.py
├── schemas.py
└── strategy.py


## Completed Subsystems

- Core Infrastructure
- Data Layer
- Feature Engineering
- Strategy Engine
- Models
- Learning Engine
- Memory
- Risk
- Evaluation
- Services
- Interfaces
- Agents

## Sprint 012 Summary

Sprint 012 completed the AQOS Agents subsystem.

The Agents subsystem provides agent-level workflows above the Services and Interfaces layers.

Agents do not replace Services.

Agents coordinate domain capabilities into higher-level workflows that can later be used by autonomous research systems, API workflows, CLI workflows, dashboards, and orchestration runtimes.

## Completed Agent Modules

```text
src/aqos/agents/
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

## Public Agent Classes

- `AgentBase`
- `AgentTask`
- `AgentResult`
- `DataAgent`
- `MarketAgent`
- `ResearchAgent`
- `StrategyAgent`
- `RiskAgent`
- `ExecutionAgent`
- `EvaluationAgent`
- `MemoryAgent`
- `AgentOrchestrator`

## Current Architecture Status

AQOS now has a complete foundation from core infrastructure through multi-agent orchestration.

The system can currently:

- Register and manage datasets
- Manage OHLCV market data
- Prepare close prices and OHLCV records
- Generate market snapshots
- Analyze simple trend and regime context
- Store and summarize news items
- Store and summarize economic calendar events
- Run model predictions
- Build world state outputs
- Generate strategy signals
- Generate strategy decisions
- Create strategy handoff payloads
- Assess trade risk
- Calculate position sizing
- Generate risk handoff payloads
- Place simulated broker orders
- Fill orders
- Cancel orders
- Close positions
- Summarize execution state
- Run backtests
- Generate evaluation reports
- Compare backtests
- Track experiments
- Generate research hypotheses
- Generate experiment plans
- Store and recall agent memory
- Run orchestrated workflows across market, strategy, risk, execution, evaluation, research, and memory agents

## Completed Multi-Agent Workflows

- Market → Strategy workflow
- Strategy → Risk workflow
- Risk → Execution workflow
- Full Trade workflow
- Research workflow
- Backtest workflow
- Memory workflow
- Agent routing workflow

## Next Step

Sprint 013 will focus on the Common Utilities subsystem.