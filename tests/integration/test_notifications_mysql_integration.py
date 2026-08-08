"""
Notifications against real MySQL.

The database is the last line of the honesty rules: a row claiming an email was
sent, or a read notification with no time it was read, is refused by a CHECK
constraint even if something bypasses the Python layer entirely. The raw-SQL
tests below prove that rather than assuming it.

Run with::

    AQOS_TEST_DB_URL=mysql+pymysql://user:password@localhost:3306/aqos_test \\
        pytest -m mysql
"""

from __future__ import annotations

import os
from datetime import datetime, timedelta

import pytest
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError, OperationalError

from aqos.database.config import parse_database_url
from aqos.database.engine import AqosDatabase
from aqos.database.migration_runner import apply_migrations
from aqos.notifications import (
    DeliveryStatus,
    NotificationCategory,
    NotificationChannel,
    NotificationError,
    NotificationPriority,
    NotificationReadState,
    NotificationService,
)
from aqos.users.repositories import UserProfileRepository


ENV_TEST_DB_URL = "AQOS_TEST_DB_URL"

FIXED_NOW = datetime(2026, 1, 1, 0, 0, 0)

pytestmark = pytest.mark.mysql


def requires_mysql() -> str:
    url = os.environ.get(ENV_TEST_DB_URL, "").strip()

    if not url:
        pytest.skip(
            f"{ENV_TEST_DB_URL} is not set, so notifications are NOT verified "
            "against MySQL by this run. Run them with:\n"
            "  AQOS_TEST_DB_URL=mysql+pymysql://user:password@localhost:3306/"
            "aqos_test pytest -m mysql"
        )

    return url


def requires_reachable_mysql(url: str) -> None:
    database = AqosDatabase(config=parse_database_url(url))

    try:
        reachable = database.ping()
    except Exception:
        reachable = False
    finally:
        database.dispose()

    if not reachable:
        pytest.skip(
            f"{ENV_TEST_DB_URL} is set but the MySQL server is not reachable, "
            "so notifications are NOT verified by this run. Start MySQL and "
            "run them with:\n"
            "  AQOS_TEST_DB_URL=mysql+pymysql://user:password@localhost:3306/"
            "aqos_test pytest -m mysql"
        )


def reset_tables(database: AqosDatabase) -> None:
    with database.session() as session:
        session.execute(text("SET FOREIGN_KEY_CHECKS = 0"))

        for table in (
            "notification_delivery_attempts",
            "notifications",
            "notification_preferences",
            "user_profiles",
        ):
            session.execute(text(f"TRUNCATE TABLE {table}"))

        session.execute(text("SET FOREIGN_KEY_CHECKS = 1"))


@pytest.fixture
def database_url() -> str:
    url = requires_mysql()
    requires_reachable_mysql(url)

    return url


@pytest.fixture
def notification_database(database_url: str) -> AqosDatabase:
    database = AqosDatabase(config=parse_database_url(database_url))

    apply_migrations(database)
    reset_tables(database)

    yield database

    reset_tables(database)
    database.dispose()


def create_user(database: AqosDatabase, email: str) -> str:
    with database.session() as session:
        return UserProfileRepository(session).create_user(
            email=email,
            display_name=email,
            created_at_utc=FIXED_NOW,
        ).user_id


@pytest.fixture
def alice(notification_database) -> str:
    return create_user(notification_database, "alice@example.com")


@pytest.fixture
def bob(notification_database) -> str:
    return create_user(notification_database, "bob@example.com")


def notify(database: AqosDatabase, user_id: str, **overrides):
    """Create one notification through the service, returning its result."""

    payload = {
        "template_key": "system_notice",
        "variables": {"title": "Hello", "message": "Something happened."},
    }
    payload.update(overrides)

    with database.session() as session:
        result = NotificationService(session).create_from_template(
            user_id=user_id,
            at_utc=FIXED_NOW,
            **payload,
        )

        return result.notification.notification_id


