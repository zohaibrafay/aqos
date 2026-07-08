"""
Unit tests for AQOS production integration helpers.
"""

import pytest

from aqos.production import (
    DeploymentManifest,
    PerformanceMeasurement,
    ProductionHardeningToolkit,
    ProductionProfile,
    ProductionStatus,
    ProductionValidationBundle,
    ReleasePlan,
    build_default_production_profile,
    build_default_release_gates,
    build_deployment_artifact,
    build_deployment_environment_variable,
    build_deployment_manifest,
    build_deployment_resource,
    build_deployment_service,
    build_performance_measurement,
    build_production_check_result,
    build_production_hardening_toolkit,
    build_production_profile,
    build_production_validation_bundle,
    compose_production_metadata,
    create_release_plan_from_profile,
    production_summary,
    run_production_hardening,
    validate_environment_name,
    validate_metadata_source,
    validate_production_profile_name,
    validate_release_version,
)


def build_ready_manifest() -> DeploymentManifest:
    return build_deployment_manifest(
        name="aqos",
        version="v0.20.0-dev",
        environment="production",
        target="docker",
        services=[
            build_deployment_service(
                name="aqos-api",
                image="aqos/api:v0.20.0-dev",
                port=8000,
            ),
        ],
        resources=[
            build_deployment_resource(
                name="postgres",
                resource_type="database",
            ),
        ],
        artifacts=[
            build_deployment_artifact(
                name="model-registry",
                path="artifacts/models",
                version="v0.20.0-dev",
            ),
        ],
        environment_variables=[
            build_deployment_environment_variable(
                name="DATABASE_URL",
                secret=True,
            ),
            build_deployment_environment_variable(
                name="AQOS_ENV",
                default="production",
            ),
        ],
    )


def build_ready_measurements() -> list[PerformanceMeasurement]:
    return [
        build_performance_measurement(
            name="latency",
            metric_type="latency_ms",
            value=250,
        ),
        build_performance_measurement(
            name="memory",
            metric_type="memory_mb",
            value=512,
        ),
        build_performance_measurement(
            name="cpu",
            metric_type="cpu_percent",
            value=50,
        ),
        build_performance_measurement(
            name="error-rate",
            metric_type="error_rate_percent",
            value=0.5,
        ),
        build_performance_measurement(
            name="throughput",
            metric_type="throughput_rps",
            value=20,
        ),
    ]


def test_build_default_release_gates():
    gates = build_default_release_gates()

    assert len(gates) == 4
    assert [gate.name for gate in gates] == [
        "runtime-configuration",
        "deployment-manifest",
        "production-readiness",
        "performance-budget",
    ]
    assert gates[-1].required is False


def test_production_profile_to_dict():
    profile = build_production_profile(
        name="aqos-production",
        version="v0.20.0-dev",
        environment="production",
        deployment_manifest=build_ready_manifest(),
        metadata={
            "source": "test",
        },
    )

    assert isinstance(profile, ProductionProfile)
    assert len(profile.resolved_release_gates) == 4

    payload = profile.to_dict()

    assert payload["name"] == "aqos-production"
    assert payload["version"] == "v0.20.0-dev"
    assert payload["environment"] == "production"
    assert payload["metadata"] == {
        "source": "test",
    }
    assert len(payload["release_gates"]) == 4


