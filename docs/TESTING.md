# AQOS Testing Guide

> AI Quant Operating System (AQOS)

This document defines the testing strategy, standards, and current test coverage for AQOS.

---

# Testing Philosophy

AQOS follows a layered testing approach.

```
Unit Tests
     ↓
Integration Tests
     ↓
System Tests
     ↓
End-to-End Tests
```

Every sprint must include unit tests for all implemented modules before the sprint is considered complete.

---

# Testing Framework

| Tool | Purpose |
|------|---------|
| pytest | Unit testing |
| pytest-cov | Coverage reporting |
| pandas | Test data generation |

---

# Running Tests

Run the complete test suite:

```bash
pytest
```

Run with verbose output:

```bash
pytest -v
```

Run a single test file:

```bash
pytest tests/unit/test_provider.py
```

Run tests with coverage:

```bash
pytest --cov=src/aqos
```

---

# Current Test Coverage

## Sprint 001 — Core Infrastructure

- Version
- Configuration
- Logger
- Exceptions
- Bootstrap
- Health Check
- CLI

Status

✅ Complete

---

## Sprint 002 — Data Layer

- Provider
- Loader
- Validator
- Cleaner
- Storage
- Catalog
- Pipeline

Status

✅ Complete

---

## Sprint 003 — Feature Engineering

- Base Feature
- Technical Indicators
- Candlestick Features
- Price Action
- Statistical Features
- Market Structure
- Feature Pipeline

Status

✅ Complete

---

## Sprint 004 — Strategy Engine

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

Status

✅ Complete

---

## Sprint 005 — Models

- Base Model
- Dataset
- Predictor
- Encoder
- Transformer
- Similarity Engine
- Uncertainty Engine
- World Model

Status

✅ Complete

---

## Sprint 006 — Learning Engine

- Trainer
- Optimizer
- Scheduler
- Loss
- Cross Validation
- Learning Pipeline

Status

✅ Complete

## Sprint 007 — Memory

- Pattern Memory
- Trade Memory
- Embedding Engine
- Vector Store
- Memory Retriever
- Memory Pipeline

Status

✅ Complete


## Sprint 008 — Risk

- Position Sizing
- Exposure Management
- Drawdown Management
- Risk Constraints
- Stop Loss Management
- Take Profit Management
- Portfolio Risk Management
- Risk Pipeline

Status

✅ Complete


## Sprint 009 — Evaluation

- Evaluation Metrics
- Backtesting
- Walk-Forward Validation
- Paper Trading
- Evaluation Reports
- Evaluation Pipeline

Status

✅ Complete

## Sprint 010 — Services Tests

Status: Completed

Sprint 010 added unit test coverage for the full Services subsystem.

### Test Files

```text
tests/unit/test_data_service.py
tests/unit/test_model_service.py
tests/unit/test_strategy_service.py
tests/unit/test_backtest_service.py
tests/unit/test_experiment_service.py
tests/unit/test_market_data.py
tests/unit/test_broker.py
tests/unit/test_news.py
tests/unit/test_economic_calendar.py
tests/unit/test_storage_service.py
tests/unit/test_services_exports.py
```

### Coverage Areas

- Dataset registration and retrieval
- Dataset validation
- Model registration and prediction
- Confidence calculation
- World state building
- Strategy signal generation
- Strategy entry and exit decisions
- Strategy stop-loss and take-profit calculation
- Backtest execution
- Backtest result storage
- Backtest report generation
- Experiment lifecycle management
- Experiment metric comparison
- Market candle validation
- Market data feed management
- Broker order placement
- Broker order cancellation
- Broker order filling
- Broker position closing
- Broker realized profit calculation
- News item storage and filtering
- News sentiment and impact scoring
- Economic calendar event storage and filtering
- High-impact event detection
- Namespace-based storage operations
- Services package exports

### Notes

The Services tests are deterministic and do not require external APIs, brokers, databases, news providers, or market data providers.

---

## Sprint 011 — Interfaces Tests

Status: Completed

Sprint 011 added unit test coverage for the full Interfaces subsystem.

### Test Files

```text
tests/unit/test_data_provider_interface.py
tests/unit/test_model_interface.py
tests/unit/test_strategy_interface.py
tests/unit/test_risk_interface.py
tests/unit/test_memory_interface.py
tests/unit/test_interface_schemas.py
tests/unit/test_api_interface.py
tests/unit/test_cli_interface.py
tests/unit/test_dashboard_interface.py
tests/unit/test_agent_interface.py
tests/unit/test_interfaces_exports.py
```

### Coverage Areas

- Data provider interface contract behavior
- Market data validation
- Latest candle retrieval
- Close price extraction
- Model interface contract behavior
- Model training data validation
- Model prediction validation
- Single-row prediction
- Model save/load contract behavior
- Strategy interface contract behavior
- Strategy decision generation
- Strategy signal validation
- Risk interface contract behavior
- Risk trade assessment
- Risk rejection reasons
- Risk position sizing
- Memory interface contract behavior
- Memory storage
- Memory retrieval
- Memory search
- Memory validation
- Request schema validation
- Response schema validation
- Interface envelope validation
- API-style interface access
- CLI-style command access
- Dashboard-style read access
- Agent-style action access
- Interfaces package exports

