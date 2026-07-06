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

## ADR-001

### Date

YYYY-MM-DD

### Sprint

Sprint XXX

### Status

Proposed | Accepted | Deprecated | Replaced

### Decision

Short description.

### Context

Why this decision was necessary.

### Alternatives Considered

Option 1

Option 2

Option 3

### Decision

Chosen solution.

### Benefits

-

-

-

### Drawbacks

-

-

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

### Decision

Freeze AQOS top-level architecture.

### Context

During development we noticed new folders were being proposed while implementation was already in progress.

Changing architecture repeatedly would create instability.

### Alternatives Considered

Option A

Continue changing folders during development.

Option B

Freeze architecture after Sprint 003.

### Decision

Freeze architecture after Sprint 003.

Architecture changes require discussion before implementation.

### Benefits

- Stable development
- Easier maintenance
- Better planning
- Cleaner Git history

### Drawbacks

Some future features may require architectural review.

### Impact

Entire project.

### Notes

No top-level folders may be added without agreement.

---

## ADR-002

### Date

2026-07-06

### Sprint

Sprint 004

### Status

Accepted

### Decision

Introduce dedicated strategy modules.

### Context

Originally market intelligence was being placed inside planner.py.

As the project evolved, it became clear that pattern detection, liquidity analysis, market regime detection, support/resistance, and trend analysis would each grow into large independent systems.

Keeping them together would violate the Single Responsibility Principle (SRP) and make testing and maintenance difficult.

### Alternatives Considered

Option A

Implement everything inside planner.py.

Option B

Split strategy into specialized modules.

### Decision

Create dedicated modules:

- pattern_detector.py
- market_regime.py
- support_resistance.py
- liquidity.py
- trend_structure.py
- signal.py

while keeping planner.py responsible for orchestration.

### Benefits

- Smaller modules
- Easier testing
- Better scalability
- Easier AI integration
- Cleaner codebase

### Drawbacks

Slightly more files.

### Impact

strategy/

### Notes

This is considered part of the frozen architecture.

---

## ADR-003

### Date

2026-07-06

### Sprint

Sprint 004

### Status

Accepted

### Decision

Adopt a Documentation-First Development Workflow.

### Context

As AQOS grows into an institutional-grade AI Quant Research Platform, maintaining accurate documentation is as important as maintaining the source code.

Without a structured workflow, documentation can quickly become outdated, making it difficult to understand project progress, architectural decisions, deferred enhancements, and future development plans.

To ensure long-term maintainability and reproducibility, documentation will be treated as part of the development process rather than an afterthought.

### Alternatives Considered

Option A

Update documentation only when convenient or before releases.

Option B

Maintain documentation continuously as part of every completed sprint.

### Decision

Documentation becomes a mandatory part of the Definition of Done.

Every sprint must follow the workflow:

Implementation

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

Move to Next Sprint

The following documents must be updated whenever applicable:

- ROADMAP.md
- DECISIONS.md
- CHANGELOG.md
- ARCHITECTURE.md
- CODEBASE.md
- CONTRIBUTING.md
- TESTING.md
- STYLE_GUIDE.md
- ENHANCEMENTS.md
- RESEARCH.md
- API.md
- PROJECT_STATE.md

### Benefits

- Documentation always reflects the current state of the project.
- Easier project maintenance and onboarding.
- Complete engineering history.
- Better traceability of architectural decisions.
- Prevents forgotten enhancements and technical debt.
- Enables long-term project continuity.

### Drawbacks

Requires additional effort at the end of every sprint.

### Impact

Entire AQOS project.

### Notes

Documentation is now considered part of the production codebase.

A sprint is **not complete** until:

- Code is implemented.
- Tests are passing.
- Documentation is updated.
- Changes are committed to Git.

# Future Decision Log

Every future architecture decision will be recorded below.

Examples

ADR-003

Introduce Time Series Transformer.

ADR-004

Replace rule-based liquidity with SMC engine.

ADR-005

Introduce Vector Database.

ADR-006

Add Reinforcement Learning.

ADR-007

Replace pandas with Polars.

ADR-008

Introduce DuckDB Data Lake.

ADR-009

Distributed Training.

ADR-010

Live Trading Infrastructure.

---

# Decision Rules

Before changing architecture we must answer:

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
- Domain-Driven Design (DDD)
- Test-Driven Development (where practical)
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