class TestSchema:
    def test_the_tables_exist(self, notification_database) -> None:
        with notification_database.session() as session:
            rows = {
                str(row[0])
                for row in session.execute(
                    text(
                        "SELECT TABLE_NAME FROM information_schema.TABLES "
                        "WHERE TABLE_SCHEMA = DATABASE()"
                    )
                ).all()
            }

        assert {
            "notifications",
            "notification_preferences",
            "notification_delivery_attempts",
        } <= rows

    def test_the_migration_is_idempotent(self, notification_database) -> None:
        apply_migrations(notification_database)


class TestPersistence:
    def test_a_notification_is_stored(self, notification_database, alice) -> None:
        notification_id = notify(notification_database, alice)

        with notification_database.session() as session:
            stored = NotificationService(session).notifications.get(notification_id)

            assert stored is not None
            assert stored.user_id == alice
            assert stored.read_state is NotificationReadState.UNREAD
            assert stored.title == "Hello"

    def test_every_channel_records_an_attempt(
        self,
        notification_database,
        alice,
    ) -> None:
        """
        Including the channels that did nothing.

        A notification with no attempt rows would be indistinguishable from one
        nobody ever tried to deliver.
        """

        notification_id = notify(notification_database, alice)

        with notification_database.session() as session:
            attempts = NotificationService(session).attempts.list_for_notification(
                notification_id
            )

        assert len(attempts) == 3
        assert {attempt.channel for attempt in attempts} == set(NotificationChannel)

    def test_in_app_is_sent_and_the_rest_are_not(
        self,
        notification_database,
        alice,
    ) -> None:
        notification_id = notify(notification_database, alice)

        with notification_database.session() as session:
            attempts = {
                attempt.channel: attempt
                for attempt in NotificationService(session).attempts
                .list_for_notification(notification_id)
            }

        assert attempts[NotificationChannel.IN_APP].status is DeliveryStatus.SENT
        assert attempts[NotificationChannel.EMAIL].status is (
            DeliveryStatus.UNSUPPORTED
        )
        assert attempts[NotificationChannel.PUSH].status is (
            DeliveryStatus.UNSUPPORTED
        )

    def test_an_unsupported_attempt_explains_itself(
        self,
        notification_database,
        alice,
    ) -> None:
        notification_id = notify(notification_database, alice)

        with notification_database.session() as session:
            attempts = NotificationService(session).attempts.list_for_notification(
                notification_id
            )
            email = next(
                attempt
                for attempt in attempts
                if attempt.channel is NotificationChannel.EMAIL
            )

        assert email.reason
        assert email.delivered is False

    def test_a_preference_is_stored_and_honoured(
        self,
        notification_database,
        alice,
    ) -> None:
        with notification_database.session() as session:
            NotificationService(session).preferences.set_preference(
                user_id=alice,
                category=NotificationCategory.SYSTEM,
                channel=NotificationChannel.IN_APP,
                enabled=False,
                at_utc=FIXED_NOW,
            )

        notification_id = notify(notification_database, alice)

        with notification_database.session() as session:
            attempts = {
                attempt.channel: attempt
                for attempt in NotificationService(session).attempts
                .list_for_notification(notification_id)
            }

        # Turned off by the user, so skipped — not unsupported, and not sent.
        assert attempts[NotificationChannel.IN_APP].status is DeliveryStatus.SKIPPED

    def test_setting_a_preference_twice_replaces_it(
        self,
        notification_database,
        alice,
    ) -> None:
        with notification_database.session() as session:
            preferences = NotificationService(session).preferences

            preferences.set_preference(
                alice,
                NotificationCategory.SIGNAL,
                NotificationChannel.IN_APP,
                enabled=False,
                at_utc=FIXED_NOW,
            )
            preferences.set_preference(
                alice,
                NotificationCategory.SIGNAL,
                NotificationChannel.IN_APP,
                enabled=True,
                at_utc=FIXED_NOW,
            )

        with notification_database.session() as session:
            stored = NotificationService(session).preferences.list_for_user(alice)

        assert len(stored) == 1
        assert stored[0].enabled is True

    def test_deleting_a_user_takes_their_notifications(
        self,
        notification_database,
        alice,
    ) -> None:
        notify(notification_database, alice)

        with notification_database.session() as session:
            UserProfileRepository(session).delete_user(alice)

        with notification_database.session() as session:
            assert (
                NotificationService(session).list_user_notifications(alice) == ()
            )

    def test_deleting_a_notification_takes_its_attempts(
        self,
        notification_database,
        alice,
    ) -> None:
        notification_id = notify(notification_database, alice)

        with notification_database.session() as session:
            service = NotificationService(session)
            service.notifications.delete_by_primary_key(notification_id)

        with notification_database.session() as session:
            assert (
                NotificationService(session).attempts.list_for_notification(
                    notification_id
                )
                == ()
            )


