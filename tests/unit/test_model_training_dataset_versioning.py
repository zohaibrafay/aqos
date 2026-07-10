from __future__ import annotations

import json

import pandas as pd
import pytest

from aqos.model_training import (
    DATASET_METADATA_VERSION,
    DatasetArtifactType,
    build_dataframe_fingerprint,
    build_dataset_version_metadata,
    build_dataset_version_string,
    build_schema_payload,
    build_schema_sha256,
    compute_file_sha256,
    read_dataset_version_metadata,
    sha256_text,
    write_dataset_version_metadata,
)


def build_dataset() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "open": [1.0, 2.0, 3.0],
            "high": [1.5, 2.5, 3.5],
            "low": [0.5, 1.5, 2.5],
            "close": [1.1, 2.1, 3.1],
            "volume": [100, 200, 300],
            "target": ["buy", "sell", "hold"],
        }
    )


def test_sha256_text_is_stable() -> None:
    assert sha256_text("aqos") == sha256_text("aqos")
    assert sha256_text("aqos") != sha256_text("AQOS")


def test_compute_file_sha256_hashes_file_content(tmp_path) -> None:
    path = tmp_path / "dataset.csv"
    payload = b"a,b\n1,2\n"
    path.write_bytes(payload)

    assert compute_file_sha256(path) == sha256_text(payload.decode("utf-8"))


def test_compute_file_sha256_rejects_missing_file(tmp_path) -> None:
    with pytest.raises(FileNotFoundError):
        compute_file_sha256(tmp_path / "missing.csv")


def test_build_schema_payload_contains_columns_and_dtypes() -> None:
    payload = build_schema_payload(build_dataset())

    assert payload["columns"] == ["open", "high", "low", "close", "volume", "target"]
    assert payload["dtypes"]["target"] in {"object", "str", "string"}


def test_build_schema_sha256_changes_when_schema_changes() -> None:
    dataset = build_dataset()
    changed_dataset = dataset.rename(columns={"close": "close_price"})

    assert build_schema_sha256(dataset) != build_schema_sha256(changed_dataset)


def test_build_dataframe_fingerprint_is_stable_for_same_dataframe() -> None:
    dataset = build_dataset()

    first = build_dataframe_fingerprint(dataset)
    second = build_dataframe_fingerprint(dataset.copy())

    assert first.content_sha256 == second.content_sha256
    assert first.schema_sha256 == second.schema_sha256
    assert first.rows == 3
    assert first.columns_count == 6
    assert first.short_hash == first.content_sha256[:12]


def test_build_dataframe_fingerprint_changes_when_content_changes() -> None:
    dataset = build_dataset()
    changed_dataset = dataset.copy()
    changed_dataset.loc[0, "close"] = 999.0

    assert (
        build_dataframe_fingerprint(dataset).content_sha256
        != build_dataframe_fingerprint(changed_dataset).content_sha256
    )


def test_build_dataframe_fingerprint_rejects_empty_dataset() -> None:
    with pytest.raises(ValueError, match="empty dataset"):
        build_dataframe_fingerprint(pd.DataFrame())


def test_build_dataset_version_string_contains_hash() -> None:
    fingerprint = build_dataframe_fingerprint(build_dataset())

    version = build_dataset_version_string(
        fingerprint,
        created_at_utc="2026-01-01T00:00:00+00:00",
    )

    assert version.startswith("v20260101_000000Z0000_")
    assert version.endswith(fingerprint.short_hash)


def test_build_dataset_version_metadata_creates_traceable_payload(tmp_path) -> None:
    dataset = build_dataset()
    dataset_path = tmp_path / "training.csv"
    quality_path = tmp_path / "quality.json"

    dataset.to_csv(dataset_path, index=False)
    quality_path.write_text("{}", encoding="utf-8")

    metadata = build_dataset_version_metadata(
        dataframe=dataset,
        dataset_name="signal_training_dataset",
        dataset_path=dataset_path,
        artifact_type=DatasetArtifactType.TRAINING_DATASET,
        source_file_path=dataset_path,
        created_at_utc="2026-01-01T00:00:00+00:00",
        parent_dataset_version="raw_v1",
        quality_report_path=quality_path,
        description="Sprint 030 test dataset",
        tags=("sprint-030", "unit-test"),
        parameters={"horizon_bars": 5},
    )

    payload = metadata.to_dict()

    assert payload["metadata_version"] == DATASET_METADATA_VERSION
    assert payload["dataset_id"].startswith("signal_training_dataset_")
    assert payload["dataset_name"] == "signal_training_dataset"
    assert payload["artifact_type"] == "training_dataset"
    assert payload["parent_dataset_version"] == "raw_v1"
    assert payload["quality_report_path"].endswith("quality.json")
    assert payload["tags"] == ["sprint-030", "unit-test"]
    assert payload["parameters"]["horizon_bars"] == 5
    assert payload["fingerprint"]["source_file_sha256"] == compute_file_sha256(dataset_path)


def test_write_and_read_dataset_version_metadata_roundtrip(tmp_path) -> None:
    metadata = build_dataset_version_metadata(
        dataframe=build_dataset(),
        dataset_name="signal_training_dataset",
        dataset_path=tmp_path / "training.csv",
        created_at_utc="2026-01-01T00:00:00+00:00",
    )

    output_path = tmp_path / "metadata" / "dataset_version.json"
    written_path = write_dataset_version_metadata(output_path, metadata)
    payload = read_dataset_version_metadata(written_path)

    assert written_path == output_path
    assert payload["dataset_name"] == "signal_training_dataset"
    assert payload["dataset_version"] == metadata.dataset_version
    assert payload["fingerprint"]["content_sha256"] == metadata.fingerprint.content_sha256


def test_read_dataset_version_metadata_rejects_missing_file(tmp_path) -> None:
    with pytest.raises(FileNotFoundError):
        read_dataset_version_metadata(tmp_path / "missing.json")


def test_dataset_version_metadata_json_is_serializable(tmp_path) -> None:
    metadata = build_dataset_version_metadata(
        dataframe=build_dataset(),
        dataset_name="signal_training_dataset",
        dataset_path=tmp_path / "training.csv",
        created_at_utc="2026-01-01T00:00:00+00:00",
    )

    payload = json.dumps(metadata.to_dict(), sort_keys=True)

    assert "signal_training_dataset" in payload