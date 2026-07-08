"""
Unit tests for AQOS API key and token primitives.
"""

import pytest

from aqos.security import (
    AccessToken,
    ApiKeyCredential,
    SecurityDecision,
    TokenStatus,
    TokenStore,
    TokenType,
    TokenValidationResult,
    build_access_token,
    build_api_key,
    build_api_key_credential,
    build_raw_token,
    build_token_id,
    hash_secret,
    is_expired_at,
    mask_secret,
    normalize_token_status,
    normalize_token_type,
    parse_iso_datetime,
    validate_access_token_record,
    validate_api_key_credential,
    validate_raw_secret,
    verify_secret,
)


RAW_API_KEY = "aqos_test_api_key_123"
RAW_ACCESS_TOKEN = "test_access_token_123"


def test_token_type_values():
    assert TokenType.API_KEY.value == "api_key"
    assert TokenType.BEARER.value == "bearer"


def test_token_status_values():
    assert TokenStatus.ACTIVE.value == "active"
    assert TokenStatus.EXPIRED.value == "expired"
    assert TokenStatus.REVOKED.value == "revoked"
    assert TokenStatus.UNKNOWN.value == "unknown"


def test_normalize_token_type_accepts_enum_and_string():
    assert normalize_token_type(TokenType.API_KEY) == TokenType.API_KEY
    assert normalize_token_type(" API_KEY ") == TokenType.API_KEY
    assert normalize_token_type("bearer") == TokenType.BEARER


def test_normalize_token_type_rejects_invalid_value():
    with pytest.raises(ValueError):
        normalize_token_type("bad")

    with pytest.raises(ValueError):
        normalize_token_type("")


def test_normalize_token_status_accepts_enum_and_string():
    assert normalize_token_status(TokenStatus.ACTIVE) == TokenStatus.ACTIVE
    assert normalize_token_status(" ACTIVE ") == TokenStatus.ACTIVE
    assert normalize_token_status("expired") == TokenStatus.EXPIRED
    assert normalize_token_status("REVOKED") == TokenStatus.REVOKED


def test_normalize_token_status_rejects_invalid_value():
    with pytest.raises(ValueError):
        normalize_token_status("bad")

    with pytest.raises(ValueError):
        normalize_token_status("")


def test_build_token_id():
    token_id = build_token_id("token")

    assert token_id.startswith("token-")
    assert len(token_id) > len("token-")


def test_build_token_id_rejects_invalid_prefix():
    with pytest.raises(ValueError):
        build_token_id("")

    with pytest.raises(ValueError):
        build_token_id("bad prefix")


def test_build_raw_token():
    token = build_raw_token(8)

    assert isinstance(token, str)
    assert len(token) >= 8

    with pytest.raises(ValueError):
        build_raw_token(0)

    with pytest.raises(ValueError):
        build_raw_token(True)

    with pytest.raises(ValueError):
        build_raw_token("8")


def test_build_api_key():
    api_key = build_api_key(prefix="aqos", length_bytes=8)

    assert api_key.startswith("aqos_")
    assert len(api_key) > len("aqos_")

    with pytest.raises(ValueError):
        build_api_key(prefix="")

    with pytest.raises(ValueError):
        build_api_key(prefix="bad prefix")


def test_validate_raw_secret():
    assert validate_raw_secret("12345678") == "12345678"

    with pytest.raises(ValueError):
        validate_raw_secret("")

    with pytest.raises(ValueError):
        validate_raw_secret("short")

    with pytest.raises(ValueError):
        validate_raw_secret(123)


def test_hash_and_verify_secret():
    secret_hash = hash_secret(RAW_API_KEY)

    assert isinstance(secret_hash, str)
    assert len(secret_hash) == 64
    assert verify_secret(RAW_API_KEY, secret_hash) is True
    assert verify_secret("wrong_api_key_123", secret_hash) is False


