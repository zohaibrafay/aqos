"""
What a user has asked to hear about, and on which channel.

The defaults are the interesting part. In-app is on because an in-app
notification is a row this system already owns — writing one delivers it, and a
user who never chose would otherwise see nothing at all. Email and push are off
because nothing delivers either yet, and a default of "on" for a channel with
no provider would mean every user is silently subscribed to something that will
never arrive.

When a provider does exist, turning that default on is a deliberate change with
a migration behind it, not a side effect of the provider appearing.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from aqos.notifications.types import (
    NotificationCategory,
    NotificationChannel,
    is_supported_channel,
)


AQOS_NOTIFICATION_PREFERENCES_VERSION = "1.0"

#: Channels a user gets without asking.
#:
#: Only the one this deployment can actually deliver.
DEFAULT_ENABLED_CHANNELS = (NotificationChannel.IN_APP,)


def default_enabled(
    channel: NotificationChannel,
    _category: NotificationCategory | None = None,
) -> bool:
    """
    Whether a channel is on for somebody who never chose.

    The category is accepted but unused: no category is quieter than another by
    default, and pretending otherwise would hide things from people who never
    asked to have them hidden.
    """

    return channel in DEFAULT_ENABLED_CHANNELS


@dataclass(frozen=True)
class ResolvedPreference:
    """
    Whether one notification may go out on one channel, and why not.

    ``allowed`` is the whole answer; ``reason`` explains a refusal in AQOS's own
    words so a delivery attempt can record something better than "no".
    """

    category: NotificationCategory
    channel: NotificationChannel
    allowed: bool
    reason: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "category": self.category.value,
            "channel": self.channel.value,
            "allowed": self.allowed,
            "reason": self.reason,
        }


#: Why a channel was not used.
CHANNEL_UNSUPPORTED_REASON = (
    "This deployment has no provider for that channel, so nothing was sent."
)

CHANNEL_DISABLED_REASON = "The recipient has turned that channel off."


def resolve_preference(
    category: NotificationCategory,
    channel: NotificationChannel,
    stored: bool | None = None,
) -> ResolvedPreference:
    """
    Decide whether one channel may carry one category.

    Support is checked before the user's own setting, and deliberately so: a
    channel nothing can deliver is unsupported whatever anybody has chosen, and
    reporting it as "the user turned it off" would blame them for a gap in the
    deployment.
    """

    if not is_supported_channel(channel):
        return ResolvedPreference(
            category=category,
            channel=channel,
            allowed=False,
            reason=CHANNEL_UNSUPPORTED_REASON,
        )

    enabled = default_enabled(channel, category) if stored is None else bool(stored)

    if not enabled:
        return ResolvedPreference(
            category=category,
            channel=channel,
            allowed=False,
            reason=CHANNEL_DISABLED_REASON,
        )

    return ResolvedPreference(category=category, channel=channel, allowed=True)


__all__ = [
    "AQOS_NOTIFICATION_PREFERENCES_VERSION",
    "CHANNEL_DISABLED_REASON",
    "CHANNEL_UNSUPPORTED_REASON",
    "DEFAULT_ENABLED_CHANNELS",
    "ResolvedPreference",
    "default_enabled",
    "resolve_preference",
]
