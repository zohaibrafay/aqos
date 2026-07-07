# Changelog

All notable changes to AQOS are documented in this file.

The format is inspired by **Keep a Changelog** and follows **Semantic Versioning** principles.

---

# [Unreleased]

Future changes will be listed here before the next release.
# [v0.13.0-dev] — Sprint 013 Common Utilities

Status: Completed

### Added

- Added `constants.py` for shared AQOS constants.
- Added `validators.py` for reusable validation helpers.
- Added `id_helpers.py` for ID generation, normalization, validation, and uniqueness helpers.
- Added `time_utils.py` for UTC datetime, date, timestamp, and time-window helpers.
- Added `serialization.py` for JSON-safe serialization and dictionary helpers.
- Added `math_utils.py` for common numeric, trading, and statistical helpers.
- Added `error_helpers.py` for structured error handling and exception conversion.
- Added complete common package exports through `src/aqos/common/__init__.py`.

### Added Constants

- Added project constants.
- Added default trading constants.
- Added valid signal constants.
- Added valid side constants.
- Added valid order type constants.
- Added valid status constants.
- Added valid sentiment constants.
- Added valid impact constants.
- Added valid memory type constants.
- Added valid timeframe constants.
- Added OHLCV column constants.
- Added namespace constants.
- Added message constants.

### Added Validators

- Added string, list, dictionary, payload, and metadata validators.
- Added positive number, non-negative number, positive integer, and ratio validators.
- Added required key and required column validators.
- Added OHLCV column and OHLCV record validators.
- Added symbol, timeframe, signal, side, order type, sentiment, impact, and memory type validators.
- Added account balance, risk percent, price, and quantity validators.

### Added ID Helpers

- Added UUID generation.
- Added short ID generation.
- Added prefixed ID generation.
- Added compound ID generation.
- Added timestamp ID generation.
- Added ID normalization.
- Added ID validation.
- Added separator validation.
- Added unique ID helper.
- Added ID validity check helper.

### Added Time Utilities

- Added UTC now helpers.
- Added ISO datetime parsing.
- Added date parsing.
- Added UTC conversion.
- Added datetime formatting.
- Added date formatting.
- Added timestamp conversion helpers.
- Added time addition helpers.
- Added time difference helpers.
- Added past/future checks.
- Added time-window checks.
- Added payload datetime normalization.

### Added Serialization Helpers

- Added JSON-safe value conversion.
- Added dictionary serialization.
- Added list serialization.
- Added JSON conversion helpers.
- Added safe dictionary access.
- Added dictionary compaction.
- Added none-value removal.
- Added dictionary flattening.
- Added dictionary unflattening.
- Added shallow dictionary merging.
- Added deep dictionary merging.

### Added Math Helpers

- Added numeric validation.
- Added safe division.
- Added percentage change.
- Added percentage return.
- Added clamping.
- Added decimal rounding.
- Added mean.
- Added median.
- Added variance.
- Added standard deviation.
- Added min-max normalization.
- Added weighted average.
- Added rolling mean.
- Added cumulative sum.
- Added maximum drawdown.
- Added profit factor.
- Added win rate.

### Added Error Helpers

- Added `ErrorInfo`.
- Added error code normalization.
- Added error message normalization.
- Added structured error builders.
- Added not-found error builder.
- Added validation error builder.
- Added type error builder.
- Added exception-to-error conversion.
- Added exception-to-dictionary conversion.
- Added error message formatting.
- Added error collection helpers.
- Added safe raise helpers.
- Added safe execution helper.

### Tests

- Added unit tests for common constants.
- Added unit tests for common validators.
- Added unit tests for ID helpers.
- Added unit tests for time utilities.
- Added unit tests for serialization helpers.
- Added unit tests for math utilities.
- Added unit tests for error helpers.
- Added unit tests for common package exports.

### Notes

- Sprint 013 utilities are deterministic and do not require external services.
- Existing placeholder files `decorators.py`, `enums.py`, `helpers.py`, and `types.py` remain reserved for future use.
- Common utilities are now ready to be adopted across future AQOS integration work.

# [v0.12.0-dev] — Sprint 012 Agents

Status: Completed

### Added

- Added `AgentTask` for agent task input.
- Added `AgentResult` for agent result output.
- Added `AgentBase` as the shared base class for all AQOS agents.
- Added `DataAgent` for market data availability, summaries, OHLCV preparation, close prices, and quality checks.
- Added `MarketAgent` for market snapshots, trend summaries, regime summaries, news context, calendar context, and market state generation.
- Added `ResearchAgent` for hypothesis generation, experiment planning, experiment creation, research finding storage, and research summaries.
- Added `StrategyAgent` for strategy signals, decisions, signal explanations, entry checks, exit checks, and strategy handoffs.
- Added `RiskAgent` for position sizing, trade assessment, trade approval, rejection reasons, and risk handoffs.
- Added `ExecutionAgent` for simulated trade execution, order placement, order filling, order cancellation, position closing, order status, and execution summaries.
- Added `EvaluationAgent` for backtest execution, backtest summaries, backtest comparison, performance grading, and evaluation reports.
- Added `MemoryAgent` for memory storage, recall, retrieval, forgetting, summaries, pattern memory, and trade memory.
- Added `AgentOrchestrator` for routing and multi-agent workflows.
- Added agents export coverage through `src/aqos/agents/__init__.py`.

### Added Workflows

- Added market-strategy workflow.
- Added strategy-risk workflow.
- Added risk-execution workflow.
- Added full trade workflow.
- Added research workflow.
- Added backtest workflow.
- Added memory workflow.
- Added generic agent routing workflow.

