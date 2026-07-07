# AQOS Architecture Decisions (ADR)

> This document records every major engineering and architectural decision made during the development of AQOS.

---

# Purpose

This document answers one question:

> **Why was this decision made?**

Code tells us **what** was built.

Tests tell us **whether it works**.

This document explains **why we built it this way.**

---

# Decision Format

Every architecture change should follow this template.

---

## ADR-XXX

### Date

YYYY-MM-DD

### Sprint

Sprint XXX

### Status

Proposed | Accepted | Deprecated | Replaced

### Title

Short decision title.

### Context

Why this decision was necessary.

### Alternatives Considered

Option A

Description.

Option B

Description.

Option C

Description.

### Decision

Chosen solution.

### Benefits

- Benefit 1
- Benefit 2
- Benefit 3

### Drawbacks

- Drawback 1
- Drawback 2

### Impact

Affected folders/files.

### Notes

Additional comments.

---

# Decisions

---

## ADR-001

### Date

2026-07-06

### Sprint

Sprint 004

### Status

Accepted

### Title

Freeze AQOS top-level architecture.

### Context

During development, new top-level folders were being proposed while implementation was already in progress.

Changing the architecture repeatedly during active sprint work would create instability, make the codebase harder to understand, and produce unnecessary Git history noise.

AQOS is intended to become a large AI Quant Operating System, so the foundation must remain stable while individual subsystems evolve internally.

### Alternatives Considered

Option A

Continue changing folders during development.

Option B

Freeze the top-level architecture after Sprint 003.

### Decision

Freeze the top-level AQOS architecture after Sprint 003.

Architecture changes require discussion before implementation.

No new top-level package may be added without an accepted ADR.

### Benefits

- Stable development
- Easier maintenance
- Better planning
- Cleaner Git history
- Easier onboarding
- More predictable sprint execution

### Drawbacks

- Some future features may require architectural review before implementation.
- Developers must think carefully before introducing new top-level packages.

### Impact

Affected scope:

```text
Entire AQOS project
```

Frozen top-level package structure:

```text
src/aqos/
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

### Notes

Internal subsystem files may evolve when necessary.

Top-level architecture changes require a documented decision.

---

## ADR-002

### Date

2026-07-06

### Sprint

Sprint 004

### Status

Accepted

### Title

Introduce dedicated strategy modules.

### Context

Originally, market intelligence logic was being placed inside `planner.py`.

As the project evolved, it became clear that pattern detection, liquidity analysis, market regime detection, support/resistance analysis, signal generation, and trend analysis would each grow into large independent systems.

Keeping everything together would violate the Single Responsibility Principle and make testing, maintenance, and future AI integration difficult.

### Alternatives Considered

Option A

Implement all strategy logic inside `planner.py`.

Option B

Split the Strategy subsystem into specialized modules.

### Decision

Create dedicated strategy modules for independent strategy responsibilities.

The Strategy subsystem includes:

```text
strategy/
├── __init__.py
├── base.py
├── planner.py
├── pattern_detector.py
├── market_regime.py
├── support_resistance.py
├── liquidity.py
├── trend_structure.py
├── signal.py
├── entry.py
├── exit.py
├── stop_loss.py
├── take_profit.py
└── execution.py
```

Each module has a focused responsibility.

`planner.py` remains responsible for future orchestration rather than containing all strategy logic directly.

### Benefits

- Smaller modules
- Easier testing
- Better scalability
- Cleaner strategy architecture
- Easier future AI integration
- Better separation of concerns
- Easier debugging

### Drawbacks

- Slightly more files.
- Developers must understand the responsibility of each strategy module.

### Impact

Affected folder:

```text
src/aqos/strategy/
```

Key affected files:

```text
src/aqos/strategy/pattern_detector.py
src/aqos/strategy/market_regime.py
src/aqos/strategy/support_resistance.py
src/aqos/strategy/liquidity.py
src/aqos/strategy/trend_structure.py
src/aqos/strategy/signal.py
src/aqos/strategy/entry.py
src/aqos/strategy/exit.py
src/aqos/strategy/stop_loss.py
src/aqos/strategy/take_profit.py
```

### Notes

This decision is considered part of the frozen architecture.

The top-level package structure did not change.

---

## ADR-003

### Date

2026-07-06

### Sprint

Sprint 004

### Status

Accepted

### Title

Adopt a documentation-first development workflow.

### Context

AQOS is growing into an institutional-grade AI Quant Research Platform.

Maintaining accurate documentation is as important as maintaining source code.

Without a structured workflow, documentation can quickly become outdated, making it difficult to understand project progress, architectural decisions, deferred enhancements, current limitations, and future development plans.

To ensure long-term maintainability and reproducibility, documentation must be treated as part of the development process rather than an afterthought.

### Alternatives Considered

Option A

Update documentation only when convenient or before releases.

Option B

Maintain documentation continuously as part of every completed sprint.

### Decision

Documentation becomes a mandatory part of the Definition of Done.

Every sprint must follow this workflow:

```text
Implementation
    ↓
