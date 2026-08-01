from __future__ import annotations

import json
from pathlib import Path

import pandas as pd
import pytest

from aqos.backtesting.model_promotion_guard import (
    BacktestModelGateConfig,
    BacktestModelGateDecision,
    BacktestModelGateStatus,
)
from aqos.backtesting.model_runner import (
    BACKTEST_MODEL_RUNNER_VERSION,
    ModelBacktestRunnerConfig,
    build_model_backtest_adapter,
    build_model_prediction_rows,
    build_traced_model_adapter_config,
    run_model_backtest,
    write_model_backtest_predictions_csv,
)
from aqos.backtesting.model_signal_adapter import ModelSignalAdapterConfig
from aqos.backtesting.signal_adapter import (
    BacktestSignalAdapterResult,
    BacktestSignalAdapterStatus,
    BacktestSignalAdapterType,
)
from aqos.backtesting.contracts import BacktestSignal, BacktestSignalAction
from aqos.backtesting.strategy_runner import StrategyBacktestRunnerConfig
from aqos.model_training.model_evaluation import ModelPromotionStage


def build_strategy_config(
    data_path: Path,
    output_dir: Path,
) -> StrategyBacktestRunnerConfig:
    return StrategyBacktestRunnerConfig(
        data_path=data_path,
        output_dir=output_dir,
        symbol="XAUUSD",
        timeframe="H1",
        strategy_name="model_strategy",
        fixed_quantity=1.0,
        max_open_positions=1,
    )


def build_runner_config(
    promoted_backtest_model_files,
    data_path: Path,
    output_dir: Path,
    required_stage: ModelPromotionStage = ModelPromotionStage.PAPER_TRADING,
) -> ModelBacktestRunnerConfig:
    return ModelBacktestRunnerConfig(
        model_path=promoted_backtest_model_files["model_path"],
        strategy_config=build_strategy_config(data_path, output_dir),
        gate_config=BacktestModelGateConfig(
            model_version_metadata_path=promoted_backtest_model_files["metadata_path"],
            promotion_registry_path=promoted_backtest_model_files["registry_path"],
            required_stage=required_stage,
        ),
        adapter_config=ModelSignalAdapterConfig(
            warmup_bars=5,
            stop_loss_points=4.0,
            take_profit_points=6.0,
        ),
    )


def test_runner_version_is_exposed() -> None:
    assert BACKTEST_MODEL_RUNNER_VERSION == "1.0"


def test_model_backtesting_symbols_are_re_exported() -> None:
    import aqos.backtesting as backtesting

    expected = (
        "BACKTEST_MODEL_PROMOTION_GUARD_VERSION",
        "BACKTEST_MODEL_RUNNER_VERSION",
        "BACKTEST_MODEL_SIGNAL_ADAPTER_VERSION",
        "BacktestModelGateConfig",
        "BacktestModelGateDecision",
        "BacktestModelGateStatus",
        "ModelBacktestRunOutput",
        "ModelBacktestRunnerConfig",
        "ModelBacktestSignalAdapter",
        "ModelSignalAdapterConfig",
        "evaluate_backtest_model_gate",
        "load_model_backtest_signal_adapter",
        "run_model_backtest",
        "validate_backtest_model_gate",
    )

    for name in expected:
        assert name in backtesting.__all__
        assert hasattr(backtesting, name)


def test_runner_config_validation(tmp_path) -> None:
    strategy_config = build_strategy_config(
        tmp_path / "bars.csv",
        tmp_path / "output",
    )

    with pytest.raises(ValueError, match="model_path cannot be empty"):
        ModelBacktestRunnerConfig(model_path="  ", strategy_config=strategy_config)

    with pytest.raises(ValueError, match="model_report_filename cannot be empty"):
        ModelBacktestRunnerConfig(
            model_path="model.joblib",
            strategy_config=strategy_config,
            model_report_filename=" ",
        )

    with pytest.raises(ValueError, match="predictions_filename cannot be empty"):
        ModelBacktestRunnerConfig(
            model_path="model.joblib",
            strategy_config=strategy_config,
            predictions_filename="",
        )


def test_runner_config_defaults_to_disabled_gate_with_override(tmp_path) -> None:
    config = ModelBacktestRunnerConfig(
        model_path="model.joblib",
        strategy_config=build_strategy_config(
            tmp_path / "bars.csv",
            tmp_path / "output",
        ),
    )

    assert config.gate_config.enabled is False
    assert config.gate_config.allow_unpromoted_model is True


