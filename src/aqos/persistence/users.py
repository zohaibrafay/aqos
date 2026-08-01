from __future__ import annotations

from dataclasses import dataclass, field as dataclass_field
from enum import Enum
from typing import Any

from aqos.persistence.database import AqosDatabase
from aqos.persistence.records import (
    build_record_id,
    decode_json_field,
    encode_json_field,
    normalize_email,
    normalize_required_text,
    record_utc_now,
)
from aqos.persistence.schema import ensure_aqos_schema


AQOS_USER_PROFILE_VERSION = "1.0"


class UserRole(str, Enum):
    OWNER = "owner"
    ADMIN = "admin"
    TRADER = "trader"
    ANALYST = "analyst"
    VIEWER = "viewer"


class UserStatus(str, Enum):
    ACTIVE = "active"
    SUSPENDED = "suspended"
    DISABLED = "disabled"


READ_ONLY_USER_ROLES = (UserRole.ANALYST, UserRole.VIEWER)


@dataclass(frozen=True)
class UserProfile:
    user_id: str
    email: str
    display_name: str
    role: UserRole
    status: UserStatus
    created_at_utc: str
    updated_at_utc: str
    timezone: str = "UTC"
    locale: str = "en"
    metadata: dict[str, Any] = dataclass_field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.user_id.strip():
            raise ValueError("user_id cannot be empty.")

        if not self.email.strip():
            raise ValueError("email cannot be empty.")

        if not self.display_name.strip():
            raise ValueError("display_name cannot be empty.")

        if not self.timezone.strip():
            raise ValueError("timezone cannot be empty.")

        if not self.locale.strip():
            raise ValueError("locale cannot be empty.")

        if not self.created_at_utc.strip():
            raise ValueError("created_at_utc cannot be empty.")

        if not self.updated_at_utc.strip():
            raise ValueError("updated_at_utc cannot be empty.")

    @property
    def is_active(self) -> bool:
        return self.status == UserStatus.ACTIVE

    @property
    def can_trade(self) -> bool:
        return self.is_active and self.role not in READ_ONLY_USER_ROLES

    def to_dict(self) -> dict[str, Any]:
        return {
            "user_id": self.user_id,
            "email": self.email,
            "display_name": self.display_name,
            "role": self.role.value,
            "status": self.status.value,
            "timezone": self.timezone,
            "locale": self.locale,
            "created_at_utc": self.created_at_utc,
            "updated_at_utc": self.updated_at_utc,
            "is_active": self.is_active,
            "can_trade": self.can_trade,
            "metadata": self.metadata,
        }


def build_user_profile_from_row(row: dict[str, Any]) -> UserProfile:
    return UserProfile(
        user_id=str(row["user_id"]),
        email=str(row["email"]),
        display_name=str(row["display_name"]),
        role=UserRole(str(row["role"])),
        status=UserStatus(str(row["status"])),
        created_at_utc=str(row["created_at_utc"]),
        updated_at_utc=str(row["updated_at_utc"]),
        timezone=str(row["timezone"]),
        locale=str(row["locale"]),
        metadata=decode_json_field(row.get("metadata")),
    )


