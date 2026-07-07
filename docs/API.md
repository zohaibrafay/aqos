# AQOS API Layer

Current version: `v0.15.0-dev`

Status: Completed foundation

## Overview

AQOS has a framework-independent API Layer.

Path:

```text
src/aqos/api/
```

This layer provides stable Python API operations that can later be connected to:

- FastAPI
- Flask
- Django
- CLI commands
- dashboards
- external service adapters

The API Layer does not start an HTTP server.

It does not define HTTP routes yet.

It wraps AQOS agents and orchestrator workflows in consistent response envelopes.

## Package Structure

```text
src/aqos/api/
├── __init__.py
├── responses.py
├── health.py
├── market.py
├── strategy.py
├── risk.py
├── execution.py
├── evaluation.py
├── research.py
├── memory.py
└── orchestrator.py
```

## Response Envelope

All API operations return:

```python
ApiResponse
```

Example:

```python
from aqos.api import api_success

response = api_success(
    message="Market state loaded.",
    data={
        "symbol": "XAUUSD",
        "timeframe": "H1",
    },
)

payload = response.to_dict()
```

Response shape:

```json
{
  "success": true,
  "status": "success",
  "message": "Market state loaded.",
  "data": {
    "symbol": "XAUUSD",
    "timeframe": "H1"
  },
  "errors": [],
  "metadata": {
    "source": "aqos-api",
    "timestamp": "..."
  }
}
```

## Error Envelope

Example:

```python
from aqos.api import validation_failure

response = validation_failure(
    message="Invalid symbol.",
    field="symbol",
)
```

Error response shape:

```json
{
  "success": false,
  "status": "error",
  "message": "Invalid symbol.",
  "data": null,
  "errors": [
    {
      "code": "VALIDATION_ERROR",
      "message": "Invalid symbol.",
      "field": "symbol"
    }
  ],
  "metadata": {
    "source": "aqos-api",
    "timestamp": "..."
  }
}
```

## API Modules

### Health

Available operations:

- `api_health`
- `system_health`
- `agent_health`
- `agents_health`
- `dependency_health`

### Market

Available operations:

- `api_market_state`
- `api_market_snapshot`
- `api_trend_summary`
- `api_regime_summary`
- `api_news_context`
- `api_calendar_context`

### Strategy

Available operations:

- `api_strategy_signal`
- `api_strategy_decision`
- `api_strategy_explanation`
- `api_entry_check`
- `api_exit_check`
- `api_strategy_handoff`

### Risk

Available operations:

- `api_position_size`
- `api_assess_trade`
- `api_approve_trade`
- `api_reject_reason`
- `api_risk_handoff`

### Execution

Available operations:

- `api_execute_trade`
- `api_place_order`
- `api_fill_order`
- `api_cancel_order`
- `api_order_status`
- `api_close_position`
- `api_execution_summary`

### Evaluation

Available operations:

- `api_run_backtest`
- `api_backtest_summary`
- `api_compare_backtests`
- `api_performance_grade`
- `api_evaluation_report`

### Research

Available operations:

- `api_research_hypothesis`
- `api_experiment_plan`
- `api_create_experiment`
- `api_record_finding`
- `api_research_summary`

### Memory

Available operations:

- `api_remember`
- `api_recall`
- `api_get_memory`
- `api_forget`
- `api_memory_summary`
- `api_pattern_memory`
- `api_trade_memory`

### Orchestrator

Available operations:

- `api_orchestrator_route`
- `api_market_strategy_workflow`
- `api_strategy_risk_workflow`
- `api_risk_execution_workflow`
- `api_trade_workflow`
- `api_research_workflow`
- `api_backtest_workflow`
- `api_memory_workflow`

## Design Rules

API modules should:

- remain framework-independent
- validate inputs before calling agents
- normalize request payloads
- call agents or orchestrators
- return `ApiResponse`
- avoid HTTP framework imports
- avoid UI dependencies
- avoid database dependencies
- avoid broker dependencies unless handled through agents

## Testing

API tests live in:

```text
tests/unit/
```

API test files:

```text
test_api_responses.py
test_api_health.py
test_api_market.py
test_api_strategy.py
test_api_risk.py
test_api_execution.py
test_api_evaluation.py
test_api_research.py
test_api_memory.py
test_api_orchestrator.py
test_api_exports.py
```

Run:

```bash
python -m pytest tests/unit/test_api_responses.py
python -m pytest tests/unit/test_api_health.py
python -m pytest tests/unit/test_api_market.py
python -m pytest tests/unit/test_api_strategy.py
python -m pytest tests/unit/test_api_risk.py
python -m pytest tests/unit/test_api_execution.py
python -m pytest tests/unit/test_api_evaluation.py
python -m pytest tests/unit/test_api_research.py
python -m pytest tests/unit/test_api_memory.py
python -m pytest tests/unit/test_api_orchestrator.py
python -m pytest tests/unit/test_api_exports.py
```

Full suite:

```bash
python -m pytest
```