### Tests

- Added unit tests for `AgentBase`, `AgentTask`, and `AgentResult`.
- Added unit tests for `DataAgent`.
- Added unit tests for `MarketAgent`.
- Added unit tests for `ResearchAgent`.
- Added unit tests for `StrategyAgent`.
- Added unit tests for `RiskAgent`.
- Added unit tests for `ExecutionAgent`.
- Added unit tests for `EvaluationAgent`.
- Added unit tests for `MemoryAgent`.
- Added unit tests for `AgentOrchestrator`.
- Added unit tests for agents package exports.

### Changed

- Expanded AQOS from service/interface-level orchestration to agent-level workflow orchestration.

### Notes

- Sprint 012 agents are deterministic, in-memory friendly, and testable.
- Agents currently coordinate existing AQOS services and internal logic.
- Agents do not call external LLMs yet.
- Autonomous reasoning, LLM tool-calling, live broker integration, and real-time agent planning are reserved for future phases.


# [v0.11.0-dev] — 2026-07-07

Status: Completed

### Added

- Added `DataProviderInterface` for market data provider contracts.
- Added `ModelInterface` for model training, prediction, saving, and loading contracts.
- Added `StrategyInterface` for strategy signal, entry, and exit contracts.
- Added `StrategyInterfaceDecision`.
- Added `RiskInterface` for trade validation, rejection explanation, and position sizing contracts.
- Added `RiskInterfaceDecision`.
- Added `MemoryInterface` for memory storage, retrieval, search, and removal contracts.
- Added `MemoryInterfaceRecord`.
- Added `MemoryInterfaceSearchResult`.
- Added interface request and response schemas.
- Added `MarketDataRequest`.
- Added `PredictionRequest`.
- Added `PredictionResponse`.
- Added `StrategyRequest`.
- Added `StrategyResponse`.
- Added `RiskRequest`.
- Added `RiskResponse`.
- Added `BacktestRequest`.
- Added `BacktestResponse`.
- Added `ExperimentRequest`.
- Added `ExperimentResponse`.
- Added `InterfaceEnvelope`.
- Added `APIInterface` for API-style access to AQOS services.
- Added `CLIInterface` for CLI-style command access.
- Added `DashboardInterface` for dashboard-style read access.
- Added `AgentInterface` for AI-agent-style action access.
- Added interfaces export coverage through `src/aqos/interfaces/__init__.py`.

### Tests

- Added unit tests for `DataProviderInterface`.
- Added unit tests for `ModelInterface`.
- Added unit tests for `StrategyInterface`.
- Added unit tests for `RiskInterface`.
- Added unit tests for `MemoryInterface`.
- Added unit tests for interface schemas.
- Added unit tests for `APIInterface`.
- Added unit tests for `CLIInterface`.
- Added unit tests for `DashboardInterface`.
- Added unit tests for `AgentInterface`.
- Added unit tests for interfaces package exports.

### Changed

- Expanded the Interfaces subsystem from only domain contracts to a complete interface layer with both domain contracts and application-facing interfaces.

### Notes

- Sprint 011 does not create a live HTTP server, web dashboard, or autonomous agent runtime.
- Current interfaces are lightweight, deterministic, testable, and in-memory friendly.
- Real FastAPI routes, terminal commands, dashboard UI, and agent orchestration can be built later on top of these interfaces.

# [v0.10.0-dev] — 2026-07-07

Status: Completed

### Added

- Added `DataService` for registering and managing market datasets.
- Added `DatasetSnapshot` data structure.
- Added `ModelService` for registering models, running predictions, calculating confidence, and building world states.
- Added `ModelSnapshot` and `PredictionSnapshot`.
- Added `StrategyService` for generating signals, entry/exit decisions, and strategy-level SL/TP planning.
- Added `StrategyDecision`.
- Added `BacktestService` for running, storing, retrieving, and reporting backtest results.
- Added `BacktestRun`.
- Added `ExperimentService` for creating, tracking, updating, failing, completing, and comparing experiments.
- Added `ExperimentRun`.
- Added `MarketDataService` for external-style OHLCV candle feed management.
- Added `MarketCandle` and `MarketDataFeed`.
- Added `BrokerService` for simulated broker order and position handling.
- Added `BrokerOrder` and `BrokerPosition`.
- Added `NewsService` for financial news storage, filtering, sentiment, and impact scoring.
- Added `NewsItem`.
- Added `EconomicCalendarService` for storing, filtering, and checking macroeconomic events.
- Added `EconomicCalendarEvent`.
- Added `StorageService` for generic namespace-based record persistence.
- Added `StorageRecord`.
- Added services export coverage through `src/aqos/services/__init__.py`.

### Tests

- Added unit tests for `DataService`.
- Added unit tests for `ModelService`.
- Added unit tests for `StrategyService`.
- Added unit tests for `BacktestService`.
- Added unit tests for `ExperimentService`.
- Added unit tests for `MarketDataService`.
- Added unit tests for `BrokerService`.
- Added unit tests for `NewsService`.
- Added unit tests for `EconomicCalendarService`.
- Added unit tests for `StorageService`.
- Added unit tests for services package exports.

### Changed

- Expanded the Services subsystem from only internal orchestration files to a complete service layer with both internal orchestration services and external integration-style service abstractions.

### Notes

- Real broker, market data, news, calendar, and persistence integrations are intentionally not connected yet.
- Current implementations are deterministic, in-memory, lightweight, and testable.
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