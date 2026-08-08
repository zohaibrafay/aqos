"""
Unit tests for the ownership rules behind the protected read endpoints.

These are pure decisions about a caller and a record, so they need no database
and no HTTP client. The wiring — that every route actually applies them — is
proven against real MySQL in the protection integration suite.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta

import pytest

from aqos.http_api.auth import AuthenticatedCaller
from aqos.http_api.authz import (
    CROSS_USER_FILTER_MESSAGE,
    DEFAULT_NOT_FOUND_MESSAGE,
    NOT_FOUND_MESSAGE_BY_RESOURCE,
    assert_owned_by_caller,
    not_found_for,
    require_owned_record,
    resolve_scoped_user_id,
)
from aqos.http_api.errors import ApiErrorCode, AqosApiError, NotFoundApiError
from aqos.users.models import UserProfile, UserRole, UserSession, UserStatus


FIXED_NOW = datetime(2026, 1, 1, 0, 0, 0)

OWNER_ID = "user_owner"
STRANGER_ID = "user_stranger"


def build_caller(user_id: str = OWNER_ID) -> AuthenticatedCaller:
    return AuthenticatedCaller(
        user=UserProfile(
            user_id=user_id,
            email=f"{user_id}@example.com",
            display_name=user_id,
            role=UserRole.TRADER,
            status=UserStatus.ACTIVE,
            created_at_utc=FIXED_NOW,
            updated_at_utc=FIXED_NOW,
        ),
        session=UserSession(
            session_id=f"session_{user_id}",
            user_id=user_id,
            token_hash="a" * 64,
            created_at_utc=FIXED_NOW,
            expires_at_utc=FIXED_NOW + timedelta(hours=1),
        ),
    )


@dataclass
class FakeRecord:
    """Any owned row; only the owner column matters here."""

    user_id: str


@dataclass
class OwnerlessRecord:
    """A row with no owner column at all."""

    name: str = "unowned"


def describe(error: AqosApiError) -> tuple:
    """Everything a caller can observe about a refusal."""

    return (error.code, error.status_code, error.message, error.details)


class TestScopedUserId:
    def test_an_absent_filter_means_my_own_data(self) -> None:
        caller = build_caller()

        assert resolve_scoped_user_id(caller, None) == OWNER_ID

    def test_my_own_id_is_accepted(self) -> None:
        """Stating the obvious is allowed; clients should not have to omit it."""

        caller = build_caller()

        assert resolve_scoped_user_id(caller, OWNER_ID) == OWNER_ID

    def test_another_user_is_refused(self) -> None:
        caller = build_caller()

        with pytest.raises(AqosApiError) as raised:
            resolve_scoped_user_id(caller, STRANGER_ID)

        assert raised.value.code is ApiErrorCode.FORBIDDEN
        assert raised.value.status_code == 403
        assert raised.value.message == CROSS_USER_FILTER_MESSAGE

    def test_the_refusal_is_never_silently_narrowed(self) -> None:
        """
        A cross-user filter must raise, never fall back to the caller.

        Returning the caller's own id would answer a question nobody asked and
        would make the attempt invisible.
        """

        caller = build_caller()

        with pytest.raises(AqosApiError):
            resolve_scoped_user_id(caller, STRANGER_ID)

    def test_an_empty_string_is_not_treated_as_absent(self) -> None:
        """Only ``None`` means "unspecified"; an empty id is a real mismatch."""

        caller = build_caller()

        with pytest.raises(AqosApiError):
            resolve_scoped_user_id(caller, "")

    def test_the_refusal_leaks_no_other_user(self) -> None:
        """Only what the caller already sent comes back."""

        caller = build_caller()

        with pytest.raises(AqosApiError) as raised:
            resolve_scoped_user_id(caller, STRANGER_ID)

        assert raised.value.details == {"requested_user_id": STRANGER_ID}
        assert OWNER_ID not in str(raised.value.details)


class TestNotFoundFor:
    @pytest.mark.parametrize(
        "resource",
        sorted(NOT_FOUND_MESSAGE_BY_RESOURCE),
    )
    def test_each_known_resource_has_its_own_wording(
        self,
        resource: str,
    ) -> None:
        error = not_found_for(resource, "id_1")

        assert error.message == NOT_FOUND_MESSAGE_BY_RESOURCE[resource]
        assert error.details == {f"{resource}_id": "id_1"}

    def test_an_unknown_resource_falls_back(self) -> None:
        error = not_found_for("widget", "id_1")

        assert error.message == DEFAULT_NOT_FOUND_MESSAGE
        assert error.details == {"widget_id": "id_1"}

    def test_it_is_a_not_found_error(self) -> None:
        error = not_found_for("signal", "id_1")

        assert isinstance(error, NotFoundApiError)
        assert error.code is ApiErrorCode.NOT_FOUND
        assert error.status_code == 404


class TestOwnershipAssertion:
    def test_the_owner_passes(self) -> None:
        assert_owned_by_caller(build_caller(), OWNER_ID, "signal", "signal_1")

    def test_a_stranger_is_refused(self) -> None:
        with pytest.raises(NotFoundApiError):
            assert_owned_by_caller(
                build_caller(),
                STRANGER_ID,
                "signal",
                "signal_1",
            )

    def test_an_unowned_record_is_refused(self) -> None:
        """A row with no owner belongs to nobody, so it belongs to nobody here."""

        with pytest.raises(NotFoundApiError):
            assert_owned_by_caller(build_caller(), None, "signal", "signal_1")


class TestRequireOwnedRecord:
    def test_it_returns_the_owned_record(self) -> None:
        record = FakeRecord(user_id=OWNER_ID)

        assert require_owned_record(
            build_caller(),
            record,
            "signal",
            "signal_1",
        ) is record

    def test_a_missing_record_is_refused(self) -> None:
        with pytest.raises(NotFoundApiError):
            require_owned_record(build_caller(), None, "signal", "signal_1")

    def test_somebody_elses_record_is_refused(self) -> None:
        with pytest.raises(NotFoundApiError):
            require_owned_record(
                build_caller(),
                FakeRecord(user_id=STRANGER_ID),
                "signal",
                "signal_1",
            )

    def test_absence_and_foreign_ownership_are_indistinguishable(self) -> None:
        """
        The property that stops ids being probed.

        If a foreign record answered differently from a missing one, a caller
        could walk the id space and learn which ids exist on other accounts.
        """

        caller = build_caller()

        with pytest.raises(NotFoundApiError) as missing:
            require_owned_record(caller, None, "signal", "signal_1")

        with pytest.raises(NotFoundApiError) as foreign:
            require_owned_record(
                caller,
                FakeRecord(user_id=STRANGER_ID),
                "signal",
                "signal_1",
            )

        assert describe(missing.value) == describe(foreign.value)

    def test_a_record_without_an_owner_column_is_refused(self) -> None:
        """
        An unknown owner is not an absent check.

        ``getattr`` yields ``None`` for a row that carries no owner, and that
        must refuse rather than fall through to "unowned, so allowed".
        """

        with pytest.raises(NotFoundApiError):
            require_owned_record(
                build_caller(),
                OwnerlessRecord(),
                "signal",
                "signal_1",
            )

    def test_a_different_owner_column_can_be_named(self) -> None:
        @dataclass
        class OtherRecord:
            owner_id: str

        record = OtherRecord(owner_id=OWNER_ID)

        assert require_owned_record(
            build_caller(),
            record,
            "report",
            "report_1",
            owner_attribute="owner_id",
        ) is record

    def test_naming_a_column_the_record_lacks_refuses(self) -> None:
        """A typo in the column name must deny, never allow."""

        with pytest.raises(NotFoundApiError):
            require_owned_record(
                build_caller(),
                FakeRecord(user_id=OWNER_ID),
                "report",
                "report_1",
                owner_attribute="owner_id",
            )