def test_production_profile_rejects_invalid_values():
    manifest = build_ready_manifest()

    with pytest.raises(ValueError):
        ProductionProfile(
            name="",
            version="v0.20.0-dev",
            deployment_manifest=manifest,
        )

    with pytest.raises(ValueError):
        ProductionProfile(
            name="profile",
            version="",
            deployment_manifest=manifest,
        )

    with pytest.raises(ValueError):
        ProductionProfile(
            name="profile",
            version="v1",
            environment="",
            deployment_manifest=manifest,
        )

    with pytest.raises(ValueError):
        ProductionProfile(
            name="profile",
            version="v1",
            runtime_config_profile="bad",
            deployment_manifest=manifest,
        )

    with pytest.raises(ValueError):
        ProductionProfile(
            name="profile",
            version="v1",
            deployment_manifest="bad",
        )

    with pytest.raises(ValueError):
        ProductionProfile(
            name="profile",
            version="v1",
            deployment_manifest=manifest,
            performance_budgets=["bad"],
        )

    with pytest.raises(ValueError):
        ProductionProfile(
            name="profile",
            version="v1",
            deployment_manifest=manifest,
            readiness_requirements=["bad"],
        )

    with pytest.raises(ValueError):
        ProductionProfile(
            name="profile",
            version="v1",
            deployment_manifest=manifest,
            release_gates=["bad"],
        )

    with pytest.raises(ValueError):
        ProductionProfile(
            name="profile",
            version="v1",
            deployment_manifest=manifest,
            metadata=[],
        )


def test_build_default_production_profile():
    profile = build_default_production_profile(
        version="v0.20.0-dev",
        environment="production",
    )

    assert isinstance(profile, ProductionProfile)
    assert profile.name == "aqos-production"
    assert profile.version == "v0.20.0-dev"
    assert profile.environment == "production"
    assert profile.metadata == {
        "generated_by": "aqos.production",
    }


def test_create_release_plan_from_profile():
    profile = build_production_profile(
        name="aqos-production",
        version="v0.20.0-dev",
        deployment_manifest=build_ready_manifest(),
    )

    plan = create_release_plan_from_profile(profile)

    assert isinstance(plan, ReleasePlan)
    assert plan.version == "v0.20.0-dev"
    assert plan.environment == "production"
    assert plan.gate_names == [
        "runtime-configuration",
        "deployment-manifest",
        "production-readiness",
        "performance-budget",
    ]

    with pytest.raises(ValueError):
        create_release_plan_from_profile("bad")


def test_compose_production_metadata():
    metadata = compose_production_metadata(
        source="test",
        environment="production",
        version="v0.20.0-dev",
        extra={
            "branch": "main",
        },
    )

    assert metadata == {
        "source": "test",
        "environment": "production",
        "version": "v0.20.0-dev",
        "branch": "main",
    }

    with pytest.raises(ValueError):
        compose_production_metadata(
            source="",
            environment="production",
            version="v1",
        )

    with pytest.raises(ValueError):
        compose_production_metadata(
            source="test",
            environment="",
            version="v1",
        )

    with pytest.raises(ValueError):
        compose_production_metadata(
            source="test",
            environment="production",
            version="",
        )

    with pytest.raises(ValueError):
        compose_production_metadata(
            source="test",
            environment="production",
            version="v1",
            extra=[],
        )


def test_run_production_hardening_ready():
    profile = build_production_profile(
        name="aqos-production",
        version="v0.20.0-dev",
        environment="production",
        deployment_manifest=build_ready_manifest(),
    )

    bundle = run_production_hardening(
        profile=profile,
        runtime_values={
            "DATABASE_URL": "postgres://example",
        },
        available_resources={
            "postgres": True,
        },
        available_artifacts={
            "model-registry": True,
        },
        environment_values={
            "DATABASE_URL": "postgres://example",
            "AQOS_ENV": "production",
        },
        performance_measurements=build_ready_measurements(),
        readiness_checks=[
            lambda: build_production_check_result(
                name="smoke-test",
                status="ready",
                passed=True,
            ),
        ],
        metadata={
            "source": "test",
        },
    )

    assert isinstance(bundle, ProductionValidationBundle)
    assert bundle.passed is True
    assert bundle.status == ProductionStatus.READY
    assert bundle.release_report.approved is True
    assert bundle.metadata == {
        "source": "test",
    }

    gate = bundle.to_gate_result()

    assert gate.gate_name == "production-hardening"
    assert gate.status == ProductionStatus.READY
    assert gate.passed is True

    summary = production_summary(bundle)

    assert summary["profile"] == "aqos-production"
    assert summary["status"] == "ready"
    assert summary["passed"] is True