Unit Tests
    ↓
Integration Tests, when applicable
    ↓
Run All Tests
    ↓
Update Documentation
    ↓
Git Commit
    ↓
Move to Next Sprint
```

The following documents must be updated whenever applicable:

```text
docs/ROADMAP.md
docs/DECISIONS.md
docs/CHANGELOG.md
docs/ARCHITECTURE.md
docs/CODEBASE.md
docs/CONTRIBUTING.md
docs/TESTING.md
docs/STYLE_GUIDE.md
docs/ENHANCEMENTS.md
docs/RESEARCH.md
docs/API.md
docs/PROJECT_STATE.md
```

### Benefits

- Documentation always reflects the current state of the project.
- Easier project maintenance.
- Easier onboarding.
- Complete engineering history.
- Better traceability of architectural decisions.
- Prevents forgotten enhancements and technical debt.
- Enables long-term project continuity.
- Makes AQOS easier to resume after breaks.

### Drawbacks

- Requires additional effort at the end of every sprint.
- Sprint completion takes longer because documentation is part of the work.

### Impact

Affected scope:

```text
Entire AQOS project
```

Affected documentation:

```text
docs/
```

### Notes

Documentation is considered part of the production codebase.

A sprint is not complete until:

- Code is implemented.
- Tests are passing.
- Documentation is updated.
- Changes are committed to Git.

---

## ADR-004

### Date

2026-07-07

### Sprint

Sprint 008

### Status

Accepted

### Title

Expand the internal Risk subsystem architecture.

### Context

During Sprint 008, the Risk subsystem was initially implemented with the following files:

```text
risk/
├── sizing.py
├── exposure.py
├── drawdown.py
└── constraints.py
```

This provided the foundation for position sizing, exposure management, drawdown management, and basic risk constraint validation.

However, before moving into Evaluation, Paper Trading, Services, Agents, Broker Integration, and Live Trading, AQOS needed a more complete risk-management foundation.

The system also needed a clear separation between:

```text
strategy-level trade planning
```

and:

```text
account-level risk control
```

AQOS already has strategy-level modules:

```text
strategy/stop_loss.py
strategy/take_profit.py
```

These are responsible for strategy planning.

Risk-level stop-loss and take-profit logic is different.

Risk modules must validate whether the trade is safe for the account, whether reward-risk is acceptable, whether a stop loss has been triggered, and whether the trade violates portfolio-level risk rules.

### Alternatives Considered

Option A

Keep the Risk subsystem minimal with only:

```text
sizing.py
exposure.py
drawdown.py
constraints.py
```

Option B

Add only `portfolio.py` and delay the rest.

Option C

Add the full internal Risk subsystem now:

```text
sizing.py
exposure.py
drawdown.py
constraints.py
stop_loss.py
take_profit.py
portfolio.py
pipeline.py
```

### Decision

Expand the internal Risk subsystem during Sprint 008.

The final Risk package contains:

```text
risk/
├── __init__.py
├── sizing.py
├── exposure.py
├── drawdown.py
├── constraints.py
├── stop_loss.py
├── take_profit.py
├── portfolio.py
└── pipeline.py
```

The top-level AQOS architecture remains frozen.

No new top-level package was introduced.

### Benefits

- Risk subsystem is complete enough before Evaluation begins.
- Risk logic remains separate from strategy logic.
- AQOS can perform unified trade-level risk assessment.
- AQOS supports portfolio-level risk checks.
- Future Evaluation, Paper Trading, Agents, and Live Trading modules can depend on a stable `RiskPipeline`.
- Risk rejection reasons can be explained clearly.
- Stop-loss and take-profit now exist at both strategy and risk layers with different responsibilities.

### Drawbacks

- More files were added to the Risk subsystem.
- There is naming overlap between `strategy/stop_loss.py` and `risk/stop_loss.py`.
- There is naming overlap between `strategy/take_profit.py` and `risk/take_profit.py`.
- Documentation must clearly explain the difference between strategy-level and risk-level modules.

### Impact

Affected folder:

```text
src/aqos/risk/
```

Affected files:

```text
src/aqos/risk/__init__.py
src/aqos/risk/sizing.py
src/aqos/risk/exposure.py
src/aqos/risk/drawdown.py
src/aqos/risk/constraints.py
src/aqos/risk/stop_loss.py
src/aqos/risk/take_profit.py
src/aqos/risk/portfolio.py
src/aqos/risk/pipeline.py
```

Affected tests:

```text
tests/unit/test_sizing.py
tests/unit/test_exposure.py
tests/unit/test_drawdown.py
tests/unit/test_constraints.py
tests/unit/test_risk_stop_loss.py
tests/unit/test_risk_take_profit.py
tests/unit/test_portfolio.py
tests/unit/test_risk_pipeline.py
```

Affected documentation:

```text
docs/ROADMAP.md
docs/PROJECT_STATE.md
docs/CHANGELOG.md
docs/CODEBASE.md
docs/TESTING.md
docs/ENHANCEMENTS.md
docs/ARCHITECTURE.md
docs/DECISIONS.md
```

Architecture version updated from:

```text
1.0
```

to:

```text
1.1
```

### Notes

Strategy modules answer:

```text
What trade setup makes sense?
```

Risk modules answer:

```text
Is this trade safe enough to allow?
```

This decision keeps account protection separate from market prediction and trade planning.

The top-level AQOS package structure remains frozen.

---

## ADR-005

### Date

2026-07-07

### Sprint

Sprint 010

### Status

Accepted

### Title

Expand the Services subsystem architecture.

### Context

Sprint 010 introduced the AQOS Services subsystem.

The original service plan focused on internal orchestration services:

```text
data_service.py
model_service.py
strategy_service.py
backtest_service.py
experiment_service.py
```

These files are responsible for wrapping existing AQOS subsystems and making them easier to use from future interfaces.

However, AQOS is not only a research library.

AQOS is intended to become a full AI Quant Operating System that can eventually connect to:

- Market data providers
- Brokers
- News providers
- Economic calendar providers
- Persistent storage backends
- Future APIs
- Future user interfaces
- Future agent workflows

Because of this, the Services subsystem also needs integration-style boundaries.

These boundaries allow AQOS to prepare for real-world trading workflows without connecting live external APIs too early.

### Alternatives Considered

Option A

Only implement internal orchestration services:

```text
data_service.py
model_service.py
strategy_service.py
backtest_service.py
experiment_service.py
```

Option B

Create separate top-level packages for broker, market data, news, calendar, and storage integrations.

Option C

Expand the existing `services/` package to include both internal orchestration services and external integration-style service boundaries.

### Decision

Expand the Services subsystem during Sprint 010.

The Services subsystem will include two categories:

1. Internal orchestration services
2. External integration-style services

The final Sprint 010 service structure is:

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
```