def test_mask_secret():
    assert mask_secret("abcdefghijkl") == "abcd****ijkl"
    assert mask_secret("abcdefghijkl", visible_prefix=2, visible_suffix=2) == "ab********kl"
    assert mask_secret("abcdefgh", visible_prefix=4, visible_suffix=4) == "********"

    with pytest.raises(ValueError):
        mask_secret("short")

    with pytest.raises(ValueError):
        mask_secret("abcdefghijkl", visible_prefix=-1)

    with pytest.raises(ValueError):
        mask_secret("abcdefghijkl", visible_suffix=True)


def test_parse_iso_datetime_and_is_expired_at():
    parsed = parse_iso_datetime("2026-01-01T00:00:00+00:00")

    assert parsed.isoformat() == "2026-01-01T00:00:00+00:00"

    assert is_expired_at(
        "2026-01-01T00:00:00+00:00",
        now="2026-01-01T00:00:01+00:00",
    ) is True

    assert is_expired_at(
        "2026-01-01T00:00:02+00:00",
        now="2026-01-01T00:00:01+00:00",
    ) is False

    assert is_expired_at(None) is False


def test_token_validation_result_to_dict_and_security_result():
    result = TokenValidationResult(
        valid=True,
        status="ACTIVE",
        reason="Token is valid.",
        principal_id="user-1",
        token_id="token-1",
        scopes=[
            "trade.execute",
        ],
        metadata={
            "source": "api",
        },
    )

    assert result.to_dict() == {
        "valid": True,
        "status": "active",
        "reason": "Token is valid.",
        "principal_id": "user-1",
        "token_id": "token-1",
        "scopes": [
            "trade.execute",
        ],
        "metadata": {
            "source": "api",
        },
    }

    security_result = result.to_security_result()

    assert security_result.decision == SecurityDecision.ALLOW
    assert security_result.allowed is True
    assert security_result.principal_id == "user-1"


def test_token_validation_result_denied_security_result():
    result = TokenValidationResult(
        valid=False,
        status="revoked",
        reason="Token revoked.",
        principal_id="user-1",
        token_id="token-1",
    )

    security_result = result.to_security_result()

    assert security_result.decision == SecurityDecision.DENY
    assert security_result.denied is True
    assert security_result.to_dict()["risk_level"] == "high"


def test_token_validation_result_rejects_invalid_values():
    with pytest.raises(ValueError):
        TokenValidationResult(
            valid="yes",
            status="active",
        )

    with pytest.raises(ValueError):
        TokenValidationResult(
            valid=True,
            status="bad",
        )

    with pytest.raises(ValueError):
        TokenValidationResult(
            valid=True,
            status="active",
            reason=123,
        )

    with pytest.raises(ValueError):
        TokenValidationResult(
            valid=True,
            status="active",
            principal_id="",
        )

    with pytest.raises(ValueError):
        TokenValidationResult(
            valid=True,
            status="active",
            token_id="",
        )

    with pytest.raises(ValueError):
        TokenValidationResult(
            valid=True,
            status="active",
            scopes=[""],
        )

    with pytest.raises(ValueError):
        TokenValidationResult(
            valid=True,
            status="active",
            metadata=[],
        )


def test_api_key_credential_to_dict_and_status():
    credential = build_api_key_credential(
        key_id="key-1",
        raw_key=RAW_API_KEY,
        owner_id="user-1",
        scopes=[
            "trade.execute",
        ],
        created_at="2026-01-01T00:00:00+00:00",
        expires_at="2026-01-01T00:00:10+00:00",
        metadata={
            "name": "test-key",
        },
    )

    assert credential.status(now="2026-01-01T00:00:01+00:00") == TokenStatus.ACTIVE
    assert credential.status(now="2026-01-01T00:00:11+00:00") == TokenStatus.EXPIRED
    assert credential.allows_scope("trade.execute") is True
    assert credential.allows_scope("admin") is False

    assert credential.to_dict(include_hash=True) == {
        "key_id": "key-1",
        "owner_id": "user-1",
        "scopes": [
            "trade.execute",
        ],
        "created_at": "2026-01-01T00:00:00+00:00",
        "expires_at": "2026-01-01T00:00:10+00:00",
        "revoked": False,
        "status": "active",
        "metadata": {
            "name": "test-key",
        },
        "key_hash": hash_secret(RAW_API_KEY),
    }


