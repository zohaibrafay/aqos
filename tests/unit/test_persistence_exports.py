from __future__ import annotations

import aqos.persistence as persistence


EXPECTED_EXPORTS = (
    "AQOS_DATABASE_VERSION",
    "AQOS_RECORDS_VERSION",
    "AQOS_SCHEMA_VERSION",
    "AQOS_USER_PROFILE_VERSION",
    "AqosDatabase",
    "AqosDatabaseConfig",
    "IN_MEMORY_DATABASE",
    "UserProfile",
    "UserProfileRepository",
    "UserRole",
    "UserStatus",
    "apply_aqos_schema",
    "build_record_id",
    "decode_json_field",
    "describe_aqos_schema",
    "encode_json_field",
    "ensure_aqos_schema",
    "normalize_email",
    "normalize_symbol",
    "open_aqos_database",
    "record_utc_now",
)


def test_expected_symbols_are_exported() -> None:
    for name in EXPECTED_EXPORTS:
        assert name in persistence.__all__
        assert hasattr(persistence, name)


def test_all_entries_are_importable() -> None:
    for name in persistence.__all__:
        assert hasattr(persistence, name), name


def test_all_has_no_duplicates() -> None:
    assert len(persistence.__all__) == len(set(persistence.__all__))
