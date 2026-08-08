"""
Unit tests for the notification foundation.

The recurring theme is honesty: a notification that reached nobody must say so,
and the four ways it can fail to arrive must stay distinguishable.
"""

from __future__ import annotations

from datetime import datetime

import pytest

from aqos.notifications import (
    CHANNEL_DISABLED_REASON,
    CHANNEL_UNSUPPORTED_REASON,
    DEFAULT_ENABLED_CHANNELS,
    FORBIDDEN_VARIABLES,
    NOTIFICATION_TEMPLATES,
    SUPPORTED_CHANNELS,
    DeliveryOutcome,
    DeliveryStatus,
    InAppDeliveryBackend,
    InvalidReadStateTransitionError,
    Notification,
    NotificationCategory,
    NotificationChannel,
    NotificationDeliveryAttempt,
    NotificationError,
    NotificationPriority,
    NotificationReadState,
    NotificationTemplate,
    TemplateError,
    UnsupportedDeliveryBackend,
    assert_delivery_is_honest,
    build_delivery_backends,
    can_transition_read_state,
    default_enabled,
    is_supported_channel,
    list_template_keys,
    render_template,
    require_template,
    resolve_preference,
    validate_read_state_transition,
)


FIXED_NOW = datetime(2026, 1, 1, 0, 0, 0)


def build_notification(**overrides) -> Notification:
    payload = {
        "notification_id": "notification_1",
        "user_id": "user_1",
        "category": NotificationCategory.SIGNAL,
        "priority": NotificationPriority.INFO,
        "template_key": "system_notice",
        "title": "A title",
        "body": "A body.",
        "created_at_utc": FIXED_NOW,
    }
    payload.update(overrides)

    return Notification(**payload)


class TestVocabulary:
    def test_only_in_app_is_deliverable(self) -> None:
        """
        Email and push exist in the vocabulary but nothing delivers them.

        Keeping them nameable lets preferences and templates be written now;
        marking them unsupported keeps AQOS from claiming they arrived.
        """

        assert SUPPORTED_CHANNELS == (NotificationChannel.IN_APP,)
        assert is_supported_channel(NotificationChannel.IN_APP) is True
        assert is_supported_channel(NotificationChannel.EMAIL) is False
        assert is_supported_channel(NotificationChannel.PUSH) is False

    def test_skipped_and_failed_are_different_facts(self) -> None:
        # One was never attempted; the other was attempted and did not arrive.
        assert DeliveryStatus.SKIPPED is not DeliveryStatus.FAILED
        assert DeliveryStatus.UNSUPPORTED is not DeliveryStatus.SKIPPED
        assert DeliveryStatus.UNSUPPORTED is not DeliveryStatus.FAILED

    def test_only_sent_means_delivered(self) -> None:
        for status in DeliveryStatus:
            attempt = NotificationDeliveryAttempt(
                attempt_id="a",
                notification_id="n",
                channel=NotificationChannel.IN_APP,
                status=status,
                attempted_at_utc=FIXED_NOW,
            )

            assert attempt.delivered is (status == DeliveryStatus.SENT)

    def test_archiving_is_one_way(self) -> None:
        """Something filed away is done with; letting it return is meaningless."""

        assert can_transition_read_state(
            NotificationReadState.ARCHIVED, NotificationReadState.UNREAD
        ) is False
        assert can_transition_read_state(
            NotificationReadState.UNREAD, NotificationReadState.ARCHIVED
        ) is True

    def test_an_illegal_move_is_refused(self) -> None:
        with pytest.raises(InvalidReadStateTransitionError):
            validate_read_state_transition(
                NotificationReadState.ARCHIVED, NotificationReadState.READ
            )


