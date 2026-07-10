from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import Enum
from pathlib import Path
from typing import Any

import pandas as pd


DATASET_METADATA_VERSION = "1.0"


class DatasetArtifactType(str, Enum):
    RAW_OHLCV = "raw_ohlcv"
    LABELED_DATASET = "labeled_dataset"
    FEATURE_DATASET = "feature_dataset"
    TRAINING_DATASET = "training_dataset"
    PREDICTION_DATASET = "prediction_dataset"


@dataclass(frozen=True)
class DatasetFingerprint:
    rows: int
    columns: tuple[str, ...]
    dtypes: dict[str, str]
    content_sha256: str
    schema_sha256: str
    source_file_sha256: str | None = None

    @property
    def columns_count(self) -> int:
        return len(self.columns)

    @property
    def short_hash(self) -> str:
        return self.content_sha256[:12]

    def to_dict(self) -> dict[str, Any]:
        return {
            "rows": self.rows,
            "columns_count": self.columns_count,
            "columns": list(self.columns),
            "dtypes": self.dtypes,
            "content_sha256": self.content_sha256,
            "schema_sha256": self.schema_sha256,
            "source_file_sha256": self.source_file_sha256,
            "short_hash": self.short_hash,
        }


@dataclass(frozen=True)
class DatasetVersionMetadata:
    dataset_name: str
    dataset_version: str
    artifact_type: DatasetArtifactType
    dataset_path: str
    created_at_utc: str
    fingerprint: DatasetFingerprint
    metadata_version: str = DATASET_METADATA_VERSION
    parent_dataset_version: str | None = None
    quality_report_path: str | None = None
    description: str | None = None
    tags: tuple[str, ...] = ()
    parameters: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.dataset_name.strip():
            raise ValueError("dataset_name cannot be empty.")

        if not self.dataset_version.strip():
            raise ValueError("dataset_version cannot be empty.")

        if not self.dataset_path.strip():
            raise ValueError("dataset_path cannot be empty.")

    @property
    def dataset_id(self) -> str:
        safe_name = self.dataset_name.strip().lower().replace(" ", "_")
        return f"{safe_name}_{self.fingerprint.short_hash}"

    def to_dict(self) -> dict[str, Any]:
        return {
            "metadata_version": self.metadata_version,
            "dataset_id": self.dataset_id,
            "dataset_name": self.dataset_name,
            "dataset_version": self.dataset_version,
            "artifact_type": self.artifact_type.value,
            "dataset_path": self.dataset_path,
            "created_at_utc": self.created_at_utc,
            "parent_dataset_version": self.parent_dataset_version,
            "quality_report_path": self.quality_report_path,
            "description": self.description,
            "tags": list(self.tags),
            "parameters": self.parameters,
            "fingerprint": self.fingerprint.to_dict(),
        }


def utc_now_iso() -> str:
    return datetime.now(tz=UTC).replace(microsecond=0).isoformat()


