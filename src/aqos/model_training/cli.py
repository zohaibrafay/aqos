from __future__ import annotations

import argparse
import json
from collections.abc import Sequence


from aqos.model_training.model_evaluation import ModelPromotionStage
from aqos.model_training.experiment_registry import read_experiment_registry
from aqos.model_training.prediction_registry import read_prediction_registry
from aqos.model_training.dataset_builder import (
    SignalMLDatasetBuildConfig,
    build_signal_ml_training_dataset_from_csv,
)
from aqos.model_training.dataset_quality import (
    DatasetQualityConfig,
    build_dataset_quality_report,
    write_dataset_quality_report,
)
from aqos.model_training.ohlcv_feature_builder import OHLCVFeatureBuilderConfig
from aqos.model_training.prediction_runner import (
    SignalPredictionRunConfig,
    predict_signals_from_csv,
)
from aqos.model_training.target_label_builder import SignalTargetLabelConfig
from aqos.model_training.training_runner import (
    SignalTrainingRunConfig,
    load_signal_training_dataset,
    train_baseline_signal_model_from_csv,
)


def build_model_training_cli_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="aqos-model-training",
        description="Train and run AQOS baseline ML signal models.",
    )

    subparsers = parser.add_subparsers(dest="command", required=True)

    build_dataset_parser = subparsers.add_parser(
        "build-dataset",
        help="Build leakage-safe ML training dataset from raw OHLCV CSV.",
    )
    build_dataset_parser.add_argument("--input-path", required=True)
    build_dataset_parser.add_argument("--output-path", required=True)
    build_dataset_parser.add_argument("--horizon-bars", type=int, default=5)
    build_dataset_parser.add_argument("--min-signal-return", type=float, default=0.001)
    build_dataset_parser.add_argument("--take-profit-return", type=float, default=0.002)
    build_dataset_parser.add_argument("--stop-loss-return", type=float, default=0.001)
    build_dataset_parser.add_argument("--target-column", default="target")
    build_dataset_parser.add_argument(
        "--keep-incomplete-horizon",
        action="store_true",
        help="Keep final rows where future horizon is incomplete.",
    )
    build_dataset_parser.add_argument(
        "--no-time-features",
        action="store_true",
        help="Skip hour/day/session features.",
    )
    build_dataset_parser.add_argument(
        "--no-fill-missing-values",
        action="store_true",
        help="Do not fill missing generated numeric feature values.",
    )
    build_dataset_parser.add_argument(
        "--no-schema-validation",
        action="store_true",
        help="Skip final ML dataset schema validation.",
    )
    build_dataset_parser.add_argument(
        "--metadata-filename",
        default="signal_ml_dataset_metadata.json",
    )

    quality_parser = subparsers.add_parser(
        "quality-report",
        help="Build JSON quality report for an existing ML training dataset.",
    )
    list_experiments_parser = subparsers.add_parser(
        "list-experiments",
        help="List experiment runs from an AQOS experiment registry JSON file.",
    )
    list_experiments_parser.add_argument(
        "--registry-path",
        default="tmp/model_training/experiment_registry.json",
    )
    list_predictions_parser = subparsers.add_parser(
        "list-predictions",
        help="List prediction runs from an AQOS prediction registry JSON file.",
    )
    list_predictions_parser.add_argument(
        "--registry-path",
        default="tmp/model_training/prediction_registry.json",
        help="Path to prediction_registry.json.",
    )
    quality_parser.add_argument("--dataset-path", required=True)
    quality_parser.add_argument("--output-path", required=True)
    quality_parser.add_argument("--target-column", default="target")
    quality_parser.add_argument("--min-rows", type=int, default=8)
    quality_parser.add_argument("--min-target-classes", type=int, default=2)
    quality_parser.add_argument("--max-majority-class-ratio", type=float, default=0.8)
    quality_parser.add_argument(
        "--fail-on-error",
        action="store_true",
        help="Return an error when the dataset quality report is invalid.",
    )

    train_parser = subparsers.add_parser(
        "train",
        help="Train baseline signal model from a CSV dataset.",
    )
    train_parser.add_argument("--dataset-path", required=True)
    train_parser.add_argument("--output-dir", default="tmp/model_training")
    train_parser.add_argument("--target-column", default="target")
    train_parser.add_argument("--feature-columns", default="")
    train_parser.add_argument("--test-size", type=float, default=0.25)
    train_parser.add_argument("--random-state", type=int, default=42)
    train_parser.add_argument("--n-estimators", type=int, default=100)
    train_parser.add_argument("--max-depth", type=int, default=6)
    train_parser.add_argument("--min-samples-leaf", type=int, default=1)
    train_parser.add_argument(
        "--model-filename",
        default="baseline_signal_model.joblib",
    )
    train_parser.add_argument(
        "--metrics-filename",
        default="baseline_signal_model_metrics.json",
    )
    train_parser.add_argument(
        "--no-schema-validation",
        action="store_true",
        help="Skip ML training dataset schema validation.",
    )
    train_parser.add_argument(
        "--no-quality-validation",
        action="store_true",
        help="Skip ML dataset quality validation before training.",
    )
    train_parser.add_argument(
        "--quality-report-filename",
        default="training_dataset_quality.json",
    )
    train_parser.add_argument(
        "--max-majority-class-ratio",
        type=float,
        default=0.8,
    )
    train_parser.add_argument(
        "--no-model-evaluation",
        action="store_true",
        help="Skip model evaluation report generation.",
    )
    train_parser.add_argument(
        "--model-evaluation-report-filename",
        default="model_evaluation_report.json",
        help="Filename for model evaluation report.",
    )
    train_parser.add_argument(
        "--fail-on-model-evaluation-error",
        action="store_true",
        help="Fail training command when model evaluation thresholds fail.",
    )
    train_parser.add_argument(
        "--evaluation-min-accuracy",
        type=float,
        default=0.45,
        help="Minimum accuracy required for model evaluation.",
    )
    train_parser.add_argument(
        "--evaluation-min-macro-f1",
        type=float,
        default=None,
        help="Optional minimum macro F1 required for model evaluation.",
    )
    train_parser.add_argument(
        "--evaluation-max-log-loss",
        type=float,
        default=None,
        help="Optional maximum log loss allowed for model evaluation.",
    )
    train_parser.add_argument(
        "--evaluation-min-test-samples",
        type=int,
        default=20,
        help="Minimum recommended number of test samples.",
    )
    train_parser.add_argument(
        "--evaluation-required-classes",
        default="",
        help="Comma-separated required target classes, for example: buy,sell,hold.",
    )
    train_parser.add_argument(
        "--evaluation-allowed-promotion-stage",
        default=ModelPromotionStage.RESEARCH.value,
        choices=[stage.value for stage in ModelPromotionStage],
        help="Allowed promotion stage when evaluation passes.",
    )
    train_parser.add_argument(
        "--model-evaluation-notes",
        default=None,
        help="Optional notes stored in model evaluation report.",
    )
    train_parser.add_argument(
        "--no-experiment-registry",
        action="store_true",
        help="Skip experiment registry output.",
    )
    predict_parser = subparsers.add_parser(
        "predict",
        help="Generate signal predictions from a saved model and CSV features.",
    )
    predict_parser.add_argument("--model-path", required=True)
    predict_parser.add_argument("--features-path", required=True)
    predict_parser.add_argument(
        "--output-path",
        default="tmp/model_training/baseline_signal_predictions.csv",
    )
    predict_parser.add_argument(
        "--no-probabilities",
        action="store_true",
        help="Skip probability columns in the prediction output.",
    )
    predict_parser.add_argument(
        "--no-schema-validation",
        action="store_true",
        help="Skip prediction feature schema validation.",
    )
    predict_parser.add_argument(
        "--model-version-metadata-path",
        default=None,
        help="Optional model_version_metadata.json path to link predictions to a model version.",
    )
    predict_parser.add_argument(
        "--prediction-metadata-filename",
        default="prediction_run_metadata.json",
        help="Filename for prediction run metadata written next to prediction output.",
    )
    predict_parser.add_argument(
        "--no-prediction-versioning",
        action="store_true",
        help="Skip prediction metadata/versioning output.",
    )
    predict_parser.add_argument(
        "--prediction-registry-filename",
        default="prediction_registry.json",
        help="Filename for prediction registry written next to prediction output.",
    )
    predict_parser.add_argument(
        "--no-prediction-registry",
        action="store_true",
        help="Skip prediction registry output.",
    )
    predict_parser.add_argument(
        "--no-prediction-validation",
        action="store_true",
        help="Skip prediction validation report output.",
    )
    predict_parser.add_argument(
        "--prediction-validation-report-filename",
        default="prediction_validation_report.json",
        help="Filename for prediction validation report written next to prediction output.",
    )
    predict_parser.add_argument(
        "--no-fail-on-prediction-validation-error",
        action="store_true",
        help="Do not raise an error when prediction validation fails.",
    )
    predict_parser.add_argument(
        "--require-model-version",
        action="store_true",
        help="Require model version metadata during prediction validation.",
    )
    predict_parser.add_argument(
        "--require-probability-columns",
        action="store_true",
        help="Require probability columns during prediction validation.",
    )
    predict_parser.add_argument(
        "--require-confidence",
        action="store_true",
        help="Require confidence values during prediction validation.",
    )
    predict_parser.add_argument(
        "--confidence-column",
        default=None,
        help="Optional confidence column to validate instead of deriving confidence from probabilities.",
    )
    predict_parser.add_argument(
        "--min-confidence",
        type=float,
        default=0.55,
        help="Minimum acceptable prediction confidence.",
    )
    predict_parser.add_argument(
        "--max-low-confidence-ratio",
        type=float,
        default=0.5,
        help="Maximum allowed ratio of predictions below the confidence threshold.",
    )
    predict_parser.add_argument(
        "--probability-sum-tolerance",
        type=float,
        default=0.01,
        help="Allowed tolerance for probability row sums.",
    )
    predict_parser.add_argument(
        "--no-require-trained-feature-columns",
        action="store_true",
        help="Do not require trained model feature columns during validation.",
    )
    predict_parser.add_argument(
        "--keep-invalid-prediction-artifact",
        action="store_true",
        help="Keep invalid prediction CSV artifacts when validation fails.",
    )

    return parser

