"""
Unit tests for AQOS training dataset export and manifest utilities.
"""

import json

import pytest

from aqos.training_data import (
    TrainingDatasetArtifact,
    TrainingDatasetArtifactType,
    TrainingDatasetExportFormat,
    TrainingDatasetExportPackage,
    TrainingDatasetManifest,
    build_dataset_split_config,
    build_label_generation_config,
    build_labeled_training_dataset,
    build_pattern_window_config,
    build_pattern_windows_from_labeled_dataset,
    build_split_plan_from_pattern_windows,
    build_training_data_config,
    build_training_dataset_artifact,
    build_training_dataset_export_summary,
    build_training_dataset_manifest,
    build_training_export_manifest_from_parts,
    build_training_export_package,
    build_training_feature_dataset,
    build_training_feature_row,
    generate_label_dataset,
    infer_dataset_health_from_artifacts,
    labeled_training_dataset_to_artifact,
    normalize_training_dataset_artifact_type,
    normalize_training_dataset_export_format,
    pattern_window_dataset_to_artifact,
    serialize_training_rows_to_json,
    serialize_training_rows_to_jsonl,
    split_plan_to_artifact,
    training_feature_dataset_to_artifact,
    training_label_dataset_to_artifact,
    validate_training_dataset_artifacts,
)


def sample_feature_rows():
    rows = []

    for index in range(6):
        close = 100 + index
        rows.append(
            build_training_feature_row(
                timestamp=f"2020-01-01T{index:02d}:00:00+00:00",
                symbol="XAUUSD",
                features={
                    "open": close - 1,
                    "high": close + 1,
                    "low": close - 2,
                    "close": close,
                    "volume": 1000 + index,
                    "aligned_event_count": 1 if index == 1 else 0,
                    "aligned_high_impact_event_count": 1 if index == 1 else 0,
                },
            )
        )

    return rows


def sample_feature_dataset():
    return build_training_feature_dataset(
        config=build_training_data_config(
            dataset_id="xauusd-features",
            symbol="XAUUSD",
            asset_type="commodity",
            timeframe="1h",
        ),
        rows=sample_feature_rows(),
        source="test",
    )


def sample_label_dataset():
    return generate_label_dataset(
        sample_feature_dataset(),
        config=build_label_generation_config(
            horizon=1,
            volatility_window=1,
        ),
    )


def sample_labeled_dataset():
    return build_labeled_training_dataset(
        sample_feature_dataset(),
        config=build_label_generation_config(
            horizon=1,
            volatility_window=1,
        ),
    )


def sample_pattern_dataset():
    return build_pattern_windows_from_labeled_dataset(
        sample_labeled_dataset(),
        config=build_pattern_window_config(
            window_size=3,
            step_size=1,
        ),
    )


def sample_split_plan():
    return build_split_plan_from_pattern_windows(
        sample_pattern_dataset(),
        config=build_dataset_split_config(
            strategy="holdout",
            train_ratio=0.5,
            validation_ratio=0.25,
            test_ratio=0.25,
        ),
    )


def test_export_enums_and_normalizers():
    assert TrainingDatasetExportFormat.JSON.value == "json"
    assert TrainingDatasetExportFormat.JSONL.value == "jsonl"
    assert TrainingDatasetExportFormat.CSV.value == "csv"
    assert TrainingDatasetExportFormat.PARQUET.value == "parquet"
    assert TrainingDatasetExportFormat.MEMORY.value == "memory"

    assert TrainingDatasetArtifactType.FEATURES.value == "features"
    assert TrainingDatasetArtifactType.LABELS.value == "labels"
    assert TrainingDatasetArtifactType.LABELED.value == "labeled"
    assert TrainingDatasetArtifactType.PATTERN_WINDOWS.value == "pattern_windows"
    assert TrainingDatasetArtifactType.SPLIT_PLAN.value == "split_plan"
    assert TrainingDatasetArtifactType.MANIFEST.value == "manifest"

    assert normalize_training_dataset_export_format(" JSON ") == TrainingDatasetExportFormat.JSON
    assert normalize_training_dataset_artifact_type(" FEATURES ") == TrainingDatasetArtifactType.FEATURES

    with pytest.raises(ValueError):
        normalize_training_dataset_export_format("bad")

    with pytest.raises(ValueError):
        normalize_training_dataset_artifact_type("bad")


