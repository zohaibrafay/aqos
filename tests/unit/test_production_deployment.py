"""
Unit tests for AQOS production deployment manifest helpers.
"""

import pytest

from aqos.production import (
    DeploymentArtifact,
    DeploymentEnvironmentVariable,
    DeploymentManifest,
    DeploymentResource,
    DeploymentResourceType,
    DeploymentService,
    DeploymentTarget,
    ProductionStatus,
    build_default_deployment_manifest,
    build_deployment_artifact,
    build_deployment_environment_variable,
    build_deployment_manifest,
    build_deployment_resource,
    build_deployment_service,
    check_deployment_artifacts,
    check_deployment_environment_variables,
    check_deployment_resources,
    check_deployment_services,
    deployment_manifest_to_gate_result,
    normalize_deployment_resource_type,
    normalize_deployment_target,
    validate_deployment_artifacts,
    validate_deployment_environment_variables,
    validate_deployment_manifest_completeness,
    validate_deployment_resources,
    validate_deployment_services,
    validate_environment_variable_name,
    validate_port,
)


def test_deployment_target_values():
    assert DeploymentTarget.LOCAL.value == "local"
    assert DeploymentTarget.DOCKER.value == "docker"
    assert DeploymentTarget.KUBERNETES.value == "kubernetes"
    assert DeploymentTarget.CLOUD.value == "cloud"


def test_deployment_resource_type_values():
    assert DeploymentResourceType.SERVICE.value == "service"
    assert DeploymentResourceType.DATABASE.value == "database"
    assert DeploymentResourceType.CACHE.value == "cache"
    assert DeploymentResourceType.QUEUE.value == "queue"
    assert DeploymentResourceType.STORAGE.value == "storage"
    assert DeploymentResourceType.MODEL.value == "model"


def test_normalize_deployment_target_accepts_enum_and_string():
    assert normalize_deployment_target(DeploymentTarget.DOCKER) == DeploymentTarget.DOCKER
    assert normalize_deployment_target(" DOCKER ") == DeploymentTarget.DOCKER
    assert normalize_deployment_target("kubernetes") == DeploymentTarget.KUBERNETES
    assert normalize_deployment_target("CLOUD") == DeploymentTarget.CLOUD


def test_normalize_deployment_target_rejects_invalid_value():
    with pytest.raises(ValueError):
        normalize_deployment_target("bad")

    with pytest.raises(ValueError):
        normalize_deployment_target("")


def test_normalize_deployment_resource_type_accepts_enum_and_string():
    assert normalize_deployment_resource_type(DeploymentResourceType.DATABASE) == DeploymentResourceType.DATABASE
    assert normalize_deployment_resource_type(" DATABASE ") == DeploymentResourceType.DATABASE
    assert normalize_deployment_resource_type("cache") == DeploymentResourceType.CACHE
    assert normalize_deployment_resource_type("MODEL") == DeploymentResourceType.MODEL


def test_normalize_deployment_resource_type_rejects_invalid_value():
    with pytest.raises(ValueError):
        normalize_deployment_resource_type("bad")

    with pytest.raises(ValueError):
        normalize_deployment_resource_type("")


def test_validate_environment_variable_name():
    assert validate_environment_variable_name("DATABASE_URL") == "DATABASE_URL"
    assert validate_environment_variable_name("AQOS_ENV") == "AQOS_ENV"

    with pytest.raises(ValueError):
        validate_environment_variable_name("")

    with pytest.raises(ValueError):
        validate_environment_variable_name("database_url")

    with pytest.raises(ValueError):
        validate_environment_variable_name("1_DATABASE")

    with pytest.raises(ValueError):
        validate_environment_variable_name("BAD-NAME")


def test_validate_port():
    assert validate_port(1) == 1
    assert validate_port(65535) == 65535

    with pytest.raises(ValueError):
        validate_port(0)

    with pytest.raises(ValueError):
        validate_port(65536)

    with pytest.raises(ValueError):
        validate_port(True)

    with pytest.raises(ValueError):
        validate_port("8000")