def parse_comma_separated_values(value: str | None) -> tuple[str, ...]:
    if value is None:
        return ()

    return tuple(
        item.strip()
        for item in value.split(",")
        if item.strip()
    )

def parse_feature_columns(raw_value: str) -> tuple[str, ...] | None:
    values = tuple(
        item.strip()
        for item in raw_value.split(",")
        if item.strip()
    )

    return values or None


def build_dataset_run_config_from_args(
    args: argparse.Namespace,
) -> SignalMLDatasetBuildConfig:
    return SignalMLDatasetBuildConfig(
        label_config=SignalTargetLabelConfig(
            horizon_bars=args.horizon_bars,
            min_signal_return=args.min_signal_return,
            take_profit_return=args.take_profit_return,
            stop_loss_return=args.stop_loss_return,
            target_column=args.target_column,
            drop_incomplete_horizon=not args.keep_incomplete_horizon,
        ),
        feature_config=OHLCVFeatureBuilderConfig(
            include_time_features=not args.no_time_features,
            fill_missing_values=not args.no_fill_missing_values,
        ),
        validate_schema=not args.no_schema_validation,
        metadata_filename=args.metadata_filename,
    )


def build_quality_report_config_from_args(
    args: argparse.Namespace,
) -> DatasetQualityConfig:
    return DatasetQualityConfig(
        target_column=args.target_column,
        min_rows=args.min_rows,
        min_target_classes=args.min_target_classes,
        max_majority_class_ratio=args.max_majority_class_ratio,
    )