No new top-level package was introduced.

The top-level AQOS architecture remains frozen.

### Internal Orchestration Services

The following services wrap existing AQOS subsystems:

```text
data_service.py
model_service.py
strategy_service.py
backtest_service.py
experiment_service.py
```

Responsibilities:

- Provide stable service-level APIs.
- Coordinate lower-level AQOS modules.
- Hide implementation details from future interfaces.
- Make AQOS easier to call from CLI, API, agents, and UI layers.

### External Integration-Style Services

The following services define lightweight integration boundaries:

```text
market_data.py
broker.py
news.py
economic_calendar.py
storage.py
```

Responsibilities:

- Represent external system boundaries.
- Keep external concerns isolated from core domain modules.
- Provide in-memory foundations before real integrations are added.
- Prepare AQOS for real broker, provider, news, calendar, and storage integrations.

### Benefits

- AQOS now has a complete service layer.
- Future Interfaces layer can depend on `services/` instead of directly calling every lower-level package.
- Internal orchestration is separated from domain logic.
- External integration boundaries are prepared early.
- Real API connections can be added later behind stable service boundaries.
- Current implementations remain deterministic and fully testable.
- No network, broker, database, or external provider is required for current tests.
- No new top-level package was needed.

### Drawbacks

- The Services subsystem now contains more files.
- Some services are future-facing and currently use in-memory implementations.
- Developers must understand the difference between orchestration services and integration-style services.
- Real external integrations will still require future adapter work.

