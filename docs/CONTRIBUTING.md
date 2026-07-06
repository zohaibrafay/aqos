# Contributing to AQOS

Welcome to **AQOS (AI Quant Operating System)**.

Thank you for contributing to the project.

This document defines the engineering standards, development workflow, coding practices, Git workflow, testing requirements, and documentation standards for AQOS.

---

# Project Goal

AQOS aims to become an institutional-grade AI Quant Research Platform capable of:

- Market Data Processing
- Feature Engineering
- Market Intelligence
- Machine Learning
- Deep Learning
- Reinforcement Learning
- Risk Management
- Backtesting
- Paper Trading
- Live Trading
- Multi-Agent AI Systems

Every contribution should move the project toward this vision.

---

# Engineering Principles

AQOS follows these principles:

- Clean Architecture
- SOLID
- DRY (Don't Repeat Yourself)
- KISS (Keep It Simple)
- Separation of Concerns
- Modular Design
- Extensibility
- Scalability
- Reproducibility
- Explainability

---

# Development Workflow

Every task must follow this workflow.

```
Code
    ↓
Unit Tests
    ↓
Integration Tests
    ↓
Run All Tests
    ↓
Update Documentation
    ↓
Git Commit
    ↓
Move to Next Task
```

A task is **NOT COMPLETE** until every step above has been completed.

---

# Definition of Done (DoD)

A task is considered complete only when:

- Code is implemented.
- Unit tests pass.
- Integration tests pass (if applicable).
- Documentation is updated.
- No linting errors.
- No circular dependencies.
- Git commit created.

---

# Git Workflow

Commit frequently.

Recommended commit format:

```
feat(data): implement market data provider

feat(features): add RSI feature

feat(strategy): implement market regime detection

fix(data): resolve validation bug

refactor(core): simplify configuration loading

docs: update roadmap

test(strategy): add liquidity detector tests
```

---

# Branch Strategy

Recommended branch naming:

```
main

develop

feature/<feature-name>

bugfix/<bug-name>

refactor/<module-name>

documentation/<topic>
```

Examples

```
feature/liquidity-detector

feature/market-regime

refactor/data-pipeline

documentation/roadmap
```

---

# Pull Request Checklist

Before opening a Pull Request:

- Code builds successfully
- Tests pass
- Documentation updated
- CHANGELOG updated
- ROADMAP updated (if applicable)
- No debug code
- No commented-out code
- No unused imports

---

# Coding Standards

Every new module must include:

- Type hints
- Docstrings
- Unit tests
- Meaningful variable names
- Small focused functions
- Logging where appropriate

Avoid:

- Global variables
- Magic numbers
- Deep nesting
- Duplicate logic

---

# File Organization

Each module should have a single responsibility.

Example

```
strategy/

base.py

pattern_detector.py

market_regime.py

liquidity.py

entry.py

exit.py

execution.py
```

Do not create large files that implement multiple unrelated responsibilities.

---

# Documentation Rules

Documentation is part of the codebase.

Whenever code changes:

Update documentation if applicable.

Possible files:

- ROADMAP.md
- DECISIONS.md
- CHANGELOG.md
- ARCHITECTURE.md
- CODEBASE.md
- TESTING.md
- API.md
- ENHANCEMENTS.md
- PROJECT_STATE.md

---

# Testing Policy

Every public class should have:

- Unit Tests

Every pipeline should have:

- Integration Tests

Critical components should also include:

- Edge Case Tests
- Error Handling Tests
- Regression Tests

---

# Architecture Changes

Architecture changes require:

1. Technical justification
2. Alternatives considered
3. Benefits
4. Drawbacks
5. Architecture Decision Record (ADR)

No architecture changes should be made without updating:

```
docs/DECISIONS.md
```

---

# Project Structure

```
src/
└── aqos/

agents/

common/

core/

data/

evaluation/

features/

interfaces/

learning/

memory/

models/

risk/

services/

strategy/
```

Top-level packages are considered stable.

---

# Dependencies

When introducing new dependencies:

Consider:

- Maintenance
- Community support
- Performance
- License
- Long-term stability

Avoid unnecessary dependencies.

Prefer the Python Standard Library whenever practical.

---

# Performance Guidelines

Prefer:

- Vectorized operations
- Efficient algorithms
- Lazy loading
- Modular pipelines

Avoid premature optimization.

Optimize based on profiling and measured bottlenecks.

---

# Security Guidelines

Never commit:

- API Keys
- Passwords
- Secrets
- Tokens
- Credentials

Use environment variables.

---

# Logging

Use the AQOS logging framework.

Avoid print statements in production code.

Log levels:

- DEBUG
- INFO
- WARNING
- ERROR
- CRITICAL

---

# Error Handling

Raise meaningful exceptions.

Never silently ignore errors.

Every exception should provide useful context.

---

# Code Reviews

During review, verify:

- Readability
- Maintainability
- Test coverage
- Documentation
- Architecture consistency

---

# Communication

Before making significant changes:

- Discuss the proposal
- Record an ADR if required
- Update documentation
- Implement after approval

---

# Long-Term Vision

AQOS is designed to evolve into an institutional-grade quantitative research platform.

Every contribution should prioritize:

- Maintainability
- Reliability
- Scalability
- Explainability
- Extensibility

over short-term convenience.

---

# Final Rule

Write code as if another engineer will maintain it five years from now.

Because that engineer may be you.