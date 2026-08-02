from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import JSON, Boolean, DateTime, ForeignKey, String, func, select
from sqlalchemy.orm import Mapped, mapped_column

from aqos.account_reports.artifacts import ReportArtifact
from aqos.account_reports.contracts import (
    AccountPerformanceReport,
    AccountReportError,
    ReportFormat,
    ReportType,
    TRADE_DEPENDENT_REPORT_TYPES,
)
from aqos.accounts.models import AccountType
from aqos.database.base import AQOS_TABLE_ARGS, AqosBase
from aqos.database.repository import AqosRepository
from aqos.database.types import EnumString, database_utc_now


AQOS_ACCOUNT_REPORT_REPOSITORIES_VERSION = "1.0"


class AccountPerformanceReportRecord(AqosBase):
    """Where a generated report artifact lives and what it claims."""

    __tablename__ = "account_performance_reports"
    __table_args__ = AQOS_TABLE_ARGS

    report_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    user_id: Mapped[str] = mapped_column(
        String(64),
        ForeignKey("user_profiles.user_id", ondelete="CASCADE"),
        nullable=False,
    )
    account_id: Mapped[str] = mapped_column(
        String(64),
        ForeignKey("trading_accounts.account_id", ondelete="CASCADE"),
        nullable=False,
    )
    account_type: Mapped[AccountType] = mapped_column(
        EnumString(AccountType),
        nullable=False,
    )
    report_type: Mapped[ReportType] = mapped_column(
        EnumString(ReportType),
        nullable=False,
    )
    analytics_snapshot_id: Mapped[str | None] = mapped_column(
        String(64),
        ForeignKey(
            "account_analytics_snapshots.snapshot_id",
            ondelete="SET NULL",
        ),
        nullable=True,
    )
    period_start_utc: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    period_end_utc: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    generated_at_utc: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    trade_metrics_available: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
    )
    artifact_format: Mapped[ReportFormat] = mapped_column(
        EnumString(ReportFormat, length=16),
        nullable=False,
        default=ReportFormat.JSON,
    )
    artifact_path: Mapped[str | None] = mapped_column(String(512), nullable=True)
    artifact_checksum: Mapped[str | None] = mapped_column(String(64), nullable=True)
    payload_json: Mapped[dict[str, Any]] = mapped_column(
        JSON,
        nullable=False,
        default=dict,
    )
    created_at_utc: Mapped[datetime] = mapped_column(
        DateTime,
        nullable=False,
        default=database_utc_now,
        server_default=func.now(),
    )
    extra_metadata: Mapped[dict[str, Any]] = mapped_column(
        "metadata_json",
        JSON,
        nullable=False,
        default=dict,
    )

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("trade_metrics_available", False)
        kwargs.setdefault("artifact_format", ReportFormat.JSON)
        kwargs.setdefault("payload_json", {})
        kwargs.setdefault("extra_metadata", {})

        super().__init__(**kwargs)

    def assert_report_is_supportable(self) -> None:
        """A trade report with no trade metrics would be empty by construction."""

        if (
            self.report_type in TRADE_DEPENDENT_REPORT_TYPES
            and not self.trade_metrics_available
        ):
            raise AccountReportError(
                f"A {self.report_type.value} report cannot be stored without "
                "trade metrics."
            )

        if self.artifact_checksum is not None and len(self.artifact_checksum) != 64:
            raise AccountReportError(
                "artifact_checksum must be a 64 character SHA-256 digest."
            )

    def to_dict(self) -> dict[str, Any]:
        return {
            "report_id": self.report_id,
            "user_id": self.user_id,
            "account_id": self.account_id,
            "account_type": (
                self.account_type.value if self.account_type else None
            ),
            "report_type": self.report_type.value if self.report_type else None,
            "analytics_snapshot_id": self.analytics_snapshot_id,
            "period_start_utc": (
                self.period_start_utc.isoformat() if self.period_start_utc else None
            ),
            "period_end_utc": (
                self.period_end_utc.isoformat() if self.period_end_utc else None
            ),
            "generated_at_utc": (
                self.generated_at_utc.isoformat() if self.generated_at_utc else None
            ),
            "trade_metrics_available": bool(self.trade_metrics_available),
            "artifact_format": (
                self.artifact_format.value if self.artifact_format else None
            ),
            "artifact_path": self.artifact_path,
            "artifact_checksum": self.artifact_checksum,
            "payload": self.payload_json or {},
            "metadata": self.extra_metadata or {},
        }

    def __repr__(self) -> str:
        return (
            f"AccountPerformanceReportRecord(report_id={self.report_id!r}, "
            f"report_type={self.report_type.value if self.report_type else None!r})"
        )