def test_deployment_resource_to_dict():
    resource = DeploymentResource(
        name=" postgres ",
        resource_type="DATABASE",
        required=True,
        metadata={
            "version": "16",
        },
    )

    assert resource.to_dict() == {
        "name": "postgres",
        "resource_type": "database",
        "required": True,
        "metadata": {
            "version": "16",
        },
    }


def test_deployment_resource_rejects_invalid_values():
    with pytest.raises(ValueError):
        DeploymentResource(name="", resource_type="database")

    with pytest.raises(ValueError):
        DeploymentResource(name="postgres", resource_type="bad")

    with pytest.raises(ValueError):
        DeploymentResource(name="postgres", resource_type="database", required="yes")

    with pytest.raises(ValueError):
        DeploymentResource(name="postgres", resource_type="database", metadata=[])


def test_build_deployment_resource():
    resource = build_deployment_resource(
        name="redis",
        resource_type="cache",
        required=False,
        metadata={
            "source": "test",
        },
    )

    assert isinstance(resource, DeploymentResource)
    assert resource.required is False
    assert resource.metadata == {
        "source": "test",
    }


def test_deployment_artifact_to_dict():
    artifact = DeploymentArtifact(
        name=" model ",
        path=" artifacts/model.pkl ",
        version=" v1 ",
        required=True,
        checksum=" abc ",
        metadata={
            "kind": "pickle",
        },
    )

    assert artifact.to_dict() == {
        "name": "model",
        "path": "artifacts/model.pkl",
        "version": "v1",
        "required": True,
        "checksum": "abc",
        "metadata": {
            "kind": "pickle",
        },
    }


def test_deployment_artifact_rejects_invalid_values():
    with pytest.raises(ValueError):
        DeploymentArtifact(name="", path="path", version="v1")

    with pytest.raises(ValueError):
        DeploymentArtifact(name="artifact", path="", version="v1")

    with pytest.raises(ValueError):
        DeploymentArtifact(name="artifact", path="path", version="")

    with pytest.raises(ValueError):
        DeploymentArtifact(name="artifact", path="path", version="v1", required="yes")

    with pytest.raises(ValueError):
        DeploymentArtifact(name="artifact", path="path", version="v1", checksum=123)

    with pytest.raises(ValueError):
        DeploymentArtifact(name="artifact", path="path", version="v1", metadata=[])


def test_build_deployment_artifact():
    artifact = build_deployment_artifact(
        name="model",
        path="artifacts/model.pkl",
        version="v1",
        checksum="abc",
    )

    assert isinstance(artifact, DeploymentArtifact)
    assert artifact.checksum == "abc"


def test_deployment_environment_variable_to_dict():
    variable = DeploymentEnvironmentVariable(
        name="DATABASE_URL",
        required=True,
        secret=True,
        default=None,
        description=" Database URL. ",
    )

    assert variable.to_dict() == {
        "name": "DATABASE_URL",
        "required": True,
        "secret": True,
        "default": None,
        "description": "Database URL.",
    }


def test_deployment_environment_variable_rejects_invalid_values():
    with pytest.raises(ValueError):
        DeploymentEnvironmentVariable(name="bad")

    with pytest.raises(ValueError):
        DeploymentEnvironmentVariable(name="DATABASE_URL", required="yes")

    with pytest.raises(ValueError):
        DeploymentEnvironmentVariable(name="DATABASE_URL", secret="yes")

    with pytest.raises(ValueError):
        DeploymentEnvironmentVariable(name="DATABASE_URL", default=123)

    with pytest.raises(ValueError):
        DeploymentEnvironmentVariable(name="DATABASE_URL", description=123)


def test_build_deployment_environment_variable():
    variable = build_deployment_environment_variable(
        name="SECRET_KEY",
        required=True,
        secret=True,
        description="Secret.",
    )

    assert isinstance(variable, DeploymentEnvironmentVariable)
    assert variable.secret is True


