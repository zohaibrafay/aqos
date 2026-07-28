from __future__ import annotations

import json

import pandas as pd
import pytest

from aqos.model_training import (
    ModelPromotionRunConfig,
    ModelPromotionStage,
    SignalPredictionRunConfig,
    SignalTrainingRunConfig,
    predict_signals_from_csv,
    promote_model_from_metadata,
    train_baseline_signal_model_from_csv,
    validate_prediction_model_promotion_gate,
)


def build_training_dataset() -> pd.DataFrame:
    rows = []

    for index in range(24):
        rows.append(
            {
                "open": 2300.0 + index,
                "high": 2302.0 + index,
                "low": 2298.0 + index,
                "close": 2301.0 + index,
                "volume": 1000 + index,
                "rsi_14": 22 + index,
                "macd_histogram": 0.4 + index * 0.01,
                "atr_14": 1.2 + index * 0.02,
                "return_5": 0.01 + index * 0.001,
                "target": "buy",
            }
        )

    for index in range(24):
        rows.append(
            {
                "open": 2350.0 - index,
                "high": 2352.0 - index,
                "low": 2348.0 - index,
                "close": 2349.0 - index,
                "volume": 1200 + index,
                "rsi_14": 78 - index,
                "macd_histogram": -0.4 - index * 0.01,
                "atr_14": 1.4 + index * 0.02,
                "return_5": -0.01 - index * 0.001,
                "target": "sell",
            }
        )

    for index in range(24):
        rows.append(
            {
                "open": 2320.0 + (index % 3),
                "high": 2321.0 + (index % 3),
                "low": 2319.0 + (index % 3),
                "close": 2320.5 + (index % 3),
                "volume": 900 + index,
                "rsi_14": 48 + (index % 4),
                "macd_histogram": 0.0,
                "atr_14": 1.0 + index * 0.01,
                "return_5": 0.0,
                "target": "hold",
            }
        )

    return pd.DataFrame(rows)


def train_and_promote_model(tmp_path):
    dataset_path = tmp_path / "training.csv"
    output_dir = tmp_path / "artifacts"

    dataset = build_training_dataset()
    dataset.to_csv(dataset_path, index=False)

    training_output = train_baseline_signal_model_from_csv(
        SignalTrainingRunConfig(
            dataset_path=dataset_path,
            output_dir=output_dir,
            n_estimators=20,
            random_state=341,
            evaluation_min_accuracy=0.0,
            evaluation_allowed_promotion_stage=ModelPromotionStage.PAPER_TRADING,
        )
    )

    promotion_output = promote_model_from_metadata(
        ModelPromotionRunConfig(
            model_version_metadata_path=training_output.model_version_metadata_path,
            target_stage=ModelPromotionStage.PAPER_TRADING,
        )
    )

    features_path = tmp_path / "features.csv"
    dataset.drop(columns=["target"]).head(8).to_csv(features_path, index=False)

    return training_output, promotion_output, features_path


def test_prediction_promotion_gate_approves_promoted_model(tmp_path) -> None:
    training_output, promotion_output, _ = train_and_promote_model(tmp_path)

    decision = validate_prediction_model_promotion_gate(
        SignalPredictionRunConfig(
            model_path=training_output.model_path,
            features_path=tmp_path / "features.csv",
            model_version_metadata_path=training_output.model_version_metadata_path,
            enable_model_promotion_gate=True,
            promotion_registry_path=promotion_output.promotion_registry_path,
            required_promotion_stage=ModelPromotionStage.PAPER_TRADING,
        )
    )

    assert decision is not None
    assert decision.approved is True
    assert decision.required_stage == ModelPromotionStage.PAPER_TRADING