class TestTemplates:
    def test_the_templates_are_a_fixed_list(self) -> None:
        assert set(list_template_keys()) == {
            "signal_status_changed",
            "signal_rejected",
            "signal_missed",
            "paper_session_completed",
            "backtest_completed",
            "account_rule_breached",
            "report_generated",
            "system_notice",
        }

    def test_an_unknown_template_is_refused(self) -> None:
        with pytest.raises(TemplateError):
            require_template("please_run_this")

    def test_it_renders_what_it_was_given(self) -> None:
        rendered = render_template(
            "signal_rejected",
            {"symbol": "XAUUSD", "action": "buy", "reason": "spread too high"},
        )

        assert rendered.title == "Signal XAUUSD was rejected"
        assert "spread too high" in rendered.body
        assert rendered.category is NotificationCategory.SIGNAL
        assert rendered.priority is NotificationPriority.WARNING

    def test_a_missing_variable_fails_loudly(self) -> None:
        """Rendering a raw placeholder at a user is worse than an error."""

        with pytest.raises(TemplateError) as raised:
            render_template("signal_rejected", {"symbol": "XAUUSD"})

        assert "action" in str(raised.value)

    def test_an_unused_variable_is_refused(self) -> None:
        # A caller passing something nobody reads has misunderstood.
        with pytest.raises(TemplateError):
            render_template(
                "signal_rejected",
                {
                    "symbol": "X",
                    "action": "buy",
                    "reason": "r",
                    "internal_note": "secret",
                },
            )

    def test_no_template_declares_a_forbidden_variable(self) -> None:
        for template in NOTIFICATION_TEMPLATES.values():
            assert not (template.variables & FORBIDDEN_VARIABLES)

    def test_a_template_naming_a_secret_is_refused(self) -> None:
        with pytest.raises(TemplateError):
            NotificationTemplate(
                key="leaky",
                category=NotificationCategory.SYSTEM,
                priority=NotificationPriority.INFO,
                title="Hello",
                body="Your token is {token_hash}.",
            )

    def test_a_value_cannot_reach_into_an_object(self) -> None:
        """
        Substitution, not formatting.

        A format string can walk attributes of whatever it is handed, which
        would turn a template into a small read primitive over caller objects.
        """

        class Probe:
            secret = "do-not-render"

            def __str__(self) -> str:
                return "probe"

        rendered = render_template(
            "system_notice", {"title": "T", "message": Probe()}
        )

        assert rendered.body == "probe"
        assert "do-not-render" not in rendered.body

    def test_braces_in_a_value_are_not_re_expanded(self) -> None:
        rendered = render_template(
            "system_notice", {"title": "T", "message": "{title}"}
        )

        assert rendered.body == "{title}"


class TestPreferences:
    def test_in_app_is_on_by_default(self) -> None:
        assert DEFAULT_ENABLED_CHANNELS == (NotificationChannel.IN_APP,)
        assert default_enabled(NotificationChannel.IN_APP) is True

    def test_email_and_push_are_off_by_default(self) -> None:
        """
        Nothing delivers either, so a default of on would subscribe every user
        to something that never arrives.
        """

        assert default_enabled(NotificationChannel.EMAIL) is False
        assert default_enabled(NotificationChannel.PUSH) is False

    def test_an_unsupported_channel_is_refused_whatever_the_user_chose(self) -> None:
        # Blaming the user for a gap in the deployment would be wrong.
        resolved = resolve_preference(
            NotificationCategory.SIGNAL, NotificationChannel.EMAIL, stored=True
        )

        assert resolved.allowed is False
        assert resolved.reason == CHANNEL_UNSUPPORTED_REASON

    def test_a_disabled_channel_says_so(self) -> None:
        resolved = resolve_preference(
            NotificationCategory.SIGNAL, NotificationChannel.IN_APP, stored=False
        )

        assert resolved.allowed is False
        assert resolved.reason == CHANNEL_DISABLED_REASON

    def test_the_two_refusals_are_distinguishable(self) -> None:
        unsupported = resolve_preference(
            NotificationCategory.SIGNAL, NotificationChannel.PUSH, stored=True
        )
        disabled = resolve_preference(
            NotificationCategory.SIGNAL, NotificationChannel.IN_APP, stored=False
        )

        assert unsupported.reason != disabled.reason

    def test_an_enabled_supported_channel_is_allowed(self) -> None:
        resolved = resolve_preference(
            NotificationCategory.SIGNAL, NotificationChannel.IN_APP, stored=True
        )

        assert resolved.allowed is True
        assert resolved.reason is None


