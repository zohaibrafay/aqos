"""
Unit tests for AQOS production package exports.
"""

import inspect

import aqos.production as production


EXPECTED_PRODUCTION_EXPORTS = [
    "ConfigRequirementLevel",
    "ConfigValueType",
    "DeploymentArtifact",
    "DeploymentEnvironmentVariable",
    "DeploymentManifest",
    "DeploymentResource",
    "DeploymentResourceType",
    "DeploymentService",
    "DeploymentTarget",
    "PerformanceBudget",
    "PerformanceBudgetDirection",
    "PerformanceBudgetReport",
    "PerformanceBudgetResult",
    "PerformanceMeasurement",
    "PerformanceMetricType",
    "ProductionCheckResult",
    "ProductionGateResult",
    "ProductionHardeningToolkit",
    "ProductionProfile",
    "ProductionSeverity",
    "ProductionStatus",
    "ProductionValidationBundle",
    "ReadinessCategory",
    "ReadinessReport",
    "ReadinessRequirement",
    "ReleaseDecision",
    "ReleaseEvaluation",
    "ReleaseGate",
    "ReleaseGateEngine",
    "ReleaseGateType",
    "ReleasePlan",
    "ReleaseReport",
    "RuntimeConfigField",
    "RuntimeConfigProfile",
    "RuntimeConfigValidationResult",
    "aggregate_production_status",
    "aggregate_release_decision",
    "build_default_deployment_manifest",
    "build_default_performance_budgets",
    "build_default_production_profile",
    "build_default_readiness_requirements",
    "build_default_release_gates",
    "build_default_runtime_config_profile",
    "build_deployment_artifact",
    "build_deployment_environment_variable",
    "build_deployment_manifest",
    "build_deployment_resource",
    "build_deployment_service",
    "build_performance_budget",
    "build_performance_measurement",
    "build_production_check_result",
    "build_production_gate_result",
    "build_production_hardening_toolkit",
    "build_production_profile",
    "build_production_validation_bundle",
    "build_readiness_report",
    "build_readiness_requirement",
    "build_release_evaluation",
    "build_release_gate",
    "build_release_gate_engine",
    "build_release_plan",
    "build_release_report",
    "build_runtime_config_field",
    "build_runtime_config_profile",
    "build_runtime_config_validation_result",
    "check_artifact_availability",
    "check_dependency_status",
    "check_deployment_artifacts",
    "check_deployment_environment_variables",
    "check_deployment_resources",
    "check_deployment_services",
    "check_minimum_test_coverage",
    "check_required_settings",
    "check_service_health",
    "compare_performance_budget",
    "compose_production_metadata",
    "create_release_plan_from_profile",
    "decide_release_from_status",
    "deployment_manifest_to_gate_result",
    "evaluate_performance_budget",
    "evaluate_performance_budgets",
    "evaluate_release_gate",
    "mask_secret_value",
    "normalize_config_requirement_level",
    "normalize_config_value_type",
    "normalize_deployment_resource_type",
    "normalize_deployment_target",
    "normalize_performance_budget_direction",
    "normalize_performance_metric_type",
    "normalize_production_severity",
    "normalize_production_status",
    "normalize_readiness_category",
    "normalize_release_decision",
    "normalize_release_gate_type",
    "performance_metric_unit",
    "production_summary",
    "release_decision_to_status",
    "resolve_runtime_config",
    "run_production_hardening",
    "run_readiness_checks",
    "run_release_gate_engine",
    "runtime_config_to_gate_result",
    "safe_production_check",
    "validate_boolean",
    "validate_check_results",
    "validate_config_checks",
    "validate_config_key",
    "validate_config_value",
    "validate_deployment_artifacts",
    "validate_deployment_environment_variables",
    "validate_deployment_manifest_completeness",
    "validate_deployment_resources",
    "validate_deployment_services",
    "validate_details",
    "validate_environment_name",
    "validate_environment_variable_name",
    "validate_evaluator_mapping",
    "validate_metadata_source",
    "validate_non_empty_string",
    "validate_non_negative_float",
    "validate_non_negative_integer",
    "validate_percentage",
    "validate_performance_budget_results",
    "validate_performance_budgets",
    "validate_performance_measurements",
    "validate_performance_value",
    "validate_port",
    "validate_positive_integer",
    "validate_production_profile_name",
    "validate_readiness_checks",
    "validate_readiness_requirements",
    "validate_release_evaluations",
    "validate_release_gates",
    "validate_release_version",
    "validate_runtime_config",
    "validate_runtime_config_fields",
    "validate_string",
    "validate_string_list",
]


