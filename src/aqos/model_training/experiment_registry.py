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


EXPERIMENT_REGISTRY_VERSION = "1.0"


class ExperimentRunStatus(str, Enum):
    CREATED = "created"
    COMPLETED = "completed"
    FAILED = "failed"


class ExperimentArtifactType(str, Enum):
    TRAINING_DATASET = "training_dataset"
    DATASET_VERSION_METADATA = "dataset_version_metadata"
    MODEL = "model"
    MODEL_VERSION_METADATA = "model_version_metadata"
    METRICS = "metrics"
    QUALITY_REPORT = "quality_report"
    PREDICTIONS = "predictions"


@dataclass(frozen=True)
class ExperimentArtifact:
    name: str
    artifact_type: ExperimentArtifactType
    path: str
    sha256: str
    size_bytes: int

    def __post_init__(self) -> None:
        if not self.name.strip():
            raise ValueError("artifact name cannot be empty.")

        if not self.path.strip():
            raise ValueError("artifact path cannot be empty.")

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "artifact_type": self.artifact_type.value,
            "path": self.path,
            "sha256": self.sha256,
            "size_bytes": self.size_bytes,
        }


@dataclass(frozen=True)
class ExperimentRunMetadata:
    experiment_name: str
    run_id: str
    status: ExperimentRunStatus
    created_at_utc: str
    dataset_id: str | None = None
    dataset_version: str | None = None
    model_name: str | None = None
    parameters: dict[str, Any] = field(default_factory=dict)
    metrics: dict[str, Any] = field(default_factory=dict)
    artifacts: tuple[ExperimentArtifact, ...] = ()
    tags: tuple[str, ...] = ()
    notes: str | None = None
    registry_version: str = EXPERIMENT_REGISTRY_VERSION

    def __post_init__(self) -> None:
        if not self.experiment_name.strip():
            raise ValueError("experiment_name cannot be empty.")

        if not self.run_id.strip():
            raise ValueError("run_id cannot be empty.")

        if not self.created_at_utc.strip():
            raise ValueError("created_at_utc cannot be empty.")

    def to_dict(self) -> dict[str, Any]:
        return {
            "registry_version": self.registry_version,
            "experiment_name": self.experiment_name,
            "run_id": self.run_id,
            "status": self.status.value,
            "created_at_utc": self.created_at_utc,
            "dataset_id": self.dataset_id,
            "dataset_version": self.dataset_version,
            "model_name": self.model_name,
            "parameters": self.parameters,
            "metrics": self.metrics,
            "artifacts": [artifact.to_dict() for artifact in self.artifacts],
            "tags": list(self.tags),
            "notes": self.notes,
        }


def experiment_utc_now_iso() -> str:
    return datetime.now(tz=UTC).replace(microsecond=0).isoformat()


def normalize_experiment_name(value: str) -> str:
    normalized = value.strip().lower().replace(" ", "_").replace("-", "_")
    normalized = "".join(
        character
        for character in normalized
        if character.isalnum() or character == "_"
    )
    return normalized or "experiment"


def build_experiment_run_id(
    experiment_name: str,
    created_at_utc: str,
    dataset_version: str | None = None,
    model_name: str | None = None,
) -> str:
    safe_name = normalize_experiment_name(experiment_name)
    fingerprint = sha256_text(
        json.dumps(
            {
                "experiment_name": experiment_name,
                "created_at_utc": created_at_utc,
                "dataset_version": dataset_version,
                "model_name": model_name,
            },
            sort_keys=True,
            separators=(",", ":"),
        )
    )[:12]

    safe_timestamp = (
        created_at_utc.replace("-", "")
        .replace(":", "")
        .replace("+", "Z")
        .replace("T", "_")
    )

    return f"{safe_name}_{safe_timestamp}_{fingerprint}"