def test_api_key_credential_wildcard_scope():
    credential = build_api_key_credential(
        key_id="key-1",
        raw_key=RAW_API_KEY,
        owner_id="user-1",
        scopes=[
            "*",
        ],
    )

    assert credential.allows_scope("trade.execute") is True


def test_api_key_credential_rejects_invalid_values():
    with pytest.raises(ValueError):
        ApiKeyCredential(
            key_id="",
            key_hash=hash_secret(RAW_API_KEY),
            owner_id="user-1",
        )

    with pytest.raises(ValueError):
        ApiKeyCredential(
            key_id="key-1",
            key_hash="",
            owner_id="user-1",
        )

    with pytest.raises(ValueError):
        ApiKeyCredential(
            key_id="key-1",
            key_hash=hash_secret(RAW_API_KEY),
            owner_id="",
        )

    with pytest.raises(ValueError):
        ApiKeyCredential(
            key_id="key-1",
            key_hash=hash_secret(RAW_API_KEY),
            owner_id="user-1",
            scopes=[""],
        )

    with pytest.raises(ValueError):
        ApiKeyCredential(
            key_id="key-1",
            key_hash=hash_secret(RAW_API_KEY),
            owner_id="user-1",
            created_at="",
        )

    with pytest.raises(ValueError):
        ApiKeyCredential(
            key_id="key-1",
            key_hash=hash_secret(RAW_API_KEY),
            owner_id="user-1",
            expires_at="",
        )

    with pytest.raises(ValueError):
        ApiKeyCredential(
            key_id="key-1",
            key_hash=hash_secret(RAW_API_KEY),
            owner_id="user-1",
            revoked="yes",
        )

    with pytest.raises(ValueError):
        ApiKeyCredential(
            key_id="key-1",
            key_hash=hash_secret(RAW_API_KEY),
            owner_id="user-1",
            metadata=[],
        )


def test_access_token_to_dict_and_status():
    token = build_access_token(
        token_id="token-1",
        raw_token=RAW_ACCESS_TOKEN,
        principal_id="user-1",
        scopes=[
            "trade.execute",
        ],
        issued_at="2026-01-01T00:00:00+00:00",
        expires_at="2026-01-01T00:00:10+00:00",
        metadata={
            "source": "api",
        },
    )

    assert token.status(now="2026-01-01T00:00:01+00:00") == TokenStatus.ACTIVE
    assert token.status(now="2026-01-01T00:00:11+00:00") == TokenStatus.EXPIRED
    assert token.allows_scope("trade.execute") is True
    assert token.allows_scope("admin") is False

    assert token.to_dict(include_hash=True) == {
        "token_id": "token-1",
        "principal_id": "user-1",
        "token_type": "bearer",
        "scopes": [
            "trade.execute",
        ],
        "issued_at": "2026-01-01T00:00:00+00:00",
        "expires_at": "2026-01-01T00:00:10+00:00",
        "revoked": False,
        "status": "active",
        "metadata": {
            "source": "api",
        },
        "token_hash": hash_secret(RAW_ACCESS_TOKEN),
    }


