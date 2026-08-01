from __future__ import annotations

import json

import pytest

from aqos.backtesting.artifacts import (
    BACKTEST_ARTIFACTS_VERSION,
    BacktestArtifact,
    BacktestArtifactKind,
    BacktestArtifactManifest,
    build_backtest_artifact,
    build_backtest_artifact_manifest,
    build_backtest_run_id,
    compute_backtest_file_sha256,
    normalize_backtest_run_slug,
    parse_backtest_artifact,
    read_backtest_artifact_manifest,
    verify_backtest_artifact_manifest,
    write_backtest_artifact_manifest,
)


def write_file(path, content: str = "payload"):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    return path


def test_artifacts_version_is_exposed() -> None:
    assert BACKTEST_ARTIFACTS_VERSION == "1.0"


def test_compute_file_sha256_is_stable(tmp_path) -> None:
    first = write_file(tmp_path / "a.txt", "same content")
    second = write_file(tmp_path / "b.txt", "same content")

    assert compute_backtest_file_sha256(first) == compute_backtest_file_sha256(second)


def test_normalize_run_slug() -> None:
    assert normalize_backtest_run_slug("Close Momentum!") == "close_momentum"
    assert normalize_backtest_run_slug("  --  ") == "backtest"
    assert normalize_backtest_run_slug("XAU/USD") == "xau_usd"


def test_build_run_id_includes_all_parts() -> None:
    run_id = build_backtest_run_id(
        strategy_name="Close Momentum",
        symbol="XAUUSD",
        timeframe="H1",
        created_at_utc="2026-01-01T00:00:00+00:00",
    )

    assert run_id == "close_momentum_xauusd_h1_20260101t000000z"


def test_build_run_id_without_optional_parts() -> None:
    run_id = build_backtest_run_id(
        strategy_name="model_strategy",
        created_at_utc="2026-01-01T00:00:00+00:00",
    )

    assert run_id == "model_strategy_20260101t000000z"


def test_build_artifact_for_existing_file(tmp_path) -> None:
    path = write_file(tmp_path / "report.json", "{}")

    artifact = build_backtest_artifact(BacktestArtifactKind.REPORT, path)

    assert artifact.kind == BacktestArtifactKind.REPORT
    assert artifact.exists is True
    assert artifact.sha256 == compute_backtest_file_sha256(path)
    assert artifact.size_bytes == 2


def test_build_artifact_for_missing_file(tmp_path) -> None:
    artifact = build_backtest_artifact(
        BacktestArtifactKind.TRADES,
        tmp_path / "missing.csv",
    )

    assert artifact.exists is False
    assert artifact.sha256 is None
    assert artifact.size_bytes is None


def test_artifact_validation() -> None:
    with pytest.raises(ValueError, match="artifact path cannot be empty"):
        BacktestArtifact(kind=BacktestArtifactKind.REPORT, path="  ", exists=False)

    with pytest.raises(ValueError, match="size_bytes cannot be negative"):
        BacktestArtifact(
            kind=BacktestArtifactKind.REPORT,
            path="report.json",
            exists=True,
            size_bytes=-1,
        )


def test_manifest_validation() -> None:
    with pytest.raises(ValueError, match="run_id cannot be empty"):
        BacktestArtifactManifest(run_id=" ", created_at_utc="2026-01-01T00:00:00")

    with pytest.raises(ValueError, match="created_at_utc cannot be empty"):
        BacktestArtifactManifest(run_id="run", created_at_utc="")


def test_build_manifest_sorts_artifacts_by_kind(tmp_path) -> None:
    report_path = write_file(tmp_path / "report.json", "{}")
    trades_path = write_file(tmp_path / "trades.csv", "trade_id\n")

    manifest = build_backtest_artifact_manifest(
        run_id="run_1",
        artifact_paths={
            BacktestArtifactKind.TRADES: trades_path,
            BacktestArtifactKind.REPORT: report_path,
        },
        created_at_utc="2026-01-01T00:00:00+00:00",
        metadata={"strategy_name": "unit_test"},
    )

    assert [artifact.kind.value for artifact in manifest.artifacts] == [
        "report",
        "trades",
    ]
    assert manifest.artifact_count == 2
    assert manifest.missing_artifacts == ()
    assert manifest.metadata == {"strategy_name": "unit_test"}


