# AQOS Style Guide

> AI Quant Operating System (AQOS)
>
> This document defines the coding standards, formatting rules,
> naming conventions, and best practices used throughout AQOS.

---

# Purpose

The purpose of this guide is to ensure that every file in AQOS:

- Looks consistent
- Is easy to read
- Is easy to maintain
- Is easy to review
- Scales as the project grows

Consistency is more important than personal preference.

---

# Python Version

Minimum Version

```
Python 3.11+
```

Current Development Version

```
Python 3.13
```

---

# General Principles

AQOS follows

- PEP 8
- PEP 257
- SOLID
- DRY
- KISS
- Clean Architecture
- Separation of Concerns
- Explicit over Implicit
- Readability Counts

---

# Code Formatting

Maximum line length

```
88 characters
```

Indentation

```
4 spaces
```

Never use tabs.

Always end files with a newline.

---

# Imports

Use the following order.

### Standard Library

```python
from pathlib import Path
import logging
```

### Third-Party

```python
import pandas as pd
import numpy as np
```

### AQOS Imports

```python
from aqos.data import Provider
```

Separate each group with one blank line.

---

# Avoid

```python
from module import *
```

Wildcard imports are prohibited.

---

# Type Hints

All public methods must include type hints.

Good

```python
def load(path: str) -> pd.DataFrame:
    ...
```

Bad

```python
def load(path):
    ...
```

---

# Docstrings

Use Google-style docstrings.

Example

```python
def generate(dataframe: pd.DataFrame) -> pd.DataFrame:
    """
    Generate trading features.

    Args:
        dataframe:
            Input market data.

    Returns:
        DataFrame containing generated features.
    """
```

Every public class and function should include a docstring.

---

# Naming Conventions

## Variables

Use

```python
market_data

close_price

trade_signal
```

Avoid

```python
x

tmp

abc

data1
```

---

## Functions

Use verbs.

Good

```python
load_data()

calculate_rsi()

generate_features()

detect_pattern()
```

---

## Classes

Use PascalCase.

Good

```python
PatternDetector

MarketRegime

FeaturePipeline
```

---

## Constants

Use uppercase.

```python
DEFAULT_WINDOW

MAX_POSITION_SIZE

DEFAULT_TIMEOUT
```

---

## Modules

Use lowercase.

```text
pattern_detector.py

market_regime.py

support_resistance.py
```

Never use CamelCase filenames.

---

# Classes

Each class should have one responsibility.

Avoid

```python
class Strategy:
    # 3000 lines
```

Prefer

```python
PatternDetector

LiquidityDetector

MarketRegime
```

Small classes are easier to test and maintain.

---

# Functions

Prefer

- Small
- Focused
- Readable

Aim for

```
10–30 lines
```

Large functions should be refactored.

---

# Comments

Explain **why**, not **what**.

Good

```python
# Rolling window is used to reduce noise in price swings.
```

Avoid

```python
# Add two numbers.
```

If the code needs comments to explain what it does, consider refactoring it.

---

# Logging

Use AQOS logging.

Good

```python
logger.info("Loading market data...")
```

Avoid

```python
print("Loading...")
```

Production code should not use `print()`.

---

# Error Handling

Raise meaningful exceptions.

Good

```python
raise DataValidationError(
    "Missing required OHLC columns."
)
```

Avoid

```python
except:
    pass
```

Never silently ignore exceptions.

---

# Magic Numbers

Avoid

```python
if value > 17:
```

Prefer

```python
DEFAULT_WINDOW = 20

if value > DEFAULT_WINDOW:
```

---

# DataFrames

Never modify input data directly.

Good

```python
dataframe = dataframe.copy()
```

Always return a new DataFrame when transforming data.

---

# Testing

Every public module should have

- Unit Tests

Every pipeline should also have

- Integration Tests

---

# File Structure

Recommended order

```python
Module Docstring

Imports

Constants

Classes

Functions

Private Helpers
```

---

# Module Exports

Every package should define

```python
__all__ = [
    ...
]
```

Avoid implicit exports.

---

# Dependencies

Prefer

- Standard Library
- Stable packages
- Well-maintained libraries

Avoid unnecessary dependencies.

---

# Performance

Prefer

- Vectorized pandas operations
- Efficient algorithms
- Lazy evaluation where appropriate

Avoid

- Unnecessary loops
- Duplicate calculations
- Premature optimization

---

# Documentation

When code changes, update documentation if applicable.

Possible files include

- ROADMAP.md
- DECISIONS.md
- CHANGELOG.md
- ARCHITECTURE.md
- CODEBASE.md
- TESTING.md
- API.md
- ENHANCEMENTS.md
- PROJECT_STATE.md

Documentation is part of the Definition of Done.

---

# Git Commit Style

Examples

```
feat(strategy): add liquidity detector

feat(data): implement data provider

fix(features): correct RSI calculation

refactor(core): simplify logger

docs: update roadmap

test(strategy): add pattern detector tests
```

---

# Folder Naming

Use lowercase.

Good

```
strategy

features

models
```

Avoid

```
Strategy

Features

Models
```

---

# File Naming

Use snake_case.

Good

```
market_regime.py

pattern_detector.py

feature_pipeline.py
```

Avoid

```
MarketRegime.py

PatternDetector.py

FeaturePipeline.py
```

---

# Code Review Checklist

Before committing, verify:

- Code builds successfully.
- Tests pass.
- Type hints are present.
- Docstrings are complete.
- Logging is appropriate.
- No unused imports.
- No wildcard imports.
- No commented-out code.
- Documentation updated.

---

# Definition of Done

A task is complete only when:

- Code implemented
- Unit tests passing
- Integration tests passing (if applicable)
- Documentation updated
- Git commit created

---

# AQOS Engineering Standards

Every module should be:

- Readable
- Modular
- Testable
- Reusable
- Extensible
- Scalable
- Well documented

---

# Final Rule

Write code for the next engineer who will maintain AQOS.

Assume that engineer has never seen your code before.

Make it easy for them to understand, test, extend, and trust.