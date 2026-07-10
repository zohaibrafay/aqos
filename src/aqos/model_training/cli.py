from __future__ import annotations

import argparse
import json
from collections.abc import Sequence

from aqos.model_training.prediction_runner import (
    SignalPredictionRunConfig,
    predict_signals_from_csv,
)
from aqos.model_training.training_runner import (
    SignalTrainingRunConfig,
    train_baseline_signal_model_from_csv,
)


def build_model_training_cli_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="aqos-model-training",
        description="Train and run AQOS baseline ML signal models.",
    )

    subparsers = parser.add_subparsers(dest="command", required=True)

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

    return parser


def parse_feature_columns(raw_value: str) -> tuple[str, ...] | None:
    values = tuple(
        item.strip()
        for item in raw_value.split(",")
        if item.strip()
    )

    return values or None


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
    )


def build_prediction_run_config_from_args(
    args: argparse.Namespace,
) -> SignalPredictionRunConfig:
    return SignalPredictionRunConfig(
        model_path=args.model_path,
        features_path=args.features_path,
        output_path=args.output_path,
        include_probabilities=not args.no_probabilities,
    )


def run_model_training_cli(argv: Sequence[str] | None = None) -> int:
    parser = build_model_training_cli_parser()
    args = parser.parse_args(argv)

    if args.command == "train":
        output = train_baseline_signal_model_from_csv(
            build_training_run_config_from_args(args)
        )
        print(json.dumps(output.to_dict(), indent=2, sort_keys=True))
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