def test_training_dataset_artifact_to_dict():
    artifact = TrainingDatasetArtifact(
        artifact_id=" artifact ",
        artifact_type=" features ",
        format=" json ",
        path=" data/features.json ",
        row_count=10,
        column_count=5,
        checksum=" abc ",
        metadata={"source": "test"},
    )

    payload = artifact.to_dict()

    assert payload == {
        "artifact_id": "artifact",
        "artifact_type": "features",
        "format": "json",
        "path": "data/features.json",
        "row_count": 10,
        "column_count": 5,
        "checksum": "abc",
        "metadata": {"source": "test"},
    }


def test_training_dataset_artifact_builder_and_rejections():
    artifact = build_training_dataset_artifact(
        artifact_id="features",
        artifact_type="features",
        row_count=10,
        column_count=5,
    )

    assert isinstance(artifact, TrainingDatasetArtifact)

    with pytest.raises(ValueError):
        TrainingDatasetArtifact(artifact_id="", artifact_type="features")

    with pytest.raises(ValueError):
        TrainingDatasetArtifact(artifact_id="x", artifact_type="bad")

    with pytest.raises(ValueError):
        TrainingDatasetArtifact(artifact_id="x", artifact_type="features", format="bad")

    with pytest.raises(ValueError):
        TrainingDatasetArtifact(artifact_id="x", artifact_type="features", path=123)

    with pytest.raises(ValueError):
        TrainingDatasetArtifact(artifact_id="x", artifact_type="features", row_count=-1)

    with pytest.raises(ValueError):
        TrainingDatasetArtifact(artifact_id="x", artifact_type="features", column_count=-1)

    with pytest.raises(ValueError):
        TrainingDatasetArtifact(artifact_id="x", artifact_type="features", checksum=123)

    with pytest.raises(ValueError):
        TrainingDatasetArtifact(artifact_id="x", artifact_type="features", metadata=[])


def test_artifact_converters():
    feature_dataset = sample_feature_dataset()
    label_dataset = sample_label_dataset()
    labeled_dataset = sample_labeled_dataset()
    pattern_dataset = sample_pattern_dataset()
    split_plan = sample_split_plan()

    feature_artifact = training_feature_dataset_to_artifact(feature_dataset)
    label_artifact = training_label_dataset_to_artifact(label_dataset)
    labeled_artifact = labeled_training_dataset_to_artifact(labeled_dataset)
    pattern_artifact = pattern_window_dataset_to_artifact(pattern_dataset)
    split_artifact = split_plan_to_artifact(split_plan)

    assert feature_artifact.artifact_type == TrainingDatasetArtifactType.FEATURES
    assert feature_artifact.row_count == feature_dataset.row_count
    assert feature_artifact.column_count == feature_dataset.column_count

    assert label_artifact.artifact_type == TrainingDatasetArtifactType.LABELS
    assert label_artifact.row_count == label_dataset.row_count
    assert label_artifact.column_count == label_dataset.label_count

    assert labeled_artifact.artifact_type == TrainingDatasetArtifactType.LABELED
    assert labeled_artifact.row_count == labeled_dataset.row_count

    assert pattern_artifact.artifact_type == TrainingDatasetArtifactType.PATTERN_WINDOWS
    assert pattern_artifact.row_count == pattern_dataset.window_count

    assert split_artifact.artifact_type == TrainingDatasetArtifactType.SPLIT_PLAN
    assert split_artifact.row_count == split_plan.range_count

    with pytest.raises(ValueError):
        training_feature_dataset_to_artifact("bad")

    with pytest.raises(ValueError):
        training_label_dataset_to_artifact("bad")

    with pytest.raises(ValueError):
        labeled_training_dataset_to_artifact("bad")

    with pytest.raises(ValueError):
        pattern_window_dataset_to_artifact("bad")

    with pytest.raises(ValueError):
        split_plan_to_artifact("bad")


def test_infer_dataset_health_from_artifacts():
    artifacts = [
        build_training_dataset_artifact(
            artifact_id="features",
            artifact_type="features",
            row_count=10,
            column_count=5,
        ),
        build_training_dataset_artifact(
            artifact_id="labels",
            artifact_type="labels",
            row_count=10,
            column_count=3,
        ),
    ]

    health = infer_dataset_health_from_artifacts(
        dataset_id="dataset",
        artifacts=artifacts,
    )

    assert health.status.value == "ready"
    assert health.row_count == 20
    assert health.feature_count == 5
    assert health.label_count == 3

    empty_health = infer_dataset_health_from_artifacts(
        dataset_id="empty",
        artifacts=[],
    )

    assert empty_health.status.value == "empty"

    with pytest.raises(ValueError):
        infer_dataset_health_from_artifacts(dataset_id="", artifacts=[])

    with pytest.raises(ValueError):
        infer_dataset_health_from_artifacts(dataset_id="dataset", artifacts=["bad"])