class UserProfileRepository:
    """SQLite-backed store for AQOS user profiles."""

    def __init__(self, database: AqosDatabase) -> None:
        self.database = database
        ensure_aqos_schema(database)

    def create_user(
        self,
        email: str,
        display_name: str,
        role: UserRole = UserRole.TRADER,
        status: UserStatus = UserStatus.ACTIVE,
        timezone: str = "UTC",
        locale: str = "en",
        metadata: dict[str, Any] | None = None,
        user_id: str | None = None,
        created_at_utc: str | None = None,
    ) -> UserProfile:
        normalized_email = normalize_email(email)

        if self.find_user_by_email(normalized_email) is not None:
            raise ValueError(f"User email already exists: {normalized_email}")

        timestamp = created_at_utc or record_utc_now()

        profile = UserProfile(
            user_id=user_id or build_record_id("user"),
            email=normalized_email,
            display_name=normalize_required_text(display_name, "display_name"),
            role=role,
            status=status,
            created_at_utc=timestamp,
            updated_at_utc=timestamp,
            timezone=normalize_required_text(timezone, "timezone"),
            locale=normalize_required_text(locale, "locale"),
            metadata=metadata or {},
        )

        self.database.execute(
            """
            INSERT INTO user_profiles (
                user_id, email, display_name, role, status,
                timezone, locale, created_at_utc, updated_at_utc, metadata
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
            """,
            (
                profile.user_id,
                profile.email,
                profile.display_name,
                profile.role.value,
                profile.status.value,
                profile.timezone,
                profile.locale,
                profile.created_at_utc,
                profile.updated_at_utc,
                encode_json_field(profile.metadata),
            ),
        )

        return profile

    def get_user(self, user_id: str) -> UserProfile | None:
        row = self.database.query_one(
            "SELECT * FROM user_profiles WHERE user_id = ?;",
            (user_id,),
        )

        return build_user_profile_from_row(row) if row is not None else None

    def require_user(self, user_id: str) -> UserProfile:
        profile = self.get_user(user_id)

        if profile is None:
            raise LookupError(f"User profile does not exist: {user_id}")

        return profile

    def find_user_by_email(self, email: str) -> UserProfile | None:
        row = self.database.query_one(
            "SELECT * FROM user_profiles WHERE email = ?;",
            (normalize_email(email),),
        )

        return build_user_profile_from_row(row) if row is not None else None

    def list_users(
        self,
        status: UserStatus | None = None,
        role: UserRole | None = None,
    ) -> tuple[UserProfile, ...]:
        clauses: list[str] = []
        parameters: list[Any] = []

        if status is not None:
            clauses.append("status = ?")
            parameters.append(status.value)

        if role is not None:
            clauses.append("role = ?")
            parameters.append(role.value)

        where = f" WHERE {' AND '.join(clauses)}" if clauses else ""

        rows = self.database.query_all(
            f"SELECT * FROM user_profiles{where} ORDER BY created_at_utc, user_id;",
            tuple(parameters),
        )

        return tuple(build_user_profile_from_row(row) for row in rows)

    def count_users(self, status: UserStatus | None = None) -> int:
        if status is None:
            return int(
                self.database.query_scalar("SELECT COUNT(*) FROM user_profiles;") or 0
            )

        return int(
            self.database.query_scalar(
                "SELECT COUNT(*) FROM user_profiles WHERE status = ?;",
                (status.value,),
            )
            or 0
        )

    def update_user(
        self,
        user_id: str,
        display_name: str | None = None,
        role: UserRole | None = None,
        status: UserStatus | None = None,
        timezone: str | None = None,
        locale: str | None = None,
        metadata: dict[str, Any] | None = None,
        email: str | None = None,
        updated_at_utc: str | None = None,
    ) -> UserProfile:
        current = self.require_user(user_id)

        normalized_email = current.email

        if email is not None:
            normalized_email = normalize_email(email)
            existing = self.find_user_by_email(normalized_email)

            if existing is not None and existing.user_id != user_id:
                raise ValueError(f"User email already exists: {normalized_email}")

        updated = UserProfile(
            user_id=current.user_id,
            email=normalized_email,
            display_name=(
                normalize_required_text(display_name, "display_name")
                if display_name is not None
                else current.display_name
            ),
            role=role or current.role,
            status=status or current.status,
            created_at_utc=current.created_at_utc,
            updated_at_utc=updated_at_utc or record_utc_now(),
            timezone=(
                normalize_required_text(timezone, "timezone")
                if timezone is not None
                else current.timezone
            ),
            locale=(
                normalize_required_text(locale, "locale")
                if locale is not None
                else current.locale
            ),
            metadata=metadata if metadata is not None else current.metadata,
        )

        self.database.execute(
            """
            UPDATE user_profiles
            SET email = ?, display_name = ?, role = ?, status = ?,
                timezone = ?, locale = ?, updated_at_utc = ?, metadata = ?
            WHERE user_id = ?;
            """,
            (
                updated.email,
                updated.display_name,
                updated.role.value,
                updated.status.value,
                updated.timezone,
                updated.locale,
                updated.updated_at_utc,
                encode_json_field(updated.metadata),
                updated.user_id,
            ),
        )

        return updated

    def set_user_status(
        self,
        user_id: str,
        status: UserStatus,
        updated_at_utc: str | None = None,
    ) -> UserProfile:
        return self.update_user(
            user_id=user_id,
            status=status,
            updated_at_utc=updated_at_utc,
        )

    def delete_user(self, user_id: str) -> bool:
        cursor = self.database.execute(
            "DELETE FROM user_profiles WHERE user_id = ?;",
            (user_id,),
        )

        return cursor.rowcount > 0


__all__ = [
    "AQOS_USER_PROFILE_VERSION",
    "READ_ONLY_USER_ROLES",
    "UserProfile",
    "UserProfileRepository",
    "UserRole",
    "UserStatus",
    "build_user_profile_from_row",
]