class TestDelivery:
    def test_in_app_delivers(self) -> None:
        outcome = InAppDeliveryBackend().deliver("notification_1")

        assert outcome.status is DeliveryStatus.SENT
        assert outcome.delivered is True

    def test_email_and_push_report_unsupported(self) -> None:
        backends = build_delivery_backends()

        for channel in (NotificationChannel.EMAIL, NotificationChannel.PUSH):
            outcome = backends[channel].deliver("notification_1")

            assert outcome.status is DeliveryStatus.UNSUPPORTED
            assert outcome.delivered is False
            assert outcome.status is not DeliveryStatus.SENT

    def test_an_unsupported_reason_explains_and_points_somewhere_useful(self) -> None:
        outcome = build_delivery_backends()[NotificationChannel.EMAIL].deliver("n")

        assert "no email provider" in (outcome.reason or "")
        assert "available in the app" in (outcome.reason or "")

    def test_every_channel_has_a_backend(self) -> None:
        backends = build_delivery_backends()

        for channel in NotificationChannel:
            assert channel in backends

    def test_a_dishonest_outcome_is_refused(self) -> None:
        """
        The check that stops a future provider stub from lying.

        A backend that started reporting `sent` on a channel this deployment
        cannot reach would write a record saying a user was told something they
        never were.
        """

        with pytest.raises(ValueError):
            assert_delivery_is_honest(
                NotificationChannel.EMAIL,
                DeliveryOutcome(
                    channel=NotificationChannel.EMAIL,
                    status=DeliveryStatus.SENT,
                ),
            )

    def test_an_honest_outcome_passes(self) -> None:
        assert_delivery_is_honest(
            NotificationChannel.IN_APP,
            DeliveryOutcome(
                channel=NotificationChannel.IN_APP, status=DeliveryStatus.SENT
            ),
        )
        assert_delivery_is_honest(
            NotificationChannel.EMAIL,
            DeliveryOutcome(
                channel=NotificationChannel.EMAIL,
                status=DeliveryStatus.UNSUPPORTED,
            ),
        )

    def test_an_unsupported_backend_never_sends(self) -> None:
        backend = UnsupportedDeliveryBackend(
            NotificationChannel.PUSH, "no provider"
        )

        assert backend.deliver("n").status is DeliveryStatus.UNSUPPORTED


class TestNotificationModel:
    def test_it_starts_unread(self) -> None:
        # Set in __init__ rather than by a column default, so a transient
        # object read before a flush carries the real value.
        assert build_notification().read_state is NotificationReadState.UNREAD

    def test_marking_read_records_when(self) -> None:
        notification = build_notification()
        notification.move_to(NotificationReadState.READ, FIXED_NOW)

        assert notification.read_at_utc == FIXED_NOW
        assert notification.is_unread is False

    def test_marking_unread_undoes_the_timestamp(self) -> None:
        """A lingering read time would be a half-truth."""

        notification = build_notification()
        notification.move_to(NotificationReadState.READ, FIXED_NOW)
        notification.move_to(NotificationReadState.UNREAD, FIXED_NOW)

        assert notification.read_at_utc is None

    def test_archiving_records_when(self) -> None:
        notification = build_notification()
        notification.move_to(NotificationReadState.ARCHIVED, FIXED_NOW)

        assert notification.archived_at_utc == FIXED_NOW
        assert notification.is_archived is True

    def test_an_archived_notification_cannot_come_back(self) -> None:
        notification = build_notification()
        notification.move_to(NotificationReadState.ARCHIVED, FIXED_NOW)

        with pytest.raises(InvalidReadStateTransitionError):
            notification.move_to(NotificationReadState.UNREAD, FIXED_NOW)

    @pytest.mark.parametrize("field", ["title", "body"])
    def test_it_refuses_empty_text(self, field: str) -> None:
        with pytest.raises(NotificationError):
            build_notification(**{field: "   "})

    def test_it_refuses_an_oversized_title(self) -> None:
        with pytest.raises(NotificationError):
            build_notification(title="x" * 500)


class TestNothingSensitiveIsSerialized:
    def test_the_payload_carries_no_secret(self) -> None:
        """
        A notification is text a template produced plus identifiers.

        There is no metadata column for a secret to hide in, and this asserts
        the serialized form stays that way.
        """

        payload = build_notification(
            account_id="account_1", signal_id="signal_1"
        ).to_dict()
        rendered = str(payload)

        for forbidden in (
            "password",
            "token_hash",
            "secret",
            "credential",
            "broker_credential_ref",
            "extra_metadata",
            "metadata",
            "payload",
            "traceback",
            "/srv/",
        ):
            assert forbidden not in rendered

    def test_the_keys_are_exactly_these(self) -> None:
        assert set(build_notification().to_dict()) == {
            "notification_id",
            "user_id",
            "category",
            "priority",
            "read_state",
            "template_key",
            "title",
            "body",
            "account_id",
            "signal_id",
            "paper_session_id",
            "backtest_id",
            "report_id",
            "created_at_utc",
            "read_at_utc",
            "archived_at_utc",
        }

    def test_a_delivery_attempt_carries_no_provider_detail(self) -> None:
        payload = NotificationDeliveryAttempt(
            attempt_id="a",
            notification_id="n",
            channel=NotificationChannel.EMAIL,
            status=DeliveryStatus.UNSUPPORTED,
            reason="AQOS has no email provider configured.",
            attempted_at_utc=FIXED_NOW,
        ).to_dict()

        assert set(payload) == {
            "attempt_id",
            "notification_id",
            "channel",
            "status",
            "reason",
            "delivered",
            "attempted_at_utc",
        }
        assert payload["delivered"] is False