def test_training_dataset_manifest_to_dict_and_json():
    artifacts = [
        build_training_dataset_artifact(
            artifact_id="features",
            artifact_type="features",
            row_count=10,
            column_count=5,
        )
    ]
    health = infer_dataset_health_from_artifacts(
        dataset_id="dataset",
        artifacts=artifacts,
    )
    manifest = TrainingDatasetManifest(
        manifest_id=" manifest ",
        dataset_id=" dataset ",
        symbol=" xauusd ",
        version=" 1.0.0 ",
        created_at="2026-01-01T00:00:00+00:00",
        artifacts=artifacts,
        health=health,
        metadata={"source": "test"},
    )

    payload = manifest.to_dict()
    parsed = json.loads(manifest.to_json())

    assert manifest.artifact_count == 1
    assert manifest.total_row_count == 10
    assert manifest.healthy is True
    assert payload["manifest_id"] == "manifest"
    assert payload["dataset_id"] == "dataset"
    assert payload["symbol"] == "XAUUSD"
    assert payload["version"] == "1.0.0"
    assert parsed["artifact_count"] == 1


def test_training_dataset_manifest_builder_and_rejections():
    manifest = build_training_dataset_manifest(
        manifest_id="manifest",
        dataset_id="dataset",
        symbol="XAUUSD",
        created_at="2026-01-01T00:00:00+00:00",
    )

    assert isinstance(manifest, TrainingDatasetManifest)

    with pytest.raises(ValueError):
        TrainingDatasetManifest(manifest_id="", dataset_id="dataset", symbol="XAUUSD")

    with pytest.raises(ValueError):
        TrainingDatasetManifest(manifest_id="manifest", dataset_id="", symbol="XAUUSD")

    with pytest.raises(ValueError):
        TrainingDatasetManifest(manifest_id="manifest", dataset_id="dataset", symbol="bad symbol")

    with pytest.raises(ValueError):
        TrainingDatasetManifest(manifest_id="manifest", dataset_id="dataset", symbol="XAUUSD", version="")

    with pytest.raises(ValueError):
        TrainingDatasetManifest(manifest_id="manifest", dataset_id="dataset", symbol="XAUUSD", created_at="")

    with pytest.raises(ValueError):
        TrainingDatasetManifest(manifest_id="manifest", dataset_id="dataset", symbol="XAUUSD", artifacts=["bad"])

    with pytest.raises(ValueError):
        TrainingDatasetManifest(manifest_id="manifest", dataset_id="dataset", symbol="XAUUSD", health="bad")

    with pytest.raises(ValueError):
        TrainingDatasetManifest(manifest_id="manifest", dataset_id="dataset", symbol="XAUUSD", metadata=[])

    assert validate_training_dataset_artifacts([]) == []


def test_build_training_export_manifest_from_parts():
    feature_dataset = sample_feature_dataset()
    label_dataset = sample_label_dataset()
    labeled_dataset = sample_labeled_dataset()
    pattern_dataset = sample_pattern_dataset()
    split_plan = sample_split_plan()

    manifest = build_training_export_manifest_from_parts(
        dataset_id="xauusd-training",
        symbol="XAUUSD",
        feature_dataset=feature_dataset,
        label_dataset=label_dataset,
        labeled_dataset=labeled_dataset,
        pattern_dataset=pattern_dataset,
        split_plan=split_plan,
        version="1.0.0",
    )

    assert isinstance(manifest, TrainingDatasetManifest)
    assert manifest.dataset_id == "xauusd-training"
    assert manifest.symbol == "XAUUSD"
    assert manifest.version == "1.0.0"
    assert manifest.artifact_count == 5
    assert manifest.healthy is True
    assert manifest.health.row_count > 0