def build_experiment_artifact(
    path: str | Path,
    artifact_type: ExperimentArtifactType,
    name: str | None = None,
) -> ExperimentArtifact:
    artifact_path = Path(path)

    if not artifact_path.exists():
        raise FileNotFoundError(f"Experiment artifact does not exist: {artifact_path}")

    if not artifact_path.is_file():
        raise ValueError(f"Experiment artifact path is not a file: {artifact_path}")

    return ExperimentArtifact(
        name=name or artifact_path.name,
        artifact_type=artifact_type,
        path=artifact_path.as_posix(),
        sha256=compute_file_sha256(artifact_path),
        size_bytes=artifact_path.stat().st_size,
    )


def build_experiment_run_metadata(
    experiment_name: str,
    status: ExperimentRunStatus = ExperimentRunStatus.COMPLETED,
    created_at_utc: str | None = None,
    dataset_id: str | None = None,
    dataset_version: str | None = None,
    model_name: str | None = None,
    parameters: dict[str, Any] | None = None,
    metrics: dict[str, Any] | None = None,
    artifacts: tuple[ExperimentArtifact, ...] = (),
    tags: tuple[str, ...] = (),
    notes: str | None = None,
) -> ExperimentRunMetadata:
    created_at = created_at_utc or experiment_utc_now_iso()
    run_id = build_experiment_run_id(
        experiment_name=experiment_name,
        created_at_utc=created_at,
        dataset_version=dataset_version,
        model_name=model_name,
    )

    return ExperimentRunMetadata(
        experiment_name=experiment_name,
        run_id=run_id,
        status=status,
        created_at_utc=created_at,
        dataset_id=dataset_id,
        dataset_version=dataset_version,
        model_name=model_name,
        parameters=parameters or {},
        metrics=metrics or {},
        artifacts=artifacts,
        tags=tags,
        notes=notes,
    )


def write_experiment_run_metadata(
    path: str | Path,
    metadata: ExperimentRunMetadata,
) -> Path:
    output_path = Path(path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    output_path.write_text(
        json.dumps(metadata.to_dict(), indent=2, sort_keys=True),
        encoding="utf-8",
    )

    return output_path


def read_experiment_run_metadata(path: str | Path) -> dict[str, Any]:
    metadata_path = Path(path)

    if not metadata_path.exists():
        raise FileNotFoundError(f"Experiment run metadata file does not exist: {metadata_path}")

    return json.loads(metadata_path.read_text(encoding="utf-8"))


def read_experiment_registry(path: str | Path) -> dict[str, Any]:
    registry_path = Path(path)

    if not registry_path.exists():
        return {
            "registry_version": EXPERIMENT_REGISTRY_VERSION,
            "runs": [],
        }

    return json.loads(registry_path.read_text(encoding="utf-8"))


def append_experiment_run_to_registry(
    registry_path: str | Path,
    metadata: ExperimentRunMetadata,
) -> Path:
    path = Path(registry_path)
    path.parent.mkdir(parents=True, exist_ok=True)

    registry = read_experiment_registry(path)
    runs = [
        run
        for run in registry.get("runs", [])
        if run.get("run_id") != metadata.run_id
    ]
    runs.append(metadata.to_dict())

    registry["registry_version"] = EXPERIMENT_REGISTRY_VERSION
    registry["runs"] = sorted(
        runs,
        key=lambda run: str(run.get("created_at_utc", "")),
    )

    path.write_text(
        json.dumps(registry, indent=2, sort_keys=True),
        encoding="utf-8",
    )

    return path


__all__ = [
    "EXPERIMENT_REGISTRY_VERSION",
    "ExperimentArtifact",
    "ExperimentArtifactType",
    "ExperimentRunMetadata",
    "ExperimentRunStatus",
    "append_experiment_run_to_registry",
    "build_experiment_artifact",
    "build_experiment_run_id",
    "build_experiment_run_metadata",
    "experiment_utc_now_iso",
    "normalize_experiment_name",
    "read_experiment_registry",
    "read_experiment_run_metadata",
    "write_experiment_run_metadata",
]