### Notes

The Interfaces tests are deterministic and do not require external APIs, databases, brokers, dashboards, HTTP servers, or live agent runtimes.

---
## Sprint 012 — Agents Tests

Status: Completed

Sprint 012 added unit test coverage for the full Agents subsystem.

### Test Files

```text
tests/unit/test_agent_base.py
tests/unit/test_data_agent.py
tests/unit/test_market_agent.py
tests/unit/test_research_agent.py
tests/unit/test_strategy_agent.py
tests/unit/test_risk_agent.py
tests/unit/test_execution_agent.py
tests/unit/test_evaluation_agent.py
tests/unit/test_memory_agent.py
tests/unit/test_agent_orchestrator.py
tests/unit/test_agents_exports.py
```

### Coverage Areas

- Agent task validation
- Agent result validation
- Agent base execution flow
- Agent action normalization
- Unsupported agent action handling
- Data availability checks
- Market data summary generation
- OHLCV preparation
- Data quality checks
- Market snapshot generation
- Trend summary generation
- Regime summary generation
- News context generation
- Economic calendar context generation
- Market state generation
- Research hypothesis generation
- Experiment planning
- Research experiment creation
- Research finding storage
- Strategy signal generation
- Strategy decision generation
- Strategy signal explanations
- Strategy entry and exit checks
- Strategy handoff generation
- Risk position sizing
- Risk trade assessment
- Risk approval and rejection handling
- Risk handoff generation
- Execution order placement
- Execution order filling
- Execution order cancellation
- Position closing
- Order status retrieval
- Execution summary generation
- Backtest execution
- Backtest summaries
- Backtest comparisons
- Performance grading
- Evaluation report generation
- Memory storage
- Memory recall
- Memory retrieval
- Memory forgetting
- Memory summary generation
- Pattern memory storage
- Trade memory storage
- Agent orchestration
- Agent routing
- Market → Strategy workflow
- Strategy → Risk workflow
- Risk → Execution workflow
- Full trade workflow
- Research workflow
- Backtest workflow
- Memory workflow
- Agents package exports

### Command

```bash
python -m pytest
```

### Notes

The Agents tests are deterministic and do not require external APIs, live brokers, real market data providers, dashboards, HTTP servers, LLM calls, or autonomous runtimes.

## Testing Standards

Each module should test:

- Successful execution
- Invalid input
- Edge cases
- Exception handling
- Return types
- Expected outputs

---

## Current Status

```text
All tests passing
```

Current Development Version:

```text
v0.12.0-dev
```

---

## Future Testing

The following test categories will be added in later phases.

### Integration Tests

- Data → Features
- Features → Models
- Models → Learning
- Learning → Memory
- Strategy → Risk
- Services → Interfaces
- Interfaces → Agents

### System Tests

- Full prediction pipeline
- Full trading pipeline
- Research workflow
- Multi-agent workflow

### Performance Tests

- Large dataset handling
- Model inference latency
- Memory usage
- Pipeline throughput

### End-to-End Tests

- Historical backtesting
- Paper trading
- Live trading
- AI research workflow

---
### Integration Tests

- Data → Features
- Features → Models
- Models → Learning
- Learning → Memory
- Strategy → Risk
- Services → Interfaces
- Interfaces → Agents
- Agents → Orchestrator

## Testing Rules

1. Every source file must have a corresponding unit test.
2. New features require new tests.
3. Bug fixes require regression tests.
4. All tests must pass before a sprint is marked complete.
5. Documentation is updated only after sprint completion.

---

## Notes

Testing is considered a first-class citizen in AQOS.

No sprint is complete until all implemented modules have passing tests.
```text
Status: Completed

Sprint 011 added unit test coverage for the full Interfaces subsystem.

### Test Files


tests/unit/test_data_provider_interface.py
tests/unit/test_model_interface.py
tests/unit/test_strategy_interface.py
tests/unit/test_risk_interface.py
tests/unit/test_memory_interface.py
tests/unit/test_interface_schemas.py
tests/unit/test_api_interface.py
tests/unit/test_cli_interface.py
tests/unit/test_dashboard_interface.py
tests/unit/test_agent_interface.py
tests/unit/test_interfaces_exports.py


### Coverage Areas

- Data provider contract behavior
- Market data validation
- Latest candle retrieval
- Close price extraction
- Model contract behavior
- Model training data validation
- Model prediction validation
- Single-row prediction
- Model save/load contract behavior
- Strategy contract behavior
- Strategy decision generation
- Strategy signal validation
- Risk contract behavior
- Risk trade assessment
- Risk rejection reasons
- Risk position sizing
- Memory contract behavior
- Memory storage
- Memory retrieval
- Memory search
- Memory validation
- Request schema validation
- Response schema validation
- Interface envelope validation
- API-style interface access
- CLI-style command access
- Dashboard-style read access
- Agent-style action access
- Interfaces package exports

### Command


python -m pytest


### Notes

The interface tests are deterministic and do not require external APIs, databases, brokers, dashboards, HTTP servers, or live agent runtimes.
```