def build_training_run_config_from_args(
    args: argparse.Namespace,
) -> SignalTrainingRunConfig:
    return SignalTrainingRunConfig(
        dataset_path=args.dataset_path,
        output_dir=args.output_dir,
        target_column=args.target_column,
        feature_columns=parse_feature_columns(args.feature_columns),
        test_size=args.test_size,
        random_state=args.random_state,
        n_estimators=args.n_estimators,
        max_depth=args.max_depth,
        min_samples_leaf=args.min_samples_leaf,
        model_filename=args.model_filename,
        metrics_filename=args.metrics_filename,
        validate_schema=not args.no_schema_validation,
        validate_quality=not args.no_quality_validation,
        quality_report_filename=args.quality_report_filename,
        max_majority_class_ratio=args.max_majority_class_ratio,
        enable_model_evaluation=not args.no_model_evaluation,
        model_evaluation_report_filename=args.model_evaluation_report_filename,
        fail_on_model_evaluation_error=args.fail_on_model_evaluation_error,
        evaluation_min_accuracy=args.evaluation_min_accuracy,
        evaluation_min_macro_f1=args.evaluation_min_macro_f1,
        evaluation_max_log_loss=args.evaluation_max_log_loss,
        evaluation_min_test_samples=args.evaluation_min_test_samples,
        evaluation_required_classes=parse_comma_separated_values(
            args.evaluation_required_classes
        ),
        evaluation_allowed_promotion_stage=ModelPromotionStage(
            args.evaluation_allowed_promotion_stage
        ),
        model_evaluation_notes=args.model_evaluation_notes,
        enable_experiment_registry=not args.no_experiment_registry,
    )