class AccountPerformanceReportRepository(
    AqosRepository[AccountPerformanceReportRecord]
):
    """Registered account performance reports."""

    model = AccountPerformanceReportRecord

    def register_report(
        self,
        report: AccountPerformanceReport,
        artifact: ReportArtifact | None = None,
        analytics_snapshot_id: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> AccountPerformanceReportRecord:
        record = AccountPerformanceReportRecord(
            report_id=report.report_id,
            user_id=report.user_id,
            account_id=report.account_id,
            account_type=report.account_type,
            report_type=report.report_type,
            analytics_snapshot_id=(
                analytics_snapshot_id or report.analytics_snapshot_id
            ),
            period_start_utc=report.period_start_utc,
            period_end_utc=report.period_end_utc,
            generated_at_utc=report.generated_at_utc,
            trade_metrics_available=report.trade_metrics_available,
            artifact_format=(
                artifact.artifact_format if artifact is not None else ReportFormat.JSON
            ),
            artifact_path=artifact.path.as_posix() if artifact is not None else None,
            artifact_checksum=artifact.checksum if artifact is not None else None,
            payload_json=report.to_dict(),
            extra_metadata=metadata or {},
        )
        record.assert_report_is_supportable()

        self.add(record)
        self.flush()

        return record

    def list_reports(
        self,
        user_id: str | None = None,
        account_id: str | None = None,
        report_type: ReportType | None = None,
    ) -> tuple[AccountPerformanceReportRecord, ...]:
        statement = select(AccountPerformanceReportRecord)

        if user_id is not None:
            statement = statement.where(
                AccountPerformanceReportRecord.user_id == user_id
            )

        if account_id is not None:
            statement = statement.where(
                AccountPerformanceReportRecord.account_id == account_id
            )

        if report_type is not None:
            statement = statement.where(
                AccountPerformanceReportRecord.report_type == report_type
            )

        statement = statement.order_by(
            AccountPerformanceReportRecord.generated_at_utc,
            AccountPerformanceReportRecord.report_id,
        )

        return tuple(self.session.execute(statement).scalars().all())

    def latest_report(
        self,
        account_id: str,
        report_type: ReportType | None = None,
    ) -> AccountPerformanceReportRecord | None:
        reports = self.list_reports(
            account_id=account_id,
            report_type=report_type,
        )

        return reports[-1] if reports else None

    def count_by_type(self, user_id: str) -> dict[str, int]:
        statement = (
            select(AccountPerformanceReportRecord.report_type, func.count())
            .where(AccountPerformanceReportRecord.user_id == user_id)
            .group_by(AccountPerformanceReportRecord.report_type)
        )

        rows = self.session.execute(statement).all()

        return dict(
            sorted(
                (
                    (
                        row[0].value if hasattr(row[0], "value") else str(row[0]),
                        int(row[1]),
                    )
                    for row in rows
                ),
            )
        )


__all__ = [
    "AQOS_ACCOUNT_REPORT_REPOSITORIES_VERSION",
    "AccountPerformanceReportRecord",
    "AccountPerformanceReportRepository",
]
