from __future__ import annotations

import csv
import hashlib
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Sequence

from aqos.account_reports.contracts import (
    AccountPerformanceReport,
    AccountReportError,
    ReportFormat,
)


AQOS_ACCOUNT_REPORT_ARTIFACTS_VERSION = "1.0"

CSV_SUMMARY_COLUMNS = (
    "report_id",
    "report_type",
    "user_id",
    "account_id",
    "account_type",
    "generated_at_utc",
    "period_start_utc",
    "period_end_utc",
    "signals_received",
    "signals_executed",
    "signals_rejected",
    "signals_missed",
    "execution_rate",
    "rejection_rate",
    "missed_rate",
    "reason_total",
    "reason_blocking_total",
    "trade_metrics_available",
    "total_trades",
    "win_rate",
    "net_pnl",
    "profit_factor",
    "max_drawdown",
)


@dataclass(frozen=True)
class ReportArtifact:
    path: Path
    artifact_format: ReportFormat
    checksum: str
    size_bytes: int

    def to_dict(self) -> dict[str, Any]:
        return {
            "path": self.path.as_posix(),
            "format": self.artifact_format.value,
            "checksum": self.checksum,
            "size_bytes": self.size_bytes,
        }


def compute_checksum(content: str) -> str:
    return hashlib.sha256(content.encode("utf-8")).hexdigest()


def render_report_json(report: AccountPerformanceReport) -> str:
    """
    Render a report as deterministic, strictly valid JSON.

    Keys are sorted so the same report always produces the same bytes and the
    same checksum. ``allow_nan`` is off because Python would otherwise emit the
    bare tokens ``Infinity`` and ``NaN``, which are not JSON: MySQL rejects them
    outright and API consumers cannot parse them. Failing here is far better
    than shipping an artifact nobody can read.
    """

    return json.dumps(
        report.to_dict(),
        indent=2,
        sort_keys=True,
        allow_nan=False,
    )


def render_report_summary_rows(
    reports: Sequence[AccountPerformanceReport],
) -> list[dict[str, Any]]:
    return [report.summary_row() for report in reports]


def write_report_json(
    path: str | Path,
    report: AccountPerformanceReport,
) -> ReportArtifact:
    output_path = Path(path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    content = render_report_json(report)
    output_path.write_text(content, encoding="utf-8")

    return ReportArtifact(
        path=output_path,
        artifact_format=ReportFormat.JSON,
        checksum=compute_checksum(content),
        size_bytes=len(content.encode("utf-8")),
    )


def write_report_summary_csv(
    path: str | Path,
    reports: Sequence[AccountPerformanceReport],
) -> ReportArtifact:
    """
    Write a flat CSV summary.

    Unavailable values stay empty rather than being written as ``0``, so the
    CSV carries the same distinction as the JSON.
    """

    if not reports:
        raise AccountReportError("At least one report is required for a CSV summary.")

    output_path = Path(path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    lines: list[str] = []
    lines.append(",".join(CSV_SUMMARY_COLUMNS))

    for row in render_report_summary_rows(reports):
        values = []

        for column in CSV_SUMMARY_COLUMNS:
            value = row.get(column)

            if value is None:
                values.append("")
            elif isinstance(value, bool):
                values.append("true" if value else "false")
            else:
                values.append(str(value))

        lines.append(",".join(values))

    content = "\n".join(lines) + "\n"
    output_path.write_text(content, encoding="utf-8", newline="")

    return ReportArtifact(
        path=output_path,
        artifact_format=ReportFormat.CSV,
        checksum=compute_checksum(content),
        size_bytes=len(content.encode("utf-8")),
    )


def read_report_json(path: str | Path) -> dict[str, Any]:
    report_path = Path(path)

    if not report_path.exists():
        raise FileNotFoundError(f"Report artifact does not exist: {report_path}")

    return json.loads(report_path.read_text(encoding="utf-8"))


def verify_report_artifact(artifact: ReportArtifact) -> bool:
    """Return True when the file on disk still matches the recorded checksum."""

    if not artifact.path.exists():
        return False

    content = artifact.path.read_text(encoding="utf-8")

    return compute_checksum(content) == artifact.checksum


__all__ = [
    "AQOS_ACCOUNT_REPORT_ARTIFACTS_VERSION",
    "CSV_SUMMARY_COLUMNS",
    "ReportArtifact",
    "compute_checksum",
    "read_report_json",
    "render_report_json",
    "render_report_summary_rows",
    "verify_report_artifact",
    "write_report_json",
    "write_report_summary_csv",
]
