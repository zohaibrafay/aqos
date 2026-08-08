"""
The fixed set of things AQOS can say.

Rendering is deliberately dull: a template is a title and a body with named
placeholders, and filling them is a dictionary lookup. There is no expression
language, no attribute access and no code path that turns caller data into
executable anything — a notification is a sentence, not a program.

Each template declares exactly which variables it accepts. A missing one fails
loudly rather than rendering a raw placeholder at a user, and an unexpected one
is refused rather than silently ignored, because a caller passing a variable
nobody reads has misunderstood something.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any

from aqos.notifications.types import (
    NotificationCategory,
    NotificationError,
    NotificationPriority,
)


AQOS_NOTIFICATION_TEMPLATES_VERSION = "1.0"

#: What a placeholder looks like.
#:
#: A bare name in braces. Nothing else is recognised, so an attribute access or
#: a conversion flag is not a placeholder and cannot reach any formatting
#: machinery.
PLACEHOLDER_PATTERN = re.compile(r"\{([a-z][a-z0-9_]*)\}")

#: Variable names a template may never declare.
#:
#: Not because rendering would break, but because a notification carrying any
#: of them would put a secret, a location or an unvetted blob in front of a
#: user — and in a mailbox, a log and a support ticket after that.
FORBIDDEN_VARIABLES = frozenset(
    {
        "password",
        "password_hash",
        "token",
        "token_hash",
        "secret",
        "credential",
        "broker_credential_ref",
        "broker_account_ref",
        "api_key",
        "path",
        "file_path",
        "report_path",
        "artifact_path",
        "data_path",
        "metadata",
        "extra_metadata",
        "payload",
        "sql",
        "traceback",
        "stack_trace",
    }
)


class TemplateError(NotificationError):
    """A template that cannot be rendered as asked."""


@dataclass(frozen=True)
class NotificationTemplate:
    """One thing AQOS knows how to say."""

    key: str
    category: NotificationCategory
    priority: NotificationPriority
    title: str
    body: str

    def __post_init__(self) -> None:
        if not self.key.strip():
            raise TemplateError("A template needs a key.")

        forbidden = self.variables & FORBIDDEN_VARIABLES

        if forbidden:
            raise TemplateError(
                f"Template {self.key} declares variables that must never reach "
                f"a notification: {', '.join(sorted(forbidden))}."
            )

    @property
    def variables(self) -> frozenset[str]:
        """Every placeholder this template expects, from both fields."""

        return frozenset(
            PLACEHOLDER_PATTERN.findall(self.title)
            + PLACEHOLDER_PATTERN.findall(self.body)
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "key": self.key,
            "category": self.category.value,
            "priority": self.priority.value,
            "variables": sorted(self.variables),
        }


def fill(text: str, values: dict[str, str]) -> str:
    """
    Replace each placeholder with its value.

    Done by substitution rather than by ``str.format``: a format string can
    reach into attributes and indexes of whatever it is given, which would turn
    a template into a small read primitive over the caller's objects.
    """

    return PLACEHOLDER_PATTERN.sub(lambda match: values[match.group(1)], text)


#: Everything AQOS can send. Adding one is a code change, by design.
NOTIFICATION_TEMPLATES: dict[str, NotificationTemplate] = {
    template.key: template
    for template in (
        NotificationTemplate(
            key="signal_status_changed",
            category=NotificationCategory.SIGNAL,
            priority=NotificationPriority.INFO,
            title="Signal {symbol} is now {status}",
            body="Your {action} signal on {symbol} moved to {status}.",
        ),
        NotificationTemplate(
            key="signal_rejected",
            category=NotificationCategory.SIGNAL,
            priority=NotificationPriority.WARNING,
            title="Signal {symbol} was rejected",
            body="The {action} signal on {symbol} was rejected: {reason}.",
        ),
        NotificationTemplate(
            key="signal_missed",
            category=NotificationCategory.SIGNAL,
            priority=NotificationPriority.WARNING,
            title="Signal {symbol} was missed",
            body="The {action} signal on {symbol} was missed: {reason}.",
        ),
        NotificationTemplate(
            key="paper_session_completed",
            category=NotificationCategory.PAPER_TRADING,
            priority=NotificationPriority.INFO,
            title="Paper run {session_name} finished",
            body=(
                "Your simulated run {session_name} completed with "
                "{total_trades} trades. Nothing was traded on a real venue."
            ),
        ),
        NotificationTemplate(
            key="backtest_completed",
            category=NotificationCategory.BACKTEST,
            priority=NotificationPriority.INFO,
            title="Backtest {strategy_name} finished",
            body=(
                "The historical run of {strategy_name} on {symbol} completed "
                "with {total_trades} trades."
            ),
        ),
        NotificationTemplate(
            key="account_rule_breached",
            category=NotificationCategory.FUNDED_RULE,
            priority=NotificationPriority.CRITICAL,
            title="Account {account_name} breached a rule",
            body="{account_name} breached its {rule_name} rule: {reason}.",
        ),
        NotificationTemplate(
            key="report_generated",
            category=NotificationCategory.REPORT,
            priority=NotificationPriority.INFO,
            title="Report ready for {account_name}",
            body="A {report_type} report is ready for {account_name}.",
        ),
        NotificationTemplate(
            key="system_notice",
            category=NotificationCategory.SYSTEM,
            priority=NotificationPriority.INFO,
            title="{title}",
            body="{message}",
        ),
    )
}


def require_template(key: str) -> NotificationTemplate:
    template = NOTIFICATION_TEMPLATES.get(key)

    if template is None:
        raise TemplateError(
            f"Unknown notification template: {key!r}. Templates are fixed; "
            f"known keys are: {', '.join(sorted(NOTIFICATION_TEMPLATES))}."
        )

    return template


@dataclass(frozen=True)
class RenderedNotification:
    """A title and a body, ready to store."""

    template_key: str
    category: NotificationCategory
    priority: NotificationPriority
    title: str
    body: str


def render_template(key: str, variables: dict[str, Any]) -> RenderedNotification:
    """
    Fill one template, or refuse.

    Both directions are checked. A missing variable would render a placeholder
    at a user; an extra one means the caller thinks it is saying something the
    template never says. Values are stringified here so nothing but text is
    ever substituted.
    """

    template = require_template(key)
    expected = template.variables
    supplied = frozenset(variables)

    missing = expected - supplied

    if missing:
        raise TemplateError(f"Template {key} needs {', '.join(sorted(missing))}.")

    unexpected = supplied - expected

    if unexpected:
        raise TemplateError(
            f"Template {key} does not use {', '.join(sorted(unexpected))}."
        )

    values = {name: str(variables[name]) for name in expected}

    return RenderedNotification(
        template_key=template.key,
        category=template.category,
        priority=template.priority,
        title=fill(template.title, values),
        body=fill(template.body, values),
    )


def list_template_keys() -> tuple[str, ...]:
    return tuple(sorted(NOTIFICATION_TEMPLATES))


__all__ = [
    "AQOS_NOTIFICATION_TEMPLATES_VERSION",
    "FORBIDDEN_VARIABLES",
    "NOTIFICATION_TEMPLATES",
    "PLACEHOLDER_PATTERN",
    "NotificationTemplate",
    "RenderedNotification",
    "TemplateError",
    "fill",
    "list_template_keys",
    "render_template",
    "require_template",
]
