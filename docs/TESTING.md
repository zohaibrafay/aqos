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

# Testing Standards

Each module should test:

- Successful execution
- Invalid input
- Edge cases
- Exception handling
- Return types
- Expected outputs

---

# Current Status

```
All tests passing
```

Current Development Version

```
v0.9.0-dev
```

---

# Future Testing

The following test categories will be added in later phases:

## Integration Tests

- Data → Features
- Features → Models
- Models → Learning
- Learning → Memory
- Strategy → Risk
- Services → Agents

---

## System Tests

- Full prediction pipeline
- Full trading pipeline
- Research workflow
- Multi-agent workflow

---

## Performance Tests

- Large dataset handling
- Model inference latency
- Memory usage
- Pipeline throughput

---

## End-to-End Tests

- Historical backtesting
- Paper trading
- Live trading
- AI research workflow

---

# Testing Rules

1. Every source file must have a corresponding unit test.
2. New features require new tests.
3. Bug fixes require regression tests.
4. All tests must pass before a sprint is marked complete.
5. Documentation is updated only after sprint completion.

---

# Notes

Testing is considered a first-class citizen in AQOS.

No sprint is complete until all implemented modules have passing tests.

