# Changelog

All notable changes to AQOS are documented in this file.

The format is inspired by **Keep a Changelog** and follows **Semantic Versioning** principles.

---

# [Unreleased]

Future changes will be listed here before the next release.

# [v0.9.0-dev] - 2026-07-07

## Added

### Sprint 009 — Evaluation

#### Evaluation Metrics

- Added classification accuracy.
- Added mean absolute error.
- Added mean squared error.
- Added root mean squared error.
- Added trade win rate.
- Added average profit.
- Added total profit.
- Added profit factor.
- Added unit tests.

#### Backtesting

- Added backtest trade model.
- Added backtest result model.
- Added lightweight backtesting engine.
- Added equity curve generation.
- Added win-rate calculation.
- Added max drawdown calculation.
- Added unit tests.

#### Walk-Forward Validation

- Added walk-forward split model.
- Added walk-forward validation splitter.
- Added configurable train size.
- Added configurable test size.
- Added configurable step size.
- Added unit tests.

#### Paper Trading

- Added paper trade model.
- Added paper trading engine.
- Added simulated trade opening.
- Added simulated trade closing.
- Added realized profit calculation.
- Added unrealized equity calculation.
- Added open and closed trade tracking.
- Added unit tests.

#### Evaluation Reports

- Added evaluation report model.
- Added backtest report generation.
- Added text summary generation.
- Added report details for trades.
- Added unit tests.

#### Evaluation Pipeline

- Added unified evaluation pipeline.
- Integrated metrics, backtesting, walk-forward validation, paper trading, and reporting.
- Added classification evaluation.
- Added regression evaluation.
- Added trade evaluation.
- Added backtest report generation.
- Added paper trading access.
- Added unit tests.

---

## Tests

- Added complete unit test coverage for all Evaluation modules.
- All Sprint 009 tests passed successfully.

---

## Documentation

- Updated project roadmap.
- Updated project state.
- Updated codebase documentation.
- Updated testing documentation.
- Updated enhancement backlog.
- Updated architecture documentation.

# [v0.8.0-dev] - 2026-07-07

## Added

### Sprint 008 — Risk

#### Position Sizing

- Added position sizing engine.
- Added risk amount calculation.
- Added maximum position size limit.
- Added unit tests.

#### Exposure Management

- Added exposure record model.
- Added exposure calculation.
- Added exposure percentage calculation.
- Added exposure limit validation.
- Added total exposure calculation.
- Added unit tests.

#### Drawdown Management

- Added drawdown record model.
- Added absolute drawdown calculation.
- Added drawdown percentage calculation.
- Added maximum drawdown calculation from equity curve.
- Added drawdown limit validation.
- Added unit tests.

#### Risk Constraints

- Added risk decision model.
- Added unified risk constraint validation.
- Added risk amount limit checks.
- Added exposure limit checks.
- Added drawdown limit checks.
- Added multi-violation reason reporting.
- Added unit tests.

#### Stop Loss Management

- Added stop-loss record model.
- Added buy-side and sell-side stop-loss calculation.
- Added stop-loss calculation from risk-per-unit amount.
- Added stop-loss trigger checks.
- Added unit tests.

#### Take Profit Management

- Added take-profit record model.
- Added reward-risk based take-profit calculation.
- Added buy-side and sell-side take-profit checks.
- Added take-profit hit detection.
- Added unit tests.

#### Portfolio Risk Management

- Added portfolio position model.
- Added portfolio position value calculation.
- Added unrealized profit/loss calculation.
- Added total portfolio value calculation.
- Added total unrealized PnL calculation.
- Added exposure grouping by symbol.
- Added symbol exposure limit checks.
- Added largest symbol exposure percentage calculation.
- Added unit tests.

#### Risk Pipeline

- Added complete risk assessment model.
- Added unified risk pipeline.
- Integrated position sizing, exposure, drawdown, constraints, stop-loss, take-profit, and portfolio risk managers.
- Added complete trade risk assessment flow.
- Added stop-loss trigger reporting.
- Added take-profit hit reporting.
- Added risk rejection reason reporting.
- Added unit tests.

---

## Changed

### Risk Architecture

- Expanded the Risk subsystem from basic risk controls to a complete risk-management package.
- Added portfolio-level and pipeline-level risk orchestration.
- Added risk-specific stop-loss and take-profit modules to separate account-level risk control from strategy-level exit logic.

---

## Tests

- Added complete unit test coverage for all Risk modules.
- All Sprint 008 tests passed successfully.

---

## Documentation

- Updated project roadmap.
- Updated project state.
- Updated codebase documentation.
- Updated testing documentation.
- Updated enhancement backlog.
- Updated architecture documentation.
- Added architecture decision record for expanded Risk subsystem.

# [v0.7.0-dev] - 2026-07-07

## Added

### Sprint 007 — Memory

#### Pattern Memory

- Added pattern record storage.
- Added pattern metadata support.
- Added pattern lookup by symbol.
- Added pattern lookup by pattern name.
- Added unit tests.

#### Trade Memory

- Added trade record storage.
- Added trade metadata support.
- Added open trade lookup.
- Added closed trade lookup.
- Added trade lookup by symbol and side.
- Added unit tests.

#### Embedding Engine

- Added deterministic hash-based embedding generation.
- Added normalized vector output.
- Added batch text encoding.
- Added unit tests.

#### Vector Store

- Added in-memory vector storage.
- Added vector record model.
- Added vector search result model.
- Added cosine similarity search.
- Added vector validation.
- Added unit tests.

#### Memory Retriever

- Added memory retrieval engine.
- Integrated embedding generation with vector search.
- Added text-based memory indexing.
- Added query-based retrieval.
- Added unit tests.

#### Memory Pipeline

- Added unified memory pipeline.
- Integrated pattern memory, trade memory, retriever, embedding, and vector store.
- Added pattern memory indexing.
- Added trade memory indexing.
- Added memory counts.
- Added memory clearing.
- Added unit tests.

---

## Tests

- Added complete unit test coverage for all Memory modules.
- All Sprint 007 tests passed successfully.

---

## Documentation

- Updated project roadmap.
- Updated project state.
- Updated codebase documentation.
- Updated testing documentation.
- Updated enhancement backlog.



# [v0.6.0-dev] - 2026-07-07

## Added

### Sprint 006 — Learning Engine

#### Trainer

- Added model training engine.
- Added training validation.
- Added unit tests.

#### Optimizer

- Added optimizer configuration.
- Added learning-rate validation.
- Added unit tests.

#### Scheduler

- Added scheduler configuration.
- Added scheduling parameter validation.
- Added unit tests.

#### Loss

- Added loss function configuration.
- Added loss validation.
- Added unit tests.

#### Cross Validation

- Added cross-validation configuration.
- Added fold validation.
- Added unit tests.

#### Learning Pipeline

- Added unified learning pipeline.
- Integrated trainer, optimizer, scheduler, loss, and cross-validation.
- Added pipeline validation.
- Added unit tests.

---

## Tests

- Added complete unit test coverage for all Learning modules.
- All Sprint 006 tests passed successfully.

---

## Documentation

- Updated project roadmap.
- Updated project state.
- Updated codebase documentation.
- Updated testing documentation.
- Updated enhancement backlog.
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