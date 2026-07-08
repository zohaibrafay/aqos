"""
Unit tests for AQOS security audit logs.
"""

import pytest

from aqos.security import (
    AuditAction,
    AuditLogRecord,
    AuditLogger,
    AuditOutcome,
    AuditQuery,
    AuditStore,
    SecurityDecision,
    build_audit_id,
    build_audit_log_record,
    build_audit_logger,
    build_audit_query,
    normalize_audit_action,
    normalize_audit_outcome,
    validate_audit_limit,
    validate_audit_message,
    validate_audit_metadata,
    validate_audit_resource,
)


def test_audit_action_values():
    assert AuditAction.AUTHENTICATE.value == "authenticate"
    assert AuditAction.AUTHORIZE.value == "authorize"
    assert AuditAction.GUARD_REQUEST.value == "guard_request"
    assert AuditAction.TOKEN_VALIDATE.value == "token_validate"
    assert AuditAction.PERMISSION_CHECK.value == "permission_check"
    assert AuditAction.POLICY_EVALUATE.value == "policy_evaluate"
    assert AuditAction.CUSTOM.value == "custom"


def test_audit_outcome_values():
    assert AuditOutcome.SUCCESS.value == "success"
    assert AuditOutcome.FAILURE.value == "failure"
    assert AuditOutcome.DENIED.value == "denied"


def test_normalize_audit_action_accepts_enum_and_string():
    assert normalize_audit_action(AuditAction.AUTHENTICATE) == AuditAction.AUTHENTICATE
    assert normalize_audit_action(" AUTHENTICATE ") == AuditAction.AUTHENTICATE
    assert normalize_audit_action("guard_request") == AuditAction.GUARD_REQUEST


def test_normalize_audit_action_rejects_invalid_value():
    with pytest.raises(ValueError):
        normalize_audit_action("bad")

    with pytest.raises(ValueError):
        normalize_audit_action("")


def test_normalize_audit_outcome_accepts_enum_and_string():
    assert normalize_audit_outcome(AuditOutcome.SUCCESS) == AuditOutcome.SUCCESS
    assert normalize_audit_outcome(" SUCCESS ") == AuditOutcome.SUCCESS
    assert normalize_audit_outcome("failure") == AuditOutcome.FAILURE
    assert normalize_audit_outcome("DENIED") == AuditOutcome.DENIED


def test_normalize_audit_outcome_rejects_invalid_value():
    with pytest.raises(ValueError):
        normalize_audit_outcome("bad")

    with pytest.raises(ValueError):
        normalize_audit_outcome("")


def test_validate_audit_helpers():
    assert validate_audit_message(" Message. ") == "Message."
    assert validate_audit_resource(" /api/trade ") == "/api/trade"
    assert validate_audit_metadata({"source": "test"}) == {"source": "test"}
    assert validate_audit_limit(1) == 1

    with pytest.raises(ValueError):
        validate_audit_message(123)

    with pytest.raises(ValueError):
        validate_audit_resource(123)

    with pytest.raises(ValueError):
        validate_audit_metadata([])

    with pytest.raises(ValueError):
        validate_audit_limit(0)

    with pytest.raises(ValueError):
        validate_audit_limit(True)


def test_build_audit_id():
    audit_id = build_audit_id()

    assert audit_id.startswith("audit-")
    assert len(audit_id) > len("audit-")

    with pytest.raises(ValueError):
        build_audit_id("")

    with pytest.raises(ValueError):
        build_audit_id("bad prefix")


def test_audit_log_record_to_dict_and_security_result():
    record = AuditLogRecord(
        audit_id="audit-1",
        action="GUARD_REQUEST",
        outcome="SUCCESS",
        actor_id="user-1",
        resource="/api/trade",
        message="Request allowed.",
        timestamp="2026-01-01T00:00:00+00:00",
        risk_level="LOW",
        metadata={
            "request_id": "req-1",
        },
    )

    assert record.allowed is True
    assert record.denied is False

    assert record.to_dict() == {
        "audit_id": "audit-1",
        "action": "guard_request",
        "outcome": "success",
        "allowed": True,
        "denied": False,
        "actor_id": "user-1",
        "resource": "/api/trade",
        "message": "Request allowed.",
        "timestamp": "2026-01-01T00:00:00+00:00",
        "risk_level": "low",
        "metadata": {
            "request_id": "req-1",
        },
    }

    security_result = record.to_security_result()

    assert security_result.decision == SecurityDecision.ALLOW
    assert security_result.allowed is True
    assert security_result.principal_id == "user-1"
    assert security_result.metadata["audit_id"] == "audit-1"