def sha256_bytes(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def sha256_text(payload: str) -> str:
    return sha256_bytes(payload.encode("utf-8"))


def compute_file_sha256(path: str | Path) -> str:
    file_path = Path(path)

    if not file_path.exists():
        raise FileNotFoundError(f"File does not exist: {file_path}")

    if not file_path.is_file():
        raise ValueError(f"Path is not a file: {file_path}")

    digest = hashlib.sha256()

    with file_path.open("rb") as file:
        for chunk in iter(lambda: file.read(1024 * 1024), b""):
            digest.update(chunk)

    return digest.hexdigest()


def dataframe_to_canonical_csv_bytes(dataframe: pd.DataFrame) -> bytes:
    canonical = dataframe.copy()
    canonical.columns = [str(column) for column in canonical.columns]

    return canonical.to_csv(
        index=False,
        lineterminator="\n",
        float_format="%.12g",
    ).encode("utf-8")


def build_schema_payload(dataframe: pd.DataFrame) -> dict[str, Any]:
    return {
        "columns": [str(column) for column in dataframe.columns],
        "dtypes": {
            str(column): str(dtype)
            for column, dtype in dataframe.dtypes.items()
        },
    }


def build_schema_sha256(dataframe: pd.DataFrame) -> str:
    payload = json.dumps(
        build_schema_payload(dataframe),
        sort_keys=True,
        separators=(",", ":"),
    )
    return sha256_text(payload)


def build_dataframe_fingerprint(
    dataframe: pd.DataFrame,
    source_file_path: str | Path | None = None,
) -> DatasetFingerprint:
    if dataframe.empty:
        raise ValueError("Cannot fingerprint an empty dataset.")

    source_file_sha256 = (
        compute_file_sha256(source_file_path)
        if source_file_path is not None
        else None
    )

    return DatasetFingerprint(
        rows=len(dataframe),
        columns=tuple(str(column) for column in dataframe.columns),
        dtypes={
            str(column): str(dtype)
            for column, dtype in dataframe.dtypes.items()
        },
        content_sha256=sha256_bytes(dataframe_to_canonical_csv_bytes(dataframe)),
        schema_sha256=build_schema_sha256(dataframe),
        source_file_sha256=source_file_sha256,
    )


def build_dataset_version_string(
    fingerprint: DatasetFingerprint,
    created_at_utc: str,
) -> str:
    safe_timestamp = (
        created_at_utc.replace("-", "")
        .replace(":", "")
        .replace("+", "Z")
        .replace("T", "_")
    )

    return f"v{safe_timestamp}_{fingerprint.short_hash}"


def build_dataset_version_metadata(
    dataframe: pd.DataFrame,
    dataset_name: str,
    dataset_path: str | Path,
    artifact_type: DatasetArtifactType = DatasetArtifactType.TRAINING_DATASET,
    source_file_path: str | Path | None = None,
    created_at_utc: str | None = None,
    dataset_version: str | None = None,
    parent_dataset_version: str | None = None,
    quality_report_path: str | Path | None = None,
    description: str | None = None,
    tags: tuple[str, ...] = (),
    parameters: dict[str, Any] | None = None,
) -> DatasetVersionMetadata:
    created_at = created_at_utc or utc_now_iso()
    fingerprint = build_dataframe_fingerprint(
        dataframe,
        source_file_path=source_file_path,
    )

    resolved_version = dataset_version or build_dataset_version_string(
        fingerprint,
        created_at,
    )

    return DatasetVersionMetadata(
        dataset_name=dataset_name,
        dataset_version=resolved_version,
        artifact_type=artifact_type,
        dataset_path=Path(dataset_path).as_posix(),
        created_at_utc=created_at,
        fingerprint=fingerprint,
        parent_dataset_version=parent_dataset_version,
        quality_report_path=(
            Path(quality_report_path).as_posix()
            if quality_report_path is not None
            else None
        ),
        description=description,
        tags=tags,
        parameters=parameters or {},
    )


def write_dataset_version_metadata(
    path: str | Path,
    metadata: DatasetVersionMetadata,
) -> Path:
    output_path = Path(path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    output_path.write_text(
        json.dumps(metadata.to_dict(), indent=2, sort_keys=True),
        encoding="utf-8",
    )

    return output_path


def read_dataset_version_metadata(path: str | Path) -> dict[str, Any]:
    metadata_path = Path(path)

    if not metadata_path.exists():
        raise FileNotFoundError(f"Dataset metadata file does not exist: {metadata_path}")

    return json.loads(metadata_path.read_text(encoding="utf-8"))


__all__ = [
    "DATASET_METADATA_VERSION",
    "DatasetArtifactType",
    "DatasetFingerprint",
    "DatasetVersionMetadata",
    "build_dataframe_fingerprint",
    "build_dataset_version_metadata",
    "build_dataset_version_string",
    "build_schema_payload",
    "build_schema_sha256",
    "compute_file_sha256",
    "dataframe_to_canonical_csv_bytes",
    "read_dataset_version_metadata",
    "sha256_bytes",
    "sha256_text",
    "utc_now_iso",
    "write_dataset_version_metadata",
]