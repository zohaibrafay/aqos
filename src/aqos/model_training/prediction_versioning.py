from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import Enum
from pathlib import Path
from typing import Any

import pandas as pd

from aqos.model_training.dataset_versioning import (
    DatasetFingerprint,
    build_dataframe_fingerprint,
    compute_file_sha256,
    sha256_text,
)
from aqos.model_training.model_versioning import read_model_version_metadata


PREDICTION_METADATA_VERSION = "1.0"


class PredictionArtifactType(str, Enum):
    INPUT_FEATURES = "input_features"
    PREDICTIONS = "predictions"
    MODEL_VERSION_METADATA = "model_version_metadata"


@dataclass(frozen=True)
class PredictionArtifactReference:
    name: str
    artifact_type: PredictionArtifactType
    path: str
    sha256: str
    size_bytes: int

    def __post_init__(self) -> None:
        if not self.name.strip():
            raise ValueError("prediction artifact name cannot be empty.")

        if not self.path.strip():
            raise ValueError("prediction artifact path cannot be empty.")

        if not self.sha256.strip():
            raise ValueError("prediction artifact sha256 cannot be empty.")

        if self.size_bytes < 0:
            raise ValueError("prediction artifact size_bytes cannot be negative.")

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "artifact_type": self.artifact_type.value,
            "path": self.path,
            "sha256": self.sha256,
            "size_bytes": self.size_bytes,
        }


@dataclass(frozen=True)
class PredictionRunMetadata:
    prediction_id: str
    created_at_utc: str
    model_name: str | None
    model_id: str | None
    model_version: str | None
    prediction_artifact: PredictionArtifactReference
    input_features_fingerprint: DatasetFingerprint
    input_features_artifact: PredictionArtifactReference | None = None
    model_version_metadata_artifact: PredictionArtifactReference | None = None
    rows: int = 0
    columns: tuple[str, ...] = ()
    prediction_column: str = "predicted_signal"
    probability_columns: tuple[str, ...] = ()
    parameters: dict[str, Any] = field(default_factory=dict)
    metadata_version: str = PREDICTION_METADATA_VERSION

    def __post_init__(self) -> None:
        if not self.prediction_id.strip():
            raise ValueError("prediction_id cannot be empty.")

        if not self.created_at_utc.strip():
            raise ValueError("created_at_utc cannot be empty.")

        if self.rows < 0:
            raise ValueError("rows cannot be negative.")

        if not self.prediction_column.strip():
            raise ValueError("prediction_column cannot be empty.")

    def to_dict(self) -> dict[str, Any]:
        return {
            "metadata_version": self.metadata_version,
            "prediction_id": self.prediction_id,
            "created_at_utc": self.created_at_utc,
            "model_name": self.model_name,
            "model_id": self.model_id,
            "model_version": self.model_version,
            "rows": self.rows,
            "columns": list(self.columns),
            "prediction_column": self.prediction_column,
            "probability_columns": list(self.probability_columns),
            "parameters": self.parameters,
            "prediction_artifact": self.prediction_artifact.to_dict(),
            "input_features_artifact": (
                self.input_features_artifact.to_dict()
                if self.input_features_artifact is not None
                else None
            ),
            "model_version_metadata_artifact": (
                self.model_version_metadata_artifact.to_dict()
                if self.model_version_metadata_artifact is not None
                else None
            ),
            "input_features_fingerprint": self.input_features_fingerprint.to_dict(),
        }


def prediction_utc_now_iso() -> str:
    return datetime.now(tz=UTC).replace(microsecond=0).isoformat()


def normalize_prediction_name(value: str) -> str:
    normalized = value.strip().lower().replace(" ", "_").replace("-", "_")
    normalized = "".join(
        character
        for character in normalized
        if character.isalnum() or character == "_"
    )
    return normalized or "prediction"


def build_prediction_artifact_reference(
    path: str | Path,
    artifact_type: PredictionArtifactType,
    name: str | None = None,
) -> PredictionArtifactReference:
    artifact_path = Path(path)

    if not artifact_path.exists():
        raise FileNotFoundError(f"Prediction artifact does not exist: {artifact_path}")

    if not artifact_path.is_file():
        raise ValueError(f"Prediction artifact path is not a file: {artifact_path}")

    return PredictionArtifactReference(
        name=name or artifact_path.name,
        artifact_type=artifact_type,
        path=artifact_path.as_posix(),
        sha256=compute_file_sha256(artifact_path),
        size_bytes=artifact_path.stat().st_size,
    )