def test_manifest_artifact_lookup(tmp_path) -> None:
    manifest = build_backtest_artifact_manifest(
        run_id="run_1",
        artifact_paths={
            BacktestArtifactKind.REPORT: write_file(tmp_path / "report.json", "{}"),
        },
    )

    assert manifest.artifact_for(BacktestArtifactKind.REPORT) is not None
    assert manifest.artifact_for(BacktestArtifactKind.PREDICTIONS) is None


def test_manifest_tracks_missing_artifacts(tmp_path) -> None:
    manifest = build_backtest_artifact_manifest(
        run_id="run_1",
        artifact_paths={
            BacktestArtifactKind.REPORT: write_file(tmp_path / "report.json", "{}"),
            BacktestArtifactKind.PREDICTIONS: tmp_path / "missing.csv",
        },
    )

    assert len(manifest.missing_artifacts) == 1
    assert manifest.to_dict()["missing_artifact_count"] == 1


def test_manifest_round_trip(tmp_path) -> None:
    manifest = build_backtest_artifact_manifest(
        run_id="run_1",
        artifact_paths={
            BacktestArtifactKind.REPORT: write_file(tmp_path / "report.json", "{}"),
            BacktestArtifactKind.TRADES: write_file(tmp_path / "trades.csv", "id\n"),
        },
        created_at_utc="2026-01-01T00:00:00+00:00",
    )

    path = write_backtest_artifact_manifest(tmp_path / "manifest.json", manifest)
    loaded = read_backtest_artifact_manifest(path)

    assert loaded.run_id == "run_1"
    assert loaded.created_at_utc == "2026-01-01T00:00:00+00:00"
    assert loaded.artifact_count == 2
    assert loaded.to_dict() == manifest.to_dict()


def test_read_manifest_rejects_missing_file(tmp_path) -> None:
    with pytest.raises(FileNotFoundError, match="does not exist"):
        read_backtest_artifact_manifest(tmp_path / "missing_manifest.json")


def test_parse_artifact_payload() -> None:
    artifact = parse_backtest_artifact(
        {
            "kind": "predictions",
            "path": "tmp/predictions.csv",
            "exists": True,
            "sha256": "abc",
            "size_bytes": 12,
        }
    )

    assert artifact.kind == BacktestArtifactKind.PREDICTIONS
    assert artifact.size_bytes == 12


def test_verify_manifest_detects_no_issues(tmp_path) -> None:
    manifest = build_backtest_artifact_manifest(
        run_id="run_1",
        artifact_paths={
            BacktestArtifactKind.REPORT: write_file(tmp_path / "report.json", "{}"),
        },
    )

    assert verify_backtest_artifact_manifest(manifest) == ()


def test_verify_manifest_detects_missing_file(tmp_path) -> None:
    report_path = write_file(tmp_path / "report.json", "{}")

    manifest = build_backtest_artifact_manifest(
        run_id="run_1",
        artifact_paths={BacktestArtifactKind.REPORT: report_path},
    )

    report_path.unlink()

    issues = verify_backtest_artifact_manifest(manifest)

    assert len(issues) == 1
    assert "Missing backtest artifact" in issues[0]


def test_verify_manifest_detects_changed_file(tmp_path) -> None:
    report_path = write_file(tmp_path / "report.json", "{}")

    manifest = build_backtest_artifact_manifest(
        run_id="run_1",
        artifact_paths={BacktestArtifactKind.REPORT: report_path},
    )

    report_path.write_text('{"changed": true}', encoding="utf-8")

    issues = verify_backtest_artifact_manifest(manifest)

    assert len(issues) == 1
    assert "checksum changed" in issues[0]


def test_manifest_json_is_deterministic(tmp_path) -> None:
    manifest = build_backtest_artifact_manifest(
        run_id="run_1",
        artifact_paths={
            BacktestArtifactKind.REPORT: write_file(tmp_path / "report.json", "{}"),
        },
        created_at_utc="2026-01-01T00:00:00+00:00",
    )

    first = write_backtest_artifact_manifest(tmp_path / "m1.json", manifest)
    second = write_backtest_artifact_manifest(tmp_path / "m2.json", manifest)

    assert first.read_text(encoding="utf-8") == second.read_text(encoding="utf-8")
    assert json.loads(first.read_text(encoding="utf-8"))["run_id"] == "run_1"
