"""
AQOS rate limiter primitives.

This module provides dependency-free fixed-window rate limiting primitives
for API, CLI, services, agents, and runtime resilience helpers.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from enum import Enum
from typing import Any, Callable

from aqos.reliability.base import (
    ReliabilityResult,
    ReliabilityStatus,
    build_reliability_result,
    validate_attributes,
    validate_non_empty_string,
    validate_non_negative_float,
    validate_non_negative_integer,
    validate_positive_integer,
    validate_string,
)


class RateLimitDecision(str, Enum):
    """Supported rate limit decisions."""

    ALLOW = "allow"
    DENY = "deny"


@dataclass(frozen=True)
class RateLimitConfig:
    """Rate limiter configuration."""

    max_requests: int = 60
    window_seconds: float = 60.0
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        validate_positive_integer(self.max_requests, "Max requests")
        validate_non_negative_float(self.window_seconds, "Window seconds")

        if self.window_seconds <= 0:
            raise ValueError("Window seconds must be greater than zero.")

        validate_attributes(self.metadata)

    def to_dict(self) -> dict[str, Any]:
        """Convert config into dictionary."""
        return {
            "max_requests": self.max_requests,
            "window_seconds": float(self.window_seconds),
            "metadata": dict(self.metadata),
        }


@dataclass
class RateLimitBucket:
    """Fixed-window rate limit bucket."""

    key: str
    window_start: str
    request_count: int = 0
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        validate_rate_limit_key(self.key)
        validate_non_empty_string(self.window_start, "Window start")
        validate_non_negative_integer(self.request_count, "Request count")
        validate_attributes(self.metadata)

    def reset(self, window_start: str) -> None:
        """Reset bucket for a new window."""
        self.window_start = validate_non_empty_string(window_start, "Window start")
        self.request_count = 0

    def increment(self) -> int:
        """Increment request count."""
        self.request_count += 1
        return self.request_count

    def remaining(self, config: RateLimitConfig) -> int:
        """Return remaining requests."""
        if not isinstance(config, RateLimitConfig):
            raise ValueError("Config must be a RateLimitConfig.")

        return max(config.max_requests - self.request_count, 0)

    def to_dict(self) -> dict[str, Any]:
        """Convert bucket into dictionary."""
        return {
            "key": self.key.strip(),
            "window_start": self.window_start.strip(),
            "request_count": self.request_count,
            "metadata": dict(self.metadata),
        }


@dataclass(frozen=True)
class RateLimitResult:
    """Rate limit check result."""

    allowed: bool
    key: str
    limit: int
    remaining: int
    reset_at: str
    retry_after_seconds: float = 0.0
    reason: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not isinstance(self.allowed, bool):
            raise ValueError("Allowed must be a boolean.")

        validate_rate_limit_key(self.key)
        validate_positive_integer(self.limit, "Limit")
        validate_non_negative_integer(self.remaining, "Remaining")
        validate_non_empty_string(self.reset_at, "Reset at")
        validate_non_negative_float(self.retry_after_seconds, "Retry after seconds")
        validate_string(self.reason, "Reason")
        validate_attributes(self.metadata)

    @property
    def denied(self) -> bool:
        """Return whether rate limit denied request."""
        return not self.allowed

    @property
    def decision(self) -> RateLimitDecision:
        """Return decision enum."""
        return RateLimitDecision.ALLOW if self.allowed else RateLimitDecision.DENY

    def to_reliability_result(self) -> ReliabilityResult:
        """Convert rate limit result into reliability result."""
        return build_reliability_result(
            success=self.allowed,
            operation="rate-limit-check",
            component="rate-limiter",
            status=ReliabilityStatus.OK if self.allowed else ReliabilityStatus.DEGRADED,
            message=self.reason,
            error=None if self.allowed else "Rate limit exceeded.",
            metadata=self.to_dict(),
        )

    def to_dict(self) -> dict[str, Any]:
        """Convert result into dictionary."""
        return {
            "allowed": self.allowed,
            "denied": self.denied,
            "decision": self.decision.value,
            "key": self.key.strip(),
            "limit": self.limit,
            "remaining": self.remaining,
            "reset_at": self.reset_at.strip(),
            "retry_after_seconds": float(self.retry_after_seconds),
            "reason": self.reason.strip(),
            "metadata": dict(self.metadata),
        }


@dataclass
class RateLimiter:
    """Dependency-free fixed-window rate limiter."""

    config: RateLimitConfig = field(default_factory=RateLimitConfig)
    buckets: dict[str, RateLimitBucket] = field(default_factory=dict)
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not isinstance(self.config, RateLimitConfig):
            raise ValueError("Config must be a RateLimitConfig.")

        for bucket in self.buckets.values():
            if not isinstance(bucket, RateLimitBucket):
                raise ValueError("Buckets must contain RateLimitBucket objects.")

        validate_attributes(self.metadata)

    def get_bucket(
        self,
        key: str,
        *,
        now: str | None = None,
    ) -> RateLimitBucket:
        """Get or create bucket."""
        normalized_key = validate_rate_limit_key(key)
        current = parse_rate_limit_datetime(now) if now is not None else datetime.now(UTC)

        bucket = self.buckets.get(normalized_key)

        if bucket is None:
            bucket = build_rate_limit_bucket(
                key=normalized_key,
                window_start=current.isoformat(),
            )
            self.buckets[normalized_key] = bucket
            return bucket

        if is_rate_limit_window_expired(
            bucket.window_start,
            self.config.window_seconds,
            now=current.isoformat(),
        ):
            bucket.reset(current.isoformat())

        return bucket

    def check(
        self,
        key: str,
        *,
        now: str | None = None,
    ) -> RateLimitResult:
        """Check whether a request would be allowed without incrementing."""
        bucket = self.get_bucket(key, now=now)
        current = parse_rate_limit_datetime(now) if now is not None else datetime.now(UTC)
        reset_at = calculate_rate_limit_reset_at(
            bucket.window_start,
            self.config.window_seconds,
        )
        allowed = bucket.request_count < self.config.max_requests
        remaining = bucket.remaining(self.config)

        return RateLimitResult(
            allowed=allowed,
            key=bucket.key,
            limit=self.config.max_requests,
            remaining=remaining,
            reset_at=reset_at,
            retry_after_seconds=0.0
            if allowed
            else calculate_retry_after_seconds(reset_at, now=current.isoformat()),
            reason="Request allowed."
            if allowed
            else "Rate limit exceeded.",
            metadata={
                "request_count": bucket.request_count,
                **self.metadata,
            },
        )

    def allow(
        self,
        key: str,
        *,
        now: str | None = None,
    ) -> RateLimitResult:
        """Consume one request if allowed."""
        bucket = self.get_bucket(key, now=now)
        current = parse_rate_limit_datetime(now) if now is not None else datetime.now(UTC)
        reset_at = calculate_rate_limit_reset_at(
            bucket.window_start,
            self.config.window_seconds,
        )

        if bucket.request_count >= self.config.max_requests:
            return RateLimitResult(
                allowed=False,
                key=bucket.key,
                limit=self.config.max_requests,
                remaining=0,
                reset_at=reset_at,
                retry_after_seconds=calculate_retry_after_seconds(
                    reset_at,
                    now=current.isoformat(),
                ),
                reason="Rate limit exceeded.",
                metadata={
                    "request_count": bucket.request_count,
                    **self.metadata,
                },
            )

        bucket.increment()

        return RateLimitResult(
            allowed=True,
            key=bucket.key,
            limit=self.config.max_requests,
            remaining=bucket.remaining(self.config),
            reset_at=reset_at,
            retry_after_seconds=0.0,
            reason="Request allowed.",
            metadata={
                "request_count": bucket.request_count,
                **self.metadata,
            },
        )

    def execute(
        self,
        key: str,
        operation: Callable[[], Any],
        *,
        now: str | None = None,
    ) -> ReliabilityResult:
        """Execute operation if rate limit allows it."""
        if not callable(operation):
            raise ValueError("Operation must be callable.")

        decision = self.allow(key, now=now)

        if decision.denied:
            return decision.to_reliability_result()

        try:
            value = operation()

            return build_reliability_result(
                success=True,
                operation="rate-limited-operation",
                component="rate-limiter",
                status=ReliabilityStatus.OK,
                message="Rate-limited operation completed successfully.",
                value=value,
                metadata=decision.to_dict(),
            )
        except Exception as exc:  # noqa: BLE001
            return build_reliability_result(
                success=False,
                operation="rate-limited-operation",
                component="rate-limiter",
                status=ReliabilityStatus.FAILED,
                message="Rate-limited operation failed.",
                error=str(exc),
                metadata={
                    "error_type": exc.__class__.__name__,
                    **decision.to_dict(),
                },
            )

    def reset_bucket(self, key: str, *, now: str | None = None) -> RateLimitBucket:
        """Reset a bucket."""
        normalized_key = validate_rate_limit_key(key)
        current = parse_rate_limit_datetime(now) if now is not None else datetime.now(UTC)
        bucket = self.get_bucket(normalized_key, now=current.isoformat())
        bucket.reset(current.isoformat())

        return bucket

    def clear(self) -> None:
        """Clear all buckets."""
        self.buckets.clear()

    def summary(self) -> dict[str, Any]:
        """Return rate limiter summary."""
        return {
            "buckets": len(self.buckets),
            "config": self.config.to_dict(),
            "bucket_keys": list(self.buckets.keys()),
            "metadata": dict(self.metadata),
        }


def normalize_rate_limit_decision(
    decision: RateLimitDecision | str,
) -> RateLimitDecision:
    """Normalize rate limit decision."""
    if isinstance(decision, RateLimitDecision):
        return decision

    normalized = validate_non_empty_string(decision, "Rate limit decision").lower()

    try:
        return RateLimitDecision(normalized)
    except ValueError as exc:
        valid = ", ".join(item.value for item in RateLimitDecision)
        raise ValueError(
            f"Invalid rate limit decision '{decision}'. Valid decisions: {valid}.",
        ) from exc


def validate_rate_limit_key(key: str) -> str:
    """Validate rate limit key."""
    normalized = validate_non_empty_string(key, "Rate limit key")

    if " " in normalized:
        raise ValueError("Rate limit key cannot contain spaces.")

    return normalized


def parse_rate_limit_datetime(value: str) -> datetime:
    """Parse rate limit datetime."""
    normalized = validate_non_empty_string(value, "Datetime")
    parsed = datetime.fromisoformat(normalized)

    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=UTC)

    return parsed


def calculate_rate_limit_reset_at(
    window_start: str,
    window_seconds: float,
) -> str:
    """Calculate rate limit reset timestamp."""
    start = parse_rate_limit_datetime(window_start)
    seconds = validate_non_negative_float(window_seconds, "Window seconds")

    if seconds <= 0:
        raise ValueError("Window seconds must be greater than zero.")

    return (start + timedelta(seconds=seconds)).isoformat()


def calculate_retry_after_seconds(
    reset_at: str,
    *,
    now: str | None = None,
) -> float:
    """Calculate retry-after seconds."""
    reset = parse_rate_limit_datetime(reset_at)
    current = parse_rate_limit_datetime(now) if now is not None else datetime.now(UTC)

    return max(
        (reset - current).total_seconds(),
        0.0,
    )


def is_rate_limit_window_expired(
    window_start: str,
    window_seconds: float,
    *,
    now: str | None = None,
) -> bool:
    """Return whether rate limit window expired."""
    reset_at = calculate_rate_limit_reset_at(
        window_start,
        window_seconds,
    )
    current = parse_rate_limit_datetime(now) if now is not None else datetime.now(UTC)

    return current >= parse_rate_limit_datetime(reset_at)


def build_rate_limit_config(
    *,
    max_requests: int = 60,
    window_seconds: float = 60.0,
    metadata: dict[str, Any] | None = None,
) -> RateLimitConfig:
    """Build rate limit config."""
    return RateLimitConfig(
        max_requests=max_requests,
        window_seconds=window_seconds,
        metadata=metadata or {},
    )


def build_rate_limit_bucket(
    *,
    key: str,
    window_start: str,
    request_count: int = 0,
    metadata: dict[str, Any] | None = None,
) -> RateLimitBucket:
    """Build rate limit bucket."""
    return RateLimitBucket(
        key=key,
        window_start=window_start,
        request_count=request_count,
        metadata=metadata or {},
    )


def build_rate_limit_result(
    *,
    allowed: bool,
    key: str,
    limit: int,
    remaining: int,
    reset_at: str,
    retry_after_seconds: float = 0.0,
    reason: str = "",
    metadata: dict[str, Any] | None = None,
) -> RateLimitResult:
    """Build rate limit result."""
    return RateLimitResult(
        allowed=allowed,
        key=key,
        limit=limit,
        remaining=remaining,
        reset_at=reset_at,
        retry_after_seconds=retry_after_seconds,
        reason=reason,
        metadata=metadata or {},
    )


def build_rate_limiter(
    *,
    config: RateLimitConfig | None = None,
    buckets: dict[str, RateLimitBucket] | None = None,
    metadata: dict[str, Any] | None = None,
) -> RateLimiter:
    """Build rate limiter."""
    return RateLimiter(
        config=config or RateLimitConfig(),
        buckets=buckets or {},
        metadata=metadata or {},
    )