def test_deployment_service_to_dict():
    service = DeploymentService(
        name=" api ",
        image=" aqos/api:v1 ",
        replicas=2,
        port=8000,
        cpu_limit=1.5,
        memory_limit_mb=1024,
        healthcheck_path=" /health ",
        metadata={
            "tier": "backend",
        },
    )

    assert service.to_dict() == {
        "name": "api",
        "image": "aqos/api:v1",
        "replicas": 2,
        "port": 8000,
        "cpu_limit": 1.5,
        "memory_limit_mb": 1024.0,
        "healthcheck_path": "/health",
        "metadata": {
            "tier": "backend",
        },
    }


def test_deployment_service_rejects_invalid_values():
    with pytest.raises(ValueError):
        DeploymentService(name="", image="image")

    with pytest.raises(ValueError):
        DeploymentService(name="api", image="")

    with pytest.raises(ValueError):
        DeploymentService(name="api", image="image", replicas=0)

    with pytest.raises(ValueError):
        DeploymentService(name="api", image="image", port=0)

    with pytest.raises(ValueError):
        DeploymentService(name="api", image="image", cpu_limit=-1)

    with pytest.raises(ValueError):
        DeploymentService(name="api", image="image", memory_limit_mb=-1)

    with pytest.raises(ValueError):
        DeploymentService(name="api", image="image", healthcheck_path=123)

    with pytest.raises(ValueError):
        DeploymentService(name="api", image="image", metadata=[])


def test_build_deployment_service():
    service = build_deployment_service(
        name="api",
        image="aqos/api:v1",
        port=8000,
    )

    assert isinstance(service, DeploymentService)
    assert service.port == 8000


def test_validate_deployment_lists():
    service = build_deployment_service(name="api", image="aqos/api:v1")
    resource = build_deployment_resource(name="postgres", resource_type="database")
    artifact = build_deployment_artifact(name="model", path="model.pkl", version="v1")
    variable = build_deployment_environment_variable(name="DATABASE_URL")

    assert validate_deployment_services([service]) == [service]
    assert validate_deployment_resources([resource]) == [resource]
    assert validate_deployment_artifacts([artifact]) == [artifact]
    assert validate_deployment_environment_variables([variable]) == [variable]

    with pytest.raises(ValueError):
        validate_deployment_services("bad")

    with pytest.raises(ValueError):
        validate_deployment_services(["bad"])

    with pytest.raises(ValueError):
        validate_deployment_resources("bad")

    with pytest.raises(ValueError):
        validate_deployment_resources(["bad"])

    with pytest.raises(ValueError):
        validate_deployment_artifacts("bad")

    with pytest.raises(ValueError):
        validate_deployment_artifacts(["bad"])

    with pytest.raises(ValueError):
        validate_deployment_environment_variables("bad")

    with pytest.raises(ValueError):
        validate_deployment_environment_variables(["bad"])


def test_deployment_manifest_to_dict():
    service = build_deployment_service(name="api", image="aqos/api:v1", port=8000)
    resource = build_deployment_resource(name="postgres", resource_type="database")
    artifact = build_deployment_artifact(name="model", path="model.pkl", version="v1")
    variable = build_deployment_environment_variable(name="DATABASE_URL", secret=True)

    manifest = DeploymentManifest(
        name=" aqos ",
        version=" v1 ",
        environment=" production ",
        target="DOCKER",
        services=[service],
        resources=[resource],
        artifacts=[artifact],
        environment_variables=[variable],
        metadata={
            "branch": "main",
        },
        generated_at="2026-01-01T00:00:00+00:00",
    )

    payload = manifest.to_dict()

    assert payload["name"] == "aqos"
    assert payload["version"] == "v1"
    assert payload["environment"] == "production"
    assert payload["target"] == "docker"
    assert payload["service_names"] == ["api"]
    assert payload["required_resource_names"] == ["postgres"]
    assert payload["required_artifact_names"] == ["model"]
    assert payload["required_environment_variable_names"] == ["DATABASE_URL"]


