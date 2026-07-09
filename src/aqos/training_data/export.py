"""
AQOS training dataset export and manifest utilities.

This module creates export-ready dataset packages, manifests, summaries,
and serializable payloads for AQOS model training pipelines.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import Enum
from typing import Any

from aqos.training_data.base import (
    TrainingDataHealth,
    TrainingDataStatus,
    build_training_data_health,
    normalize_training_symbol,
    validate_metadata,
    validate_non_empty_string,
    validate_non_negative_integer,
    validate_string,
)
from aqos.training_data.dataset_builder import TrainingFeatureDataset
from aqos.training_data.labels import LabeledTrainingDataset, TrainingLabelDataset
from aqos.training_data.pattern_windows import PatternWindowDataset
from aqos.training_data.splits import DatasetSplitPlan


class TrainingDatasetExportFormat(str, Enum):
    """Supported training dataset export formats."""

    JSON = "json"
    JSONL = "jsonl"
    CSV = "csv"
    PARQUET = "parquet"
    MEMORY = "memory"


class TrainingDatasetArtifactType(str, Enum):
    """Supported training dataset artifact types."""

    FEATURES = "features"
    LABELS = "labels"
    LABELED = "labeled"
    PATTERN_WINDOWS = "pattern_windows"
    SPLIT_PLAN = "split_plan"
    MANIFEST = "manifest"


@dataclass(frozen=True)
class TrainingDatasetArtifact:
    """Training dataset artifact metadata."""

    artifact_id: str
    artifact_type: TrainingDatasetArtifactType | str
    format: TrainingDatasetExportFormat | str = TrainingDatasetExportFormat.JSON
    path: str = ""
    row_count: int = 0
    column_count: int = 0
    checksum: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        validate_non_empty_string(self.artifact_id, "Artifact ID")
        normalize_training_dataset_artifact_type(self.artifact_type)
        normalize_training_dataset_export_format(self.format)
        validate_string(self.path, "Path")
        validate_non_negative_integer(self.row_count, "Row count")
        validate_non_negative_integer(self.column_count, "Column count")
        validate_string(self.checksum, "Checksum")
        validate_metadata(self.metadata, "Metadata")

    def to_dict(self) -> dict[str, Any]:
        """Convert artifact to dictionary."""
        return {
            "artifact_id": self.artifact_id.strip(),
            "artifact_type": normalize_training_dataset_artifact_type(self.artifact_type).value,
            "format": normalize_training_dataset_export_format(self.format).value,
            "path": self.path.strip(),
            "row_count": self.row_count,
            "column_count": self.column_count,
            "checksum": self.checksum.strip(),
            "metadata": dict(self.metadata),
        }


@dataclass(frozen=True)
class TrainingDatasetManifest:
    """Training dataset manifest."""

    manifest_id: str
    dataset_id: str
    symbol: str
    version: str = "0.1.0"
    created_at: str = field(default_factory=lambda: datetime.now(UTC).isoformat())
    artifacts: list[TrainingDatasetArtifact] = field(default_factory=list)
    health: TrainingDataHealth | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        validate_non_empty_string(self.manifest_id, "Manifest ID")
        validate_non_empty_string(self.dataset_id, "Dataset ID")
        normalize_training_symbol(self.symbol)
        validate_non_empty_string(self.version, "Version")
        validate_non_empty_string(self.created_at, "Created at")
        validate_training_dataset_artifacts(self.artifacts)

        if self.health is not None and not isinstance(self.health, TrainingDataHealth):
            raise ValueError("Health must be TrainingDataHealth.")

        validate_metadata(self.metadata, "Metadata")

    @property
    def artifact_count(self) -> int:
        """Return artifact count."""
        return len(self.artifacts)

    @property
    def total_row_count(self) -> int:
        """Return total artifact row count."""
        return sum(artifact.row_count for artifact in self.artifacts)

    @property
    def healthy(self) -> bool:
        """Return whether manifest is healthy."""
        return self.health.healthy if self.health is not None else self.artifact_count > 0

    def to_dict(self) -> dict[str, Any]:
        """Convert manifest to dictionary."""
        return {
            "manifest_id": self.manifest_id.strip(),
            "dataset_id": self.dataset_id.strip(),
            "symbol": normalize_training_symbol(self.symbol),
            "version": self.version.strip(),
            "created_at": self.created_at.strip(),
            "artifacts": [artifact.to_dict() for artifact in self.artifacts],
            "artifact_count": self.artifact_count,
            "total_row_count": self.total_row_count,
            "healthy": self.healthy,
            "health": self.health.to_dict() if self.health is not None else None,
            "metadata": dict(self.metadata),
        }

    def to_json(self) -> str:
        """Convert manifest to JSON."""
        return json.dumps(self.to_dict(), indent=2, sort_keys=True)


@dataclass(frozen=True)
class TrainingDatasetExportPackage:
    """Export-ready training dataset package."""

    package_id: str
    manifest: TrainingDatasetManifest
    payloads: dict[str, Any] = field(default_factory=dict)
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        validate_non_empty_string(self.package_id, "Package ID")

        if not isinstance(self.manifest, TrainingDatasetManifest):
            raise ValueError("Manifest must be TrainingDatasetManifest.")

        validate_metadata(self.payloads, "Payloads")
        validate_metadata(self.metadata, "Metadata")

    @property
    def artifact_count(self) -> int:
        """Return artifact count."""
        return self.manifest.artifact_count

    @property
    def payload_count(self) -> int:
        """Return payload count."""
        return len(self.payloads)

    def to_dict(self) -> dict[str, Any]:
        """Convert package to dictionary."""
        return {
            "package_id": self.package_id.strip(),
            "manifest": self.manifest.to_dict(),
            "payloads": dict(self.payloads),
            "artifact_count": self.artifact_count,
            "payload_count": self.payload_count,
            "metadata": dict(self.metadata),
        }

    def to_json(self) -> str:
        """Convert package to JSON."""
        return json.dumps(self.to_dict(), indent=2, sort_keys=True)


def normalize_training_dataset_export_format(
    value: TrainingDatasetExportFormat | str,
) -> TrainingDatasetExportFormat:
    """Normalize training dataset export format."""
    if isinstance(value, TrainingDatasetExportFormat):
        return value

    normalized = validate_non_empty_string(value, "Export format").lower()

    try:
        return TrainingDatasetExportFormat(normalized)
    except ValueError as exc:
        valid = ", ".join(item.value for item in TrainingDatasetExportFormat)
        raise ValueError(
            f"Invalid export format '{value}'. Valid formats: {valid}.",
        ) from exc


def normalize_training_dataset_artifact_type(
    value: TrainingDatasetArtifactType | str,
) -> TrainingDatasetArtifactType:
    """Normalize training dataset artifact type."""
    if isinstance(value, TrainingDatasetArtifactType):
        return value

    normalized = validate_non_empty_string(value, "Artifact type").lower()

    try:
        return TrainingDatasetArtifactType(normalized)
    except ValueError as exc:
        valid = ", ".join(item.value for item in TrainingDatasetArtifactType)
        raise ValueError(
            f"Invalid artifact type '{value}'. Valid artifact types: {valid}.",
        ) from exc


def validate_training_dataset_artifacts(
    artifacts: list[TrainingDatasetArtifact],
) -> list[TrainingDatasetArtifact]:
    """Validate training dataset artifacts."""
    if not isinstance(artifacts, list):
        raise ValueError("Artifacts must be a list.")

    for artifact in artifacts:
        if not isinstance(artifact, TrainingDatasetArtifact):
            raise ValueError("Artifacts must contain TrainingDatasetArtifact objects.")

    return artifacts


def build_training_dataset_artifact(
    *,
    artifact_id: str,
    artifact_type: TrainingDatasetArtifactType | str,
    format: TrainingDatasetExportFormat | str = TrainingDatasetExportFormat.JSON,
    path: str = "",
    row_count: int = 0,
    column_count: int = 0,
    checksum: str = "",
    metadata: dict[str, Any] | None = None,
) -> TrainingDatasetArtifact:
    """Build training dataset artifact."""
    return TrainingDatasetArtifact(
        artifact_id=artifact_id,
        artifact_type=artifact_type,
        format=format,
        path=path,
        row_count=row_count,
        column_count=column_count,
        checksum=checksum,
        metadata=metadata or {},
    )


def build_training_dataset_manifest(
    *,
    manifest_id: str,
    dataset_id: str,
    symbol: str,
    version: str = "0.1.0",
    created_at: str | None = None,
    artifacts: list[TrainingDatasetArtifact] | None = None,
    health: TrainingDataHealth | None = None,
    metadata: dict[str, Any] | None = None,
) -> TrainingDatasetManifest:
    """Build training dataset manifest."""
    manifest_kwargs: dict[str, Any] = {
        "manifest_id": manifest_id,
        "dataset_id": dataset_id,
        "symbol": symbol,
        "version": version,
        "artifacts": artifacts or [],
        "health": health,
        "metadata": metadata or {},
    }

    if created_at is not None:
        manifest_kwargs["created_at"] = created_at

    return TrainingDatasetManifest(**manifest_kwargs)


def infer_dataset_health_from_artifacts(
    *,
    dataset_id: str,
    artifacts: list[TrainingDatasetArtifact],
) -> TrainingDataHealth:
    """Infer dataset health from artifacts."""
    validate_non_empty_string(dataset_id, "Dataset ID")
    validate_training_dataset_artifacts(artifacts)

    total_rows = sum(artifact.row_count for artifact in artifacts)
    feature_count = sum(
        artifact.column_count
        for artifact in artifacts
        if normalize_training_dataset_artifact_type(artifact.artifact_type)
        == TrainingDatasetArtifactType.FEATURES
    )
    label_count = sum(
        artifact.column_count
        for artifact in artifacts
        if normalize_training_dataset_artifact_type(artifact.artifact_type)
        == TrainingDatasetArtifactType.LABELS
    )

    return build_training_data_health(
        dataset_id=dataset_id,
        status=TrainingDataStatus.READY if total_rows > 0 else TrainingDataStatus.EMPTY,
        row_count=total_rows,
        feature_count=feature_count,
        label_count=label_count,
        metadata={
            "artifact_count": len(artifacts),
        },
    )


def training_feature_dataset_to_artifact(
    dataset: TrainingFeatureDataset,
    *,
    format: TrainingDatasetExportFormat | str = TrainingDatasetExportFormat.JSON,
    path: str = "",
) -> TrainingDatasetArtifact:
    """Convert feature dataset to artifact."""
    if not isinstance(dataset, TrainingFeatureDataset):
        raise ValueError("Dataset must be TrainingFeatureDataset.")

    return build_training_dataset_artifact(
        artifact_id=f"{dataset.dataset_id}-features",
        artifact_type=TrainingDatasetArtifactType.FEATURES,
        format=format,
        path=path,
        row_count=dataset.row_count,
        column_count=dataset.column_count,
        metadata={
            "source": dataset.source,
        },
    )


def training_label_dataset_to_artifact(
    dataset: TrainingLabelDataset,
    *,
    format: TrainingDatasetExportFormat | str = TrainingDatasetExportFormat.JSON,
    path: str = "",
) -> TrainingDatasetArtifact:
    """Convert label dataset to artifact."""
    if not isinstance(dataset, TrainingLabelDataset):
        raise ValueError("Dataset must be TrainingLabelDataset.")

    return build_training_dataset_artifact(
        artifact_id=f"{dataset.dataset_id}-labels",
        artifact_type=TrainingDatasetArtifactType.LABELS,
        format=format,
        path=path,
        row_count=dataset.row_count,
        column_count=dataset.label_count,
        metadata={
            "source_dataset_id": dataset.source_dataset_id,
        },
    )


def labeled_training_dataset_to_artifact(
    dataset: LabeledTrainingDataset,
    *,
    format: TrainingDatasetExportFormat | str = TrainingDatasetExportFormat.JSON,
    path: str = "",
) -> TrainingDatasetArtifact:
    """Convert labeled dataset to artifact."""
    if not isinstance(dataset, LabeledTrainingDataset):
        raise ValueError("Dataset must be LabeledTrainingDataset.")

    rows = dataset.to_flat_rows()
    column_count = len(rows[0]) if rows else 0

    return build_training_dataset_artifact(
        artifact_id=f"{dataset.dataset_id}-joined",
        artifact_type=TrainingDatasetArtifactType.LABELED,
        format=format,
        path=path,
        row_count=len(rows),
        column_count=column_count,
        metadata={
            "feature_dataset_id": dataset.feature_dataset.dataset_id,
            "label_dataset_id": dataset.label_dataset.dataset_id,
        },
    )


def pattern_window_dataset_to_artifact(
    dataset: PatternWindowDataset,
    *,
    format: TrainingDatasetExportFormat | str = TrainingDatasetExportFormat.JSON,
    path: str = "",
) -> TrainingDatasetArtifact:
    """Convert pattern window dataset to artifact."""
    if not isinstance(dataset, PatternWindowDataset):
        raise ValueError("Dataset must be PatternWindowDataset.")

    return build_training_dataset_artifact(
        artifact_id=f"{dataset.dataset_id}-windows",
        artifact_type=TrainingDatasetArtifactType.PATTERN_WINDOWS,
        format=format,
        path=path,
        row_count=dataset.window_count,
        column_count=dataset.config.window_size,
        metadata={
            "source_dataset_id": dataset.source_dataset_id,
            "labeled_window_count": dataset.labeled_window_count,
        },
    )


def split_plan_to_artifact(
    plan: DatasetSplitPlan,
    *,
    format: TrainingDatasetExportFormat | str = TrainingDatasetExportFormat.JSON,
    path: str = "",
) -> TrainingDatasetArtifact:
    """Convert split plan to artifact."""
    if not isinstance(plan, DatasetSplitPlan):
        raise ValueError("Plan must be DatasetSplitPlan.")

    return build_training_dataset_artifact(
        artifact_id=f"{plan.dataset_id}-split-plan",
        artifact_type=TrainingDatasetArtifactType.SPLIT_PLAN,
        format=format,
        path=path,
        row_count=plan.range_count,
        column_count=0,
        metadata={
            "strategy": plan.strategy.value if hasattr(plan.strategy, "value") else str(plan.strategy),
            "fold_count": plan.fold_count,
        },
    )


def build_training_export_manifest_from_parts(
    *,
    dataset_id: str,
    symbol: str,
    feature_dataset: TrainingFeatureDataset | None = None,
    label_dataset: TrainingLabelDataset | None = None,
    labeled_dataset: LabeledTrainingDataset | None = None,
    pattern_dataset: PatternWindowDataset | None = None,
    split_plan: DatasetSplitPlan | None = None,
    version: str = "0.1.0",
    format: TrainingDatasetExportFormat | str = TrainingDatasetExportFormat.JSON,
    metadata: dict[str, Any] | None = None,
) -> TrainingDatasetManifest:
    """Build manifest from available dataset parts."""
    artifacts: list[TrainingDatasetArtifact] = []

    if feature_dataset is not None:
        artifacts.append(training_feature_dataset_to_artifact(feature_dataset, format=format))

    if label_dataset is not None:
        artifacts.append(training_label_dataset_to_artifact(label_dataset, format=format))

    if labeled_dataset is not None:
        artifacts.append(labeled_training_dataset_to_artifact(labeled_dataset, format=format))

    if pattern_dataset is not None:
        artifacts.append(pattern_window_dataset_to_artifact(pattern_dataset, format=format))

    if split_plan is not None:
        artifacts.append(split_plan_to_artifact(split_plan, format=format))

    health = infer_dataset_health_from_artifacts(
        dataset_id=dataset_id,
        artifacts=artifacts,
    )

    return build_training_dataset_manifest(
        manifest_id=f"{dataset_id}-manifest",
        dataset_id=dataset_id,
        symbol=symbol,
        version=version,
        artifacts=artifacts,
        health=health,
        metadata=metadata or {},
    )


def build_training_export_package(
    *,
    package_id: str,
    manifest: TrainingDatasetManifest,
    feature_dataset: TrainingFeatureDataset | None = None,
    label_dataset: TrainingLabelDataset | None = None,
    labeled_dataset: LabeledTrainingDataset | None = None,
    pattern_dataset: PatternWindowDataset | None = None,
    split_plan: DatasetSplitPlan | None = None,
    metadata: dict[str, Any] | None = None,
) -> TrainingDatasetExportPackage:
    """Build in-memory training export package."""
    payloads: dict[str, Any] = {}

    if feature_dataset is not None:
        payloads["features"] = feature_dataset.to_flat_rows()

    if label_dataset is not None:
        payloads["labels"] = label_dataset.to_flat_rows()

    if labeled_dataset is not None:
        payloads["labeled"] = labeled_dataset.to_flat_rows()

    if pattern_dataset is not None:
        payloads["pattern_windows"] = pattern_dataset.to_windows()

    if split_plan is not None:
        payloads["split_plan"] = split_plan.to_dict()

    return TrainingDatasetExportPackage(
        package_id=package_id,
        manifest=manifest,
        payloads=payloads,
        metadata=metadata or {},
    )


def serialize_training_rows_to_json(rows: list[dict[str, Any]]) -> str:
    """Serialize training rows to JSON."""
    if not isinstance(rows, list):
        raise ValueError("Rows must be a list.")

    for row in rows:
        validate_metadata(row, "Training row")

    return json.dumps(rows, indent=2, sort_keys=True)


def serialize_training_rows_to_jsonl(rows: list[dict[str, Any]]) -> str:
    """Serialize training rows to JSONL."""
    if not isinstance(rows, list):
        raise ValueError("Rows must be a list.")

    lines: list[str] = []

    for row in rows:
        validate_metadata(row, "Training row")
        lines.append(json.dumps(row, sort_keys=True))

    return "\n".join(lines)


def build_training_dataset_export_summary(
    manifest: TrainingDatasetManifest,
) -> dict[str, Any]:
    """Build export summary dictionary."""
    if not isinstance(manifest, TrainingDatasetManifest):
        raise ValueError("Manifest must be TrainingDatasetManifest.")

    artifact_types: dict[str, int] = {}

    for artifact in manifest.artifacts:
        artifact_type = normalize_training_dataset_artifact_type(
            artifact.artifact_type,
        ).value
        artifact_types[artifact_type] = artifact_types.get(artifact_type, 0) + 1

    return {
        "manifest_id": manifest.manifest_id,
        "dataset_id": manifest.dataset_id,
        "symbol": normalize_training_symbol(manifest.symbol),
        "version": manifest.version,
        "artifact_count": manifest.artifact_count,
        "total_row_count": manifest.total_row_count,
        "healthy": manifest.healthy,
        "artifact_types": artifact_types,
    }