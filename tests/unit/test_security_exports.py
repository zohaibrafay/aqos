"""
Unit tests for AQOS security package exports.
"""

import inspect

import aqos.security as security


EXPECTED_SECURITY_EXPORTS = [
    "AccessToken",
    "ApiKeyCredential",
    "AuditAction",
    "AuditLogRecord",
    "AuditLogger",
    "AuditOutcome",
    "AuditQuery",
    "AuditStore",
    "DEFAULT_BLOCKED_PATTERNS",
    "GuardAction",
    "GuardedRequest",
    "Permission",
    "PermissionCheck",
    "PermissionCheckResult",
    "PermissionEffect",
    "PermissionRegistry",
    "PolicyCondition",
    "PolicyEffect",
    "PolicyEngine",
    "PolicyEvaluationRequest",
    "PolicyEvaluationResult",
    "PolicyOperator",
    "PolicyRule",
    "RequestGuard",
    "RequestGuardConfig",
    "RequestGuardResult",
    "Role",
    "RuntimeEnvironment",
    "SanitizationResult",
    "SecurityContextManager",
    "SecurityContextState",
    "SecurityDecision",
    "SecurityPrincipal",
    "SecurityResult",
    "SecurityRiskLevel",
    "SecurityRuntimeContext",
    "TokenStatus",
    "TokenStore",
    "TokenType",
    "TokenValidationResult",
    "build_access_token",
    "build_anonymous_context",
    "build_api_key",
    "build_api_key_credential",
    "build_audit_id",
    "build_audit_log_record",
    "build_audit_logger",
    "build_audit_query",
    "build_authenticated_context",
    "build_context_from_token_validation",
    "build_context_id",
    "build_default_permission_registry",
    "build_guarded_request",
    "build_permission",
    "build_permission_check",
    "build_policy_condition",
    "build_policy_context",
    "build_policy_engine",
    "build_policy_evaluation_request",
    "build_policy_rule",
    "build_raw_token",
    "build_request_guard",
    "build_role",
    "build_security_principal",
    "build_security_result",
    "build_security_runtime_context",
    "build_token_id",
    "compare_policy_condition",
    "contains_blocked_pattern",
    "context_has_permission",
    "context_has_role",
    "context_has_scope",
    "deduplicate_violations",
    "evaluate_permission_check",
    "get_nested_context_value",
    "hash_secret",
    "is_expired_at",
    "mask_secret",
    "match_policy_pattern",
    "merge_context_attributes",
    "normalize_audit_action",
    "normalize_audit_outcome",
    "normalize_context_state",
    "normalize_guard_action",
    "normalize_permission_effect",
    "normalize_policy_effect",
    "normalize_policy_operator",
    "normalize_risk_level",
    "normalize_runtime_environment",
    "normalize_security_decision",
    "normalize_security_decision_for_policy",
    "normalize_token_status",
    "normalize_token_type",
    "parse_iso_datetime",
    "remove_control_characters",
    "require_permission",
    "sanitize_dict",
    "sanitize_guarded_request",
    "sanitize_list",
    "sanitize_string",
    "sanitize_value",
    "validate_access_token_record",
    "validate_api_key_credential",
    "validate_attributes",
    "validate_audit_limit",
    "validate_audit_message",
    "validate_audit_metadata",
    "validate_audit_resource",
    "validate_context_id",
    "validate_http_method",
    "validate_http_method_list",
    "validate_max_string_length",
    "validate_non_empty_string",
    "validate_permission_list",
    "validate_permission_name",
    "validate_policy_action",
    "validate_policy_conditions",
    "validate_policy_field",
    "validate_policy_name",
    "validate_policy_priority",
    "validate_policy_resource",
    "validate_raw_secret",
    "validate_request_path",
    "validate_role_name",
    "validate_string",
    "validate_string_list",
    "verify_secret",
]