class TestOwnership:
    def test_a_user_sees_only_their_own(
        self,
        notification_database,
        alice,
        bob,
    ) -> None:
        notify(notification_database, alice)
        notify(notification_database, bob)

        with notification_database.session() as session:
            service = NotificationService(session)

            assert len(service.list_user_notifications(alice)) == 1
            assert len(service.list_user_notifications(bob)) == 1

    def test_another_users_notification_is_reported_absent(
        self,
        notification_database,
        alice,
        bob,
    ) -> None:
        """Identical to one that never existed, so ids cannot be probed."""

        notification_id = notify(notification_database, alice)

        with notification_database.session() as session:
            service = NotificationService(session)

            with pytest.raises(NotificationError) as foreign:
                service.mark_read(notification_id, bob)

            with pytest.raises(NotificationError) as missing:
                service.mark_read("notification_nope", bob)

        assert "was not found" in str(foreign.value)
        assert "was not found" in str(missing.value)

    def test_another_user_cannot_archive_it(
        self,
        notification_database,
        alice,
        bob,
    ) -> None:
        notification_id = notify(notification_database, alice)

        with notification_database.session() as session:
            with pytest.raises(NotificationError):
                NotificationService(session).archive(notification_id, bob)

        with notification_database.session() as session:
            stored = NotificationService(session).notifications.get(notification_id)

            assert stored is not None
            assert stored.read_state is NotificationReadState.UNREAD


class TestReadState:
    def test_marking_read_persists(self, notification_database, alice) -> None:
        notification_id = notify(notification_database, alice)

        with notification_database.session() as session:
            NotificationService(session).mark_read(notification_id, alice, FIXED_NOW)

        with notification_database.session() as session:
            stored = NotificationService(session).notifications.get(notification_id)

            assert stored is not None
            assert stored.read_state is NotificationReadState.READ
            assert stored.read_at_utc == FIXED_NOW

    def test_marking_unread_clears_the_timestamp(
        self,
        notification_database,
        alice,
    ) -> None:
        notification_id = notify(notification_database, alice)

        with notification_database.session() as session:
            service = NotificationService(session)
            service.mark_read(notification_id, alice, FIXED_NOW)
            service.mark_unread(notification_id, alice, FIXED_NOW)

        with notification_database.session() as session:
            stored = NotificationService(session).notifications.get(notification_id)

            assert stored is not None
            assert stored.read_at_utc is None

    def test_an_archived_notification_cannot_return(
        self,
        notification_database,
        alice,
    ) -> None:
        notification_id = notify(notification_database, alice)

        with notification_database.session() as session:
            service = NotificationService(session)
            service.archive(notification_id, alice, FIXED_NOW)

            with pytest.raises(NotificationError):
                service.mark_unread(notification_id, alice, FIXED_NOW)