### Impact

Affected folder:

```text
src/aqos/services/
```

Affected service files:

```text
src/aqos/services/__init__.py
src/aqos/services/data_service.py
src/aqos/services/model_service.py
src/aqos/services/strategy_service.py
src/aqos/services/backtest_service.py
src/aqos/services/experiment_service.py
src/aqos/services/market_data.py
src/aqos/services/broker.py
src/aqos/services/news.py
src/aqos/services/economic_calendar.py
src/aqos/services/storage.py
```

Affected tests:

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

Affected documentation:

```text
docs/ROADMAP.md
docs/PROJECT_STATE.md
docs/CHANGELOG.md
docs/CODEBASE.md
docs/TESTING.md
docs/ENHANCEMENTS.md
docs/ARCHITECTURE.md
docs/DECISIONS.md
```

Architecture version updated from:

```text
1.1
```

to:

```text
1.2
```

### Notes

The Services subsystem does not replace lower-level AQOS modules.

Lower-level modules remain responsible for domain logic.

Services are responsible for:

- Orchestration
- Input/output convenience
- Workflow boundaries
- Future integration boundaries

Current Sprint 010 services are intentionally:

- Lightweight
- In-memory
- Deterministic
- Testable
- Free from external API dependencies

Future sprints may add:

- Real market data adapters
- Real broker adapters
- News provider adapters
- Economic calendar provider adapters
- Persistent storage backends
- Service-level configuration
- Service health checks
- Async service interfaces
- API schemas

---

---

## ADR-006

### Date

2026-07-07

### Sprint

Sprint 011

### Status

Accepted

### Title

Expand the Interfaces subsystem architecture.

### Context

Sprint 011 was originally planned around existing domain interface contract files:

```text
data_provider.py
model.py
strategy.py
risk.py
memory.py
```

These files define how core AQOS components should behave.

However, after completing the Services subsystem in Sprint 010, AQOS also needed clear application-facing interfaces for future API, CLI, dashboard, and agent workflows.

Without these interface boundaries, future external layers would either call lower-level modules directly or duplicate orchestration logic.

AQOS needs a stable interface layer above `services/` so that future applications can interact with the system through consistent request and response patterns.

### Alternatives Considered

Option A

Only implement domain contracts during Sprint 011 and delay application-facing interfaces.

Option B

Create separate top-level packages for API, CLI, dashboard, and agent access.

Option C

Expand the existing `interfaces/` package to include both domain contracts and application-facing interfaces.

### Decision

Expand the Interfaces subsystem during Sprint 011.

The Interfaces subsystem will include two categories:

1. Domain interface contracts
2. Application-facing interfaces

