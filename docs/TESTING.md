# AQOS Testing Strategy

> AI Quant Operating System (AQOS)
>
> This document defines the testing philosophy, testing standards,
> testing workflow, and quality requirements for AQOS.

---

# Purpose

Testing ensures that AQOS remains:

- Correct
- Reliable
- Maintainable
- Reproducible
- Safe to refactor

Every feature added to AQOS must be verifiable through automated tests.

---

# Testing Philosophy

AQOS follows the following testing principles:

- Test early
- Test often
- Automate everything possible
- Small isolated tests
- Reproducible results
- Fast feedback

Tests should make development safer—not slower.

---

# Testing Pyramid

```

                End-to-End Tests
                     ▲
                     │
            Integration Tests
                     ▲
                     │
               Unit Tests

```

Most tests should be Unit Tests.

---

# Testing Types

## 1. Unit Tests

Purpose

Verify individual classes and functions.

Examples

- Pattern Detector
- Market Regime
- Data Validator
- Feature Calculator

Requirements

- Independent
- Fast
- No external services
- Deterministic

Status

Required

---

## 2. Integration Tests

Purpose

Verify multiple modules working together.

Examples

```
Provider
    ↓
Loader
    ↓
Validator
    ↓
Cleaner
```

or

```
Data
    ↓
Features
    ↓
Strategy
```

Status

Required where applicable.

---

## 3. End-to-End Tests

Purpose

Verify the complete AQOS workflow.

Example

```
Market Data

↓

Features

↓

Strategy

↓

Prediction

↓

Risk

↓

Evaluation
```

Status

Phase 3

---

## 4. Regression Tests

Purpose

Ensure previously fixed bugs never return.

Status

Required

---

## 5. Performance Tests

Purpose

Measure:

- Speed
- Memory
- CPU
- Scalability

Status

Phase 2

---

## 6. Stress Tests

Purpose

Verify AQOS under heavy workloads.

Examples

- Millions of candles
- Large datasets
- Multiple symbols
- Multiple timeframes

Status

Phase 3

---

# Test Directory Structure

```
tests/

├── unit/
├── integration/
├── regression/
├── performance/
└── end_to_end/
```

---

# Unit Testing Rules

Every public class should have a corresponding test.

Example

```
src/aqos/data/provider.py

↓

tests/unit/test_provider.py
```

Naming convention

```
test_<module>.py
```

Examples

```
test_provider.py

test_pattern_detector.py

test_market_regime.py

test_liquidity.py
```

---

# Integration Testing Rules

Integration tests validate module interaction.

Examples

```
test_data_pipeline.py

test_feature_pipeline.py

test_strategy_pipeline.py

test_training_pipeline.py
```

---

# Test Naming Convention

Test functions

```
test_provider_loads_dataframe()

test_market_regime_detects_bull_market()

test_pattern_detector_detects_doji()
```

Avoid

```
test1()

test_case()

check()

example()
```

---

# Test Coverage

Current Goal

```
Minimum

80%
```

Long-Term Goal

```
90%+
```

Critical modules should approach

```
100%
```

Examples

- Risk
- Strategy
- Models
- Evaluation

---

# Running Tests

Run all tests

```bash
python -m pytest
```

Run unit tests

```bash
python -m pytest tests/unit
```

Run integration tests

```bash
python -m pytest tests/integration
```

Run a single file

```bash
python -m pytest tests/unit/test_provider.py
```

Run a single test

```bash
python -m pytest -k provider
```

---

# Current Test Status

| Sprint | Status |
|---------|--------|
| Sprint 000 | ✅ |
| Sprint 001 | ✅ |
| Sprint 002 | ✅ |
| Sprint 003 | ✅ |
| Sprint 004 | 🟡 |
| Sprint 005 | ⏳ |
| Sprint 006 | ⏳ |
| Sprint 007 | ⏳ |
| Sprint 008 | ⏳ |
| Sprint 009 | ⏳ |
| Sprint 010 | ⏳ |
| Sprint 011 | ⏳ |
| Sprint 012 | ⏳ |

---

# Current Tested Modules

Completed

- Version
- Configuration
- Logger
- Exceptions
- Data Provider
- Data Loader
- Data Validator
- Data Cleaner
- Data Storage
- Data Catalog
- Data Pipeline
- Feature Base
- Technical Features
- Candlestick Features
- Price Action
- Statistical Features
- Market Structure
- Feature Pipeline
- Pattern Detector
- Market Regime
- Support & Resistance
- Liquidity

---

# Test Data

Whenever possible:

Use

- Small datasets
- Deterministic values
- Fixed random seeds

Avoid

- Live APIs
- Random failures
- Time-dependent assertions

---

# Mocking

External dependencies should be mocked.

Examples

- APIs
- Databases
- Brokers
- WebSockets

Unit tests should never depend on internet connectivity.

---

# Continuous Testing

Every completed task must pass:

```
Unit Tests

↓

Integration Tests

↓

Regression Tests
```

before moving to the next task.

---

# Bug Fix Policy

Every bug fix must include:

1. A failing test.
2. The code fix.
3. A passing test.

Never fix a bug without adding a test.

---

# Definition of Tested

A feature is considered tested when:

- Unit tests pass
- Integration tests pass (if applicable)
- Edge cases covered
- Error handling verified
- No regression introduced

---

# Future Testing Roadmap

Phase 2

- Performance Benchmarks
- Memory Benchmarks
- ML Model Validation
- Walk-Forward Testing
- Monte Carlo Testing

Phase 3

- Paper Trading Validation
- Live Trading Simulation
- Broker Integration Tests
- Distributed System Tests
- End-to-End Automation

---

# Testing Principles

Every test should be:

- Fast
- Independent
- Repeatable
- Readable
- Deterministic
- Easy to maintain

---

# Final Rule

No feature is considered complete until it has automated tests.

If a feature cannot be tested, its design should be reconsidered.