def test_audit_log_record_denied_security_result():
    record = AuditLogRecord(
        audit_id="audit-1",
        action="permission_check",
        outcome="denied",
        actor_id="user-1",
        resource="/api/trade",
        message="Permission denied.",
        risk_level="high",
    )

    security_result = record.to_security_result()

    assert record.allowed is False
    assert record.denied is True
    assert security_result.decision == SecurityDecision.DENY
    assert security_result.denied is True
    assert security_result.to_dict()["risk_level"] == "high"


def test_audit_log_record_rejects_invalid_values():
    with pytest.raises(ValueError):
        AuditLogRecord(
            audit_id="",
            action="custom",
            outcome="success",
        )

    with pytest.raises(ValueError):
        AuditLogRecord(
            audit_id="audit-1",
            action="bad",
            outcome="success",
        )

    with pytest.raises(ValueError):
        AuditLogRecord(
            audit_id="audit-1",
            action="custom",
            outcome="bad",
        )

    with pytest.raises(ValueError):
        AuditLogRecord(
            audit_id="audit-1",
            action="custom",
            outcome="success",
            actor_id="",
        )

    with pytest.raises(ValueError):
        AuditLogRecord(
            audit_id="audit-1",
            action="custom",
            outcome="success",
            resource=123,
        )

    with pytest.raises(ValueError):
        AuditLogRecord(
            audit_id="audit-1",
            action="custom",
            outcome="success",
            message=123,
        )

    with pytest.raises(ValueError):
        AuditLogRecord(
            audit_id="audit-1",
            action="custom",
            outcome="success",
            timestamp="",
        )

    with pytest.raises(ValueError):
        AuditLogRecord(
            audit_id="audit-1",
            action="custom",
            outcome="success",
            risk_level="bad",
        )

    with pytest.raises(ValueError):
        AuditLogRecord(
            audit_id="audit-1",
            action="custom",
            outcome="success",
            metadata=[],
        )


def test_build_audit_log_record_with_timestamp():
    record = build_audit_log_record(
        audit_id="audit-1",
        action="token_validate",
        outcome="success",
        actor_id="user-1",
        resource="/api/health",
        message="Token valid.",
        timestamp="2026-01-01T00:00:00+00:00",
        metadata={
            "token_id": "token-1",
        },
    )

    assert isinstance(record, AuditLogRecord)
    assert record.to_dict()["audit_id"] == "audit-1"
    assert record.to_dict()["action"] == "token_validate"
    assert record.to_dict()["metadata"] == {
        "token_id": "token-1",
    }


def test_audit_query_to_dict_and_matches():
    record = build_audit_log_record(
        audit_id="audit-1",
        action="guard_request",
        outcome="success",
        actor_id="user-1",
        resource="/api/trade",
    )

    query = AuditQuery(
        actor_id="user-1",
        action="guard_request",
        outcome="success",
        resource="/api/trade",
        limit=10,
    )

    assert query.matches(record) is True
    assert query.to_dict() == {
        "actor_id": "user-1",
        "action": "guard_request",
        "outcome": "success",
        "resource": "/api/trade",
        "limit": 10,
    }


def test_audit_query_rejects_invalid_values():
    with pytest.raises(ValueError):
        AuditQuery(actor_id="")

    with pytest.raises(ValueError):
        AuditQuery(action="bad")

    with pytest.raises(ValueError):
        AuditQuery(outcome="bad")

    with pytest.raises(ValueError):
        AuditQuery(resource=123)

    with pytest.raises(ValueError):
        AuditQuery(limit=0)

    query = AuditQuery()

    with pytest.raises(ValueError):
        query.matches("bad")


def test_build_audit_query():
    query = build_audit_query(
        actor_id="user-1",
        action="custom",
        outcome="success",
        limit=5,
    )

    assert isinstance(query, AuditQuery)
    assert query.to_dict() == {
        "actor_id": "user-1",
        "action": "custom",
        "outcome": "success",
        "limit": 5,
    }


def test_audit_store_append_record_latest_and_summary():
    store = AuditStore()

    record_1 = store.record(
        audit_id="audit-1",
        action="guard_request",
        outcome="success",
        actor_id="user-1",
        resource="/api/health",
        message="Allowed.",
        timestamp="2026-01-01T00:00:00+00:00",
    )
    record_2 = store.record(
        audit_id="audit-2",
        action="permission_check",
        outcome="denied",
        actor_id="user-1",
        resource="/api/trade",
        message="Denied.",
        timestamp="2026-01-01T00:00:01+00:00",
    )

    assert store.count() == 2
    assert store.latest() == [
        record_1,
        record_2,
    ]
    assert store.latest(limit=1) == [
        record_2,
    ]

    assert store.summary() == {
        "records": 2,
        "actions": {
            "guard_request": 1,
            "permission_check": 1,
        },
        "outcomes": {
            "success": 1,
            "denied": 1,
        },
        "actors": {
            "user-1": 2,
        },
    }


