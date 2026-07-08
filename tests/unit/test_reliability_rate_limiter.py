"""
Unit tests for AQOS rate limiter primitives.
"""

import pytest

from aqos.reliability import (
    RateLimitBucket,
    RateLimitConfig,
    RateLimitDecision,
    RateLimitResult,
    RateLimiter,
    ReliabilityStatus,
    build_rate_limit_bucket,
    build_rate_limit_config,
    build_rate_limit_result,
    build_rate_limiter,
    calculate_rate_limit_reset_at,
    calculate_retry_after_seconds,
    is_rate_limit_window_expired,
    normalize_rate_limit_decision,
    parse_rate_limit_datetime,
    validate_rate_limit_key,
)


def test_rate_limit_decision_values():
    assert RateLimitDecision.ALLOW.value == "allow"
    assert RateLimitDecision.DENY.value == "deny"


def test_normalize_rate_limit_decision_accepts_enum_and_string():
    assert normalize_rate_limit_decision(RateLimitDecision.ALLOW) == RateLimitDecision.ALLOW
    assert normalize_rate_limit_decision(" ALLOW ") == RateLimitDecision.ALLOW
    assert normalize_rate_limit_decision("deny") == RateLimitDecision.DENY


def test_normalize_rate_limit_decision_rejects_invalid_value():
    with pytest.raises(ValueError):
        normalize_rate_limit_decision("bad")

    with pytest.raises(ValueError):
        normalize_rate_limit_decision("")


def test_validate_rate_limit_key():
    assert validate_rate_limit_key("user-1") == "user-1"

    with pytest.raises(ValueError):
        validate_rate_limit_key("")

    with pytest.raises(ValueError):
        validate_rate_limit_key("bad key")


def test_parse_rate_limit_datetime():
    parsed = parse_rate_limit_datetime("2026-01-01T00:00:00+00:00")

    assert parsed.isoformat() == "2026-01-01T00:00:00+00:00"

    parsed_naive = parse_rate_limit_datetime("2026-01-01T00:00:00")

    assert parsed_naive.isoformat() == "2026-01-01T00:00:00+00:00"

    with pytest.raises(ValueError):
        parse_rate_limit_datetime("")


def test_rate_limit_time_helpers():
    assert calculate_rate_limit_reset_at(
        "2026-01-01T00:00:00+00:00",
        60,
    ) == "2026-01-01T00:01:00+00:00"

    assert calculate_retry_after_seconds(
        "2026-01-01T00:01:00+00:00",
        now="2026-01-01T00:00:30+00:00",
    ) == 30.0

    assert calculate_retry_after_seconds(
        "2026-01-01T00:01:00+00:00",
        now="2026-01-01T00:02:00+00:00",
    ) == 0.0

    assert is_rate_limit_window_expired(
        "2026-01-01T00:00:00+00:00",
        60,
        now="2026-01-01T00:00:59+00:00",
    ) is False

    assert is_rate_limit_window_expired(
        "2026-01-01T00:00:00+00:00",
        60,
        now="2026-01-01T00:01:00+00:00",
    ) is True

    with pytest.raises(ValueError):
        calculate_rate_limit_reset_at("2026-01-01T00:00:00+00:00", 0)


def test_rate_limit_config_to_dict():
    config = RateLimitConfig(
        max_requests=2,
        window_seconds=10,
        metadata={
            "scope": "trade",
        },
    )

    assert config.to_dict() == {
        "max_requests": 2,
        "window_seconds": 10.0,
        "metadata": {
            "scope": "trade",
        },
    }


def test_rate_limit_config_rejects_invalid_values():
    with pytest.raises(ValueError):
        RateLimitConfig(max_requests=0)

    with pytest.raises(ValueError):
        RateLimitConfig(window_seconds=0)

    with pytest.raises(ValueError):
        RateLimitConfig(window_seconds=-1)

    with pytest.raises(ValueError):
        RateLimitConfig(metadata=[])


def test_build_rate_limit_config():
    config = build_rate_limit_config(
        max_requests=5,
        window_seconds=30,
        metadata={
            "source": "test",
        },
    )

    assert isinstance(config, RateLimitConfig)
    assert config.to_dict()["metadata"] == {
        "source": "test",
    }


def test_rate_limit_bucket_to_dict_increment_remaining_and_reset():
    bucket = RateLimitBucket(
        key="user-1",
        window_start="2026-01-01T00:00:00+00:00",
        request_count=1,
        metadata={
            "source": "test",
        },
    )

    assert bucket.increment() == 2
    assert bucket.remaining(
        RateLimitConfig(
            max_requests=3,
            window_seconds=60,
        ),
    ) == 1

    bucket.reset("2026-01-01T00:01:00+00:00")

    assert bucket.to_dict() == {
        "key": "user-1",
        "window_start": "2026-01-01T00:01:00+00:00",
        "request_count": 0,
        "metadata": {
            "source": "test",
        },
    }