The final Sprint 011 interface structure is:

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
```

No new top-level package was introduced.

The top-level AQOS architecture remains frozen.

### Domain Interface Contracts

The following files define contracts for internal components:

```text
data_provider.py
model.py
strategy.py
risk.py
memory.py
```

Responsibilities:

- Define component behavior contracts.
- Reduce coupling to concrete implementations.
- Enable future provider/model/strategy/risk/memory replacements.
- Improve testability.

### Application-Facing Interfaces

The following files define interfaces for external-facing workflows:

```text
schemas.py
api_interface.py
cli_interface.py
dashboard_interface.py
agent_interface.py
```

Responsibilities:

- Define request and response schemas.
- Provide API-style access.
- Provide CLI-style command access.
- Provide dashboard-style read access.
- Provide agent-style action access.
- Standardize outputs through `InterfaceEnvelope`.

### Benefits

- AQOS now has a complete interface layer.
- Future APIs can depend on `APIInterface`.
- Future CLI commands can depend on `CLIInterface`.
- Future dashboards can depend on `DashboardInterface`.
- Future agents can depend on `AgentInterface`.
- External layers do not need to call low-level modules directly.
- Interface responses are standardized through `InterfaceEnvelope`.
- Domain contracts and application-facing interfaces stay inside the existing frozen architecture.
- Tests remain deterministic and do not require external servers or services.

### Drawbacks

- The Interfaces subsystem now contains more files.
- Application-facing interfaces are currently lightweight and not yet connected to real HTTP routes, terminal commands, dashboard UI, or autonomous agent runtimes.
- Future work is required to connect these interfaces to real frameworks.

### Impact

Affected folder:

```text
src/aqos/interfaces/
```

Affected interface files:

```text
src/aqos/interfaces/__init__.py
src/aqos/interfaces/data_provider.py
src/aqos/interfaces/model.py
src/aqos/interfaces/strategy.py
src/aqos/interfaces/risk.py
src/aqos/interfaces/memory.py
src/aqos/interfaces/schemas.py
src/aqos/interfaces/api_interface.py
src/aqos/interfaces/cli_interface.py
src/aqos/interfaces/dashboard_interface.py
src/aqos/interfaces/agent_interface.py
```

Affected tests:

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

Affected documentation:

```text
docs/ROADMAP.md
docs/PROJECT_STATE.md
docs/CHANGELOG.md
docs/CODEBASE.md
docs/TESTING.md
docs/ENHANCEMENTS.md
docs/ARCHITECTURE.md
docs/DECISIONS.md
```

Architecture version updated from:

```text
1.2
```

to:

```text
1.3
```

### Notes

Domain interface contracts answer:

```text
How should AQOS components behave?
```

Application-facing interfaces answer:

```text
How should external users, apps, dashboards, APIs, and agents call AQOS?
```

The Interfaces subsystem does not contain core trading logic.

The Services subsystem remains responsible for orchestration.

The Interfaces subsystem remains responsible for interaction boundaries.

Future sprints may add:

- Real FastAPI routes
- Real CLI commands
- Real dashboard DTOs
- Real agent orchestration
- Tool-call schemas
- OpenAPI documentation
- Pydantic models
- Request IDs
- Trace IDs
- Error codes
---

## ADR-007

### Date

2026-07-07

### Sprint

Sprint 012

### Status

Accepted

### Title

Introduce the Agents subsystem architecture.

### Context

After Sprint 011, AQOS had a completed Interfaces subsystem that exposed domain contracts and application-facing interfaces.

The next required layer was an agent-oriented workflow layer capable of coordinating existing services and interfaces into higher-level actions.

AQOS needs agents because the long-term product direction is an AI Quant Operating System, not only a collection of isolated modules.

The system must support workflows such as:

```text
market analysis → strategy decision → risk assessment → execution
```

and:

```text
research hypothesis → experiment plan → backtest → evaluation report
```

Without an Agents subsystem, these workflows would need to be manually assembled in external applications.

### Alternatives Considered

Option A

Delay agents until after live API/dashboard work.

Option B

Implement agents outside the main package.

Option C

Introduce a dedicated `agents/` subsystem using the already frozen top-level AQOS architecture.

### Decision

Implement the Agents subsystem in Sprint 012.

The top-level `agents/` package already existed in the frozen architecture, so no new top-level package was introduced.

The final Sprint 012 agent structure is:

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

### Shared Agent Contract

All agents use a shared task/result pattern:

```text
AgentTask
AgentResult
AgentBase
```

`AgentTask` carries:

- action
- payload
- metadata

`AgentResult` carries:

- success
- message
- data
- metadata

`AgentBase` provides:

- shared validation
- action normalization
- supported action checks
- success result builder
- failure result builder
- payload helpers

### Implemented Agents

Sprint 012 introduced:

- `DataAgent`
- `MarketAgent`
- `ResearchAgent`
- `StrategyAgent`
- `RiskAgent`
- `ExecutionAgent`
- `EvaluationAgent`
- `MemoryAgent`
- `AgentOrchestrator`

### Workflow Design

Agents coordinate existing AQOS capabilities.

They do not replace Services.

They sit above Services and provide workflow-level execution.

Example:

```text
AgentOrchestrator
    ↓
