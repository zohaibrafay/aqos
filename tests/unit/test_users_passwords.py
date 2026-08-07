from __future__ import annotations

import json

import pytest

from aqos.users.passwords import (
    AQOS_PASSWORDS_VERSION,
    MIN_PASSWORD_LENGTH,
    PASSWORD_HASH_ALGORITHM,
    PasswordHash,
    derive_password_hash,
    generate_session_token,
    hash_password,
    hash_session_token,
    mask_secret,
    parse_password_hash,
    validate_password_policy,
    verify_password,
    verify_session_token,
)


VALID_PASSWORD = "Sup3rSecretPhrase"
FAST_ITERATIONS = 1_000


def test_passwords_version_is_exposed() -> None:
    assert AQOS_PASSWORDS_VERSION == "1.0"


def test_policy_accepts_strong_password() -> None:
    result = validate_password_policy(VALID_PASSWORD)

    assert result.is_valid is True
    assert result.issues == ()

    result.raise_if_invalid()


def test_policy_rejects_short_password() -> None:
    result = validate_password_policy("Ab1")

    assert result.is_valid is False
    assert any(str(MIN_PASSWORD_LENGTH) in issue for issue in result.issues)


def test_policy_rejects_missing_character_classes() -> None:
    assert any(
        "lowercase" in issue for issue in validate_password_policy("ABCDEFGH1234").issues
    )
    assert any(
        "uppercase" in issue for issue in validate_password_policy("abcdefgh1234").issues
    )
    assert any(
        "digit" in issue for issue in validate_password_policy("AbcdefghIJkl").issues
    )


def test_policy_rejects_surrounding_whitespace() -> None:
    assert any(
        "whitespace" in issue
        for issue in validate_password_policy(" Sup3rSecretPhrase ").issues
    )


def test_policy_rejects_overlong_password() -> None:
    assert any(
        "longer than" in issue
        for issue in validate_password_policy("Aa1" + "x" * 400).issues
    )


def test_policy_rejects_common_password() -> None:
    assert validate_password_policy("Password1").is_valid is False


def test_policy_raise_if_invalid() -> None:
    with pytest.raises(ValueError, match="Password rejected"):
        validate_password_policy("short").raise_if_invalid()


def test_hash_password_produces_verifiable_hash() -> None:
    password_hash = hash_password(VALID_PASSWORD, iterations=FAST_ITERATIONS)

    assert password_hash.algorithm == PASSWORD_HASH_ALGORITHM
    assert verify_password(VALID_PASSWORD, password_hash) is True
    assert verify_password("WrongPassword1", password_hash) is False


def test_hash_password_uses_unique_salts() -> None:
    first = hash_password(VALID_PASSWORD, iterations=FAST_ITERATIONS)
    second = hash_password(VALID_PASSWORD, iterations=FAST_ITERATIONS)

    assert first.salt_hex != second.salt_hex
    assert first.hash_hex != second.hash_hex


def test_hash_password_enforces_policy_by_default() -> None:
    with pytest.raises(ValueError, match="Password rejected"):
        hash_password("weak", iterations=FAST_ITERATIONS)


def test_hash_password_can_skip_policy() -> None:
    password_hash = hash_password(
        "weak",
        iterations=FAST_ITERATIONS,
        enforce_policy=False,
    )

    assert verify_password("weak", password_hash) is True


def test_hash_password_is_deterministic_for_fixed_salt() -> None:
    salt = b"0123456789abcdef"

    first = hash_password(VALID_PASSWORD, iterations=FAST_ITERATIONS, salt=salt)
    second = hash_password(VALID_PASSWORD, iterations=FAST_ITERATIONS, salt=salt)

    assert first.hash_hex == second.hash_hex