def test_prediction_runner_blocks_unpromoted_model_before_writing_predictions(
    tmp_path,
) -> None:
    dataset_path = tmp_path / "training.csv"
    output_dir = tmp_path / "artifacts"
    features_path = tmp_path / "features.csv"
    predictions_path = tmp_path / "predictions.csv"

    dataset = build_training_dataset()
    dataset.to_csv(dataset_path, index=False)
    dataset.drop(columns=["target"]).head(8).to_csv(features_path, index=False)

    training_output = train_baseline_signal_model_from_csv(
        SignalTrainingRunConfig(
            dataset_path=dataset_path,
            output_dir=output_dir,
            n_estimators=20,
            random_state=343,
            evaluation_min_accuracy=0.0,
            evaluation_allowed_promotion_stage=ModelPromotionStage.PAPER_TRADING,
        )
    )

    empty_registry_path = tmp_path / "model_promotion_registry.json"
    empty_registry_path.write_text(
        json.dumps({"registry_version": "1.0", "promotions": []}),
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="Model promotion gate rejected"):
        predict_signals_from_csv(
            SignalPredictionRunConfig(
                model_path=training_output.model_path,
                features_path=features_path,
                output_path=predictions_path,
                model_version_metadata_path=training_output.model_version_metadata_path,
                enable_model_promotion_gate=True,
                promotion_registry_path=empty_registry_path,
                required_promotion_stage=ModelPromotionStage.PAPER_TRADING,
            )
        )

    assert not predictions_path.exists()


def test_prediction_runner_allows_promoted_model_and_outputs_gate_decision(
    tmp_path,
) -> None:
    training_output, promotion_output, features_path = train_and_promote_model(tmp_path)
    predictions_path = tmp_path / "predictions.csv"

    output = predict_signals_from_csv(
        SignalPredictionRunConfig(
            model_path=training_output.model_path,
            features_path=features_path,
            output_path=predictions_path,
            model_version_metadata_path=training_output.model_version_metadata_path,
            enable_model_promotion_gate=True,
            promotion_registry_path=promotion_output.promotion_registry_path,
            required_promotion_stage=ModelPromotionStage.PAPER_TRADING,
        )
    )

    payload = output.to_dict()

    assert predictions_path.exists()
    assert output.model_promotion_gate_decision is not None
    assert output.model_promotion_gate_decision.approved is True
    assert payload["model_promotion_gate_decision"]["approved"] is True
    assert payload["model_promotion_gate_decision"]["required_stage"] == (
        "paper_trading"
    )


def test_prediction_runner_can_record_rejected_gate_without_raising(
    tmp_path,
) -> None:
    dataset_path = tmp_path / "training.csv"
    output_dir = tmp_path / "artifacts"
    features_path = tmp_path / "features.csv"
    predictions_path = tmp_path / "predictions.csv"

    dataset = build_training_dataset()
    dataset.to_csv(dataset_path, index=False)
    dataset.drop(columns=["target"]).head(8).to_csv(features_path, index=False)

    training_output = train_baseline_signal_model_from_csv(
        SignalTrainingRunConfig(
            dataset_path=dataset_path,
            output_dir=output_dir,
            n_estimators=20,
            random_state=347,
            evaluation_min_accuracy=0.0,
            evaluation_allowed_promotion_stage=ModelPromotionStage.PAPER_TRADING,
        )
    )

    empty_registry_path = tmp_path / "model_promotion_registry.json"
    empty_registry_path.write_text(
        json.dumps({"registry_version": "1.0", "promotions": []}),
        encoding="utf-8",
    )

    output = predict_signals_from_csv(
        SignalPredictionRunConfig(
            model_path=training_output.model_path,
            features_path=features_path,
            output_path=predictions_path,
            model_version_metadata_path=training_output.model_version_metadata_path,
            enable_model_promotion_gate=True,
            promotion_registry_path=empty_registry_path,
            required_promotion_stage=ModelPromotionStage.PAPER_TRADING,
            fail_on_promotion_gate_error=False,
        )
    )

    assert predictions_path.exists()
    assert output.model_promotion_gate_decision is not None
    assert output.model_promotion_gate_decision.approved is False