class TestCounts:
    def test_the_unread_count_is_measured(
        self,
        notification_database,
        alice,
    ) -> None:
        for _ in range(3):
            notify(notification_database, alice)

        with notification_database.session() as session:
            assert NotificationService(session).unread_count(alice) == 3

    def test_a_caught_up_user_reads_zero(
        self,
        notification_database,
        alice,
    ) -> None:
        """
        Nought unread is a measured fact, not an absence.

        A user who has read everything is caught up; that is different from a
        user with no notifications at all, which the list answers.
        """

        notification_id = notify(notification_database, alice)

        with notification_database.session() as session:
            NotificationService(session).mark_read(notification_id, alice, FIXED_NOW)

        with notification_database.session() as session:
            service = NotificationService(session)

            assert service.unread_count(alice) == 0
            assert len(service.list_user_notifications(alice)) == 1

    def test_a_user_with_nothing_reads_zero_too(
        self,
        notification_database,
        alice,
    ) -> None:
        with notification_database.session() as session:
            service = NotificationService(session)

            assert service.unread_count(alice) == 0
            assert service.list_user_notifications(alice) == ()

    def test_every_state_is_counted_including_the_empty_ones(
        self,
        notification_database,
        alice,
    ) -> None:
        notify(notification_database, alice)

        with notification_database.session() as session:
            counts = NotificationService(session).notifications.count_by_state(alice)

        assert counts == {"unread": 1, "read": 0, "archived": 0}

    def test_delivery_counts_cover_every_status(
        self,
        notification_database,
        alice,
    ) -> None:
        notification_id = notify(notification_database, alice)

        with notification_database.session() as session:
            counts = NotificationService(session).attempts.count_by_status(
                notification_id
            )

        assert counts["sent"] == 1
        assert counts["unsupported"] == 2
        assert counts["failed"] == 0

    def test_delivered_means_something_actually_arrived(
        self,
        notification_database,
        alice,
    ) -> None:
        notification_id = notify(notification_database, alice)

        with notification_database.session() as session:
            assert (
                NotificationService(session).attempts.was_delivered(notification_id)
                is True
            )


