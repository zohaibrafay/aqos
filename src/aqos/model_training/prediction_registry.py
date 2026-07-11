from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from aqos.model_training.prediction_versioning import (
    PREDICTION_METADATA_VERSION,
    PredictionRunMetadata,
)


PREDICTION_REGISTRY_VERSION = "1.0"


def read_prediction_registry(path: str | Path) -> dict[str, Any]:
    registry_path = Path(path)

    if not registry_path.exists():
        return {
            "registry_version": PREDICTION_REGISTRY_VERSION,
            "prediction_metadata_version": PREDICTION_METADATA_VERSION,
            "runs": [],
        }

    return json.loads(registry_path.read_text(encoding="utf-8"))


def build_prediction_registry_entry(
    metadata: PredictionRunMetadata,
    metadata_path: str | Path,
) -> dict[str, Any]:
    return {
        "prediction_id": metadata.prediction_id,
        "created_at_utc": metadata.created_at_utc,
        "model_name": metadata.model_name,
        "model_id": metadata.model_id,
        "model_version": metadata.model_version,
        "rows": metadata.rows,
        "prediction_column": metadata.prediction_column,
        "probability_columns": list(metadata.probability_columns),
        "metadata_path": Path(metadata_path).as_posix(),
        "prediction_path": metadata.prediction_artifact.path,
        "prediction_sha256": metadata.prediction_artifact.sha256,
        "input_features_sha256": metadata.input_features_fingerprint.content_sha256,
        "input_features_rows": metadata.input_features_fingerprint.rows,
        "input_features_columns_count": metadata.input_features_fingerprint.columns_count,
    }


def append_prediction_run_to_registry(
    registry_path: str | Path,
    metadata: PredictionRunMetadata,
    metadata_path: str | Path,
) -> Path:
    path = Path(registry_path)
    path.parent.mkdir(parents=True, exist_ok=True)

    registry = read_prediction_registry(path)
    entry = build_prediction_registry_entry(metadata, metadata_path)

    runs = [
        run
        for run in registry.get("runs", [])
        if run.get("prediction_id") != metadata.prediction_id
    ]
    runs.append(entry)

    registry["registry_version"] = PREDICTION_REGISTRY_VERSION
    registry["prediction_metadata_version"] = PREDICTION_METADATA_VERSION
    registry["runs"] = sorted(
        runs,
        key=lambda run: str(run.get("created_at_utc", "")),
    )

    path.write_text(
        json.dumps(registry, indent=2, sort_keys=True),
        encoding="utf-8",
    )

    return path


def list_prediction_registry_runs(
    registry_path: str | Path,
) -> tuple[dict[str, Any], ...]:
    registry = read_prediction_registry(registry_path)

    return tuple(registry.get("runs", []))


def find_prediction_registry_run(
    registry_path: str | Path,
    prediction_id: str,
) -> dict[str, Any] | None:
    for run in list_prediction_registry_runs(registry_path):
        if run.get("prediction_id") == prediction_id:
            return run

    return None


__all__ = [
    "PREDICTION_REGISTRY_VERSION",
    "append_prediction_run_to_registry",
    "build_prediction_registry_entry",
    "find_prediction_registry_run",
    "list_prediction_registry_runs",
    "read_prediction_registry",
]