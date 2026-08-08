"""
Persisted notifications, preferences and delivery attempts.

Three tables, and the shape of each is chosen so a reader can always tell what
actually happened. A notification carries no free-form payload — the title and
the body are already rendered text, so there is nothing stored that a template
did not produce. A delivery attempt records its own outcome rather than being
inferred from the notification, because "never tried" and "tried and failed"
are different answers to the same question.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import Boolean, DateTime, ForeignKey, Index, String, Text
from sqlalchemy.orm import Mapped, mapped_column, validates

from aqos.database.base import AQOS_TABLE_ARGS, AqosBase
from aqos.database.types import EnumString, database_utc_now
from aqos.notifications.types import (
    DeliveryStatus,
    NotificationCategory,
    NotificationChannel,
    NotificationError,
    NotificationPriority,
    NotificationReadState,
    validate_read_state_transition,
)


AQOS_NOTIFICATION_MODELS_VERSION = "1.0"

MAX_TITLE_LENGTH = 191
MAX_BODY_LENGTH = 2000


class NotificationPreference(AqosBase):
    """
    Whether one user wants one category on one channel.

    A row per user, category and channel. Absent means "no opinion", and the
    default is resolved in :mod:`aqos.notifications.preferences` rather than
    here, so a channel that gains a provider later does not silently switch on
    for everybody who never chose it.
    """

    __tablename__ = "notification_preferences"
    __table_args__ = (
        Index("ix_notification_preferences_user", "user_id", "category"),
        AQOS_TABLE_ARGS,
    )

    preference_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    user_id: Mapped[str] = mapped_column(
        String(64),
        ForeignKey("user_profiles.user_id", ondelete="CASCADE"),
        nullable=False,
    )
    category: Mapped[NotificationCategory] = mapped_column(
        EnumString(NotificationCategory, 32),
        nullable=False,
    )
    channel: Mapped[NotificationChannel] = mapped_column(
        EnumString(NotificationChannel, 32),
        nullable=False,
    )
    enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at_utc: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    updated_at_utc: Mapped[datetime] = mapped_column(DateTime, nullable=False)

    def __init__(self, **kwargs: Any) -> None:
        now = kwargs.get("created_at_utc") or database_utc_now()
        kwargs.setdefault("created_at_utc", now)
        kwargs.setdefault("updated_at_utc", now)
        kwargs.setdefault("enabled", True)

        super().__init__(**kwargs)

    def to_dict(self) -> dict[str, Any]:
        return {
            "preference_id": self.preference_id,
            "user_id": self.user_id,
            "category": self.category.value,
            "channel": self.channel.value,
            "enabled": bool(self.enabled),
        }


class Notification(AqosBase):
    """
    One thing AQOS told one user.

    The optional references — account, signal, paper session, backtest, report
    — are plain identifier columns rather than foreign keys, so deleting the
    thing a notification described does not delete the record that it was
    mentioned. What was said stays said.
    """

    __tablename__ = "notifications"
    __table_args__ = (
        Index("ix_notifications_user_state", "user_id", "read_state", "created_at_utc"),
        Index("ix_notifications_user_category", "user_id", "category"),
        AQOS_TABLE_ARGS,
    )

    notification_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    user_id: Mapped[str] = mapped_column(
        String(64),
        ForeignKey("user_profiles.user_id", ondelete="CASCADE"),
        nullable=False,
    )
    category: Mapped[NotificationCategory] = mapped_column(
        EnumString(NotificationCategory, 32),
        nullable=False,
    )
    priority: Mapped[NotificationPriority] = mapped_column(
        EnumString(NotificationPriority, 16),
        nullable=False,
    )
    read_state: Mapped[NotificationReadState] = mapped_column(
        EnumString(NotificationReadState, 16),
        nullable=False,
        default=NotificationReadState.UNREAD,
    )
    template_key: Mapped[str] = mapped_column(String(64), nullable=False)
    title: Mapped[str] = mapped_column(String(MAX_TITLE_LENGTH), nullable=False)
    body: Mapped[str] = mapped_column(Text, nullable=False)
    account_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    signal_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    paper_session_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    backtest_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    report_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    created_at_utc: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    read_at_utc: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    archived_at_utc: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("created_at_utc", database_utc_now())
        # Set explicitly rather than through the column default: a transient
        # object read before a flush would otherwise carry None, which is the
        # trap Sprint 043 and Sprint 052 both hit.
        kwargs.setdefault("read_state", NotificationReadState.UNREAD)

        super().__init__(**kwargs)

    @validates("title")
    def _validate_title(self, _key: str, value: str) -> str:
        text = (value or "").strip()

        if not text:
            raise NotificationError("A notification needs a title.")

        if len(text) > MAX_TITLE_LENGTH:
            raise NotificationError(
                f"A notification title may be at most {MAX_TITLE_LENGTH} characters."
            )

        return text

    @validates("body")
    def _validate_body(self, _key: str, value: str) -> str:
        text = (value or "").strip()

        if not text:
            raise NotificationError("A notification needs a body.")

        if len(text) > MAX_BODY_LENGTH:
            raise NotificationError(
                f"A notification body may be at most {MAX_BODY_LENGTH} characters."
            )

        return text

    @property
    def is_unread(self) -> bool:
        return self.read_state == NotificationReadState.UNREAD

    @property
    def is_archived(self) -> bool:
        return self.read_state == NotificationReadState.ARCHIVED

    def move_to(
        self,
        state: NotificationReadState,
        at_utc: datetime | None = None,
    ) -> None:
        """
        Move to a new read state, stamping when it happened.

        The transition rules live in :mod:`aqos.notifications.types`; this only
        applies them and records the timestamps that go with each outcome.
        """

        validate_read_state_transition(self.read_state, state)

        moment = at_utc or database_utc_now()
        self.read_state = state

        if state == NotificationReadState.READ:
            self.read_at_utc = moment
        elif state == NotificationReadState.UNREAD:
            # Marking unread genuinely undoes the reading, so the timestamp
            # goes with it rather than lingering as a half-truth.
            self.read_at_utc = None
        elif state == NotificationReadState.ARCHIVED:
            self.archived_at_utc = moment

    def to_dict(self) -> dict[str, Any]:
        """
        The notification as anything outside this package may see it.

        Every field here is either an identifier or text a template produced.
        There is no metadata column to leak, and none of the optional
        references is a secret.
        """

        return {
            "notification_id": self.notification_id,
            "user_id": self.user_id,
            "category": self.category.value,
            "priority": self.priority.value,
            "read_state": self.read_state.value,
            "template_key": self.template_key,
            "title": self.title,
            "body": self.body,
            "account_id": self.account_id,
            "signal_id": self.signal_id,
            "paper_session_id": self.paper_session_id,
            "backtest_id": self.backtest_id,
            "report_id": self.report_id,
            "created_at_utc": (
                self.created_at_utc.isoformat() if self.created_at_utc else None
            ),
            "read_at_utc": (
                self.read_at_utc.isoformat() if self.read_at_utc else None
            ),
            "archived_at_utc": (
                self.archived_at_utc.isoformat() if self.archived_at_utc else None
            ),
        }


class NotificationDeliveryAttempt(AqosBase):
    """
    One attempt to get a notification to somebody.

    A row is written whatever the outcome, including when nothing was tried:
    a channel the user turned off is ``skipped`` and a channel with nothing
    behind it is ``unsupported``, and both are recorded so "why did they not
    hear about this?" has an answer that is not a shrug.
    """

    __tablename__ = "notification_delivery_attempts"
    __table_args__ = (
        Index("ix_delivery_attempts_notification", "notification_id", "channel"),
        Index("ix_delivery_attempts_status", "status", "attempted_at_utc"),
        AQOS_TABLE_ARGS,
    )

    attempt_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    notification_id: Mapped[str] = mapped_column(
        String(64),
        ForeignKey("notifications.notification_id", ondelete="CASCADE"),
        nullable=False,
    )
    channel: Mapped[NotificationChannel] = mapped_column(
        EnumString(NotificationChannel, 32),
        nullable=False,
    )
    status: Mapped[DeliveryStatus] = mapped_column(
        EnumString(DeliveryStatus, 32),
        nullable=False,
    )
    #: Why, in AQOS's own words. Never a provider message, a stack trace or a
    #: connection detail — none of those belongs in a row a user may be shown.
    reason: Mapped[str | None] = mapped_column(String(512), nullable=True)
    attempted_at_utc: Mapped[datetime] = mapped_column(DateTime, nullable=False)

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("attempted_at_utc", database_utc_now())

        super().__init__(**kwargs)

    @property
    def delivered(self) -> bool:
        """Whether a person could actually have seen it. Only ``sent`` counts."""

        return self.status == DeliveryStatus.SENT

    def to_dict(self) -> dict[str, Any]:
        return {
            "attempt_id": self.attempt_id,
            "notification_id": self.notification_id,
            "channel": self.channel.value,
            "status": self.status.value,
            "reason": self.reason,
            "delivered": self.delivered,
            "attempted_at_utc": (
                self.attempted_at_utc.isoformat() if self.attempted_at_utc else None
            ),
        }


__all__ = [
    "AQOS_NOTIFICATION_MODELS_VERSION",
    "MAX_BODY_LENGTH",
    "MAX_TITLE_LENGTH",
    "Notification",
    "NotificationDeliveryAttempt",
    "NotificationPreference",
]