def test_audit_store_query_filters():
    store = AuditStore()

    success = store.record(
        audit_id="audit-1",
        action="guard_request",
        outcome="success",
        actor_id="user-1",
        resource="/api/health",
    )
    denied = store.record(
        audit_id="audit-2",
        action="permission_check",
        outcome="denied",
        actor_id="user-2",
        resource="/api/trade",
    )

    assert store.filter_by_actor("user-1") == [
        success,
    ]
    assert store.filter_by_action("permission_check") == [
        denied,
    ]
    assert store.filter_by_outcome("denied") == [
        denied,
    ]
    assert store.filter_by_resource("/api/health") == [
        success,
    ]

    assert store.query(
        AuditQuery(
            outcome="success",
        ),
    ) == [
        success,
    ]


def test_audit_store_to_dicts_and_clear():
    store = AuditStore()

    store.record(
        audit_id="audit-1",
        action="custom",
        outcome="success",
        timestamp="2026-01-01T00:00:00+00:00",
    )

    assert store.to_dicts() == [
        {
            "audit_id": "audit-1",
            "action": "custom",
            "outcome": "success",
            "allowed": True,
            "denied": False,
            "resource": "",
            "message": "",
            "timestamp": "2026-01-01T00:00:00+00:00",
            "risk_level": "low",
            "metadata": {},
        },
    ]

    store.clear()

    assert store.count() == 0
    assert store.summary() == {
        "records": 0,
        "actions": {},
        "outcomes": {},
        "actors": {},
    }


def test_audit_store_rejects_invalid_values():
    store = AuditStore()

    with pytest.raises(ValueError):
        store.append("bad")

    with pytest.raises(ValueError):
        store.latest(limit=0)

    with pytest.raises(ValueError):
        store.query("bad")


def test_audit_logger_records_success_failure_and_denied():
    store = AuditStore()
    logger = AuditLogger(
        store=store,
        component="api",
        default_metadata={
            "env": "test",
        },
    )

    success = logger.success(
        action="guard_request",
        actor_id="user-1",
        resource="/api/health",
        message="Allowed.",
        metadata={
            "request_id": "req-1",
        },
    )
    failure = logger.failure(
        action="token_validate",
        actor_id="user-1",
        resource="/api/health",
        message="Token failed.",
    )
    denied = logger.denied(
        action="permission_check",
        actor_id="user-1",
        resource="/api/trade",
        message="Permission denied.",
    )

    assert store.count() == 3
    assert success.outcome == AuditOutcome.SUCCESS
    assert failure.outcome == AuditOutcome.FAILURE
    assert denied.outcome == AuditOutcome.DENIED
    assert success.metadata == {
        "component": "api",
        "env": "test",
        "request_id": "req-1",
    }
    assert failure.risk_level.value == "high"
    assert denied.risk_level.value == "high"


def test_audit_logger_rejects_invalid_values():
    with pytest.raises(ValueError):
        AuditLogger(store="bad")

    with pytest.raises(ValueError):
        AuditLogger(component="")

    with pytest.raises(ValueError):
        AuditLogger(default_metadata=[])


def test_build_audit_logger():
    logger = build_audit_logger(
        component="security-api",
        default_metadata={
            "env": "test",
        },
    )

    record = logger.success(
        action="custom",
        message="Recorded.",
    )

    assert isinstance(logger, AuditLogger)
    assert record.metadata == {
        "component": "security-api",
        "env": "test",
    }


def test_security_audit_exports_exist():
    import aqos.security as security

    expected_exports = [
        "AuditAction",
        "AuditLogRecord",
        "AuditLogger",
        "AuditOutcome",
        "AuditQuery",
        "AuditStore",
        "build_audit_id",
        "build_audit_log_record",
        "build_audit_logger",
        "build_audit_query",
        "normalize_audit_action",
        "normalize_audit_outcome",
        "validate_audit_limit",
        "validate_audit_message",
        "validate_audit_metadata",
        "validate_audit_resource",
    ]

    for export_name in expected_exports:
        assert hasattr(security, export_name), export_name