def test_rate_limit_bucket_rejects_invalid_values():
    with pytest.raises(ValueError):
        RateLimitBucket(key="", window_start="2026-01-01T00:00:00+00:00")

    with pytest.raises(ValueError):
        RateLimitBucket(key="user-1", window_start="")

    with pytest.raises(ValueError):
        RateLimitBucket(
            key="user-1",
            window_start="2026-01-01T00:00:00+00:00",
            request_count=-1,
        )

    with pytest.raises(ValueError):
        RateLimitBucket(
            key="user-1",
            window_start="2026-01-01T00:00:00+00:00",
            metadata=[],
        )

    bucket = build_rate_limit_bucket(
        key="user-1",
        window_start="2026-01-01T00:00:00+00:00",
    )

    with pytest.raises(ValueError):
        bucket.remaining("bad")


def test_build_rate_limit_bucket():
    bucket = build_rate_limit_bucket(
        key="user-1",
        window_start="2026-01-01T00:00:00+00:00",
        request_count=1,
        metadata={
            "source": "test",
        },
    )

    assert isinstance(bucket, RateLimitBucket)
    assert bucket.request_count == 1


def test_rate_limit_result_to_dict_and_reliability_result():
    result = RateLimitResult(
        allowed=True,
        key="user-1",
        limit=2,
        remaining=1,
        reset_at="2026-01-01T00:01:00+00:00",
        retry_after_seconds=0,
        reason="Allowed.",
        metadata={
            "request_count": 1,
        },
    )

    assert result.denied is False
    assert result.decision == RateLimitDecision.ALLOW

    assert result.to_dict() == {
        "allowed": True,
        "denied": False,
        "decision": "allow",
        "key": "user-1",
        "limit": 2,
        "remaining": 1,
        "reset_at": "2026-01-01T00:01:00+00:00",
        "retry_after_seconds": 0.0,
        "reason": "Allowed.",
        "metadata": {
            "request_count": 1,
        },
    }

    reliability_result = result.to_reliability_result()

    assert reliability_result.success is True
    assert reliability_result.status == ReliabilityStatus.OK


def test_rate_limit_result_denied_to_reliability_result():
    result = RateLimitResult(
        allowed=False,
        key="user-1",
        limit=1,
        remaining=0,
        reset_at="2026-01-01T00:01:00+00:00",
        retry_after_seconds=60,
        reason="Rate limit exceeded.",
    )

    reliability_result = result.to_reliability_result()

    assert result.denied is True
    assert result.decision == RateLimitDecision.DENY
    assert reliability_result.success is False
    assert reliability_result.status == ReliabilityStatus.DEGRADED
    assert reliability_result.error == "Rate limit exceeded."


def test_rate_limit_result_rejects_invalid_values():
    with pytest.raises(ValueError):
        RateLimitResult(
            allowed="yes",
            key="user-1",
            limit=1,
            remaining=0,
            reset_at="2026-01-01T00:01:00+00:00",
        )

    with pytest.raises(ValueError):
        RateLimitResult(
            allowed=True,
            key="",
            limit=1,
            remaining=0,
            reset_at="2026-01-01T00:01:00+00:00",
        )

    with pytest.raises(ValueError):
        RateLimitResult(
            allowed=True,
            key="user-1",
            limit=0,
            remaining=0,
            reset_at="2026-01-01T00:01:00+00:00",
        )

    with pytest.raises(ValueError):
        RateLimitResult(
            allowed=True,
            key="user-1",
            limit=1,
            remaining=-1,
            reset_at="2026-01-01T00:01:00+00:00",
        )

    with pytest.raises(ValueError):
        RateLimitResult(
            allowed=True,
            key="user-1",
            limit=1,
            remaining=0,
            reset_at="",
        )

    with pytest.raises(ValueError):
        RateLimitResult(
            allowed=True,
            key="user-1",
            limit=1,
            remaining=0,
            reset_at="2026-01-01T00:01:00+00:00",
            retry_after_seconds=-1,
        )

    with pytest.raises(ValueError):
        RateLimitResult(
            allowed=True,
            key="user-1",
            limit=1,
            remaining=0,
            reset_at="2026-01-01T00:01:00+00:00",
            reason=123,
        )

    with pytest.raises(ValueError):
        RateLimitResult(
            allowed=True,
            key="user-1",
            limit=1,
            remaining=0,
            reset_at="2026-01-01T00:01:00+00:00",
            metadata=[],
        )


def test_build_rate_limit_result():
    result = build_rate_limit_result(
        allowed=True,
        key="user-1",
        limit=2,
        remaining=1,
        reset_at="2026-01-01T00:01:00+00:00",
    )

    assert isinstance(result, RateLimitResult)
    assert result.allowed is True


