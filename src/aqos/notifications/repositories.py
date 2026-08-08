"""
Reading and writing notifications.

Every query that returns notifications takes a ``user_id`` and applies it. That
is not a convenience filter: a notification is addressed to one person, and a
method that could return somebody else's would make every caller responsible
for remembering to scope it.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from aqos.database.repository import AqosRepository
from aqos.database.types import database_utc_now
from aqos.notifications.models import (
    Notification,
    NotificationDeliveryAttempt,
    NotificationPreference,
)
from aqos.notifications.types import (
    DeliveryStatus,
    NotificationCategory,
    NotificationChannel,
    NotificationError,
    NotificationReadState,
)
from aqos.users.repositories import build_entity_id


AQOS_NOTIFICATION_REPOSITORIES_VERSION = "1.0"


class NotificationPreferenceRepository(AqosRepository[NotificationPreference]):
    """One row per user, category and channel."""

    model = NotificationPreference

    def get_preference(
        self,
        user_id: str,
        category: NotificationCategory,
        channel: NotificationChannel,
    ) -> NotificationPreference | None:
        return self.find_one_by(
            user_id=user_id,
            category=category,
            channel=channel,
        )

    def set_preference(
        self,
        user_id: str,
        category: NotificationCategory,
        channel: NotificationChannel,
        enabled: bool,
        at_utc: datetime | None = None,
    ) -> NotificationPreference:
        """Record a choice, replacing any earlier one for the same triple."""

        timestamp = at_utc or database_utc_now()
        existing = self.get_preference(user_id, category, channel)

        if existing is not None:
            existing.enabled = enabled
            existing.updated_at_utc = timestamp
            self.flush()

            return existing

        preference = NotificationPreference(
            preference_id=build_entity_id("notifpref"),
            user_id=user_id,
            category=category,
            channel=channel,
            enabled=enabled,
            created_at_utc=timestamp,
            updated_at_utc=timestamp,
        )
        self.add(preference)
        self.flush()

        return preference

    def list_for_user(self, user_id: str) -> tuple[NotificationPreference, ...]:
        return self.find_by(user_id=user_id)


class NotificationRepository(AqosRepository[Notification]):
    """The notifications themselves."""

    model = Notification

    def create_notification(
        self,
        user_id: str,
        category: NotificationCategory,
        priority: Any,
        template_key: str,
        title: str,
        body: str,
        account_id: str | None = None,
        signal_id: str | None = None,
        paper_session_id: str | None = None,
        backtest_id: str | None = None,
        report_id: str | None = None,
        created_at_utc: datetime | None = None,
        notification_id: str | None = None,
    ) -> Notification:
        notification = Notification(
            notification_id=notification_id or build_entity_id("notification"),
            user_id=user_id,
            category=category,
            priority=priority,
            template_key=template_key,
            title=title,
            body=body,
            account_id=account_id,
            signal_id=signal_id,
            paper_session_id=paper_session_id,
            backtest_id=backtest_id,
            report_id=report_id,
            created_at_utc=created_at_utc or database_utc_now(),
        )
        self.add(notification)
        self.flush()

        return notification

    def require_for_user(self, notification_id: str, user_id: str) -> Notification:
        """
        Load a notification the caller owns, or refuse.

        Somebody else's notification is reported as absent, exactly like one
        that never existed, so notification ids cannot be probed.
        """

        notification = self.get(notification_id)

        if notification is None or notification.user_id != user_id:
            raise NotificationError(
                f"Notification {notification_id} was not found."
            )

        return notification

    def list_for_user(
        self,
        user_id: str,
        category: NotificationCategory | None = None,
        read_state: NotificationReadState | None = None,
        limit: int | None = None,
        offset: int | None = None,
    ) -> tuple[Notification, ...]:
        statement = (
            select(Notification)
            .where(Notification.user_id == user_id)
            .order_by(Notification.created_at_utc.desc(), Notification.notification_id)
        )

        if category is not None:
            statement = statement.where(Notification.category == category)

        if read_state is not None:
            statement = statement.where(Notification.read_state == read_state)

        if offset is not None:
            statement = statement.offset(offset)

        if limit is not None:
            statement = statement.limit(limit)

        return tuple(self.session.execute(statement).scalars().all())

    def unread_count(self, user_id: str) -> int:
        """
        How many a user has not read.

        Always a number. Nought unread is a measured fact — the user is caught
        up — and is never confused with having no notifications at all, which
        the list answers separately.
        """

        statement = (
            select(func.count())
            .select_from(Notification)
            .where(Notification.user_id == user_id)
            .where(Notification.read_state == NotificationReadState.UNREAD)
        )

        return int(self.session.execute(statement).scalar_one())

    def count_by_state(self, user_id: str) -> dict[str, int]:
        """Every state with a count, including the states with none."""

        statement = (
            select(Notification.read_state, func.count())
            .where(Notification.user_id == user_id)
            .group_by(Notification.read_state)
        )
        counted = {
            state.value: int(total)
            for state, total in self.session.execute(statement).all()
        }

        return {state.value: counted.get(state.value, 0) for state in NotificationReadState}


class NotificationDeliveryAttemptRepository(
    AqosRepository[NotificationDeliveryAttempt]
):
    """What happened when AQOS tried to deliver."""

    model = NotificationDeliveryAttempt

    def record_attempt(
        self,
        notification_id: str,
        channel: NotificationChannel,
        status: DeliveryStatus,
        reason: str | None = None,
        attempted_at_utc: datetime | None = None,
    ) -> NotificationDeliveryAttempt:
        attempt = NotificationDeliveryAttempt(
            attempt_id=build_entity_id("notifattempt"),
            notification_id=notification_id,
            channel=channel,
            status=status,
            reason=reason,
            attempted_at_utc=attempted_at_utc or database_utc_now(),
        )
        self.add(attempt)
        self.flush()

        return attempt

    def list_for_notification(
        self,
        notification_id: str,
    ) -> tuple[NotificationDeliveryAttempt, ...]:
        statement = (
            select(NotificationDeliveryAttempt)
            .where(NotificationDeliveryAttempt.notification_id == notification_id)
            .order_by(
                NotificationDeliveryAttempt.attempted_at_utc,
                NotificationDeliveryAttempt.attempt_id,
            )
        )

        return tuple(self.session.execute(statement).scalars().all())

    def was_delivered(self, notification_id: str) -> bool:
        """
        Whether any channel actually reached the recipient.

        Only ``sent`` counts. A notification with three unsupported attempts
        was not delivered, however many rows it has.
        """

        return any(
            attempt.status == DeliveryStatus.SENT
            for attempt in self.list_for_notification(notification_id)
        )

    def count_by_status(self, notification_id: str) -> dict[str, int]:
        attempts = self.list_for_notification(notification_id)

        return {
            status.value: sum(
                1 for attempt in attempts if attempt.status == status
            )
            for status in DeliveryStatus
        }


__all__ = [
    "AQOS_NOTIFICATION_REPOSITORIES_VERSION",
    "NotificationDeliveryAttemptRepository",
    "NotificationPreferenceRepository",
    "NotificationRepository",
]