def test_password_hash_validation() -> None:
    with pytest.raises(ValueError, match="Unsupported password algorithm"):
        PasswordHash(algorithm="md5", iterations=1, salt_hex="aa", hash_hex="bb")

    with pytest.raises(ValueError, match="iterations must be at least 1"):
        PasswordHash(
            algorithm=PASSWORD_HASH_ALGORITHM,
            iterations=0,
            salt_hex="aa",
            hash_hex="bb",
        )

    with pytest.raises(ValueError, match="salt_hex cannot be empty"):
        PasswordHash(
            algorithm=PASSWORD_HASH_ALGORITHM,
            iterations=1,
            salt_hex=" ",
            hash_hex="bb",
        )

    with pytest.raises(ValueError, match="hash_hex cannot be empty"):
        PasswordHash(
            algorithm=PASSWORD_HASH_ALGORITHM,
            iterations=1,
            salt_hex="aa",
            hash_hex="",
        )


def test_derive_password_hash_validation() -> None:
    with pytest.raises(ValueError, match="iterations must be at least 1"):
        derive_password_hash(VALID_PASSWORD, b"salt", iterations=0)

    with pytest.raises(ValueError, match="salt cannot be empty"):
        derive_password_hash(VALID_PASSWORD, b"")


def test_storage_string_round_trip() -> None:
    original = hash_password(VALID_PASSWORD, iterations=FAST_ITERATIONS)
    stored = original.to_storage_string()

    assert parse_password_hash(stored) == original
    assert verify_password(VALID_PASSWORD, stored) is True


def test_parse_password_hash_rejects_malformed_values() -> None:
    with pytest.raises(ValueError, match="malformed"):
        parse_password_hash("not-a-hash")

    with pytest.raises(ValueError, match="invalid iterations"):
        parse_password_hash(f"{PASSWORD_HASH_ALGORITHM}$many$aa$bb")


def test_password_hash_dict_exposes_nothing_attackable() -> None:
    """
    The serialized verifier must not be an offline cracking oracle.

    The salt plus any part of the derived key is enough to confirm a guess:
    derive a candidate with the same salt and compare the prefix. So neither
    the salt nor a preview of the key may appear — only the algorithm and the
    work factor, which describe the scheme without helping to break it.
    """

    stored = hash_password(VALID_PASSWORD, iterations=FAST_ITERATIONS)
    payload = stored.to_dict()

    assert set(payload) == {"algorithm", "iterations"}
    assert payload["algorithm"] == PASSWORD_HASH_ALGORITHM
    assert payload["iterations"] == FAST_ITERATIONS

    rendered = json.dumps(payload)

    assert stored.salt_hex not in rendered
    assert stored.hash_hex not in rendered
    assert stored.hash_hex[:8] not in rendered
    assert VALID_PASSWORD not in rendered


def test_password_hash_dict_still_reports_the_work_factor() -> None:
    """Operators need to see the iteration count to audit it over time."""

    payload = hash_password(VALID_PASSWORD, iterations=FAST_ITERATIONS).to_dict()

    assert payload["iterations"] == FAST_ITERATIONS


def test_verify_password_rejects_bad_salt() -> None:
    broken = PasswordHash(
        algorithm=PASSWORD_HASH_ALGORITHM,
        iterations=FAST_ITERATIONS,
        salt_hex="not-hex",
        hash_hex="aa",
    )

    assert verify_password(VALID_PASSWORD, broken) is False


def test_session_token_generation_is_unique() -> None:
    assert generate_session_token() != generate_session_token()

    with pytest.raises(ValueError, match="at least 16 bytes"):
        generate_session_token(8)


def test_session_token_hash_round_trip() -> None:
    token = generate_session_token()
    token_hash = hash_session_token(token)

    assert token_hash != token
    assert len(token_hash) == 64
    assert verify_session_token(token, token_hash) is True
    assert verify_session_token("other-token", token_hash) is False


def test_hash_session_token_rejects_empty() -> None:
    with pytest.raises(ValueError, match="cannot be empty"):
        hash_session_token("   ")


def test_verify_session_token_handles_empty_inputs() -> None:
    assert verify_session_token("", "abc") is False
    assert verify_session_token("abc", "") is False


def test_mask_secret() -> None:
    assert mask_secret("supersecrettoken") == "************oken"
    assert mask_secret("abc") == "***"
    assert mask_secret("abcdef", visible_characters=0) == "******"
    assert mask_secret("") == ""

    with pytest.raises(ValueError, match="cannot be negative"):
        mask_secret("abc", visible_characters=-1)