def build_prediction_run_config_from_args(
    args: argparse.Namespace,
) -> SignalPredictionRunConfig:
    return SignalPredictionRunConfig(
        model_path=args.model_path,
        features_path=args.features_path,
        output_path=args.output_path,
        include_probabilities=not args.no_probabilities,
        validate_schema=not args.no_schema_validation,
        enable_prediction_versioning=not args.no_prediction_versioning,
        prediction_metadata_filename=args.prediction_metadata_filename,
        enable_prediction_registry=not args.no_prediction_registry,
        prediction_registry_filename=args.prediction_registry_filename,
        model_version_metadata_path=args.model_version_metadata_path,
        enable_prediction_validation=not args.no_prediction_validation,
        prediction_validation_report_filename=args.prediction_validation_report_filename,
        fail_on_prediction_validation_error=not args.no_fail_on_prediction_validation_error,
        require_model_version=args.require_model_version,
        require_probability_columns=args.require_probability_columns,
        require_confidence=args.require_confidence,
        confidence_column=args.confidence_column,
        min_confidence=args.min_confidence,
        max_low_confidence_ratio=args.max_low_confidence_ratio,
        probability_sum_tolerance=args.probability_sum_tolerance,
        require_trained_feature_columns=not args.no_require_trained_feature_columns,
        remove_invalid_prediction_artifact=not args.keep_invalid_prediction_artifact,
    )


def run_model_training_cli(argv: Sequence[str] | None = None) -> int:
    parser = build_model_training_cli_parser()
    args = parser.parse_args(argv)

    if args.command == "build-dataset":
        output = build_signal_ml_training_dataset_from_csv(
            input_path=args.input_path,
            output_path=args.output_path,
            config=build_dataset_run_config_from_args(args),
        )
        print(json.dumps(output.to_dict(), indent=2, sort_keys=True))
        return 0

    if args.command == "quality-report":
        dataset = load_signal_training_dataset(args.dataset_path)
        report = build_dataset_quality_report(
            dataset,
            config=build_quality_report_config_from_args(args),
        )
        report_path = write_dataset_quality_report(args.output_path, report)

        payload = {
            "report_path": report_path.as_posix(),
            "quality_report": report.to_dict(),
        }

        print(json.dumps(payload, indent=2, sort_keys=True))

        if args.fail_on_error:
            report.raise_if_invalid()

        return 0

    if args.command == "train":
        output = train_baseline_signal_model_from_csv(
            build_training_run_config_from_args(args)
        )
        print(json.dumps(output.to_dict(), indent=2, sort_keys=True))
        return 0
    if args.command == "list-experiments":
        registry = read_experiment_registry(args.registry_path)
        print(json.dumps(registry, indent=2, sort_keys=True))
        return 0
    if args.command == "list-predictions":
        registry = read_prediction_registry(args.registry_path)
        print(json.dumps(registry, indent=2, sort_keys=True))
        return 0
    if args.command == "predict":
        output = predict_signals_from_csv(
            build_prediction_run_config_from_args(args)
        )
        print(json.dumps(output.to_dict(), indent=2, sort_keys=True))
        return 0

    parser.error(f"Unsupported command: {args.command}")
    return 2


def main() -> int:
    return run_model_training_cli()


if __name__ == "__main__":
    raise SystemExit(main())