def extract_model_version_reference(
    model_version_metadata_path: str | Path | None,
) -> tuple[str | None, str | None, str | None]:
    if model_version_metadata_path is None:
        return None, None, None

    payload = read_model_version_metadata(model_version_metadata_path)

    return (
        payload.get("model_name"),
        payload.get("model_id"),
        payload.get("model_version"),
    )


def build_prediction_run_id(
    model_version: str | None,
    input_features_fingerprint: DatasetFingerprint,
    prediction_artifact: PredictionArtifactReference,
    created_at_utc: str,
) -> str:
    safe_timestamp = (
        created_at_utc.replace("-", "")
        .replace(":", "")
        .replace("+", "Z")
        .replace("T", "_")
    )

    fingerprint = sha256_text(
        json.dumps(
            {
                "model_version": model_version,
                "input_features_sha256": input_features_fingerprint.content_sha256,
                "prediction_sha256": prediction_artifact.sha256,
                "created_at_utc": created_at_utc,
            },
            sort_keys=True,
            separators=(",", ":"),
        )
    )[:12]

    return f"prediction_v{safe_timestamp}_{fingerprint}"


def build_prediction_run_metadata(
    predictions: pd.DataFrame,
    prediction_path: str | Path,
    input_features: pd.DataFrame,
    input_features_path: str | Path | None = None,
    model_version_metadata_path: str | Path | None = None,
    created_at_utc: str | None = None,
    prediction_column: str = "predicted_signal",
    probability_columns: tuple[str, ...] = (),
    parameters: dict[str, Any] | None = None,
) -> PredictionRunMetadata:
    if predictions.empty:
        raise ValueError("Cannot build prediction metadata for empty predictions.")

    if input_features.empty:
        raise ValueError("Cannot build prediction metadata for empty input features.")

    created_at = created_at_utc or prediction_utc_now_iso()

    prediction_artifact = build_prediction_artifact_reference(
        prediction_path,
        PredictionArtifactType.PREDICTIONS,
        name="prediction_output",
    )

    input_features_artifact = (
        build_prediction_artifact_reference(
            input_features_path,
            PredictionArtifactType.INPUT_FEATURES,
            name="input_features",
        )
        if input_features_path is not None
        else None
    )

    model_version_metadata_artifact = (
        build_prediction_artifact_reference(
            model_version_metadata_path,
            PredictionArtifactType.MODEL_VERSION_METADATA,
            name="model_version_metadata",
        )
        if model_version_metadata_path is not None
        else None
    )

    model_name, model_id, model_version = extract_model_version_reference(
        model_version_metadata_path
    )

    input_features_fingerprint = build_dataframe_fingerprint(
        input_features,
        source_file_path=input_features_path,
    )

    prediction_id = build_prediction_run_id(
        model_version=model_version,
        input_features_fingerprint=input_features_fingerprint,
        prediction_artifact=prediction_artifact,
        created_at_utc=created_at,
    )

    return PredictionRunMetadata(
        prediction_id=prediction_id,
        created_at_utc=created_at,
        model_name=model_name,
        model_id=model_id,
        model_version=model_version,
        prediction_artifact=prediction_artifact,
        input_features_fingerprint=input_features_fingerprint,
        input_features_artifact=input_features_artifact,
        model_version_metadata_artifact=model_version_metadata_artifact,
        rows=len(predictions),
        columns=tuple(str(column) for column in predictions.columns),
        prediction_column=prediction_column,
        probability_columns=probability_columns,
        parameters=parameters or {},
    )


def write_prediction_run_metadata(
    path: str | Path,
    metadata: PredictionRunMetadata,
) -> Path:
    output_path = Path(path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    output_path.write_text(
        json.dumps(metadata.to_dict(), indent=2, sort_keys=True),
        encoding="utf-8",
    )

    return output_path


def read_prediction_run_metadata(path: str | Path) -> dict[str, Any]:
    metadata_path = Path(path)

    if not metadata_path.exists():
        raise FileNotFoundError(
            f"Prediction metadata file does not exist: {metadata_path}"
        )

    return json.loads(metadata_path.read_text(encoding="utf-8"))


__all__ = [
    "PREDICTION_METADATA_VERSION",
    "PredictionArtifactReference",
    "PredictionArtifactType",
    "PredictionRunMetadata",
    "build_prediction_artifact_reference",
    "build_prediction_run_id",
    "build_prediction_run_metadata",
    "extract_model_version_reference",
    "normalize_prediction_name",
    "prediction_utc_now_iso",
    "read_prediction_run_metadata",
    "write_prediction_run_metadata",
]