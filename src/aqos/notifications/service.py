"""
The notification service.

One place that turns "something happened" into a stored notification and an
honest record of what AQOS did about it. The caller owns the session and the
transaction, as everywhere else in this codebase.

Creating a notification always writes a delivery attempt per channel, including
the channels that did nothing. A notification with no attempt rows would be
indistinguishable from one nobody ever tried to deliver, and that difference is
the whole point of keeping the attempts.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any

from sqlalchemy.orm import Session

from aqos.notifications.delivery import (
    DeliveryOutcome,
    assert_delivery_is_honest,
    build_delivery_backends,
)
from aqos.notifications.models import Notification, NotificationDeliveryAttempt
from aqos.notifications.preferences import ResolvedPreference, resolve_preference
from aqos.notifications.repositories import (
    NotificationDeliveryAttemptRepository,
    NotificationPreferenceRepository,
    NotificationRepository,
)
from aqos.notifications.templates import render_template
from aqos.notifications.types import (
    DeliveryStatus,
    NotificationCategory,
    NotificationChannel,
    NotificationPriority,
    NotificationReadState,
)


AQOS_NOTIFICATION_SERVICE_VERSION = "1.0"

#: The channels every notification is considered for.
DEFAULT_CHANNELS = (
    NotificationChannel.IN_APP,
    NotificationChannel.EMAIL,
    NotificationChannel.PUSH,
)


@dataclass(frozen=True)
class NotificationResult:
    """
    A notification and what happened to it.

    ``delivered`` is true only if some channel actually reached the recipient.
    A notification that exists but reached nobody is a real and reportable
    state, not a failure to record.
    """

    notification: Notification
    attempts: tuple[NotificationDeliveryAttempt, ...]

    @property
    def delivered(self) -> bool:
        return any(attempt.delivered for attempt in self.attempts)

    def to_dict(self) -> dict[str, Any]:
        return {
            "notification": self.notification.to_dict(),
            "attempts": [attempt.to_dict() for attempt in self.attempts],
            "delivered": self.delivered,
        }


class NotificationService:
    """Creates notifications and records what AQOS did with them."""

    def __init__(self, session: Session) -> None:
        if session is None:
            raise ValueError("A SQLAlchemy session is required.")

        self.session = session
        self.notifications = NotificationRepository(session)
        self.preferences = NotificationPreferenceRepository(session)
        self.attempts = NotificationDeliveryAttemptRepository(session)
        self.backends = build_delivery_backends()

    # -- preferences ------------------------------------------------------

    def resolve_preferences(
        self,
        user_id: str,
        category: NotificationCategory,
        channels: tuple[NotificationChannel, ...] = DEFAULT_CHANNELS,
    ) -> tuple[ResolvedPreference, ...]:
        """
        Decide, per channel, whether this notification may go out.

        A user's stored choice is read where they made one; where they did not,
        the default applies. Support is checked first either way.
        """

        resolved: list[ResolvedPreference] = []

        for channel in channels:
            stored = self.preferences.get_preference(user_id, category, channel)
            resolved.append(
                resolve_preference(
                    category=category,
                    channel=channel,
                    stored=None if stored is None else bool(stored.enabled),
                )
            )

        return tuple(resolved)

    # -- creation ---------------------------------------------------------

    def create_notification(
        self,
        user_id: str,
        category: NotificationCategory,
        priority: NotificationPriority,
        template_key: str,
        title: str,
        body: str,
        channels: tuple[NotificationChannel, ...] = DEFAULT_CHANNELS,
        at_utc: datetime | None = None,
        **references: str | None,
    ) -> NotificationResult:
        """
        Store a notification and attempt delivery on each channel.

        The notification is written first, so a channel that refuses does not
        prevent the user from seeing it in the app.
        """

        notification = self.notifications.create_notification(
            user_id=user_id,
            category=category,
            priority=priority,
            template_key=template_key,
            title=title,
            body=body,
            account_id=references.get("account_id"),
            signal_id=references.get("signal_id"),
            paper_session_id=references.get("paper_session_id"),
            backtest_id=references.get("backtest_id"),
            report_id=references.get("report_id"),
            created_at_utc=at_utc,
        )

        attempts = tuple(
            self._attempt(notification.notification_id, preference, at_utc)
            for preference in self.resolve_preferences(user_id, category, channels)
        )

        return NotificationResult(notification=notification, attempts=attempts)

    def create_from_template(
        self,
        user_id: str,
        template_key: str,
        variables: dict[str, Any],
        channels: tuple[NotificationChannel, ...] = DEFAULT_CHANNELS,
        at_utc: datetime | None = None,
        **references: str | None,
    ) -> NotificationResult:
        """
        Render one of the fixed templates and store the result.

        The category and the priority come from the template, not from the
        caller: what a notification is about is a property of what happened,
        and letting a caller restate it would let the two disagree.
        """

        rendered = render_template(template_key, variables)

        return self.create_notification(
            user_id=user_id,
            category=rendered.category,
            priority=rendered.priority,
            template_key=rendered.template_key,
            title=rendered.title,
            body=rendered.body,
            channels=channels,
            at_utc=at_utc,
            **references,
        )

    def _attempt(
        self,
        notification_id: str,
        preference: ResolvedPreference,
        at_utc: datetime | None,
    ) -> NotificationDeliveryAttempt:
        """
        Try one channel, and record whatever came of it.

        A refusal is recorded with the reason the preference gave, so a skipped
        channel and an unsupported one stay distinguishable in the row itself.
        """

        if not preference.allowed:
            status = (
                DeliveryStatus.UNSUPPORTED
                if not self._is_supported(preference.channel)
                else DeliveryStatus.SKIPPED
            )

            return self.attempts.record_attempt(
                notification_id=notification_id,
                channel=preference.channel,
                status=status,
                reason=preference.reason,
                attempted_at_utc=at_utc,
            )

        outcome = self._deliver(preference.channel, notification_id)

        return self.attempts.record_attempt(
            notification_id=notification_id,
            channel=preference.channel,
            status=outcome.status,
            reason=outcome.reason,
            attempted_at_utc=at_utc,
        )

    def _is_supported(self, channel: NotificationChannel) -> bool:
        from aqos.notifications.types import is_supported_channel

        return is_supported_channel(channel)

    def _deliver(
        self,
        channel: NotificationChannel,
        notification_id: str,
    ) -> DeliveryOutcome:
        backend = self.backends.get(channel)

        if backend is None:
            return DeliveryOutcome(
                channel=channel,
                status=DeliveryStatus.UNSUPPORTED,
                reason="AQOS has no backend for that channel.",
            )

        outcome = backend.deliver(notification_id)
        # Checked rather than trusted: a backend that started claiming a
        # delivery it cannot make would put a false record in front of a user.
        assert_delivery_is_honest(channel, outcome)

        return outcome

    # -- reading ----------------------------------------------------------

    def list_user_notifications(
        self,
        user_id: str,
        category: NotificationCategory | None = None,
        read_state: NotificationReadState | None = None,
        limit: int | None = None,
        offset: int | None = None,
    ) -> tuple[Notification, ...]:
        return self.notifications.list_for_user(
            user_id=user_id,
            category=category,
            read_state=read_state,
            limit=limit,
            offset=offset,
        )

    def unread_count(self, user_id: str) -> int:
        return self.notifications.unread_count(user_id)

    # -- state ------------------------------------------------------------

    def _move(
        self,
        notification_id: str,
        user_id: str,
        state: NotificationReadState,
        at_utc: datetime | None,
    ) -> Notification:
        notification = self.notifications.require_for_user(notification_id, user_id)
        notification.move_to(state, at_utc)
        self.notifications.flush()

        return notification

    def mark_read(
        self,
        notification_id: str,
        user_id: str,
        at_utc: datetime | None = None,
    ) -> Notification:
        return self._move(
            notification_id, user_id, NotificationReadState.READ, at_utc
        )

    def mark_unread(
        self,
        notification_id: str,
        user_id: str,
        at_utc: datetime | None = None,
    ) -> Notification:
        return self._move(
            notification_id, user_id, NotificationReadState.UNREAD, at_utc
        )

    def archive(
        self,
        notification_id: str,
        user_id: str,
        at_utc: datetime | None = None,
    ) -> Notification:
        return self._move(
            notification_id, user_id, NotificationReadState.ARCHIVED, at_utc
        )

    def record_delivery_attempt(
        self,
        notification_id: str,
        user_id: str,
        channel: NotificationChannel,
        status: DeliveryStatus,
        reason: str | None = None,
        at_utc: datetime | None = None,
    ) -> NotificationDeliveryAttempt:
        """
        Record an attempt made elsewhere.

        Ownership is proved first, and a ``sent`` claim on an unsupported
        channel is refused: a caller cannot write a record saying somebody was
        reached by a pipe this deployment does not have.
        """

        self.notifications.require_for_user(notification_id, user_id)

        assert_delivery_is_honest(
            channel,
            DeliveryOutcome(channel=channel, status=status, reason=reason),
        )

        return self.attempts.record_attempt(
            notification_id=notification_id,
            channel=channel,
            status=status,
            reason=reason,
            attempted_at_utc=at_utc,
        )


__all__ = [
    "AQOS_NOTIFICATION_SERVICE_VERSION",
    "DEFAULT_CHANNELS",
    "NotificationResult",
    "NotificationService",
]
