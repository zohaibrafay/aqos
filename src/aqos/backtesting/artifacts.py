from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass, field as dataclass_field
from enum import Enum
from pathlib import Path
from typing import Any

from aqos.backtesting.contracts import backtesting_utc_now_iso


BACKTEST_ARTIFACTS_VERSION = "1.0"


class BacktestArtifactKind(str, Enum):
    REPORT = "report"
    ANALYTICS = "analytics"
    TRADES = "trades"
    ORDERS = "orders"
    EQUITY_CURVE = "equity_curve"
    SIGNALS = "signals"
    ADAPTER_RESULTS = "adapter_results"
    PREDICTIONS = "predictions"
    COMPARISON = "comparison"
    MANIFEST = "manifest"


@dataclass(frozen=True)
class BacktestArtifact:
    kind: BacktestArtifactKind
    path: str
    exists: bool
    sha256: str | None = None
    size_bytes: int | None = None

    def __post_init__(self) -> None:
        if not self.path.strip():
            raise ValueError("artifact path cannot be empty.")

        if self.size_bytes is not None and self.size_bytes < 0:
            raise ValueError("artifact size_bytes cannot be negative.")

    def to_dict(self) -> dict[str, Any]:
        return {
            "kind": self.kind.value,
            "path": self.path,
            "exists": self.exists,
            "sha256": self.sha256,
            "size_bytes": self.size_bytes,
        }


@dataclass(frozen=True)
class BacktestArtifactManifest:
    run_id: str
    created_at_utc: str
    artifacts: tuple[BacktestArtifact, ...] = ()
    manifest_version: str = BACKTEST_ARTIFACTS_VERSION
    metadata: dict[str, Any] = dataclass_field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.run_id.strip():
            raise ValueError("run_id cannot be empty.")

        if not self.created_at_utc.strip():
            raise ValueError("created_at_utc cannot be empty.")

    @property
    def artifact_count(self) -> int:
        return len(self.artifacts)

    @property
    def missing_artifacts(self) -> tuple[BacktestArtifact, ...]:
        return tuple(artifact for artifact in self.artifacts if not artifact.exists)

    def artifact_for(self, kind: BacktestArtifactKind) -> BacktestArtifact | None:
        for artifact in self.artifacts:
            if artifact.kind == kind:
                return artifact

        return None

    def to_dict(self) -> dict[str, Any]:
        return {
            "manifest_version": self.manifest_version,
            "run_id": self.run_id,
            "created_at_utc": self.created_at_utc,
            "artifact_count": self.artifact_count,
            "missing_artifact_count": len(self.missing_artifacts),
            "artifacts": [artifact.to_dict() for artifact in self.artifacts],
            "metadata": self.metadata,
        }


def compute_backtest_file_sha256(path: str | Path) -> str:
    digest = hashlib.sha256()

    with Path(path).open("rb") as handle:
        for chunk in iter(lambda: handle.read(65536), b""):
            digest.update(chunk)

    return digest.hexdigest()


def normalize_backtest_run_slug(value: str) -> str:
    normalized = re.sub(r"[^a-zA-Z0-9]+", "_", value.strip().lower())
    normalized = re.sub(r"_+", "_", normalized).strip("_")

    return normalized or "backtest"


def build_backtest_run_id(
    strategy_name: str,
    symbol: str | None = None,
    timeframe: str | None = None,
    created_at_utc: str | None = None,
) -> str:
    created_at = created_at_utc or backtesting_utc_now_iso()

    parts = [normalize_backtest_run_slug(strategy_name)]

    if symbol:
        parts.append(normalize_backtest_run_slug(symbol))

    if timeframe:
        parts.append(normalize_backtest_run_slug(timeframe))

    timestamp = (
        created_at.replace("-", "")
        .replace(":", "")
        .replace("+0000", "Z")
        .replace("+00:00", "Z")
    )
    parts.append(normalize_backtest_run_slug(timestamp))

    return "_".join(parts)


def build_backtest_artifact(
    kind: BacktestArtifactKind,
    path: str | Path,
) -> BacktestArtifact:
    artifact_path = Path(path)
    exists = artifact_path.is_file()

    return BacktestArtifact(
        kind=kind,
        path=artifact_path.as_posix(),
        exists=exists,
        sha256=compute_backtest_file_sha256(artifact_path) if exists else None,
        size_bytes=artifact_path.stat().st_size if exists else None,
    )


def build_backtest_artifact_manifest(
    run_id: str,
    artifact_paths: dict[BacktestArtifactKind, str | Path],
    created_at_utc: str | None = None,
    metadata: dict[str, Any] | None = None,
) -> BacktestArtifactManifest:
    artifacts = tuple(
        build_backtest_artifact(kind, artifact_paths[kind])
        for kind in sorted(artifact_paths, key=lambda item: item.value)
    )

    return BacktestArtifactManifest(
        run_id=run_id,
        created_at_utc=created_at_utc or backtesting_utc_now_iso(),
        artifacts=artifacts,
        metadata=metadata or {},
    )


def write_backtest_artifact_manifest(
    path: str | Path,
    manifest: BacktestArtifactManifest,
) -> Path:
    output_path = Path(path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(manifest.to_dict(), indent=2, sort_keys=True),
        encoding="utf-8",
    )

    return output_path


def parse_backtest_artifact(payload: dict[str, Any]) -> BacktestArtifact:
    size_bytes = payload.get("size_bytes")

    return BacktestArtifact(
        kind=BacktestArtifactKind(str(payload["kind"])),
        path=str(payload["path"]),
        exists=bool(payload.get("exists", False)),
        sha256=payload.get("sha256"),
        size_bytes=int(size_bytes) if size_bytes is not None else None,
    )


def read_backtest_artifact_manifest(path: str | Path) -> BacktestArtifactManifest:
    manifest_path = Path(path)

    if not manifest_path.exists():
        raise FileNotFoundError(
            f"Backtest artifact manifest does not exist: {manifest_path}"
        )

    payload = json.loads(manifest_path.read_text(encoding="utf-8"))

    return BacktestArtifactManifest(
        run_id=str(payload["run_id"]),
        created_at_utc=str(payload["created_at_utc"]),
        artifacts=tuple(
            parse_backtest_artifact(item) for item in payload.get("artifacts", ())
        ),
        manifest_version=str(
            payload.get("manifest_version", BACKTEST_ARTIFACTS_VERSION)
        ),
        metadata=payload.get("metadata", {}),
    )


def verify_backtest_artifact_manifest(
    manifest: BacktestArtifactManifest,
) -> tuple[str, ...]:
    """Return one issue message per artifact that is missing or has changed."""

    issues: list[str] = []

    for artifact in manifest.artifacts:
        artifact_path = Path(artifact.path)

        if not artifact_path.is_file():
            issues.append(f"Missing backtest artifact: {artifact.path}")
            continue

        if artifact.sha256 is None:
            continue

        if compute_backtest_file_sha256(artifact_path) != artifact.sha256:
            issues.append(f"Backtest artifact checksum changed: {artifact.path}")

    return tuple(issues)


__all__ = [
    "BACKTEST_ARTIFACTS_VERSION",
    "BacktestArtifact",
    "BacktestArtifactKind",
    "BacktestArtifactManifest",
    "build_backtest_artifact",
    "build_backtest_artifact_manifest",
    "build_backtest_run_id",
    "compute_backtest_file_sha256",
    "normalize_backtest_run_slug",
    "parse_backtest_artifact",
    "read_backtest_artifact_manifest",
    "verify_backtest_artifact_manifest",
    "write_backtest_artifact_manifest",
]
