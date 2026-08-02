from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import JSON, DateTime, ForeignKey, String, func
from sqlalchemy.orm import Mapped, mapped_column, validates

from aqos.database.base import AQOS_TABLE_ARGS, AqosBase
from aqos.database.types import EnumString, database_utc_now
from aqos.signals.models import SignalStatus
from aqos.signal_reasons.taxonomy import (
    SignalReasonCategory,
    SignalReasonCode,
    SignalReasonError,
    SignalReasonSeverity,
    default_reason_message,
    resolve_minimum_severity,
    resolve_reason_category,
    validate_reason,
)


AQOS_SIGNAL_REASON_MODELS_VERSION = "1.0"


def build_reason_message(
    code: SignalReasonCode,
    message: str | None = None,
) -> str:
    """
    Resolve the human readable message for a reason.

    A blank message is replaced by the canonical one rather than stored, so a
    reason row can never explain nothing.
    """

    text = (message or "").strip()

    return text or default_reason_message(code)


class SignalReason(AqosBase):
    """
    Why a signal was rejected, missed, failed, expired or cancelled.

    This complements the signal audit trail: ``signal_events`` records that a
    transition happened, ``signal_reasons`` records why in a form that can be
    counted and reported on. One signal can carry several reasons, for example
    one per account it was evaluated against.
    """

    __tablename__ = "signal_reasons"
    __table_args__ = AQOS_TABLE_ARGS

    reason_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    signal_id: Mapped[str] = mapped_column(
        String(64),
        ForeignKey("trading_signals.signal_id", ondelete="CASCADE"),
        nullable=False,
    )
    user_id: Mapped[str] = mapped_column(
        String(64),
        ForeignKey("user_profiles.user_id", ondelete="CASCADE"),
        nullable=False,
    )
    account_id: Mapped[str | None] = mapped_column(
        String(64),
        ForeignKey("trading_accounts.account_id", ondelete="SET NULL"),
        nullable=True,
    )
    signal_status: Mapped[SignalStatus] = mapped_column(
        EnumString(SignalStatus),
        nullable=False,
    )
    reason_category: Mapped[SignalReasonCategory] = mapped_column(
        EnumString(SignalReasonCategory),
        nullable=False,
    )
    reason_code: Mapped[SignalReasonCode] = mapped_column(
        EnumString(SignalReasonCode, length=64),
        nullable=False,
    )
    severity: Mapped[SignalReasonSeverity] = mapped_column(
        EnumString(SignalReasonSeverity, length=16),
        nullable=False,
    )
    message: Mapped[str] = mapped_column(String(512), nullable=False)
    source: Mapped[str | None] = mapped_column(String(191), nullable=True)
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
        """
        Fill the derivable fields before construction.

        Category and severity are properties of the reason code, so a caller
        that omits them gets the canonical values rather than ``None``.
        """

        code = kwargs.get("reason_code")

        if isinstance(code, str) and not isinstance(code, SignalReasonCode):
            code = SignalReasonCode(code)
            kwargs["reason_code"] = code

        if isinstance(code, SignalReasonCode):
            kwargs.setdefault("reason_category", resolve_reason_category(code))
            kwargs.setdefault("severity", resolve_minimum_severity(code))
            kwargs["message"] = build_reason_message(code, kwargs.get("message"))

        kwargs.setdefault("extra_metadata", {})

        super().__init__(**kwargs)

    @validates("message")
    def _validate_message(self, key: str, value: str) -> str:
        text = (value or "").strip()

        if not text:
            raise SignalReasonError("message cannot be empty.")

        return text

    def assert_no_unset_reason_fields(self) -> None:
        """
        Guard against a reason row that cannot be interpreted.

        A missing code, category or severity would make the row invisible to
        every severity filter and category report, which is the dangerous
        direction for a record that exists to explain a blocked trade.
        """

        unset = [
            field_name
            for field_name in (
                "reason_id",
                "signal_id",
                "user_id",
                "signal_status",
                "reason_category",
                "reason_code",
                "severity",
                "message",
            )
            if getattr(self, field_name, None) is None
        ]

        if unset:
            raise SignalReasonError(
                "Signal reason fields must never be unset: "
                + ", ".join(sorted(unset))
            )

    def validate_taxonomy(self) -> None:
        """Check the row against the canonical meaning of its reason code."""

        self.assert_no_unset_reason_fields()

        validate_reason(
            code=self.reason_code,
            category=self.reason_category,
            severity=self.severity,
            status=self.signal_status,
        )

    @property
    def is_blocking(self) -> bool:
        return self.severity in (
            SignalReasonSeverity.BLOCKING,
            SignalReasonSeverity.CRITICAL,
        )

    @property
    def is_critical(self) -> bool:
        return self.severity == SignalReasonSeverity.CRITICAL

    def to_dict(self) -> dict[str, Any]:
        return {
            "reason_id": self.reason_id,
            "signal_id": self.signal_id,
            "user_id": self.user_id,
            "account_id": self.account_id,
            "signal_status": (
                self.signal_status.value if self.signal_status else None
            ),
            "reason_category": (
                self.reason_category.value if self.reason_category else None
            ),
            "reason_code": self.reason_code.value if self.reason_code else None,
            "severity": self.severity.value if self.severity else None,
            "message": self.message,
            "source": self.source,
            "is_blocking": self.is_blocking,
            "is_critical": self.is_critical,
            "created_at_utc": (
                self.created_at_utc.isoformat() if self.created_at_utc else None
            ),
            "metadata": self.extra_metadata or {},
        }

    def __repr__(self) -> str:
        return (
            f"SignalReason(signal_id={self.signal_id!r}, "
            f"reason_code={self.reason_code.value if self.reason_code else None!r})"
        )


__all__ = [
    "AQOS_SIGNAL_REASON_MODELS_VERSION",
    "SignalReason",
    "build_reason_message",
]