def test_access_token_rejects_invalid_values():
    with pytest.raises(ValueError):
        AccessToken(
            token_id="",
            token_hash=hash_secret(RAW_ACCESS_TOKEN),
            principal_id="user-1",
        )

    with pytest.raises(ValueError):
        AccessToken(
            token_id="token-1",
            token_hash="",
            principal_id="user-1",
        )

    with pytest.raises(ValueError):
        AccessToken(
            token_id="token-1",
            token_hash=hash_secret(RAW_ACCESS_TOKEN),
            principal_id="",
        )

    with pytest.raises(ValueError):
        AccessToken(
            token_id="token-1",
            token_hash=hash_secret(RAW_ACCESS_TOKEN),
            principal_id="user-1",
            token_type="bad",
        )

    with pytest.raises(ValueError):
        AccessToken(
            token_id="token-1",
            token_hash=hash_secret(RAW_ACCESS_TOKEN),
            principal_id="user-1",
            scopes=[""],
        )

    with pytest.raises(ValueError):
        AccessToken(
            token_id="token-1",
            token_hash=hash_secret(RAW_ACCESS_TOKEN),
            principal_id="user-1",
            issued_at="",
        )

    with pytest.raises(ValueError):
        AccessToken(
            token_id="token-1",
            token_hash=hash_secret(RAW_ACCESS_TOKEN),
            principal_id="user-1",
            expires_at="",
        )

    with pytest.raises(ValueError):
        AccessToken(
            token_id="token-1",
            token_hash=hash_secret(RAW_ACCESS_TOKEN),
            principal_id="user-1",
            revoked="yes",
        )

    with pytest.raises(ValueError):
        AccessToken(
            token_id="token-1",
            token_hash=hash_secret(RAW_ACCESS_TOKEN),
            principal_id="user-1",
            metadata=[],
        )


def test_validate_api_key_credential():
    credential = build_api_key_credential(
        key_id="key-1",
        raw_key=RAW_API_KEY,
        owner_id="user-1",
        scopes=[
            "trade.execute",
        ],
        expires_at="2026-01-01T00:00:10+00:00",
    )

    result = validate_api_key_credential(
        credential,
        required_scope="trade.execute",
        now="2026-01-01T00:00:01+00:00",
    )

    assert result.valid is True
    assert result.reason == "API key is valid."

    missing_scope = validate_api_key_credential(
        credential,
        required_scope="admin",
        now="2026-01-01T00:00:01+00:00",
    )

    assert missing_scope.valid is False
    assert missing_scope.reason == "API key does not include required scope."

    expired = validate_api_key_credential(
        credential,
        now="2026-01-01T00:00:11+00:00",
    )

    assert expired.valid is False
    assert expired.status == TokenStatus.EXPIRED

    with pytest.raises(ValueError):
        validate_api_key_credential("bad")


def test_validate_access_token_record():
    token = build_access_token(
        token_id="token-1",
        raw_token=RAW_ACCESS_TOKEN,
        principal_id="user-1",
        scopes=[
            "trade.execute",
        ],
        expires_at="2026-01-01T00:00:10+00:00",
    )

    result = validate_access_token_record(
        token,
        required_scope="trade.execute",
        now="2026-01-01T00:00:01+00:00",
    )

    assert result.valid is True
    assert result.reason == "Access token is valid."

    missing_scope = validate_access_token_record(
        token,
        required_scope="admin",
        now="2026-01-01T00:00:01+00:00",
    )

    assert missing_scope.valid is False
    assert missing_scope.reason == "Access token does not include required scope."

    expired = validate_access_token_record(
        token,
        now="2026-01-01T00:00:11+00:00",
    )

    assert expired.valid is False
    assert expired.status == TokenStatus.EXPIRED

    with pytest.raises(ValueError):
        validate_access_token_record("bad")


