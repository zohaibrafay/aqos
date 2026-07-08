"""
AQOS API key and token primitives.

This module provides dependency-free helpers for issuing, hashing, storing,
revoking, and validating API keys and access tokens.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import Enum
from hashlib import sha256
from secrets import compare_digest, token_urlsafe
from typing import Any

from aqos.security.base import (
    SecurityDecision,
    SecurityResult,
    build_security_result,
    validate_attributes,
    validate_non_empty_string,
    validate_string,
    validate_string_list,
)


class TokenType(str, Enum):
    """Supported token types."""

    API_KEY = "api_key"
    BEARER = "bearer"


class TokenStatus(str, Enum):
    """Supported token statuses."""

    ACTIVE = "active"
    EXPIRED = "expired"
    REVOKED = "revoked"
    UNKNOWN = "unknown"


@dataclass(frozen=True)
class TokenValidationResult:
    """Result of validating an API key or access token."""

    valid: bool
    status: TokenStatus | str
    reason: str = ""
    principal_id: str | None = None
    token_id: str | None = None
    scopes: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not isinstance(self.valid, bool):
            raise ValueError("Valid must be a boolean.")

        normalize_token_status(self.status)
        validate_string(self.reason, "Reason")
        validate_string_list(self.scopes, "Scopes")
        validate_attributes(self.metadata)

        if self.principal_id is not None:
            validate_non_empty_string(self.principal_id, "Principal ID")

        if self.token_id is not None:
            validate_non_empty_string(self.token_id, "Token ID")

    def to_dict(self) -> dict[str, Any]:
        """Convert validation result into a serializable dictionary."""
        payload = {
            "valid": self.valid,
            "status": normalize_token_status(self.status).value,
            "reason": self.reason.strip(),
            "principal_id": self.principal_id.strip() if self.principal_id else None,
            "token_id": self.token_id.strip() if self.token_id else None,
            "scopes": [
                scope.strip()
                for scope in self.scopes
            ],
            "metadata": dict(self.metadata),
        }

        return {
            key: value
            for key, value in payload.items()
            if value is not None
        }

    def to_security_result(self) -> SecurityResult:
        """Convert validation result into a security result."""
        decision = SecurityDecision.ALLOW if self.valid else SecurityDecision.DENY

        return build_security_result(
            decision=decision,
            reason=self.reason,
            risk_level="low" if self.valid else "high",
            principal_id=self.principal_id,
            metadata={
                "token_id": self.token_id,
                "status": normalize_token_status(self.status).value,
                "scopes": [
                    scope.strip()
                    for scope in self.scopes
                ],
                **self.metadata,
            },
        )


@dataclass(frozen=True)
class ApiKeyCredential:
    """Stored API key credential.

    The raw API key should never be stored. Store only the hashed API key.
    """

    key_id: str
    key_hash: str
    owner_id: str
    scopes: list[str] = field(default_factory=list)
    created_at: str = field(default_factory=lambda: datetime.now(UTC).isoformat())
    expires_at: str | None = None
    revoked: bool = False
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        validate_non_empty_string(self.key_id, "Key ID")
        validate_non_empty_string(self.key_hash, "Key hash")
        validate_non_empty_string(self.owner_id, "Owner ID")
        validate_string_list(self.scopes, "Scopes")
        validate_non_empty_string(self.created_at, "Created at")
        validate_attributes(self.metadata)

        if self.expires_at is not None:
            validate_non_empty_string(self.expires_at, "Expires at")

        if not isinstance(self.revoked, bool):
            raise ValueError("Revoked must be a boolean.")

    def is_expired(self, now: str | None = None) -> bool:
        """Return whether API key is expired."""
        return is_expired_at(self.expires_at, now=now)

    def status(self, now: str | None = None) -> TokenStatus:
        """Return API key status."""
        if self.revoked:
            return TokenStatus.REVOKED

        if self.is_expired(now=now):
            return TokenStatus.EXPIRED

        return TokenStatus.ACTIVE

    def allows_scope(self, scope: str) -> bool:
        """Return whether API key allows a scope."""
        normalized_scope = validate_non_empty_string(scope, "Scope")

        return "*" in self.scopes or normalized_scope in [
            item.strip()
            for item in self.scopes
        ]

    def to_dict(self, *, include_hash: bool = False) -> dict[str, Any]:
        """Convert API key credential into a serializable dictionary."""
        payload = {
            "key_id": self.key_id.strip(),
            "owner_id": self.owner_id.strip(),
            "scopes": [
                scope.strip()
                for scope in self.scopes
            ],
            "created_at": self.created_at.strip(),
            "expires_at": self.expires_at.strip() if self.expires_at else None,
            "revoked": self.revoked,
            "status": self.status(now=self.created_at).value,
            "metadata": dict(self.metadata),
        }

        if include_hash:
            payload["key_hash"] = self.key_hash.strip()

        return {
            key: value
            for key, value in payload.items()
            if value is not None
        }


@dataclass(frozen=True)
class AccessToken:
    """Stored access token credential.

    The raw token should never be stored. Store only the hashed token.
    """

    token_id: str
    token_hash: str
    principal_id: str
    token_type: TokenType | str = TokenType.BEARER
    scopes: list[str] = field(default_factory=list)
    issued_at: str = field(default_factory=lambda: datetime.now(UTC).isoformat())
    expires_at: str | None = None
    revoked: bool = False
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        validate_non_empty_string(self.token_id, "Token ID")
        validate_non_empty_string(self.token_hash, "Token hash")
        validate_non_empty_string(self.principal_id, "Principal ID")
        normalize_token_type(self.token_type)
        validate_string_list(self.scopes, "Scopes")
        validate_non_empty_string(self.issued_at, "Issued at")
        validate_attributes(self.metadata)

        if self.expires_at is not None:
            validate_non_empty_string(self.expires_at, "Expires at")

        if not isinstance(self.revoked, bool):
            raise ValueError("Revoked must be a boolean.")

    def is_expired(self, now: str | None = None) -> bool:
        """Return whether access token is expired."""
        return is_expired_at(self.expires_at, now=now)

    def status(self, now: str | None = None) -> TokenStatus:
        """Return access token status."""
        if self.revoked:
            return TokenStatus.REVOKED

        if self.is_expired(now=now):
            return TokenStatus.EXPIRED

        return TokenStatus.ACTIVE

    def allows_scope(self, scope: str) -> bool:
        """Return whether token allows a scope."""
        normalized_scope = validate_non_empty_string(scope, "Scope")

        return "*" in self.scopes or normalized_scope in [
            item.strip()
            for item in self.scopes
        ]

    def to_dict(self, *, include_hash: bool = False) -> dict[str, Any]:
        """Convert access token into a serializable dictionary."""
        payload = {
            "token_id": self.token_id.strip(),
            "principal_id": self.principal_id.strip(),
            "token_type": normalize_token_type(self.token_type).value,
            "scopes": [
                scope.strip()
                for scope in self.scopes
            ],
            "issued_at": self.issued_at.strip(),
            "expires_at": self.expires_at.strip() if self.expires_at else None,
            "revoked": self.revoked,
            "status": self.status(now=self.issued_at).value,
            "metadata": dict(self.metadata),
        }

        if include_hash:
            payload["token_hash"] = self.token_hash.strip()

        return {
            key: value
            for key, value in payload.items()
            if value is not None
        }


@dataclass
class TokenStore:
    """In-memory token and API key store."""

    api_keys: dict[str, ApiKeyCredential] = field(default_factory=dict)
    access_tokens: dict[str, AccessToken] = field(default_factory=dict)

    def register_api_key(self, credential: ApiKeyCredential) -> ApiKeyCredential:
        """Register an API key credential."""
        if not isinstance(credential, ApiKeyCredential):
            raise ValueError("Credential must be an ApiKeyCredential.")

        if credential.key_id in self.api_keys:
            raise ValueError("API key already exists.")

        self.api_keys[credential.key_id] = credential
        return credential

    def register_access_token(self, token: AccessToken) -> AccessToken:
        """Register an access token."""
        if not isinstance(token, AccessToken):
            raise ValueError("Token must be an AccessToken.")

        if token.token_id in self.access_tokens:
            raise ValueError("Access token already exists.")

        self.access_tokens[token.token_id] = token
        return token

    def issue_api_key(
        self,
        *,
        owner_id: str,
        scopes: list[str] | None = None,
        key_id: str | None = None,
        raw_key: str | None = None,
        prefix: str = "aqos",
        expires_at: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> tuple[str, ApiKeyCredential]:
        """Issue and store an API key credential."""
        key_value = raw_key or build_api_key(prefix=prefix)
        credential = build_api_key_credential(
            key_id=key_id or build_token_id("key"),
            raw_key=key_value,
            owner_id=owner_id,
            scopes=scopes or [],
            expires_at=expires_at,
            metadata=metadata or {},
        )

        self.register_api_key(credential)
        return key_value, credential

    def issue_access_token(
        self,
        *,
        principal_id: str,
        scopes: list[str] | None = None,
        token_id: str | None = None,
        raw_token: str | None = None,
        token_type: TokenType | str = TokenType.BEARER,
        expires_at: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> tuple[str, AccessToken]:
        """Issue and store an access token."""
        token_value = raw_token or build_raw_token()
        token = build_access_token(
            token_id=token_id or build_token_id("token"),
            raw_token=token_value,
            principal_id=principal_id,
            token_type=token_type,
            scopes=scopes or [],
            expires_at=expires_at,
            metadata=metadata or {},
        )

        self.register_access_token(token)
        return token_value, token

    def get_api_key(self, key_id: str) -> ApiKeyCredential | None:
        """Get API key credential by ID."""
        normalized = validate_non_empty_string(key_id, "Key ID")

        return self.api_keys.get(normalized)

    def get_access_token(self, token_id: str) -> AccessToken | None:
        """Get access token by ID."""
        normalized = validate_non_empty_string(token_id, "Token ID")

        return self.access_tokens.get(normalized)

    def revoke_api_key(self, key_id: str) -> ApiKeyCredential:
        """Revoke API key credential."""
        credential = self.get_api_key(key_id)

        if credential is None:
            raise ValueError("API key not found.")

        revoked = ApiKeyCredential(
            key_id=credential.key_id,
            key_hash=credential.key_hash,
            owner_id=credential.owner_id,
            scopes=credential.scopes,
            created_at=credential.created_at,
            expires_at=credential.expires_at,
            revoked=True,
            metadata=credential.metadata,
        )

        self.api_keys[credential.key_id] = revoked
        return revoked

    def revoke_access_token(self, token_id: str) -> AccessToken:
        """Revoke access token."""
        token = self.get_access_token(token_id)

        if token is None:
            raise ValueError("Access token not found.")

        revoked = AccessToken(
            token_id=token.token_id,
            token_hash=token.token_hash,
            principal_id=token.principal_id,
            token_type=token.token_type,
            scopes=token.scopes,
            issued_at=token.issued_at,
            expires_at=token.expires_at,
            revoked=True,
            metadata=token.metadata,
        )

        self.access_tokens[token.token_id] = revoked
        return revoked

    def validate_api_key(
        self,
        raw_key: str,
        *,
        required_scope: str | None = None,
        now: str | None = None,
    ) -> TokenValidationResult:
        """Validate raw API key against stored credentials."""
        validate_raw_secret(raw_key, "API key")

        for credential in self.api_keys.values():
            if verify_secret(raw_key, credential.key_hash):
                return validate_api_key_credential(
                    credential,
                    required_scope=required_scope,
                    now=now,
                )

        return TokenValidationResult(
            valid=False,
            status=TokenStatus.UNKNOWN,
            reason="API key not found.",
        )

    def validate_access_token(
        self,
        raw_token: str,
        *,
        required_scope: str | None = None,
        now: str | None = None,
    ) -> TokenValidationResult:
        """Validate raw access token against stored tokens."""
        validate_raw_secret(raw_token, "Access token")

        for token in self.access_tokens.values():
            if verify_secret(raw_token, token.token_hash):
                return validate_access_token_record(
                    token,
                    required_scope=required_scope,
                    now=now,
                )

        return TokenValidationResult(
            valid=False,
            status=TokenStatus.UNKNOWN,
            reason="Access token not found.",
        )

    def summary(self) -> dict[str, Any]:
        """Return token store summary."""
        return {
            "api_keys": len(self.api_keys),
            "access_tokens": len(self.access_tokens),
            "active_api_keys": len(
                [
                    credential
                    for credential in self.api_keys.values()
                    if credential.status() == TokenStatus.ACTIVE
                ],
            ),
            "active_access_tokens": len(
                [
                    token
                    for token in self.access_tokens.values()
                    if token.status() == TokenStatus.ACTIVE
                ],
            ),
            "api_key_ids": list(self.api_keys.keys()),
            "access_token_ids": list(self.access_tokens.keys()),
        }

    def clear(self) -> None:
        """Clear token store."""
        self.api_keys.clear()
        self.access_tokens.clear()


def normalize_token_type(token_type: TokenType | str) -> TokenType:
    """Normalize token type."""
    if isinstance(token_type, TokenType):
        return token_type

    normalized = validate_non_empty_string(token_type, "Token type").lower()

    try:
        return TokenType(normalized)
    except ValueError as exc:
        valid = ", ".join(item.value for item in TokenType)
        raise ValueError(f"Invalid token type '{token_type}'. Valid token types: {valid}.") from exc


def normalize_token_status(status: TokenStatus | str) -> TokenStatus:
    """Normalize token status."""
    if isinstance(status, TokenStatus):
        return status

    normalized = validate_non_empty_string(status, "Token status").lower()

    try:
        return TokenStatus(normalized)
    except ValueError as exc:
        valid = ", ".join(item.value for item in TokenStatus)
        raise ValueError(f"Invalid token status '{status}'. Valid statuses: {valid}.") from exc


def build_token_id(prefix: str = "token") -> str:
    """Build token identifier."""
    normalized_prefix = validate_non_empty_string(prefix, "Token ID prefix")

    if " " in normalized_prefix:
        raise ValueError("Token ID prefix cannot contain spaces.")

    return f"{normalized_prefix}-{token_urlsafe(16)}"


def build_raw_token(length_bytes: int = 32) -> str:
    """Build raw token value."""
    if isinstance(length_bytes, bool) or not isinstance(length_bytes, int) or length_bytes <= 0:
        raise ValueError("Length bytes must be a positive integer.")

    return token_urlsafe(length_bytes)


def build_api_key(prefix: str = "aqos", length_bytes: int = 32) -> str:
    """Build raw API key value."""
    normalized_prefix = validate_non_empty_string(prefix, "API key prefix")

    if " " in normalized_prefix:
        raise ValueError("API key prefix cannot contain spaces.")

    return f"{normalized_prefix}_{build_raw_token(length_bytes)}"


def validate_raw_secret(secret: str, field_name: str = "Secret") -> str:
    """Validate raw token or API key secret."""
    normalized = validate_non_empty_string(secret, field_name)

    if len(normalized) < 8:
        raise ValueError(f"{field_name} must be at least 8 characters.")

    return normalized


def hash_secret(secret: str) -> str:
    """Hash a raw secret using SHA-256."""
    normalized = validate_raw_secret(secret)

    return sha256(normalized.encode("utf-8")).hexdigest()


def verify_secret(raw_secret: str, secret_hash: str) -> bool:
    """Verify raw secret against stored hash."""
    validate_raw_secret(raw_secret)
    normalized_hash = validate_non_empty_string(secret_hash, "Secret hash")

    return compare_digest(
        hash_secret(raw_secret),
        normalized_hash,
    )


def mask_secret(secret: str, *, visible_prefix: int = 4, visible_suffix: int = 4) -> str:
    """Mask a secret for safe display."""
    normalized = validate_raw_secret(secret)

    if isinstance(visible_prefix, bool) or not isinstance(visible_prefix, int) or visible_prefix < 0:
        raise ValueError("Visible prefix must be a non-negative integer.")

    if isinstance(visible_suffix, bool) or not isinstance(visible_suffix, int) or visible_suffix < 0:
        raise ValueError("Visible suffix must be a non-negative integer.")

    if visible_prefix + visible_suffix >= len(normalized):
        return "*" * len(normalized)

    return (
        normalized[:visible_prefix]
        + "*" * (len(normalized) - visible_prefix - visible_suffix)
        + normalized[-visible_suffix:]
    )


def parse_iso_datetime(value: str) -> datetime:
    """Parse ISO datetime string."""
    normalized = validate_non_empty_string(value, "Datetime")

    parsed = datetime.fromisoformat(normalized)

    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=UTC)

    return parsed


def is_expired_at(expires_at: str | None, *, now: str | None = None) -> bool:
    """Return whether expiry time has passed."""
    if expires_at is None:
        return False

    expiry = parse_iso_datetime(expires_at)
    current = parse_iso_datetime(now) if now is not None else datetime.now(UTC)

    return current >= expiry


def build_api_key_credential(
    *,
    key_id: str,
    raw_key: str,
    owner_id: str,
    scopes: list[str] | None = None,
    created_at: str | None = None,
    expires_at: str | None = None,
    revoked: bool = False,
    metadata: dict[str, Any] | None = None,
) -> ApiKeyCredential:
    """Build an API key credential from a raw key."""
    credential_kwargs: dict[str, Any] = {
        "key_id": key_id,
        "key_hash": hash_secret(raw_key),
        "owner_id": owner_id,
        "scopes": scopes or [],
        "expires_at": expires_at,
        "revoked": revoked,
        "metadata": metadata or {},
    }

    if created_at is not None:
        credential_kwargs["created_at"] = created_at

    return ApiKeyCredential(**credential_kwargs)


def build_access_token(
    *,
    token_id: str,
    raw_token: str,
    principal_id: str,
    token_type: TokenType | str = TokenType.BEARER,
    scopes: list[str] | None = None,
    issued_at: str | None = None,
    expires_at: str | None = None,
    revoked: bool = False,
    metadata: dict[str, Any] | None = None,
) -> AccessToken:
    """Build an access token record from a raw token."""
    token_kwargs: dict[str, Any] = {
        "token_id": token_id,
        "token_hash": hash_secret(raw_token),
        "principal_id": principal_id,
        "token_type": token_type,
        "scopes": scopes or [],
        "expires_at": expires_at,
        "revoked": revoked,
        "metadata": metadata or {},
    }

    if issued_at is not None:
        token_kwargs["issued_at"] = issued_at

    return AccessToken(**token_kwargs)


def validate_api_key_credential(
    credential: ApiKeyCredential,
    *,
    required_scope: str | None = None,
    now: str | None = None,
) -> TokenValidationResult:
    """Validate stored API key credential."""
    if not isinstance(credential, ApiKeyCredential):
        raise ValueError("Credential must be an ApiKeyCredential.")

    status = credential.status(now=now)

    if status == TokenStatus.REVOKED:
        return TokenValidationResult(
            valid=False,
            status=status,
            reason="API key is revoked.",
            principal_id=credential.owner_id,
            token_id=credential.key_id,
            scopes=credential.scopes,
        )

    if status == TokenStatus.EXPIRED:
        return TokenValidationResult(
            valid=False,
            status=status,
            reason="API key is expired.",
            principal_id=credential.owner_id,
            token_id=credential.key_id,
            scopes=credential.scopes,
        )

    if required_scope is not None and not credential.allows_scope(required_scope):
        return TokenValidationResult(
            valid=False,
            status=status,
            reason="API key does not include required scope.",
            principal_id=credential.owner_id,
            token_id=credential.key_id,
            scopes=credential.scopes,
            metadata={
                "required_scope": required_scope,
            },
        )

    return TokenValidationResult(
        valid=True,
        status=status,
        reason="API key is valid.",
        principal_id=credential.owner_id,
        token_id=credential.key_id,
        scopes=credential.scopes,
    )


def validate_access_token_record(
    token: AccessToken,
    *,
    required_scope: str | None = None,
    now: str | None = None,
) -> TokenValidationResult:
    """Validate stored access token."""
    if not isinstance(token, AccessToken):
        raise ValueError("Token must be an AccessToken.")

    status = token.status(now=now)

    if status == TokenStatus.REVOKED:
        return TokenValidationResult(
            valid=False,
            status=status,
            reason="Access token is revoked.",
            principal_id=token.principal_id,
            token_id=token.token_id,
            scopes=token.scopes,
        )

    if status == TokenStatus.EXPIRED:
        return TokenValidationResult(
            valid=False,
            status=status,
            reason="Access token is expired.",
            principal_id=token.principal_id,
            token_id=token.token_id,
            scopes=token.scopes,
        )

    if required_scope is not None and not token.allows_scope(required_scope):
        return TokenValidationResult(
            valid=False,
            status=status,
            reason="Access token does not include required scope.",
            principal_id=token.principal_id,
            token_id=token.token_id,
            scopes=token.scopes,
            metadata={
                "required_scope": required_scope,
            },
        )

    return TokenValidationResult(
        valid=True,
        status=status,
        reason="Access token is valid.",
        principal_id=token.principal_id,
        token_id=token.token_id,
        scopes=token.scopes,
    )