def test_rate_limiter_allows_until_limit_then_denies():
    limiter = build_rate_limiter(
        config=build_rate_limit_config(
            max_requests=2,
            window_seconds=60,
        ),
    )

    first = limiter.allow(
        "user-1",
        now="2026-01-01T00:00:00+00:00",
    )
    second = limiter.allow(
        "user-1",
        now="2026-01-01T00:00:01+00:00",
    )
    third = limiter.allow(
        "user-1",
        now="2026-01-01T00:00:02+00:00",
    )

    assert first.allowed is True
    assert first.remaining == 1
    assert second.allowed is True
    assert second.remaining == 0
    assert third.allowed is False
    assert third.retry_after_seconds == 58.0


def test_rate_limiter_check_does_not_increment():
    limiter = build_rate_limiter(
        config=build_rate_limit_config(
            max_requests=1,
            window_seconds=60,
        ),
    )

    check = limiter.check(
        "user-1",
        now="2026-01-01T00:00:00+00:00",
    )

    assert check.allowed is True
    assert check.remaining == 1

    bucket = limiter.get_bucket(
        "user-1",
        now="2026-01-01T00:00:00+00:00",
    )

    assert bucket.request_count == 0


def test_rate_limiter_resets_after_window_expired():
    limiter = build_rate_limiter(
        config=build_rate_limit_config(
            max_requests=1,
            window_seconds=60,
        ),
    )

    first = limiter.allow(
        "user-1",
        now="2026-01-01T00:00:00+00:00",
    )
    second = limiter.allow(
        "user-1",
        now="2026-01-01T00:01:00+00:00",
    )

    assert first.allowed is True
    assert second.allowed is True
    assert second.remaining == 0


def test_rate_limiter_execute_success_denied_and_failure():
    limiter = build_rate_limiter(
        config=build_rate_limit_config(
            max_requests=1,
            window_seconds=60,
        ),
    )

    success = limiter.execute(
        "user-1",
        lambda: 10,
        now="2026-01-01T00:00:00+00:00",
    )

    denied = limiter.execute(
        "user-1",
        lambda: 20,
        now="2026-01-01T00:00:01+00:00",
    )

    assert success.success is True
    assert success.value == 10
    assert denied.success is False
    assert denied.status == ReliabilityStatus.DEGRADED

    def fail():
        raise RuntimeError("boom")

    failure = limiter.execute(
        "user-2",
        fail,
        now="2026-01-01T00:00:00+00:00",
    )

    assert failure.success is False
    assert failure.status == ReliabilityStatus.FAILED
    assert failure.error == "boom"


def test_rate_limiter_reset_bucket_clear_and_summary():
    limiter = build_rate_limiter(
        config=build_rate_limit_config(max_requests=1),
        metadata={
            "source": "test",
        },
    )

    limiter.allow(
        "user-1",
        now="2026-01-01T00:00:00+00:00",
    )

    assert limiter.summary() == {
        "buckets": 1,
        "config": limiter.config.to_dict(),
        "bucket_keys": [
            "user-1",
        ],
        "metadata": {
            "source": "test",
        },
    }

    bucket = limiter.reset_bucket(
        "user-1",
        now="2026-01-01T00:00:10+00:00",
    )

    assert bucket.request_count == 0
    assert bucket.window_start == "2026-01-01T00:00:10+00:00"

    limiter.clear()

    assert limiter.summary()["buckets"] == 0


def test_rate_limiter_rejects_invalid_values():
    with pytest.raises(ValueError):
        RateLimiter(config="bad")

    with pytest.raises(ValueError):
        RateLimiter(buckets={"bad": "bad"})

    with pytest.raises(ValueError):
        RateLimiter(metadata=[])

    limiter = build_rate_limiter()

    with pytest.raises(ValueError):
        limiter.execute("user-1", "bad")


def test_build_rate_limiter():
    limiter = build_rate_limiter(
        config=build_rate_limit_config(max_requests=2),
        metadata={
            "source": "test",
        },
    )

    assert isinstance(limiter, RateLimiter)
    assert limiter.config.max_requests == 2
    assert limiter.metadata == {
        "source": "test",
    }


def test_reliability_rate_limiter_exports_exist():
    import aqos.reliability as reliability

    expected_exports = [
        "RateLimitBucket",
        "RateLimitConfig",
        "RateLimitDecision",
        "RateLimitResult",
        "RateLimiter",
        "build_rate_limit_bucket",
        "build_rate_limit_config",
        "build_rate_limit_result",
        "build_rate_limiter",
        "calculate_rate_limit_reset_at",
        "calculate_retry_after_seconds",
        "is_rate_limit_window_expired",
        "normalize_rate_limit_decision",
        "parse_rate_limit_datetime",
        "validate_rate_limit_key",
    ]

    for export_name in expected_exports:
        assert hasattr(reliability, export_name), export_name