def test_token_store_issue_validate_and_revoke_api_key():
    store = TokenStore()

    raw_key, credential = store.issue_api_key(
        owner_id="user-1",
        key_id="key-1",
        raw_key=RAW_API_KEY,
        scopes=[
            "trade.execute",
        ],
    )

    assert raw_key == RAW_API_KEY
    assert store.get_api_key("key-1") is credential

    result = store.validate_api_key(
        RAW_API_KEY,
        required_scope="trade.execute",
    )

    assert result.valid is True
    assert result.principal_id == "user-1"

    missing = store.validate_api_key("aqos_missing_key_123")
    assert missing.valid is False
    assert missing.status == TokenStatus.UNKNOWN

    revoked = store.revoke_api_key("key-1")
    assert revoked.revoked is True

    revoked_result = store.validate_api_key(RAW_API_KEY)
    assert revoked_result.valid is False
    assert revoked_result.status == TokenStatus.REVOKED


def test_token_store_issue_validate_and_revoke_access_token():
    store = TokenStore()

    raw_token, token = store.issue_access_token(
        principal_id="user-1",
        token_id="token-1",
        raw_token=RAW_ACCESS_TOKEN,
        scopes=[
            "trade.execute",
        ],
    )

    assert raw_token == RAW_ACCESS_TOKEN
    assert store.get_access_token("token-1") is token

    result = store.validate_access_token(
        RAW_ACCESS_TOKEN,
        required_scope="trade.execute",
    )

    assert result.valid is True
    assert result.principal_id == "user-1"

    missing = store.validate_access_token("missing_access_token_123")
    assert missing.valid is False
    assert missing.status == TokenStatus.UNKNOWN

    revoked = store.revoke_access_token("token-1")
    assert revoked.revoked is True

    revoked_result = store.validate_access_token(RAW_ACCESS_TOKEN)
    assert revoked_result.valid is False
    assert revoked_result.status == TokenStatus.REVOKED


def test_token_store_summary_and_clear():
    store = TokenStore()

    store.issue_api_key(
        owner_id="user-1",
        key_id="key-1",
        raw_key=RAW_API_KEY,
    )
    store.issue_access_token(
        principal_id="user-1",
        token_id="token-1",
        raw_token=RAW_ACCESS_TOKEN,
    )

    assert store.summary() == {
        "api_keys": 1,
        "access_tokens": 1,
        "active_api_keys": 1,
        "active_access_tokens": 1,
        "api_key_ids": [
            "key-1",
        ],
        "access_token_ids": [
            "token-1",
        ],
    }

    store.clear()

    assert store.summary() == {
        "api_keys": 0,
        "access_tokens": 0,
        "active_api_keys": 0,
        "active_access_tokens": 0,
        "api_key_ids": [],
        "access_token_ids": [],
    }


def test_token_store_rejects_invalid_values():
    store = TokenStore()

    with pytest.raises(ValueError):
        store.register_api_key("bad")

    with pytest.raises(ValueError):
        store.register_access_token("bad")

    _, credential = store.issue_api_key(
        owner_id="user-1",
        key_id="key-1",
        raw_key=RAW_API_KEY,
    )

    _, token = store.issue_access_token(
        principal_id="user-1",
        token_id="token-1",
        raw_token=RAW_ACCESS_TOKEN,
    )

    with pytest.raises(ValueError):
        store.register_api_key(credential)

    with pytest.raises(ValueError):
        store.register_access_token(token)

    with pytest.raises(ValueError):
        store.revoke_api_key("missing-key")

    with pytest.raises(ValueError):
        store.revoke_access_token("missing-token")


def test_security_token_exports_exist():
    import aqos.security as security

    expected_exports = [
        "AccessToken",
        "ApiKeyCredential",
        "TokenStatus",
        "TokenStore",
        "TokenType",
        "TokenValidationResult",
        "build_access_token",
        "build_api_key",
        "build_api_key_credential",
        "build_raw_token",
        "build_token_id",
        "hash_secret",
        "is_expired_at",
        "mask_secret",
        "normalize_token_status",
        "normalize_token_type",
        "parse_iso_datetime",
        "validate_access_token_record",
        "validate_api_key_credential",
        "validate_raw_secret",
        "verify_secret",
    ]

    for export_name in expected_exports:
        assert hasattr(security, export_name), export_name