def test_training_dataset_export_package_to_dict_and_json():
    feature_dataset = sample_feature_dataset()
    label_dataset = sample_label_dataset()
    labeled_dataset = sample_labeled_dataset()
    pattern_dataset = sample_pattern_dataset()
    split_plan = sample_split_plan()

    manifest = build_training_export_manifest_from_parts(
        dataset_id="xauusd-training",
        symbol="XAUUSD",
        feature_dataset=feature_dataset,
        label_dataset=label_dataset,
        labeled_dataset=labeled_dataset,
        pattern_dataset=pattern_dataset,
        split_plan=split_plan,
    )
    package = build_training_export_package(
        package_id="xauusd-package",
        manifest=manifest,
        feature_dataset=feature_dataset,
        label_dataset=label_dataset,
        labeled_dataset=labeled_dataset,
        pattern_dataset=pattern_dataset,
        split_plan=split_plan,
        metadata={"source": "test"},
    )

    payload = package.to_dict()
    parsed = json.loads(package.to_json())

    assert isinstance(package, TrainingDatasetExportPackage)
    assert package.package_id == "xauusd-package"
    assert package.artifact_count == 5
    assert package.payload_count == 5
    assert "features" in package.payloads
    assert "labels" in package.payloads
    assert "labeled" in package.payloads
    assert "pattern_windows" in package.payloads
    assert "split_plan" in package.payloads
    assert payload["package_id"] == "xauusd-package"
    assert parsed["payload_count"] == 5


def test_training_dataset_export_package_rejections():
    manifest = build_training_dataset_manifest(
        manifest_id="manifest",
        dataset_id="dataset",
        symbol="XAUUSD",
    )

    with pytest.raises(ValueError):
        TrainingDatasetExportPackage(package_id="", manifest=manifest)

    with pytest.raises(ValueError):
        TrainingDatasetExportPackage(package_id="package", manifest="bad")

    with pytest.raises(ValueError):
        TrainingDatasetExportPackage(package_id="package", manifest=manifest, payloads=[])

    with pytest.raises(ValueError):
        TrainingDatasetExportPackage(package_id="package", manifest=manifest, metadata=[])


def test_serializers():
    rows = [
        {"timestamp": "2020-01-01", "close": 100},
        {"timestamp": "2020-01-02", "close": 101},
    ]

    json_payload = serialize_training_rows_to_json(rows)
    jsonl_payload = serialize_training_rows_to_jsonl(rows)

    assert json.loads(json_payload)[0]["close"] == 100
    assert jsonl_payload.splitlines()[0] == '{"close": 100, "timestamp": "2020-01-01"}'
    assert len(jsonl_payload.splitlines()) == 2

    with pytest.raises(ValueError):
        serialize_training_rows_to_json("bad")

    with pytest.raises(ValueError):
        serialize_training_rows_to_json(["bad"])

    with pytest.raises(ValueError):
        serialize_training_rows_to_jsonl("bad")

    with pytest.raises(ValueError):
        serialize_training_rows_to_jsonl(["bad"])


def test_build_training_dataset_export_summary():
    manifest = build_training_export_manifest_from_parts(
        dataset_id="xauusd-training",
        symbol="XAUUSD",
        feature_dataset=sample_feature_dataset(),
        label_dataset=sample_label_dataset(),
        labeled_dataset=sample_labeled_dataset(),
        pattern_dataset=sample_pattern_dataset(),
        split_plan=sample_split_plan(),
    )

    summary = build_training_dataset_export_summary(manifest)

    assert summary["manifest_id"] == "xauusd-training-manifest"
    assert summary["dataset_id"] == "xauusd-training"
    assert summary["symbol"] == "XAUUSD"
    assert summary["artifact_count"] == 5
    assert summary["healthy"] is True
    assert summary["artifact_types"]["features"] == 1
    assert summary["artifact_types"]["labels"] == 1

    with pytest.raises(ValueError):
        build_training_dataset_export_summary("bad")


def test_training_data_export_exports_exist():
    import aqos.training_data as training_data

    expected_exports = [
        "TrainingDatasetArtifact",
        "TrainingDatasetArtifactType",
        "TrainingDatasetExportFormat",
        "TrainingDatasetExportPackage",
        "TrainingDatasetManifest",
        "build_training_dataset_artifact",
        "build_training_dataset_export_summary",
        "build_training_dataset_manifest",
        "build_training_export_manifest_from_parts",
        "build_training_export_package",
        "infer_dataset_health_from_artifacts",
        "labeled_training_dataset_to_artifact",
        "normalize_training_dataset_artifact_type",
        "normalize_training_dataset_export_format",
        "pattern_window_dataset_to_artifact",
        "serialize_training_rows_to_json",
        "serialize_training_rows_to_jsonl",
        "split_plan_to_artifact",
        "training_feature_dataset_to_artifact",
        "training_label_dataset_to_artifact",
        "validate_training_dataset_artifacts",
    ]

    for export_name in expected_exports:
        assert hasattr(training_data, export_name), export_name