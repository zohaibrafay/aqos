"""
Getting a notification to somebody, or honestly saying it did not go.

There is exactly one working backend: in-app, which "delivers" by virtue of the
notification row existing. Email and push are declared so preferences and
templates can be written against them, and both refuse — they report
``unsupported`` and never ``sent``.

Nothing here opens a socket, imports a provider SDK or reads a credential. A
backend that claimed to send while doing nothing would make every delivery
record a lie, and the records are the only evidence anybody has.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Protocol

from aqos.notifications.types import (
    DeliveryStatus,
    NotificationChannel,
    is_supported_channel,
)


AQOS_NOTIFICATION_DELIVERY_VERSION = "1.0"


@dataclass(frozen=True)
class DeliveryOutcome:
    """
    What one backend did, in its own words.

    ``status`` is the fact and ``reason`` is the explanation. A backend that
    did nothing must say so here rather than returning ``SENT`` and leaving the
    caller to guess.
    """

    channel: NotificationChannel
    status: DeliveryStatus
    reason: str | None = None

    @property
    def delivered(self) -> bool:
        return self.status == DeliveryStatus.SENT

    def to_dict(self) -> dict[str, Any]:
        return {
            "channel": self.channel.value,
            "status": self.status.value,
            "reason": self.reason,
            "delivered": self.delivered,
        }


class DeliveryBackend(Protocol):
    """One way of reaching somebody."""

    channel: NotificationChannel

    def deliver(self, notification_id: str) -> DeliveryOutcome: ...


class InAppDeliveryBackend:
    """
    In-app delivery.

    The notification row is the delivery: once it exists the user can read it
    the next time they look. There is nothing to send and nothing that can
    fail, which is why this is the only backend that reports ``SENT``.
    """

    channel = NotificationChannel.IN_APP

    def deliver(self, notification_id: str) -> DeliveryOutcome:
        if not notification_id.strip():
            raise ValueError("notification_id is required.")

        return DeliveryOutcome(
            channel=self.channel,
            status=DeliveryStatus.SENT,
            reason=None,
        )


class UnsupportedDeliveryBackend:
    """
    A channel this deployment cannot reach.

    Reports ``unsupported`` every time. Not ``failed``, because nothing was
    attempted and nothing broke; not ``skipped``, because the user did not
    choose this; and never ``sent``, because nobody received anything.
    """

    def __init__(self, channel: NotificationChannel, reason: str) -> None:
        self.channel = channel
        self.reason = reason

    def deliver(self, notification_id: str) -> DeliveryOutcome:
        if not notification_id.strip():
            raise ValueError("notification_id is required.")

        return DeliveryOutcome(
            channel=self.channel,
            status=DeliveryStatus.UNSUPPORTED,
            reason=self.reason,
        )


EMAIL_UNSUPPORTED_REASON = (
    "AQOS has no email provider configured, so this notification was not "
    "emailed. It is available in the app."
)

PUSH_UNSUPPORTED_REASON = (
    "AQOS has no push provider configured, so this notification was not "
    "pushed. It is available in the app."
)


def build_delivery_backends() -> dict[NotificationChannel, DeliveryBackend]:
    """
    Every channel AQOS knows about, and what actually happens on each.

    Email and push are present rather than absent on purpose: a missing entry
    would look like an oversight, while an entry that refuses is a statement
    that the channel is known and deliberately not wired.
    """

    return {
        NotificationChannel.IN_APP: InAppDeliveryBackend(),
        NotificationChannel.EMAIL: UnsupportedDeliveryBackend(
            NotificationChannel.EMAIL,
            EMAIL_UNSUPPORTED_REASON,
        ),
        NotificationChannel.PUSH: UnsupportedDeliveryBackend(
            NotificationChannel.PUSH,
            PUSH_UNSUPPORTED_REASON,
        ),
    }


def assert_delivery_is_honest(
    channel: NotificationChannel,
    outcome: DeliveryOutcome,
) -> None:
    """
    Refuse an outcome that claims more than the deployment can do.

    Called after every delivery. If a backend for an unsupported channel ever
    starts reporting ``sent``, this raises rather than letting a record be
    written that says a user was reached when they were not.
    """

    if outcome.status == DeliveryStatus.SENT and not is_supported_channel(channel):
        raise ValueError(
            f"The {channel.value} channel is not supported by this deployment, "
            "so it cannot report a delivery as sent."
        )


__all__ = [
    "AQOS_NOTIFICATION_DELIVERY_VERSION",
    "EMAIL_UNSUPPORTED_REASON",
    "PUSH_UNSUPPORTED_REASON",
    "DeliveryBackend",
    "DeliveryOutcome",
    "InAppDeliveryBackend",
    "UnsupportedDeliveryBackend",
    "assert_delivery_is_honest",
    "build_delivery_backends",
]