def test_deployment_manifest_rejects_invalid_values():
    with pytest.raises(ValueError):
        DeploymentManifest(name="", version="v1", environment="production", target="docker")

    with pytest.raises(ValueError):
        DeploymentManifest(name="aqos", version="", environment="production", target="docker")

    with pytest.raises(ValueError):
        DeploymentManifest(name="aqos", version="v1", environment="", target="docker")

    with pytest.raises(ValueError):
        DeploymentManifest(name="aqos", version="v1", environment="production", target="bad")

    with pytest.raises(ValueError):
        DeploymentManifest(name="aqos", version="v1", environment="production", target="docker", services=["bad"])

    with pytest.raises(ValueError):
        DeploymentManifest(name="aqos", version="v1", environment="production", target="docker", resources=["bad"])

    with pytest.raises(ValueError):
        DeploymentManifest(name="aqos", version="v1", environment="production", target="docker", artifacts=["bad"])

    with pytest.raises(ValueError):
        DeploymentManifest(
            name="aqos",
            version="v1",
            environment="production",
            target="docker",
            environment_variables=["bad"],
        )

    with pytest.raises(ValueError):
        DeploymentManifest(name="aqos", version="v1", environment="production", target="docker", metadata=[])

    with pytest.raises(ValueError):
        DeploymentManifest(name="aqos", version="v1", environment="production", target="docker", generated_at="")


def test_build_deployment_manifest():
    manifest = build_deployment_manifest(
        name="aqos",
        version="v1",
        environment="production",
        target="docker",
        generated_at="2026-01-01T00:00:00+00:00",
    )

    assert isinstance(manifest, DeploymentManifest)
    assert manifest.name == "aqos"


def test_deployment_checks_ready_and_blocked():
    manifest = build_deployment_manifest(
        name="aqos",
        version="v1",
        environment="production",
        target="docker",
        services=[
            build_deployment_service(name="api", image="aqos/api:v1"),
        ],
        resources=[
            build_deployment_resource(name="postgres", resource_type="database"),
        ],
        artifacts=[
            build_deployment_artifact(name="model", path="model.pkl", version="v1"),
        ],
        environment_variables=[
            build_deployment_environment_variable(name="DATABASE_URL"),
        ],
    )

    services = check_deployment_services(manifest)
    resources_ready = check_deployment_resources(
        manifest,
        available_resources={
            "postgres": True,
        },
    )
    artifacts_ready = check_deployment_artifacts(
        manifest,
        available_artifacts={
            "model": True,
        },
    )
    env_ready = check_deployment_environment_variables(
        manifest,
        environment_values={
            "DATABASE_URL": "postgres://example",
        },
    )

    assert services.status == ProductionStatus.READY
    assert resources_ready.status == ProductionStatus.READY
    assert artifacts_ready.status == ProductionStatus.READY
    assert env_ready.status == ProductionStatus.READY

    resources_blocked = check_deployment_resources(
        manifest,
        available_resources={},
    )
    artifacts_blocked = check_deployment_artifacts(
        manifest,
        available_artifacts={},
    )
    env_blocked = check_deployment_environment_variables(
        manifest,
        environment_values={},
    )

    assert resources_blocked.status == ProductionStatus.BLOCKED
    assert resources_blocked.details["missing"] == ["postgres"]
    assert artifacts_blocked.status == ProductionStatus.BLOCKED
    assert artifacts_blocked.details["missing"] == ["model"]
    assert env_blocked.status == ProductionStatus.BLOCKED
    assert env_blocked.details["missing"] == ["DATABASE_URL"]


def test_check_deployment_services_blocks_empty_services():
    manifest = build_deployment_manifest(
        name="aqos",
        version="v1",
        environment="production",
        target="docker",
    )

    result = check_deployment_services(manifest)

    assert result.status == ProductionStatus.BLOCKED
    assert result.passed is False


