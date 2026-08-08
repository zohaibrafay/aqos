"""
The vocabulary notifications are written in.

Every value here is a fixed enum. A caller cannot invent a channel, a status or
a category, which is what keeps a notification from claiming it was delivered
by something that does not exist.

Nothing in this module names a provider, a firm or a vendor. AQOS notifies a
user; which pipe it eventually travels down is a deployment concern, and
writing one into the domain would make the domain wrong the day it changes.
"""

from __future__ import annotations

from enum import Enum


AQOS_NOTIFICATION_TYPES_VERSION = "1.0"


class NotificationChannel(str, Enum):
    """Where a notification is meant to arrive."""

    IN_APP = "in_app"
    EMAIL = "email"
    PUSH = "push"


class NotificationCategory(str, Enum):
    """What the notification is about."""

    SIGNAL = "signal"
    ACCOUNT = "account"
    FUNDED_RULE = "funded_rule"
    PAPER_TRADING = "paper_trading"
    BACKTEST = "backtest"
    REPORT = "report"
    SYSTEM = "system"


class NotificationPriority(str, Enum):
    """How much this should interrupt somebody."""

    INFO = "info"
    WARNING = "warning"
    CRITICAL = "critical"


class NotificationReadState(str, Enum):
    """
    What the recipient has done with it.

    Archiving is deliberately separate from reading: a user who files something
    away has read it, and a system that conflated the two would keep showing
    them things they had already dealt with.
    """

    UNREAD = "unread"
    READ = "read"
    ARCHIVED = "archived"


class DeliveryStatus(str, Enum):
    """
    What happened when AQOS tried to deliver.

    ``SKIPPED`` and ``FAILED`` are different facts and must stay so. A skipped
    notification was never attempted — the user turned the channel off, or no
    provider exists — while a failed one was attempted and did not arrive.
    Collapsing them would make "did this reach them?" unanswerable.

    ``UNSUPPORTED`` is narrower still: the channel exists in the vocabulary but
    this deployment has nothing behind it. It is never ``SENT``.
    """

    PENDING = "pending"
    QUEUED = "queued"
    SENT = "sent"
    FAILED = "failed"
    SKIPPED = "skipped"
    UNSUPPORTED = "unsupported"
    CANCELLED = "cancelled"


#: Read states a notification may move to, from each state.
#:
#: Archiving is one-way. Something filed away is done with, and letting it
#: return to the inbox would make the inbox meaningless.
READ_STATE_TRANSITIONS: dict[NotificationReadState, tuple[NotificationReadState, ...]] = {
    NotificationReadState.UNREAD: (
        NotificationReadState.READ,
        NotificationReadState.ARCHIVED,
    ),
    NotificationReadState.READ: (
        NotificationReadState.UNREAD,
        NotificationReadState.ARCHIVED,
    ),
    NotificationReadState.ARCHIVED: (),
}

#: Delivery outcomes that mean the attempt is over.
TERMINAL_DELIVERY_STATUSES = (
    DeliveryStatus.SENT,
    DeliveryStatus.FAILED,
    DeliveryStatus.SKIPPED,
    DeliveryStatus.UNSUPPORTED,
    DeliveryStatus.CANCELLED,
)

#: The only outcome that means a person could actually have seen it.
DELIVERED_STATUSES = (DeliveryStatus.SENT,)

#: Channels this deployment can actually deliver to.
#:
#: Only in-app, because an in-app notification is a row this system already
#: owns. Email and push are in the vocabulary so preferences and templates can
#: be built against them, but nothing delivers either yet, and a request for
#: one is recorded as unsupported rather than quietly marked sent.
SUPPORTED_CHANNELS = (NotificationChannel.IN_APP,)


class NotificationError(ValueError):
    """A notification that cannot be created or moved as asked."""


class InvalidReadStateTransitionError(NotificationError):
    """Raised when a notification is asked to make an illegal move."""


def is_supported_channel(channel: NotificationChannel) -> bool:
    return channel in SUPPORTED_CHANNELS


def is_terminal_delivery(status: DeliveryStatus) -> bool:
    return status in TERMINAL_DELIVERY_STATUSES


def can_transition_read_state(
    from_state: NotificationReadState,
    to_state: NotificationReadState,
) -> bool:
    return to_state in READ_STATE_TRANSITIONS.get(from_state, ())


def validate_read_state_transition(
    from_state: NotificationReadState,
    to_state: NotificationReadState,
) -> None:
    if can_transition_read_state(from_state, to_state):
        return

    raise InvalidReadStateTransitionError(
        f"A notification cannot move from {from_state.value} to {to_state.value}."
    )


__all__ = [
    "AQOS_NOTIFICATION_TYPES_VERSION",
    "DELIVERED_STATUSES",
    "READ_STATE_TRANSITIONS",
    "SUPPORTED_CHANNELS",
    "TERMINAL_DELIVERY_STATUSES",
    "DeliveryStatus",
    "InvalidReadStateTransitionError",
    "NotificationCategory",
    "NotificationChannel",
    "NotificationError",
    "NotificationPriority",
    "NotificationReadState",
    "can_transition_read_state",
    "is_supported_channel",
    "is_terminal_delivery",
    "validate_read_state_transition",
]
