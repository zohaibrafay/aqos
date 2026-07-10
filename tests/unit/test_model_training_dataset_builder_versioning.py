from __future__ import annotations

import json

import pandas as pd

from aqos.model_training import (
    SignalMLDatasetBuildConfig,
    SignalTargetLabelConfig,
    build_signal_dataset_version_parameters,
    build_signal_ml_training_dataset_from_csv,
    compute_file_sha256,
    read_dataset_version_metadata,
)


def build_raw_ohlcv_dataset(rows: int = 48) -> pd.DataFrame:
    records = []

    for index in range(rows):
        phase = index % 12

        if phase <= 4:
            close_price = 2300.0 + phase
        elif phase <= 7:
            close_price = 2304.0 - (phase - 4)
        else:
            close_price = 2300.0 + (0.02 if phase % 2 else 0.0)

        open_price = close_price - 0.2
        high_price = max(open_price, close_price) + 1.2
        low_price = min(open_price, close_price) - 1.2

        records.append(
            {
                "timestamp": f"2026-01-01 00:{index:02d}:00",
                "symbol": "XAUUSD",
                "timeframe": "M15",
                "open": open_price,
                "high": high_price,
                "low": low_price,
                "close": close_price,
                "volume": 1000 + index,
            }
        )

    return pd.DataFrame(records)


def test_dataset_builder_writes_version_metadata_file(tmp_path) -> None:
    input_path = tmp_path / "raw_ohlcv.csv"
    output_path = tmp_path / "training" / "signal_ml_dataset.csv"

    build_raw_ohlcv_dataset().to_csv(input_path, index=False)

    output = build_signal_ml_training_dataset_from_csv(
        input_path,
        output_path,
        config=SignalMLDatasetBuildConfig(
            label_config=SignalTargetLabelConfig(
                horizon_bars=3,
                min_signal_return=0.0002,
            ),
            dataset_name="xauusd_m15_signal_dataset",
            dataset_description="XAUUSD M15 dataset for Sprint 030.",
            dataset_tags=("xauusd", "m15", "sprint-030"),
        ),
    )

    payload = read_dataset_version_metadata(output.version_metadata_path)

    assert output.version_metadata_path.exists()
    assert payload["dataset_name"] == "xauusd_m15_signal_dataset"
    assert payload["dataset_id"].startswith("xauusd_m15_signal_dataset_")
    assert payload["artifact_type"] == "training_dataset"
    assert payload["dataset_path"].endswith("signal_ml_dataset.csv")
    assert payload["quality_report_path"].endswith("signal_ml_dataset_quality.json")
    assert payload["tags"] == ["xauusd", "m15", "sprint-030"]
    assert payload["fingerprint"]["rows"] == 45
    assert payload["fingerprint"]["source_file_sha256"] == compute_file_sha256(input_path)


def test_dataset_builder_metadata_includes_version_payload(tmp_path) -> None:
    input_path = tmp_path / "raw_ohlcv.csv"
    output_path = tmp_path / "training" / "signal_ml_dataset.csv"

    build_raw_ohlcv_dataset().to_csv(input_path, index=False)

    output = build_signal_ml_training_dataset_from_csv(
        input_path,
        output_path,
        config=SignalMLDatasetBuildConfig(
            label_config=SignalTargetLabelConfig(
                horizon_bars=3,
                min_signal_return=0.0002,
            )
        ),
    )

    metadata = json.loads(output.metadata_path.read_text(encoding="utf-8"))

    assert metadata["version_metadata_path"].endswith("signal_ml_dataset_version.json")
    assert metadata["version_metadata"]["dataset_name"] == "signal_ml_training_dataset"
    assert metadata["version_metadata"]["fingerprint"]["rows"] == 45
    assert metadata["version_metadata"]["fingerprint"]["content_sha256"] == (
        output.version_metadata.fingerprint.content_sha256
    )


def test_dataset_version_parameters_are_serializable() -> None:
    config = SignalMLDatasetBuildConfig(
        label_config=SignalTargetLabelConfig(
            horizon_bars=7,
            min_signal_return=0.0005,
        )
    )

    parameters = build_signal_dataset_version_parameters(config)

    assert parameters["label_config"]["horizon_bars"] == 7
    assert parameters["label_config"]["min_signal_return"] == 0.0005
    assert parameters["feature_config"]["include_time_features"] is True
    assert parameters["validate_schema"] is True