MarketAgent
    ↓
StrategyAgent
    ↓
RiskAgent
    ↓
ExecutionAgent
```

### Benefits

- AQOS now supports task-based agent workflows.
- Each agent has a clear responsibility.
- Workflows are deterministic and testable.
- Services remain reusable and isolated.
- Agent outputs are standardized through `AgentResult`.
- Agents support future LLM tool-calling integration.
- AgentOrchestrator enables multi-step workflow composition.
- Future autonomous planning can build on this foundation.

### Drawbacks

- Agents add another coordination layer.
- Current agents are deterministic and do not yet use LLM reasoning.
- Current execution agent uses simulated broker execution only.
- Current orchestrator workflows are simple and rule-based.
- Future work is required for real autonomous behavior.

### Impact

Affected folder:

```text
src/aqos/agents/
```

Affected files:

```text
src/aqos/agents/__init__.py
src/aqos/agents/base.py
src/aqos/agents/data_agent.py
src/aqos/agents/market_agent.py
src/aqos/agents/research_agent.py
src/aqos/agents/strategy_agent.py
src/aqos/agents/risk_agent.py
src/aqos/agents/execution_agent.py
src/aqos/agents/evaluation_agent.py
src/aqos/agents/memory_agent.py
src/aqos/agents/orchestrator.py
```

Affected tests:

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

Affected documentation:

```text
docs/ROADMAP.md
docs/PROJECT_STATE.md
docs/CHANGELOG.md
docs/CODEBASE.md
docs/TESTING.md
docs/ENHANCEMENTS.md
docs/ARCHITECTURE.md
docs/DECISIONS.md
```

Architecture version updated from:

```text
1.3
```

to:

```text
1.4
```

### Notes

Agents answer:

```text
How should AQOS coordinate intelligent workflows?
```

Services answer:

```text
How should AQOS orchestrate subsystem operations?
```

Interfaces answer:

```text
How should external systems call AQOS?
```

The current Agents subsystem is a deterministic foundation.

Future sprints may add:

- LLM-backed reasoning
- Tool-call schemas
- Autonomous planning
- Agent memory loops
- Multi-agent debate
- Workflow graphs
- Agent telemetry
- Agent persistence
- Real paper trading loops
- Live broker adapters

---

## ADR-008

### Date

2026-07-07

### Sprint

Sprint 013

### Status

Accepted

### Title

Introduce the Common Utilities subsystem.

### Context

After Sprint 012, AQOS had completed its Agents subsystem and supported deterministic multi-agent workflows.

At this stage, several shared patterns existed across modules:

- default constants
- repeated validation logic
- repeated ID construction
- timestamp and datetime handling
- dictionary serialization
- numeric helper logic
- error formatting patterns

Without a completed Common Utilities subsystem, future integration work would duplicate utility logic across agents, services, interfaces, risk, strategy, evaluation, and data modules.

The frozen top-level architecture already included:

```text
src/aqos/common/
```

so this sprint completed the existing common package without introducing a new top-level package.

### Decision

Implement the Common Utilities subsystem in Sprint 013.

The completed modules are:

```text
src/aqos/common/constants.py
src/aqos/common/validators.py
src/aqos/common/id_helpers.py
src/aqos/common/time_utils.py
src/aqos/common/serialization.py
src/aqos/common/math_utils.py
src/aqos/common/error_helpers.py
```

The completed public utilities are exported through:

```text
src/aqos/common/__init__.py
```

### Reserved Files

The following existing files remain reserved for future use:

```text
src/aqos/common/decorators.py
src/aqos/common/enums.py
src/aqos/common/helpers.py
src/aqos/common/types.py
```

They were not removed because they already existed in the package and may be used in future sprints.

### Alternatives Considered

Option A

Leave common utilities empty until later.

Option B

Implement only validators.

Option C

Implement a complete lightweight common utilities foundation now.

### Decision Outcome

Option C was selected.

Sprint 013 implemented a complete deterministic common utilities foundation covering:

- constants
- validation
- ID helpers
- time helpers
- serialization
- math helpers
- error helpers

### Benefits

- Reduces future duplication.
- Provides stable common primitives.
- Makes future integration cleaner.
- Supports reusable validation across modules.
- Supports standardized ID generation.
- Supports UTC-first datetime handling.
- Supports JSON-safe output formatting.
- Supports structured error responses.
- Supports common trading math helpers.
- Keeps common utilities dependency-minimal.

### Drawbacks

- Adds more public exports to maintain.
- Some existing modules do not yet use these utilities.
- Future refactoring is required to adopt common utilities across older code.
- Some reserved common files remain empty until future need is clear.

### Impact

Affected folder:

```text
src/aqos/common/
```

Affected files:

```text
src/aqos/common/__init__.py
src/aqos/common/constants.py
src/aqos/common/validators.py
src/aqos/common/id_helpers.py
src/aqos/common/time_utils.py
src/aqos/common/serialization.py
src/aqos/common/math_utils.py
src/aqos/common/error_helpers.py
```

Affected tests:

```text
tests/unit/test_common_constants.py
tests/unit/test_common_validators.py
tests/unit/test_common_id_helpers.py
tests/unit/test_common_time_utils.py
tests/unit/test_common_serialization.py
tests/unit/test_common_math_utils.py
tests/unit/test_common_error_helpers.py
tests/unit/test_common_exports.py
```

Affected documentation:

```text
docs/ROADMAP.md
docs/PROJECT_STATE.md
docs/CHANGELOG.md
docs/CODEBASE.md
docs/TESTING.md
docs/ENHANCEMENTS.md
docs/ARCHITECTURE.md
docs/DECISIONS.md
```

Architecture version updated from:

```text
1.4
```

to:

```text
1.5
```

### Design Rule

The Common Utilities subsystem must remain dependency-minimal.

It may be imported by high-level modules.

It should not import high-level modules.

This avoids circular dependencies and keeps common helpers stable.

### Future Work

Future sprints may add:

- decorators
- enums
- shared types
- generic helper wrappers
- pandas-specific validators
- numpy-specific serializers
- market calendar utilities
- advanced trading metrics
- HTTP/API error mapping
- common utilities adoption across existing AQOS modules

# Future Decision Log

Every future architecture decision will be recorded below.

Examples:

## ADR-006

Introduce Time Series Transformer.

## ADR-007

Replace rule-based liquidity with SMC engine.

## ADR-008

Introduce Vector Database.

## ADR-009

Add Reinforcement Learning.

---

## ADR-010

### Date

2026-07-07

### Sprint

Sprint 015

### Status

Accepted

### Title

Allow flexible top-level architecture and introduce dedicated API package.

### Context

Earlier AQOS development kept a conservative top-level package structure.

This helped avoid random folders and uncontrolled architecture growth.

However, AQOS is becoming a larger AI Quant Operating System.

After Sprint 014, AQOS had:

- domain subsystems
- service layer
- agent layer
- common utilities
- system integration tests

Sprint 015 needed a clear API boundary.

Forcing API code into an existing package would reduce clarity because API is a major product-facing boundary.

### Decision

AQOS top-level architecture is flexible.

New top-level packages are allowed when they:

- represent a meaningful product or architecture boundary
- improve separation of concerns
- make the system easier to scale
- make the system easier to test
- make production integration cleaner
- are documented in architecture docs
- are supported by tests

Sprint 015 introduces:

```text
src/aqos/api/
```

as a dedicated top-level API package.

### API Package Scope

The API package is framework-independent.

It contains:

```text
src/aqos/api/__init__.py
src/aqos/api/responses.py
src/aqos/api/health.py
src/aqos/api/market.py
src/aqos/api/strategy.py
src/aqos/api/risk.py
src/aqos/api/execution.py
src/aqos/api/evaluation.py
src/aqos/api/research.py
src/aqos/api/memory.py
src/aqos/api/orchestrator.py
```

### Non-Goals

Sprint 015 does not add:

- FastAPI runtime
- Flask runtime
- Django runtime
- HTTP routes
- API server process
- authentication middleware
- database persistence
- live broker connectivity

### Benefits

- Gives AQOS a clean API boundary.
- Keeps API code separate from interfaces, services, and agents.
- Allows future FastAPI or CLI layers to reuse the same API operations.
- Keeps response format consistent.
- Makes API behavior easy to unit test.
- Avoids mixing HTTP concerns into domain subsystems.
- Supports productization of AQOS.

### Drawbacks

- Adds a new top-level package.
- Requires documentation discipline to avoid architecture sprawl.
- Public API exports must be maintained.
- Future API runtime adapters must not duplicate API business logic.

### Rule Going Forward

New top-level AQOS packages are allowed, but they must be justified.

Each major new top-level package should be documented in:

```text
docs/ARCHITECTURE.md
docs/DECISIONS.md
docs/CODEBASE.md
```

and tested through unit or integration tests.

### Impact

Affected package:

```text
src/aqos/api/
```

Affected tests:

```text
tests/unit/test_api_responses.py
tests/unit/test_api_health.py
tests/unit/test_api_market.py
tests/unit/test_api_strategy.py
tests/unit/test_api_risk.py
tests/unit/test_api_execution.py
tests/unit/test_api_evaluation.py
tests/unit/test_api_research.py
tests/unit/test_api_memory.py
tests/unit/test_api_orchestrator.py
tests/unit/test_api_exports.py
```

Affected documentation:

```text
docs/ROADMAP.md
docs/PROJECT_STATE.md
docs/CHANGELOG.md
docs/CODEBASE.md
docs/TESTING.md
docs/ENHANCEMENTS.md
docs/ARCHITECTURE.md
docs/DECISIONS.md
docs/API.md
```

Architecture version updated from:

```text
1.6
```

to:

```text
1.7
```

### Future Work

Future sprints may add:

- CLI layer using API operations
- FastAPI adapter
- API route modules
- OpenAPI schemas
- API authentication
- API authorization
- API request tracing
- dashboard API integration
- production API server entrypoint
## ADR-011

Introduce DuckDB Data Lake.

## ADR-012

Distributed Training.

## ADR-013

Live Trading Infrastructure.

---

# Decision Rules

Before changing architecture, we must answer:

1. Why is the current design insufficient?
2. What alternatives were considered?
3. Why is the proposed design better?
4. What are the drawbacks?
5. What files are affected?
6. Is migration required?
7. Is it backward compatible?

If these questions cannot be answered, the architecture should not change.

---

# Engineering Principles

AQOS follows:

- SOLID
- DRY
- KISS
- Clean Architecture
- Domain-Driven Design
- Test-Driven Development where practical
- Modular Design
- Separation of Concerns
- Reproducibility
- Explainability
- Scalability
- Extensibility

---

# Final Rule

Architecture changes are intentional.

Architecture changes are documented.

Architecture changes are agreed upon.

Architecture changes are versioned.

Nothing changes without a recorded decision.