def test_runner_config_serialization(
    promoted_backtest_model_files,
    backtest_model_data_path,
    tmp_path,
) -> None:
    config = build_runner_config(
        promoted_backtest_model_files,
        backtest_model_data_path,
        tmp_path / "output",
    )

    payload = config.to_dict()

    assert payload["model_path"].endswith("backtest_signal_model.joblib")
    assert payload["strategy_config"]["symbol"] == "XAUUSD"
    assert payload["gate_config"]["required_stage"] == "paper_trading"
    assert payload["adapter_config"]["warmup_bars"] == 5
    assert payload["model_report_filename"] == "model_backtest_report.json"


def test_traced_adapter_config_merges_model_identity() -> None:
    decision = BacktestModelGateDecision(
        status=BacktestModelGateStatus.APPROVED,
        allowed=True,
        required_stage=ModelPromotionStage.PAPER_TRADING,
        model_name="m",
        model_id="model_abc",
        model_version="v1",
        promotion_stage="paper_trading",
    )

    traced = build_traced_model_adapter_config(
        ModelSignalAdapterConfig(model_identity={"origin": "unit_test"}),
        decision,
    )

    assert traced.model_identity["model_id"] == "model_abc"
    assert traced.model_identity["promotion_stage"] == "paper_trading"
    assert traced.model_identity["origin"] == "unit_test"


def test_traced_adapter_config_prefers_explicit_identity() -> None:
    decision = BacktestModelGateDecision(
        status=BacktestModelGateStatus.APPROVED,
        allowed=True,
        required_stage=ModelPromotionStage.PAPER_TRADING,
        model_id="from_gate",
    )

    traced = build_traced_model_adapter_config(
        ModelSignalAdapterConfig(model_identity={"model_id": "explicit"}),
        decision,
    )

    assert traced.model_identity["model_id"] == "explicit"


def test_build_model_backtest_adapter_carries_identity(
    promoted_backtest_model_files,
    backtest_model_data_path,
    tmp_path,
) -> None:
    config = build_runner_config(
        promoted_backtest_model_files,
        backtest_model_data_path,
        tmp_path / "output",
    )

    decision = BacktestModelGateDecision(
        status=BacktestModelGateStatus.APPROVED,
        allowed=True,
        required_stage=ModelPromotionStage.PAPER_TRADING,
        model_id=str(promoted_backtest_model_files["model_id"]),
    )

    adapter = build_model_backtest_adapter(config, decision)

    assert adapter.model.is_trained is True
    assert adapter.config.model_identity["model_id"] == (
        promoted_backtest_model_files["model_id"]
    )


def test_prediction_rows_expand_probability_columns() -> None:
    result = BacktestSignalAdapterResult(
        signal=BacktestSignal(
            timestamp="2026-01-01T00:00:00",
            symbol="XAUUSD",
            action=BacktestSignalAction.BUY,
            confidence=0.8,
            source="model_backtest_signal_adapter",
            stop_loss=95.0,
            take_profit=110.0,
            metadata={
                "predicted_label": "buy",
                "model_id": "model_abc",
                "model_version": "v1",
                "promotion_stage": "paper_trading",
                "probabilities": {"probability_buy": 0.8, "probability_sell": 0.2},
            },
        ),
        status=BacktestSignalAdapterStatus.GENERATED,
        adapter_type=BacktestSignalAdapterType.ML_MODEL,
        adapter_name="model_backtest_signal_adapter",
    )

    rows = build_model_prediction_rows((result,))

    assert rows[0]["bar_index"] == 0
    assert rows[0]["predicted_label"] == "buy"
    assert rows[0]["action"] == "buy"
    assert rows[0]["model_id"] == "model_abc"
    assert rows[0]["probability_buy"] == 0.8
    assert rows[0]["probability_sell"] == 0.2


def test_write_predictions_csv(tmp_path) -> None:
    result = BacktestSignalAdapterResult(
        signal=BacktestSignal(
            timestamp="2026-01-01T00:00:00",
            symbol="XAUUSD",
            action=BacktestSignalAction.HOLD,
            source="model_backtest_signal_adapter",
            metadata={"predicted_label": "hold"},
        ),
        status=BacktestSignalAdapterStatus.SKIPPED,
        adapter_type=BacktestSignalAdapterType.ML_MODEL,
        adapter_name="model_backtest_signal_adapter",
    )

    path = write_model_backtest_predictions_csv(
        tmp_path / "nested" / "predictions.csv",
        (result,),
    )

    frame = pd.read_csv(path)

    assert path.exists()
    assert len(frame) == 1
    assert frame.iloc[0]["action"] == "hold"