CLASS_EXPORTS = [
    "ConfigRequirementLevel",
    "ConfigValueType",
    "DeploymentArtifact",
    "DeploymentEnvironmentVariable",
    "DeploymentManifest",
    "DeploymentResource",
    "DeploymentResourceType",
    "DeploymentService",
    "DeploymentTarget",
    "PerformanceBudget",
    "PerformanceBudgetDirection",
    "PerformanceBudgetReport",
    "PerformanceBudgetResult",
    "PerformanceMeasurement",
    "PerformanceMetricType",
    "ProductionCheckResult",
    "ProductionGateResult",
    "ProductionHardeningToolkit",
    "ProductionProfile",
    "ProductionSeverity",
    "ProductionStatus",
    "ProductionValidationBundle",
    "ReadinessCategory",
    "ReadinessReport",
    "ReadinessRequirement",
    "ReleaseDecision",
    "ReleaseEvaluation",
    "ReleaseGate",
    "ReleaseGateEngine",
    "ReleaseGateType",
    "ReleasePlan",
    "ReleaseReport",
    "RuntimeConfigField",
    "RuntimeConfigProfile",
    "RuntimeConfigValidationResult",
]


FUNCTION_EXPORTS = [
    export_name
    for export_name in EXPECTED_PRODUCTION_EXPORTS
    if export_name not in CLASS_EXPORTS
]


def test_production_exports_are_complete():
    assert production.__all__ == EXPECTED_PRODUCTION_EXPORTS


def test_production_exports_are_sorted():
    assert production.__all__ == sorted(production.__all__)


def test_production_exports_are_unique():
    assert len(production.__all__) == len(set(production.__all__))


def test_production_exports_exist_on_package():
    for export_name in EXPECTED_PRODUCTION_EXPORTS:
        assert hasattr(production, export_name), export_name


def test_production_class_exports_are_classes():
    for export_name in CLASS_EXPORTS:
        assert inspect.isclass(getattr(production, export_name)), export_name


def test_production_function_exports_are_callables():
    for export_name in FUNCTION_EXPORTS:
        assert callable(getattr(production, export_name)), export_name


def test_production_core_exports_import_directly():
    from aqos.production import (  # noqa: PLC0415
        DeploymentManifest,
        PerformanceBudget,
        ProductionCheckResult,
        ProductionHardeningToolkit,
        ProductionProfile,
        ReadinessReport,
        ReleaseGate,
        RuntimeConfigProfile,
    )

    assert DeploymentManifest.__name__ == "DeploymentManifest"
    assert PerformanceBudget.__name__ == "PerformanceBudget"
    assert ProductionCheckResult.__name__ == "ProductionCheckResult"
    assert ProductionHardeningToolkit.__name__ == "ProductionHardeningToolkit"
    assert ProductionProfile.__name__ == "ProductionProfile"
    assert ReadinessReport.__name__ == "ReadinessReport"
    assert ReleaseGate.__name__ == "ReleaseGate"
    assert RuntimeConfigProfile.__name__ == "RuntimeConfigProfile"


def test_production_export_groups_exist():
    base_exports = {
        "ProductionCheckResult",
        "ProductionGateResult",
        "ProductionSeverity",
        "ProductionStatus",
    }
    config_exports = {
        "ConfigRequirementLevel",
        "ConfigValueType",
        "RuntimeConfigField",
        "RuntimeConfigProfile",
        "RuntimeConfigValidationResult",
    }
    deployment_exports = {
        "DeploymentArtifact",
        "DeploymentEnvironmentVariable",
        "DeploymentManifest",
        "DeploymentResource",
        "DeploymentResourceType",
        "DeploymentService",
        "DeploymentTarget",
    }
    performance_exports = {
        "PerformanceBudget",
        "PerformanceBudgetDirection",
        "PerformanceBudgetReport",
        "PerformanceBudgetResult",
        "PerformanceMeasurement",
        "PerformanceMetricType",
    }
    readiness_exports = {
        "ReadinessCategory",
        "ReadinessReport",
        "ReadinessRequirement",
    }
    release_exports = {
        "ReleaseDecision",
        "ReleaseEvaluation",
        "ReleaseGate",
        "ReleaseGateEngine",
        "ReleaseGateType",
        "ReleasePlan",
        "ReleaseReport",
    }
    integration_exports = {
        "ProductionHardeningToolkit",
        "ProductionProfile",
        "ProductionValidationBundle",
    }

    exports = set(production.__all__)

    assert base_exports.issubset(exports)
    assert config_exports.issubset(exports)
    assert deployment_exports.issubset(exports)
    assert performance_exports.issubset(exports)
    assert readiness_exports.issubset(exports)
    assert release_exports.issubset(exports)
    assert integration_exports.issubset(exports)