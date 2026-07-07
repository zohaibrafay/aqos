"""
Storage service.

Provides a lightweight generic storage service for saving,
retrieving, updating, and organizing AQOS records by namespace.
"""

from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass, field
from typing import Any


@dataclass(slots=True, frozen=True)
class StorageRecord:
    """
    Represents a stored AQOS record.
    """

    key: str
    namespace: str
    value: Any
    metadata: dict[str, Any] = field(default_factory=dict)


class StorageService:
    """
    Service layer for generic AQOS storage.
    """

    DEFAULT_NAMESPACE = "default"

    def __init__(self) -> None:
        self._records: dict[tuple[str, str], StorageRecord] = {}

    def save(
        self,
        key: str,
        value: Any,
        namespace: str = DEFAULT_NAMESPACE,
        metadata: dict[str, Any] | None = None,
        overwrite: bool = True,
    ) -> StorageRecord:
        """
        Save a record.
        """

        self._validate_key(key)
        self._validate_namespace(namespace)

        storage_key = self._storage_key(
            key=key,
            namespace=namespace,
        )

        if not overwrite and storage_key in self._records:
            raise ValueError("Storage record already exists.")

        record = StorageRecord(
            key=key,
            namespace=namespace,
            value=deepcopy(value),
            metadata=metadata or {},
        )

        self._records[storage_key] = record

        return record

    def get(
        self,
        key: str,
        namespace: str = DEFAULT_NAMESPACE,
    ) -> StorageRecord | None:
        """
        Get a storage record.
        """

        self._validate_key(key)
        self._validate_namespace(namespace)

        return self._records.get(
            self._storage_key(
                key=key,
                namespace=namespace,
            )
        )

    def get_required(
        self,
        key: str,
        namespace: str = DEFAULT_NAMESPACE,
    ) -> StorageRecord:
        """
        Get a storage record or raise if it does not exist.
        """

        record = self.get(
            key=key,
            namespace=namespace,
        )

        if record is None:
            raise ValueError("Storage record does not exist.")

        return record

    def load(
        self,
        key: str,
        namespace: str = DEFAULT_NAMESPACE,
    ) -> Any:
        """
        Load a stored value.
        """

        record = self.get_required(
            key=key,
            namespace=namespace,
        )

        return deepcopy(record.value)

    def exists(
        self,
        key: str,
        namespace: str = DEFAULT_NAMESPACE,
    ) -> bool:
        """
        Check whether a record exists.
        """

        self._validate_key(key)
        self._validate_namespace(namespace)

        return self._storage_key(
            key=key,
            namespace=namespace,
        ) in self._records

    def list(
        self,
        namespace: str | None = None,
    ) -> list[StorageRecord]:
        """
        Return stored records.
        """

        if namespace is not None:
            self._validate_namespace(namespace)

        records = [
            record
            for record in self._records.values()
            if namespace is None or record.namespace == namespace
        ]

        return sorted(
            records,
            key=lambda record: (record.namespace, record.key),
        )

    def list_keys(
        self,
        namespace: str | None = None,
    ) -> list[str]:
        """
        Return stored keys.
        """

        return [
            record.key
            for record in self.list(namespace=namespace)
        ]

    def list_namespaces(self) -> list[str]:
        """
        Return all namespaces.
        """

        namespaces = {
            record.namespace
            for record in self._records.values()
        }

        return sorted(namespaces)

    def update_metadata(
        self,
        key: str,
        metadata: dict[str, Any],
        namespace: str = DEFAULT_NAMESPACE,
    ) -> StorageRecord:
        """
        Update metadata for a stored record.
        """

        if not metadata:
            raise ValueError("Metadata cannot be empty.")

        record = self.get_required(
            key=key,
            namespace=namespace,
        )

        updated_metadata = dict(record.metadata)
        updated_metadata.update(metadata)

        updated = StorageRecord(
            key=record.key,
            namespace=record.namespace,
            value=deepcopy(record.value),
            metadata=updated_metadata,
        )

        self._records[
            self._storage_key(
                key=key,
                namespace=namespace,
            )
        ] = updated

        return updated

    def remove(
        self,
        key: str,
        namespace: str = DEFAULT_NAMESPACE,
    ) -> None:
        """
        Remove a stored record.
        """

        self._validate_key(key)
        self._validate_namespace(namespace)

        self._records.pop(
            self._storage_key(
                key=key,
                namespace=namespace,
            ),
            None,
        )

    def clear_namespace(
        self,
        namespace: str,
    ) -> None:
        """
        Clear all records in a namespace.
        """

        self._validate_namespace(namespace)

        keys_to_remove = [
            storage_key
            for storage_key, record in self._records.items()
            if record.namespace == namespace
        ]

        for storage_key in keys_to_remove:
            self._records.pop(storage_key, None)

    def clear(self) -> None:
        """
        Clear all storage records.
        """

        self._records.clear()

    def count(
        self,
        namespace: str | None = None,
    ) -> int:
        """
        Return number of storage records.
        """

        return len(self.list(namespace=namespace))

    def _storage_key(
        self,
        key: str,
        namespace: str,
    ) -> tuple[str, str]:
        """
        Build internal storage key.
        """

        return namespace, key

    def _validate_key(
        self,
        key: str,
    ) -> None:
        """
        Validate storage key.
        """

        if not key:
            raise ValueError("Storage key cannot be empty.")

    def _validate_namespace(
        self,
        namespace: str,
    ) -> None:
        """
        Validate namespace.
        """

        if not namespace:
            raise ValueError("Namespace cannot be empty.")


__all__ = [
    "StorageRecord",
    "StorageService",
]