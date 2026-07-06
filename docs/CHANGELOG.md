# Changelog

All notable changes to AQOS are documented in this file.

The format is inspired by **Keep a Changelog** and follows **Semantic Versioning** principles.

---

# [Unreleased]

Future changes will be listed here before the next release.

---

# [v0.5.0-dev] - 2026-07-07

## Added

### Sprint 005 — Models

#### Base Model

- Added abstract base model interface.
- Standardized model lifecycle (`fit`, `predict`, `save`, `load`).
- Added unit tests.

#### Dataset

- Added dataset preparation utility.
- Added feature/target splitting.
- Added dataset validation.
- Added configurable target column.
- Added unit tests.

#### Predictor

- Added prediction engine.
- Added model wrapper for inference.
- Added prediction validation.
- Added unit tests.

#### Encoder

- Added feature encoder.
- Added encoded feature interface.
- Added unit tests.

#### Transformer

- Added feature transformer.
- Added transformation interface.
- Added unit tests.

#### Similarity Engine

- Added feature vector similarity engine.
- Added similarity scoring.
- Added input validation.
- Added unit tests.

#### Uncertainty Engine

- Added prediction confidence estimation.
- Added probability validation.
- Added unit tests.

#### World Model

- Added market world-state representation.
- Added prediction aggregation.
- Added confidence integration.
- Added world-state validation.
- Added unit tests.

---

## Tests

- Added complete unit test coverage for all Model modules.
- Improved floating-point assertions using `pytest.approx()`.
- All Sprint 005 tests passed successfully.

---

## Documentation

- Updated project roadmap.
- Updated project state.
- Updated codebase documentation.
- Updated testing documentation.
- Updated enhancement backlog.

---

# [v0.4.0-dev] - 2026-07-07

## Added

### Sprint 004 — Strategy Engine

#### Base Strategy

- Implemented base strategy interface.

#### Pattern Detector

- Added candlestick pattern detection.
- Added unit tests.

#### Market Regime

- Added Bull Market detection.
- Added Bear Market detection.
- Added Sideways Market detection.
- Added unit tests.

#### Support & Resistance

- Added rolling support detection.
- Added rolling resistance detection.
- Added unit tests.

#### Liquidity

- Added liquidity zone detection.
- Added unit tests.

#### Trend Structure

- Added Higher High detection.
- Added Higher Low detection.
- Added Lower High detection.
- Added Lower Low detection.
- Added trend classification.
- Added unit tests.

#### Signal Engine

- Added Buy signal generation.
- Added Sell signal generation.
- Added Hold signal generation.
- Added unit tests.

#### Entry Engine

- Added trade entry decision engine.
- Added unit tests.

#### Exit Engine

- Added trade exit decision engine.
- Added unit tests.

#### Stop Loss Engine

- Added configurable stop-loss engine.
- Added unit tests.

#### Take Profit Engine

- Added configurable take-profit engine.
- Added unit tests.

---

## Tests

- Added complete unit test coverage for all Strategy modules.
- All Sprint 004 tests passed successfully.

---

## Documentation

- Updated project roadmap.
- Updated project state.
- Updated architecture documentation.
- Updated codebase documentation.
- Updated testing documentation.
- Updated enhancement backlog.
- Updated API documentation.
- Added Architecture Decision Records for Sprint 004.

---

# [v0.3.0-dev] - 2026-07-06

## Added

### Sprint 003 — Feature Engineering

- Base feature interface.
- Technical indicators.
- Candlestick feature extraction.
- Price Action features.
- Statistical features.
- Market Structure features.
- Feature pipeline.
- Complete unit tests.

---

# [v0.2.0-dev] - 2026-07-06

## Added

### Sprint 002 — Data Layer

- Data Provider.
- Data Loader.
- Data Validator.
- Data Cleaner.
- Data Storage.
- Data Catalog.
- Data Pipeline.
- Complete unit tests.

---

# [v0.1.0-dev] - 2026-07-06

## Added

### Sprint 001 — Core Infrastructure

- Version management.
- Configuration management.
- Logger.
- Exception framework.
- Bootstrap.
- Health check.
- Command Line Interface.
- Complete unit tests.

---

# [v0.0.0-dev] - 2026-07-06

## Added

### Sprint 000 — Project Foundation

- Repository initialization.
- Project structure.
- Python packaging.
- Development environment.
- Initial documentation.
- Testing framework.
- Coding standards.

---

## Versioning Strategy

Development versions

```
v0.x.x-dev
```

Release candidates

```
v1.0.0-rc1
```

Production releases

```
v1.0.0
```

Patch releases

```
v1.0.1
```

Minor releases

```
v1.1.0
```

Major releases

```
v2.0.0
```

---

## Change Categories

Each release should use one or more of the following categories:

- Added
- Changed
- Deprecated
- Removed
- Fixed
- Security
- Performance
- Documentation
- Refactored

---

## Notes

Every completed sprint should create a new changelog entry.

This file represents the historical development timeline of AQOS and should never have previous entries removed or rewritten.