def test_run_model_backtest_produces_artifacts(
    promoted_backtest_model_files,
    backtest_model_data_path,
    tmp_path,
) -> None:
    output_dir = tmp_path / "model_backtest_output"
    config = build_runner_config(
        promoted_backtest_model_files,
        backtest_model_data_path,
        output_dir,
    )

    output = run_model_backtest(config)

    assert output.gate_decision.approved is True
    assert output.prediction_rows == 80
    assert output.model_report_path.exists()
    assert output.predictions_path.exists()
    assert output.strategy_output.report_path.exists()
    assert output.strategy_output.trades_path.exists()
    assert output.strategy_output.equity_curve_path.exists()

    report = json.loads(output.model_report_path.read_text(encoding="utf-8"))

    assert report["gate_decision"]["status"] == "approved"
    assert report["model_identity"]["model_id"] == (
        promoted_backtest_model_files["model_id"]
    )
    assert report["strategy_backtest"]["metrics"]["metadata"]["adapter_type"] == (
        "ml_model"
    )
    assert report["prediction_rows"] == 80


def test_run_model_backtest_writes_traceable_predictions(
    promoted_backtest_model_files,
    backtest_model_data_path,
    tmp_path,
) -> None:
    output = run_model_backtest(
        build_runner_config(
            promoted_backtest_model_files,
            backtest_model_data_path,
            tmp_path / "model_backtest_output",
        )
    )

    predictions = pd.read_csv(output.predictions_path)

    assert len(predictions) == 80
    assert set(predictions.iloc[10:]["predicted_label"]) <= {"buy", "sell"}
    assert (
        predictions.iloc[10]["model_id"] == promoted_backtest_model_files["model_id"]
    )
    assert predictions.iloc[10]["promotion_stage"] == "paper_trading"
    assert predictions.iloc[:5]["adapter_status"].tolist() == ["skipped"] * 5


def test_run_model_backtest_executes_model_trades(
    promoted_backtest_model_files,
    backtest_model_data_path,
    tmp_path,
) -> None:
    output = run_model_backtest(
        build_runner_config(
            promoted_backtest_model_files,
            backtest_model_data_path,
            tmp_path / "model_backtest_output",
        )
    )

    metrics = output.strategy_output.metrics

    assert metrics.total_trades > 0
    assert output.strategy_output.final_state.open_position_count == 0


def test_run_model_backtest_blocks_unpromoted_model(
    unpromoted_backtest_model_files,
    backtest_model_data_path,
    tmp_path,
) -> None:
    config = ModelBacktestRunnerConfig(
        model_path=unpromoted_backtest_model_files["model_path"],
        strategy_config=build_strategy_config(
            backtest_model_data_path,
            tmp_path / "blocked_output",
        ),
        gate_config=BacktestModelGateConfig(
            model_version_metadata_path=(
                unpromoted_backtest_model_files["metadata_path"]
            ),
            promotion_registry_path=(
                unpromoted_backtest_model_files["registry_path"]
            ),
            required_stage=ModelPromotionStage.PAPER_TRADING,
        ),
    )

    with pytest.raises(ValueError, match="Backtest model promotion gate rejected"):
        run_model_backtest(config)

    assert not (tmp_path / "blocked_output" / "model_backtest_report.json").exists()


def test_run_model_backtest_allows_explicit_override(
    unpromoted_backtest_model_files,
    backtest_model_data_path,
    tmp_path,
) -> None:
    output_dir = tmp_path / "override_output"

    config = ModelBacktestRunnerConfig(
        model_path=unpromoted_backtest_model_files["model_path"],
        strategy_config=build_strategy_config(backtest_model_data_path, output_dir),
        gate_config=BacktestModelGateConfig(
            model_version_metadata_path=(
                unpromoted_backtest_model_files["metadata_path"]
            ),
            promotion_registry_path=(
                unpromoted_backtest_model_files["registry_path"]
            ),
            required_stage=ModelPromotionStage.PAPER_TRADING,
            allow_unpromoted_model=True,
        ),
        adapter_config=ModelSignalAdapterConfig(warmup_bars=5),
    )

    output = run_model_backtest(config)
    report = json.loads(output.model_report_path.read_text(encoding="utf-8"))

    assert output.gate_decision.status == BacktestModelGateStatus.OVERRIDDEN
    assert report["gate_decision"]["override_applied"] is True
    assert report["gate_decision"]["reasons"]