def test_run_production_hardening_blocks_missing_values():
    profile = build_production_profile(
        name="aqos-production",
        version="v0.20.0-dev",
        environment="production",
        deployment_manifest=build_ready_manifest(),
    )

    bundle = run_production_hardening(
        profile=profile,
        runtime_values={},
        available_resources={},
        available_artifacts={},
        environment_values={},
        performance_measurements=[],
        readiness_checks=[],
    )

    assert bundle.failed is True
    assert bundle.status == ProductionStatus.BLOCKED
    assert bundle.release_report.blocked is True


def test_run_production_hardening_rejects_invalid_values():
    profile = build_default_production_profile()

    with pytest.raises(ValueError):
        run_production_hardening(
            profile="bad",
            runtime_values={},
        )

    with pytest.raises(ValueError):
        run_production_hardening(
            profile=profile,
            runtime_values=[],
        )

    with pytest.raises(ValueError):
        run_production_hardening(
            profile=profile,
            runtime_values={},
            available_resources=[],
        )

    with pytest.raises(ValueError):
        run_production_hardening(
            profile=profile,
            runtime_values={},
            available_artifacts=[],
        )

    with pytest.raises(ValueError):
        run_production_hardening(
            profile=profile,
            runtime_values={},
            environment_values=[],
        )

    with pytest.raises(ValueError):
        run_production_hardening(
            profile=profile,
            runtime_values={},
            performance_measurements=["bad"],
        )

    with pytest.raises(ValueError):
        run_production_hardening(
            profile=profile,
            runtime_values={},
            readiness_checks="bad",
        )

    with pytest.raises(ValueError):
        run_production_hardening(
            profile=profile,
            runtime_values={},
            metadata=[],
        )


def test_production_validation_bundle_to_dict_rejects_invalid_values():
    profile = build_production_profile(
        name="aqos-production",
        version="v0.20.0-dev",
        deployment_manifest=build_ready_manifest(),
    )

    bundle = run_production_hardening(
        profile=profile,
        runtime_values={
            "DATABASE_URL": "postgres://example",
        },
        available_resources={
            "postgres": True,
        },
        available_artifacts={
            "model-registry": True,
        },
        environment_values={
            "DATABASE_URL": "postgres://example",
            "AQOS_ENV": "production",
        },
        performance_measurements=build_ready_measurements(),
    )

    payload = bundle.to_dict()

    assert payload["status"] == "ready"
    assert payload["passed"] is True
    assert payload["profile"]["name"] == "aqos-production"

    rebuilt = build_production_validation_bundle(
        profile=bundle.profile,
        config_result=bundle.config_result,
        deployment_gate=bundle.deployment_gate,
        readiness_report=bundle.readiness_report,
        performance_report=bundle.performance_report,
        release_report=bundle.release_report,
        metadata={
            "source": "rebuilt",
        },
    )

    assert isinstance(rebuilt, ProductionValidationBundle)
    assert rebuilt.metadata == {
        "source": "rebuilt",
    }

    with pytest.raises(ValueError):
        ProductionValidationBundle(
            profile="bad",
            config_result=bundle.config_result,
            deployment_gate=bundle.deployment_gate,
            readiness_report=bundle.readiness_report,
            performance_report=bundle.performance_report,
            release_report=bundle.release_report,
        )

    with pytest.raises(ValueError):
        ProductionValidationBundle(
            profile=bundle.profile,
            config_result="bad",
            deployment_gate=bundle.deployment_gate,
            readiness_report=bundle.readiness_report,
            performance_report=bundle.performance_report,
            release_report=bundle.release_report,
        )

    with pytest.raises(ValueError):
        ProductionValidationBundle(
            profile=bundle.profile,
            config_result=bundle.config_result,
            deployment_gate="bad",
            readiness_report=bundle.readiness_report,
            performance_report=bundle.performance_report,
            release_report=bundle.release_report,
        )

    with pytest.raises(ValueError):
        ProductionValidationBundle(
            profile=bundle.profile,
            config_result=bundle.config_result,
            deployment_gate=bundle.deployment_gate,
            readiness_report="bad",
            performance_report=bundle.performance_report,
            release_report=bundle.release_report,
        )

    with pytest.raises(ValueError):
        ProductionValidationBundle(
            profile=bundle.profile,
            config_result=bundle.config_result,
            deployment_gate=bundle.deployment_gate,
            readiness_report=bundle.readiness_report,
            performance_report="bad",
            release_report=bundle.release_report,
        )

    with pytest.raises(ValueError):
        ProductionValidationBundle(
            profile=bundle.profile,
            config_result=bundle.config_result,
            deployment_gate=bundle.deployment_gate,
            readiness_report=bundle.readiness_report,
            performance_report=bundle.performance_report,
            release_report="bad",
        )

    with pytest.raises(ValueError):
        ProductionValidationBundle(
            profile=bundle.profile,
            config_result=bundle.config_result,
            deployment_gate=bundle.deployment_gate,
            readiness_report=bundle.readiness_report,
            performance_report=bundle.performance_report,
            release_report=bundle.release_report,
            metadata=[],
        )