def test_validate_deployment_manifest_completeness_and_gate_result():
    manifest = build_deployment_manifest(
        name="aqos",
        version="v1",
        environment="production",
        target="docker",
        services=[
            build_deployment_service(name="api", image="aqos/api:v1"),
        ],
        resources=[
            build_deployment_resource(name="postgres", resource_type="database"),
        ],
        artifacts=[
            build_deployment_artifact(name="model", path="model.pkl", version="v1"),
        ],
        environment_variables=[
            build_deployment_environment_variable(name="DATABASE_URL"),
        ],
        generated_at="2026-01-01T00:00:00+00:00",
    )

    checks = validate_deployment_manifest_completeness(
        manifest,
        available_resources={
            "postgres": True,
        },
        available_artifacts={
            "model": True,
        },
        environment_values={
            "DATABASE_URL": "postgres://example",
        },
    )

    assert len(checks) == 4
    assert all(check.status == ProductionStatus.READY for check in checks)

    gate = deployment_manifest_to_gate_result(
        manifest,
        available_resources={
            "postgres": True,
        },
        available_artifacts={
            "model": True,
        },
        environment_values={
            "DATABASE_URL": "postgres://example",
        },
    )

    assert gate.status == ProductionStatus.READY
    assert gate.passed is True
    assert gate.gate_name == "deployment-manifest"


def test_deployment_validation_rejects_invalid_values():
    manifest = build_default_deployment_manifest()

    with pytest.raises(ValueError):
        validate_deployment_manifest_completeness("bad")

    with pytest.raises(ValueError):
        validate_deployment_manifest_completeness(
            manifest,
            available_resources=[],
        )

    with pytest.raises(ValueError):
        validate_deployment_manifest_completeness(
            manifest,
            available_artifacts=[],
        )

    with pytest.raises(ValueError):
        validate_deployment_manifest_completeness(
            manifest,
            environment_values=[],
        )

    with pytest.raises(ValueError):
        check_deployment_services("bad")

    with pytest.raises(ValueError):
        check_deployment_resources(
            "bad",
            available_resources={},
        )

    with pytest.raises(ValueError):
        check_deployment_resources(
            manifest,
            available_resources=[],
        )

    with pytest.raises(ValueError):
        check_deployment_artifacts(
            "bad",
            available_artifacts={},
        )

    with pytest.raises(ValueError):
        check_deployment_artifacts(
            manifest,
            available_artifacts=[],
        )

    with pytest.raises(ValueError):
        check_deployment_environment_variables(
            "bad",
            environment_values={},
        )

    with pytest.raises(ValueError):
        check_deployment_environment_variables(
            manifest,
            environment_values=[],
        )


def test_build_default_deployment_manifest():
    manifest = build_default_deployment_manifest(
        version="v0.20.0-dev",
        environment="production",
        target="docker",
    )

    assert isinstance(manifest, DeploymentManifest)
    assert manifest.name == "aqos"
    assert manifest.version == "v0.20.0-dev"
    assert manifest.target == "docker"
    assert manifest.services[0].name == "aqos-api"
    assert "DATABASE_URL" in manifest.required_environment_variable_names


def test_production_deployment_exports_exist():
    import aqos.production as production

    expected_exports = [
        "DeploymentArtifact",
        "DeploymentEnvironmentVariable",
        "DeploymentManifest",
        "DeploymentResource",
        "DeploymentResourceType",
        "DeploymentService",
        "DeploymentTarget",
        "build_default_deployment_manifest",
        "build_deployment_artifact",
        "build_deployment_environment_variable",
        "build_deployment_manifest",
        "build_deployment_resource",
        "build_deployment_service",
        "check_deployment_artifacts",
        "check_deployment_environment_variables",
        "check_deployment_resources",
        "check_deployment_services",
        "deployment_manifest_to_gate_result",
        "normalize_deployment_resource_type",
        "normalize_deployment_target",
        "validate_deployment_artifacts",
        "validate_deployment_environment_variables",
        "validate_deployment_manifest_completeness",
        "validate_deployment_resources",
        "validate_deployment_services",
        "validate_environment_variable_name",
        "validate_port",
    ]

    for export_name in expected_exports:
        assert hasattr(production, export_name), export_name