class TestTheDatabaseEnforcesHonesty:
    """
    Raw SQL, bypassing every Python check.

    These prove the constraints are real rather than decorative: a bug, a
    migration script or a console session cannot write a row that lies.
    """

    def _insert_notification(self, session, **overrides) -> None:
        payload = {
            "notification_id": "notification_raw",
            "user_id": overrides.pop("user_id"),
            "category": "system",
            "priority": "info",
            "read_state": "unread",
            "template_key": "system_notice",
            "title": "T",
            "body": "B",
            "created_at_utc": FIXED_NOW,
            "read_at_utc": None,
            "archived_at_utc": None,
        }
        payload.update(overrides)

        session.execute(
            text(
                "INSERT INTO notifications (notification_id, user_id, category, "
                "priority, read_state, template_key, title, body, "
                "created_at_utc, read_at_utc, archived_at_utc) VALUES "
                "(:notification_id, :user_id, :category, :priority, "
                ":read_state, :template_key, :title, :body, :created_at_utc, "
                ":read_at_utc, :archived_at_utc)"
            ),
            payload,
        )

    def test_an_unknown_category_is_refused(
        self,
        notification_database,
        alice,
    ) -> None:
        with pytest.raises((IntegrityError, OperationalError)):
            with notification_database.session() as session:
                self._insert_notification(
                    session, user_id=alice, category="whatever"
                )

    def test_an_unknown_read_state_is_refused(
        self,
        notification_database,
        alice,
    ) -> None:
        with pytest.raises((IntegrityError, OperationalError)):
            with notification_database.session() as session:
                self._insert_notification(
                    session, user_id=alice, read_state="skimmed"
                )

    def test_a_read_notification_needs_a_read_time(
        self,
        notification_database,
        alice,
    ) -> None:
        # Otherwise a row could claim to be read with no record of when.
        with pytest.raises((IntegrityError, OperationalError)):
            with notification_database.session() as session:
                self._insert_notification(
                    session, user_id=alice, read_state="read", read_at_utc=None
                )

    def test_an_unread_notification_cannot_claim_a_read_time(
        self,
        notification_database,
        alice,
    ) -> None:
        with pytest.raises((IntegrityError, OperationalError)):
            with notification_database.session() as session:
                self._insert_notification(
                    session,
                    user_id=alice,
                    read_state="unread",
                    read_at_utc=FIXED_NOW,
                )

    def test_only_in_app_may_be_recorded_as_sent(
        self,
        notification_database,
        alice,
    ) -> None:
        """
        The constraint that matters most.

        Email and push have no provider. A row claiming either was sent would
        be a record of something that did not happen, and MySQL refuses it
        whatever wrote the statement.
        """

        notification_id = notify(notification_database, alice)

        with pytest.raises((IntegrityError, OperationalError)):
            with notification_database.session() as session:
                session.execute(
                    text(
                        "INSERT INTO notification_delivery_attempts "
                        "(attempt_id, notification_id, channel, status, "
                        "reason, attempted_at_utc) VALUES "
                        "('a_raw', :notification_id, 'email', 'sent', NULL, "
                        ":at)"
                    ),
                    {"notification_id": notification_id, "at": FIXED_NOW},
                )

    def test_in_app_may_be_recorded_as_sent(
        self,
        notification_database,
        alice,
    ) -> None:
        """The positive control: the constraint refuses a lie, not everything."""

        notification_id = notify(notification_database, alice)

        with notification_database.session() as session:
            session.execute(
                text(
                    "INSERT INTO notification_delivery_attempts "
                    "(attempt_id, notification_id, channel, status, reason, "
                    "attempted_at_utc) VALUES "
                    "('a_ok', :notification_id, 'in_app', 'sent', NULL, :at)"
                ),
                {"notification_id": notification_id, "at": FIXED_NOW},
            )

    def test_an_unknown_delivery_status_is_refused(
        self,
        notification_database,
        alice,
    ) -> None:
        notification_id = notify(notification_database, alice)

        with pytest.raises((IntegrityError, OperationalError)):
            with notification_database.session() as session:
                session.execute(
                    text(
                        "INSERT INTO notification_delivery_attempts "
                        "(attempt_id, notification_id, channel, status, "
                        "reason, attempted_at_utc) VALUES "
                        "('a_bad', :notification_id, 'in_app', 'probably', "
                        "NULL, :at)"
                    ),
                    {"notification_id": notification_id, "at": FIXED_NOW},
                )

    def test_one_preference_per_user_category_and_channel(
        self,
        notification_database,
        alice,
    ) -> None:
        with pytest.raises((IntegrityError, OperationalError)):
            with notification_database.session() as session:
                for index in range(2):
                    session.execute(
                        text(
                            "INSERT INTO notification_preferences "
                            "(preference_id, user_id, category, channel, "
                            "enabled, created_at_utc, updated_at_utc) VALUES "
                            "(:pid, :user_id, 'signal', 'in_app', 1, :at, :at)"
                        ),
                        {"pid": f"p{index}", "user_id": alice, "at": FIXED_NOW},
                    )


class TestServiceRefusesDishonestRecords:
    def test_it_will_not_record_an_email_as_sent(
        self,
        notification_database,
        alice,
    ) -> None:
        notification_id = notify(notification_database, alice)

        with notification_database.session() as session:
            with pytest.raises(ValueError):
                NotificationService(session).record_delivery_attempt(
                    notification_id=notification_id,
                    user_id=alice,
                    channel=NotificationChannel.EMAIL,
                    status=DeliveryStatus.SENT,
                )

    def test_it_will_record_an_email_as_failed(
        self,
        notification_database,
        alice,
    ) -> None:
        """Failure is a real outcome; it is only `sent` that must be earned."""

        notification_id = notify(notification_database, alice)

        with notification_database.session() as session:
            attempt = NotificationService(session).record_delivery_attempt(
                notification_id=notification_id,
                user_id=alice,
                channel=NotificationChannel.EMAIL,
                status=DeliveryStatus.FAILED,
                reason="Nothing to send with.",
                at_utc=FIXED_NOW,
            )

            assert attempt.status is DeliveryStatus.FAILED
            assert attempt.delivered is False
