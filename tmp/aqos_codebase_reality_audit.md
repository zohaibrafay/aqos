# AQOS Codebase Reality Audit

Generated at: `2026-07-11T16:54:09.130300+00:00`

## Summary

- Total Python files: `515`
- Source Python files: `256`
- Test Python files: `259`
- Script Python files: `0`
- Total code lines: `141053`
- Total classes: `727`
- Total functions: `8378`

## Classification Counts

- cli_entrypoint: `1`
- constants_module: `1`
- implemented: `498`
- tooling_script: `5`
- valid_contract: `10`

## Dependencies

Declared dependencies:
- `PyYAML`
- `joblib`
- `numpy`
- `pandas`
- `pytest`
- `python-dotenv`
- `requires = ["setuptools`
- `requires-python = `
- `scikit-learn`

External imports detected:
- `dotenv`
- `joblib`
- `numpy`
- `pandas`
- `pytest`
- `sklearn`
- `yaml`

Possible missing dependencies:
- `None detected`

## Empty / Init Files

- `None detected`

## Review Or Upgrade Files

- `None detected`

## Possible Unused Modules

- `None detected`

## Duplicate File Names

- `base.py` appears `14` times
- `orchestrator.py` appears `3` times
- `evaluation.py` appears `2` times
- `execution.py` appears `2` times
- `health.py` appears `4` times
- `market.py` appears `3` times
- `memory.py` appears `3` times
- `research.py` appears `3` times
- `risk.py` appears `3` times
- `strategy.py` appears `3` times
- `integration.py` appears `7` times
- `registry.py` appears `2` times
- `cli.py` appears `2` times
- `serialization.py` appears `2` times
- `portfolio.py` appears `3` times
- `signals.py` appears `2` times
- `pipeline.py` appears `6` times
- `storage.py` appears `2` times
- `metrics.py` appears `2` times
- `dataset_builder.py` appears `2` times
- `economic_calendar.py` appears `2` times
- `http_provider.py` appears `2` times
- `market_data.py` appears `2` times
- `stop_loss.py` appears `2` times
- `take_profit.py` appears `2` times

## Duplicate Class Names

- `HealthCheck`
  - `src/aqos/api/health.py`
  - `src/aqos/core/health.py`
- `BrokerPosition`
  - `src/aqos/brokers/account.py`
  - `src/aqos/services/broker.py`
- `BrokerOrder`
  - `src/aqos/brokers/orders.py`
  - `src/aqos/services/broker.py`
- `EconomicCalendarEvent`
  - `src/aqos/news_providers/economic_calendar.py`
  - `src/aqos/services/economic_calendar.py`
- `DummyMemory`
  - `tests/unit/test_agent_interface.py`
  - `tests/unit/test_memory_interface.py`
- `DummyRiskManager`
  - `tests/unit/test_agent_interface.py`
  - `tests/unit/test_api_interface.py`
  - `tests/unit/test_cli_interface.py`
  - `tests/unit/test_risk_interface.py`
- `DummyModel`
  - `tests/unit/test_api_interface.py`
  - `tests/unit/test_base_model.py`
  - `tests/unit/test_cli_interface.py`
  - `tests/unit/test_model_interface.py`
  - `tests/unit/test_model_service.py`
  - `tests/unit/test_pipeline.py`
  - `tests/unit/test_predictor.py`
  - `tests/unit/test_trainer.py`

## Next Action

Use this audit to decide which files should be kept, upgraded, connected, or removed before adding the next ML training modules.