def test_production_hardening_toolkit():
    profile = build_production_profile(
        name="aqos-production",
        version="v0.20.0-dev",
        deployment_manifest=build_ready_manifest(),
    )
    toolkit = build_production_hardening_toolkit(
        profile=profile,
        metadata={
            "source": "toolkit",
        },
    )

    assert isinstance(toolkit, ProductionHardeningToolkit)
    assert toolkit.summary()["profile"] == "aqos-production"
    assert toolkit.summary()["metadata"] == {
        "source": "toolkit",
    }

    plan = toolkit.build_release_plan()

    assert isinstance(plan, ReleasePlan)

    bundle = toolkit.run(
        runtime_values={
            "DATABASE_URL": "postgres://example",
        },
        available_resources={
            "postgres": True,
        },
        available_artifacts={
            "model-registry": True,
        },
        environment_values={
            "DATABASE_URL": "postgres://example",
            "AQOS_ENV": "production",
        },
        performance_measurements=build_ready_measurements(),
    )

    assert bundle.passed is True

    with pytest.raises(ValueError):
        ProductionHardeningToolkit(profile="bad")

    with pytest.raises(ValueError):
        ProductionHardeningToolkit(profile=profile, metadata=[])


def test_validate_production_helpers():
    assert validate_production_profile_name("aqos-production") == "aqos-production"
    assert validate_release_version("v0.20.0-dev") == "v0.20.0-dev"
    assert validate_environment_name("production") == "production"
    assert validate_environment_name("staging") == "staging"
    assert validate_metadata_source("test") == "test"

    with pytest.raises(ValueError):
        validate_production_profile_name("")

    with pytest.raises(ValueError):
        validate_production_profile_name("bad profile")

    with pytest.raises(ValueError):
        validate_release_version("0.20.0-dev")

    with pytest.raises(ValueError):
        validate_environment_name("qa")

    with pytest.raises(ValueError):
        validate_metadata_source("")


def test_production_summary_rejects_invalid_value():
    with pytest.raises(ValueError):
        production_summary("bad")


def test_production_integration_exports_exist():
    import aqos.production as production

    expected_exports = [
        "ProductionHardeningToolkit",
        "ProductionProfile",
        "ProductionValidationBundle",
        "build_default_production_profile",
        "build_default_release_gates",
        "build_production_hardening_toolkit",
        "build_production_profile",
        "build_production_validation_bundle",
        "compose_production_metadata",
        "create_release_plan_from_profile",
        "production_summary",
        "run_production_hardening",
        "validate_environment_name",
        "validate_metadata_source",
        "validate_production_profile_name",
        "validate_release_version",
    ]

    for export_name in expected_exports:
        assert hasattr(production, export_name), export_name