CLASS_EXPORTS = [
    "AccessToken",
    "ApiKeyCredential",
    "AuditAction",
    "AuditLogRecord",
    "AuditLogger",
    "AuditOutcome",
    "AuditQuery",
    "AuditStore",
    "GuardAction",
    "GuardedRequest",
    "Permission",
    "PermissionCheck",
    "PermissionCheckResult",
    "PermissionEffect",
    "PermissionRegistry",
    "PolicyCondition",
    "PolicyEffect",
    "PolicyEngine",
    "PolicyEvaluationRequest",
    "PolicyEvaluationResult",
    "PolicyOperator",
    "PolicyRule",
    "RequestGuard",
    "RequestGuardConfig",
    "RequestGuardResult",
    "Role",
    "RuntimeEnvironment",
    "SanitizationResult",
    "SecurityContextManager",
    "SecurityContextState",
    "SecurityDecision",
    "SecurityPrincipal",
    "SecurityResult",
    "SecurityRiskLevel",
    "SecurityRuntimeContext",
    "TokenStatus",
    "TokenStore",
    "TokenType",
    "TokenValidationResult",
]


FUNCTION_EXPORTS = [
    export_name
    for export_name in EXPECTED_SECURITY_EXPORTS
    if export_name not in CLASS_EXPORTS and export_name != "DEFAULT_BLOCKED_PATTERNS"
]


def test_security_exports_are_complete():
    assert security.__all__ == EXPECTED_SECURITY_EXPORTS


def test_security_exports_are_sorted():
    assert security.__all__ == sorted(security.__all__)


def test_security_exports_are_unique():
    assert len(security.__all__) == len(set(security.__all__))


def test_security_exports_exist_on_package():
    for export_name in EXPECTED_SECURITY_EXPORTS:
        assert hasattr(security, export_name), export_name


def test_security_class_exports_are_classes():
    for export_name in CLASS_EXPORTS:
        assert inspect.isclass(getattr(security, export_name)), export_name


def test_security_function_exports_are_callables():
    for export_name in FUNCTION_EXPORTS:
        assert callable(getattr(security, export_name)), export_name


def test_security_constant_exports_exist():
    assert isinstance(security.DEFAULT_BLOCKED_PATTERNS, list)
    assert "<script" in security.DEFAULT_BLOCKED_PATTERNS


def test_core_security_exports_import_directly():
    from aqos.security import (  # noqa: PLC0415
        AuditLogger,
        PermissionRegistry,
        PolicyEngine,
        RequestGuard,
        SecurityContextManager,
        SecurityPrincipal,
        TokenStore,
    )

    assert SecurityPrincipal.__name__ == "SecurityPrincipal"
    assert TokenStore.__name__ == "TokenStore"
    assert PermissionRegistry.__name__ == "PermissionRegistry"
    assert RequestGuard.__name__ == "RequestGuard"
    assert AuditLogger.__name__ == "AuditLogger"
    assert PolicyEngine.__name__ == "PolicyEngine"
    assert SecurityContextManager.__name__ == "SecurityContextManager"


def test_security_export_groups_exist():
    base_exports = {
        "SecurityDecision",
        "SecurityPrincipal",
        "SecurityResult",
        "SecurityRiskLevel",
    }
    token_exports = {
        "AccessToken",
        "ApiKeyCredential",
        "TokenStore",
        "TokenValidationResult",
    }
    permission_exports = {
        "Permission",
        "PermissionRegistry",
        "Role",
    }
    guard_exports = {
        "GuardedRequest",
        "RequestGuard",
        "RequestGuardConfig",
    }
    audit_exports = {
        "AuditLogRecord",
        "AuditLogger",
        "AuditStore",
    }
    policy_exports = {
        "PolicyCondition",
        "PolicyEngine",
        "PolicyRule",
    }
    context_exports = {
        "SecurityContextManager",
        "SecurityRuntimeContext",
    }

    exports = set(security.__all__)

    assert base_exports.issubset(exports)
    assert token_exports.issubset(exports)
    assert permission_exports.issubset(exports)
    assert guard_exports.issubset(exports)
    assert audit_exports.issubset(exports)
    assert policy_exports.issubset(exports)
    assert context_exports.issubset(exports)