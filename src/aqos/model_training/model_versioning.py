from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import Enum
from pathlib import Path
from typing import Any

from aqos.model_training.dataset_versioning import (
    compute_file_sha256,
    sha256_text,
)


MODEL_METADATA_VERSION = "1.0"


class ModelArtifactFormat(str, Enum):
    JOBLIB = "joblib"
    PICKLE = "pickle"
    ONNX = "onnx"
    UNKNOWN = "unknown"


@dataclass(frozen=True)
class ModelArtifactReference:
    path: str
    sha256: str
    size_bytes: int
    artifact_format: ModelArtifactFormat

    def __post_init__(self) -> None:
        if not self.path.strip():
            raise ValueError("model artifact path cannot be empty.")

        if not self.sha256.strip():
            raise ValueError("model artifact sha256 cannot be empty.")

        if self.size_bytes < 0:
            raise ValueError("model artifact size_bytes cannot be negative.")

    def to_dict(self) -> dict[str, Any]:
        return {
            "path": self.path,
            "sha256": self.sha256,
            "size_bytes": self.size_bytes,
            "artifact_format": self.artifact_format.value,
        }


@dataclass(frozen=True)
class ModelVersionMetadata:
    model_name: str
    model_version: str
    model_artifact: ModelArtifactReference
    created_at_utc: str
    metadata_version: str = MODEL_METADATA_VERSION
    dataset_id: str | None = None
    dataset_version: str | None = None
    experiment_run_id: str | None = None
    training_parameters: dict[str, Any] = field(default_factory=dict)
    training_metrics: dict[str, Any] = field(default_factory=dict)
    description: str | None = None
    tags: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if not self.model_name.strip():
            raise ValueError("model_name cannot be empty.")

        if not self.model_version.strip():
            raise ValueError("model_version cannot be empty.")

        if not self.created_at_utc.strip():
            raise ValueError("created_at_utc cannot be empty.")

    @property
    def model_id(self) -> str:
        safe_name = normalize_model_name(self.model_name)
        return f"{safe_name}_{self.model_artifact.sha256[:12]}"

    def to_dict(self) -> dict[str, Any]:
        return {
            "metadata_version": self.metadata_version,
            "model_id": self.model_id,
            "model_name": self.model_name,
            "model_version": self.model_version,
            "created_at_utc": self.created_at_utc,
            "dataset_id": self.dataset_id,
            "dataset_version": self.dataset_version,
            "experiment_run_id": self.experiment_run_id,
            "training_parameters": self.training_parameters,
            "training_metrics": self.training_metrics,
            "description": self.description,
            "tags": list(self.tags),
            "model_artifact": self.model_artifact.to_dict(),
        }


def model_utc_now_iso() -> str:
    return datetime.now(tz=UTC).replace(microsecond=0).isoformat()


def normalize_model_name(value: str) -> str:
    normalized = value.strip().lower().replace(" ", "_").replace("-", "_")
    normalized = "".join(
        character
        for character in normalized
        if character.isalnum() or character == "_"
    )
    return normalized or "model"


def infer_model_artifact_format(path: str | Path) -> ModelArtifactFormat:
    suffix = Path(path).suffix.lower()

    if suffix == ".joblib":
        return ModelArtifactFormat.JOBLIB

    if suffix in {".pkl", ".pickle"}:
        return ModelArtifactFormat.PICKLE

    if suffix == ".onnx":
        return ModelArtifactFormat.ONNX

    return ModelArtifactFormat.UNKNOWN


def build_model_artifact_reference(
    model_path: str | Path,
    artifact_format: ModelArtifactFormat | None = None,
) -> ModelArtifactReference:
    path = Path(model_path)

    if not path.exists():
        raise FileNotFoundError(f"Model artifact does not exist: {path}")

    if not path.is_file():
        raise ValueError(f"Model artifact path is not a file: {path}")

    return ModelArtifactReference(
        path=path.as_posix(),
        sha256=compute_file_sha256(path),
        size_bytes=path.stat().st_size,
        artifact_format=artifact_format or infer_model_artifact_format(path),
    )


def build_model_version_string(
    model_name: str,
    model_artifact: ModelArtifactReference,
    created_at_utc: str,
) -> str:
    safe_name = normalize_model_name(model_name)
    safe_timestamp = (
        created_at_utc.replace("-", "")
        .replace(":", "")
        .replace("+", "Z")
        .replace("T", "_")
    )

    fingerprint = sha256_text(
        json.dumps(
            {
                "model_name": model_name,
                "created_at_utc": created_at_utc,
                "artifact_sha256": model_artifact.sha256,
            },
            sort_keys=True,
            separators=(",", ":"),
        )
    )[:12]

    return f"{safe_name}_v{safe_timestamp}_{fingerprint}"


def build_model_version_metadata(
    model_name: str,
    model_path: str | Path,
    created_at_utc: str | None = None,
    model_version: str | None = None,
    dataset_id: str | None = None,
    dataset_version: str | None = None,
    experiment_run_id: str | None = None,
    training_parameters: dict[str, Any] | None = None,
    training_metrics: dict[str, Any] | None = None,
    description: str | None = None,
    tags: tuple[str, ...] = (),
) -> ModelVersionMetadata:
    created_at = created_at_utc or model_utc_now_iso()
    artifact = build_model_artifact_reference(model_path)

    resolved_version = model_version or build_model_version_string(
        model_name=model_name,
        model_artifact=artifact,
        created_at_utc=created_at,
    )

    return ModelVersionMetadata(
        model_name=model_name,
        model_version=resolved_version,
        model_artifact=artifact,
        created_at_utc=created_at,
        dataset_id=dataset_id,
        dataset_version=dataset_version,
        experiment_run_id=experiment_run_id,
        training_parameters=training_parameters or {},
        training_metrics=training_metrics or {},
        description=description,
        tags=tags,
    )


def write_model_version_metadata(
    path: str | Path,
    metadata: ModelVersionMetadata,
) -> Path:
    output_path = Path(path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    output_path.write_text(
        json.dumps(metadata.to_dict(), indent=2, sort_keys=True),
        encoding="utf-8",
    )

    return output_path


def read_model_version_metadata(path: str | Path) -> dict[str, Any]:
    metadata_path = Path(path)

    if not metadata_path.exists():
        raise FileNotFoundError(f"Model version metadata file does not exist: {metadata_path}")

    return json.loads(metadata_path.read_text(encoding="utf-8"))


__all__ = [
    "MODEL_METADATA_VERSION",
    "ModelArtifactFormat",
    "ModelArtifactReference",
    "ModelVersionMetadata",
    "build_model_artifact_reference",
    "build_model_version_metadata",
    "build_model_version_string",
    "infer_model_artifact_format",
    "model_utc_now_iso",
    "normalize_model_name",
    "read_model_version_metadata",
    "write_model_version_metadata",
]