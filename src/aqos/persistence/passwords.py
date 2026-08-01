from __future__ import annotations

import hashlib
import hmac
import re
import secrets
from dataclasses import dataclass
from typing import Any


AQOS_PASSWORDS_VERSION = "1.0"

PASSWORD_HASH_ALGORITHM = "pbkdf2_sha256"
DEFAULT_PASSWORD_ITERATIONS = 200_000
DEFAULT_SALT_BYTES = 16
MIN_PASSWORD_LENGTH = 10
MAX_PASSWORD_LENGTH = 256

COMMON_WEAK_PASSWORDS = frozenset(
    {
        "password",
        "password1",
        "12345678",
        "123456789",
        "qwertyuiop",
        "letmein123",
        "changeme123",
        "aqospassword",
    }
)


@dataclass(frozen=True)
class PasswordHash:
    """
    A stored password verifier.

    The plaintext password is never kept anywhere: only the algorithm, the
    iteration count, a random salt and the derived key are persisted.
    """

    algorithm: str
    iterations: int
    salt_hex: str
    hash_hex: str

    def __post_init__(self) -> None:
        if self.algorithm != PASSWORD_HASH_ALGORITHM:
            raise ValueError(f"Unsupported password algorithm: {self.algorithm}")

        if self.iterations < 1:
            raise ValueError("iterations must be at least 1.")

        if not self.salt_hex.strip():
            raise ValueError("salt_hex cannot be empty.")

        if not self.hash_hex.strip():
            raise ValueError("hash_hex cannot be empty.")

    def to_storage_string(self) -> str:
        return f"{self.algorithm}${self.iterations}${self.salt_hex}${self.hash_hex}"

    def to_dict(self) -> dict[str, Any]:
        """Serialize without ever exposing the derived key."""

        return {
            "algorithm": self.algorithm,
            "iterations": self.iterations,
            "salt_hex": self.salt_hex,
            "hash_preview": f"{self.hash_hex[:8]}...",
        }


@dataclass(frozen=True)
class PasswordPolicyResult:
    is_valid: bool
    issues: tuple[str, ...] = ()

    def raise_if_invalid(self) -> None:
        if self.is_valid:
            return

        raise ValueError("Password rejected: " + "; ".join(self.issues))

    def to_dict(self) -> dict[str, Any]:
        return {
            "is_valid": self.is_valid,
            "issues": list(self.issues),
        }


def validate_password_policy(password: str) -> PasswordPolicyResult:
    issues: list[str] = []

    if len(password) < MIN_PASSWORD_LENGTH:
        issues.append(
            f"Password must be at least {MIN_PASSWORD_LENGTH} characters long."
        )

    if len(password) > MAX_PASSWORD_LENGTH:
        issues.append(
            f"Password cannot be longer than {MAX_PASSWORD_LENGTH} characters."
        )

    if not re.search(r"[a-z]", password):
        issues.append("Password must contain a lowercase letter.")

    if not re.search(r"[A-Z]", password):
        issues.append("Password must contain an uppercase letter.")

    if not re.search(r"\d", password):
        issues.append("Password must contain a digit.")

    if password.strip() != password:
        issues.append("Password cannot start or end with whitespace.")

    if password.lower() in COMMON_WEAK_PASSWORDS:
        issues.append("Password is too common.")

    return PasswordPolicyResult(is_valid=not issues, issues=tuple(issues))


def derive_password_hash(
    password: str,
    salt: bytes,
    iterations: int = DEFAULT_PASSWORD_ITERATIONS,
) -> str:
    if iterations < 1:
        raise ValueError("iterations must be at least 1.")

    if not salt:
        raise ValueError("salt cannot be empty.")

    derived = hashlib.pbkdf2_hmac(
        "sha256",
        password.encode("utf-8"),
        salt,
        iterations,
    )

    return derived.hex()


def hash_password(
    password: str,
    iterations: int = DEFAULT_PASSWORD_ITERATIONS,
    salt: bytes | None = None,
    enforce_policy: bool = True,
) -> PasswordHash:
    if enforce_policy:
        validate_password_policy(password).raise_if_invalid()

    resolved_salt = salt or secrets.token_bytes(DEFAULT_SALT_BYTES)

    return PasswordHash(
        algorithm=PASSWORD_HASH_ALGORITHM,
        iterations=iterations,
        salt_hex=resolved_salt.hex(),
        hash_hex=derive_password_hash(password, resolved_salt, iterations),
    )


def parse_password_hash(value: str) -> PasswordHash:
    parts = value.split("$")

    if len(parts) != 4:
        raise ValueError("Stored password hash is malformed.")

    algorithm, iterations, salt_hex, hash_hex = parts

    try:
        iteration_count = int(iterations)
    except ValueError as exc:
        raise ValueError("Stored password hash has invalid iterations.") from exc

    return PasswordHash(
        algorithm=algorithm,
        iterations=iteration_count,
        salt_hex=salt_hex,
        hash_hex=hash_hex,
    )


def verify_password(password: str, stored: PasswordHash | str) -> bool:
    password_hash = parse_password_hash(stored) if isinstance(stored, str) else stored

    try:
        salt = bytes.fromhex(password_hash.salt_hex)
    except ValueError:
        return False

    candidate = derive_password_hash(
        password=password,
        salt=salt,
        iterations=password_hash.iterations,
    )

    return hmac.compare_digest(candidate, password_hash.hash_hex)


def generate_session_token(bytes_length: int = 32) -> str:
    if bytes_length < 16:
        raise ValueError("Session tokens must use at least 16 bytes of entropy.")

    return secrets.token_urlsafe(bytes_length)


def hash_session_token(token: str) -> str:
    if not token.strip():
        raise ValueError("Session token cannot be empty.")

    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def verify_session_token(token: str, token_hash: str) -> bool:
    if not token.strip() or not token_hash.strip():
        return False

    return hmac.compare_digest(hash_session_token(token), token_hash)


def mask_secret(value: str, visible_characters: int = 4) -> str:
    """Render a secret safe for logs, keeping only a short suffix."""

    if visible_characters < 0:
        raise ValueError("visible_characters cannot be negative.")

    if not value:
        return ""

    if visible_characters == 0 or len(value) <= visible_characters:
        return "*" * len(value)

    return "*" * (len(value) - visible_characters) + value[-visible_characters:]


__all__ = [
    "AQOS_PASSWORDS_VERSION",
    "COMMON_WEAK_PASSWORDS",
    "DEFAULT_PASSWORD_ITERATIONS",
    "DEFAULT_SALT_BYTES",
    "MAX_PASSWORD_LENGTH",
    "MIN_PASSWORD_LENGTH",
    "PASSWORD_HASH_ALGORITHM",
    "PasswordHash",
    "PasswordPolicyResult",
    "derive_password_hash",
    "generate_session_token",
    "hash_password",
    "hash_session_token",
    "mask_secret",
    "parse_password_hash",
    "validate_password_policy",
    "verify_password",
    "verify_session_token",
]
