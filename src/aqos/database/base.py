from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import DateTime, Integer, MetaData, String, func
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


AQOS_DATABASE_BASE_VERSION = "1.0"

#: Deterministic constraint names keep MySQL migrations reviewable.
AQOS_NAMING_CONVENTION = {
    "ix": "ix_%(table_name)s_%(column_0_N_name)s",
    "uq": "uq_%(table_name)s_%(column_0_N_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s",
}

#: Every AQOS table uses the same MySQL engine and collation.
AQOS_TABLE_ARGS: dict[str, Any] = {
    "mysql_engine": "InnoDB",
    "mysql_charset": "utf8mb4",
    "mysql_collate": "utf8mb4_unicode_ci",
}

AQOS_METADATA = MetaData(naming_convention=AQOS_NAMING_CONVENTION)


class AqosBase(DeclarativeBase):
    """Declarative base shared by every AQOS ORM model."""

    metadata = AQOS_METADATA

    def __init__(self, **kwargs: Any) -> None:
        """
        Reject the one keyword that would fail silently.

        ``metadata`` is SQLAlchemy's ``MetaData`` on every declarative class, so
        passing it as a column value shadows the mapper's registry instead of
        raising. AQOS names its JSON column attribute ``extra_metadata``, and a
        caller reaching for ``metadata`` is told so rather than losing the value.
        """

        if "metadata" in kwargs:
            raise TypeError(
                "'metadata' is reserved by SQLAlchemy. AQOS models take "
                "'extra_metadata' for their JSON metadata column."
            )

        # SQLAlchemy installs its declarative constructor on the mapped class
        # rather than leaving it reachable through super(), so the same
        # attribute assignment is performed here.
        for key, value in kwargs.items():
            if not hasattr(type(self), key):
                raise TypeError(
                    f"{type(self).__name__} has no attribute named {key!r}."
                )

            setattr(self, key, value)

    def to_dict(self) -> dict[str, Any]:
        return {
            column.name: getattr(self, column.name)
            for column in self.__table__.columns
        }


class TimestampMixin:
    """Adds server-managed UTC timestamps to a model."""

    created_at_utc: Mapped[datetime] = mapped_column(
        DateTime,
        nullable=False,
        server_default=func.now(),
    )
    updated_at_utc: Mapped[datetime] = mapped_column(
        DateTime,
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )


class SchemaMigration(AqosBase):
    """One applied migration file."""

    __tablename__ = "schema_migrations"
    __table_args__ = AQOS_TABLE_ARGS

    version: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    checksum: Mapped[str] = mapped_column(String(64), nullable=False)
    applied_at_utc: Mapped[datetime] = mapped_column(
        DateTime,
        nullable=False,
        server_default=func.now(),
    )

    def __repr__(self) -> str:
        return f"SchemaMigration(version={self.version}, name={self.name!r})"


class AqosMetadataEntry(AqosBase):
    """Free-form platform metadata such as the owning application version."""

    __tablename__ = "aqos_metadata"
    __table_args__ = AQOS_TABLE_ARGS

    metadata_key: Mapped[str] = mapped_column(String(191), primary_key=True)
    metadata_value: Mapped[str] = mapped_column(String(1024), nullable=False)
    updated_at_utc: Mapped[datetime] = mapped_column(
        DateTime,
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )

    def __repr__(self) -> str:
        return f"AqosMetadataEntry(metadata_key={self.metadata_key!r})"


def list_aqos_model_tables() -> tuple[str, ...]:
    return tuple(sorted(AQOS_METADATA.tables))


__all__ = [
    "AQOS_DATABASE_BASE_VERSION",
    "AQOS_METADATA",
    "AQOS_NAMING_CONVENTION",
    "AQOS_TABLE_ARGS",
    "AqosBase",
    "AqosMetadataEntry",
    "SchemaMigration",
    "TimestampMixin",
    "list_aqos_model_tables",
]
