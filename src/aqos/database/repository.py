from __future__ import annotations

from typing import Any, Generic, Sequence, TypeVar

from sqlalchemy import delete as sql_delete, func, select
from sqlalchemy.orm import Session

from aqos.database.base import AqosBase


AQOS_REPOSITORY_VERSION = "1.0"

ModelType = TypeVar("ModelType", bound=AqosBase)


class RepositoryError(RuntimeError):
    """Raised when a repository operation cannot be satisfied."""


class RecordNotFoundError(RepositoryError):
    """Raised when a required record does not exist."""


class AqosRepository(Generic[ModelType]):
    """
    Base class for every AQOS SQLAlchemy repository.

    A repository never owns a session: it is handed one by the caller, so a
    single unit of work can span several repositories and still commit once.
    """

    model: type[ModelType]

    def __init__(self, session: Session) -> None:
        if session is None:
            raise ValueError("A SQLAlchemy session is required.")

        if getattr(self, "model", None) is None:
            raise ValueError(
                f"{type(self).__name__} must define a model class attribute."
            )

        self.session = session

    def add(self, entity: ModelType) -> ModelType:
        self.session.add(entity)
        return entity

    def add_all(self, entities: Sequence[ModelType]) -> tuple[ModelType, ...]:
        self.session.add_all(list(entities))
        return tuple(entities)

    def get(self, primary_key: Any) -> ModelType | None:
        return self.session.get(self.model, primary_key)

    def require(self, primary_key: Any) -> ModelType:
        entity = self.get(primary_key)

        if entity is None:
            raise RecordNotFoundError(
                f"{self.model.__name__} does not exist: {primary_key}"
            )

        return entity

    def exists(self, primary_key: Any) -> bool:
        return self.get(primary_key) is not None

    def list_all(self, limit: int | None = None) -> tuple[ModelType, ...]:
        statement = select(self.model)

        if limit is not None:
            statement = statement.limit(limit)

        return tuple(self.session.execute(statement).scalars().all())

    def find_by(self, **filters: Any) -> tuple[ModelType, ...]:
        statement = select(self.model)

        for column_name, value in filters.items():
            statement = statement.where(
                self._resolve_column(column_name) == value
            )

        return tuple(self.session.execute(statement).scalars().all())

    def find_one_by(self, **filters: Any) -> ModelType | None:
        results = self.find_by(**filters)

        if len(results) > 1:
            raise RepositoryError(
                f"Expected at most one {self.model.__name__}, found {len(results)}."
            )

        return results[0] if results else None

    def count(self, **filters: Any) -> int:
        statement = select(func.count()).select_from(self.model)

        for column_name, value in filters.items():
            statement = statement.where(
                self._resolve_column(column_name) == value
            )

        return int(self.session.execute(statement).scalar() or 0)

    def delete(self, entity: ModelType) -> None:
        self.session.delete(entity)

    def delete_by_primary_key(self, primary_key: Any) -> bool:
        entity = self.get(primary_key)

        if entity is None:
            return False

        self.session.delete(entity)

        return True

    def delete_where(self, **filters: Any) -> int:
        statement = sql_delete(self.model)

        for column_name, value in filters.items():
            statement = statement.where(
                self._resolve_column(column_name) == value
            )

        return int(self.session.execute(statement).rowcount or 0)

    def flush(self) -> None:
        self.session.flush()

    def refresh(self, entity: ModelType) -> ModelType:
        self.session.refresh(entity)
        return entity

    def _resolve_column(self, column_name: str) -> Any:
        column = getattr(self.model, column_name, None)

        if column is None:
            raise RepositoryError(
                f"{self.model.__name__} has no column named {column_name}."
            )

        return column


__all__ = [
    "AQOS_REPOSITORY_VERSION",
    "AqosRepository",
    "RecordNotFoundError",
    "RepositoryError",
]
