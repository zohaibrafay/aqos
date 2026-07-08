"""
AQOS production deployment manifest helpers.

This module provides dependency-free deployment manifest primitives for
services, environment variables, artifacts, resources, and release metadata.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import Enum
from typing import Any

from aqos.production.base import (
    ProductionCheckResult,
    ProductionGateResult,
    ProductionSeverity,
    ProductionStatus,
    aggregate_production_status,
    build_production_check_result,
    build_production_gate_result,
    validate_details,
    validate_non_empty_string,
    validate_non_negative_float,
    validate_positive_integer,
    validate_string,
)


class DeploymentTarget(str, Enum):
    """Supported deployment targets."""

    LOCAL = "local"
    DOCKER = "docker"
    KUBERNETES = "kubernetes"
    CLOUD = "cloud"


class DeploymentResourceType(str, Enum):
    """Supported deployment resource types."""

    SERVICE = "service"
    DATABASE = "database"
    CACHE = "cache"
    QUEUE = "queue"
    STORAGE = "storage"
    MODEL = "model"


@dataclass(frozen=True)
class DeploymentResource:
    """Single deployment resource."""

    name: str
    resource_type: DeploymentResourceType | str
    required: bool = True
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        validate_non_empty_string(self.name, "Resource name")
        normalize_deployment_resource_type(self.resource_type)

        if not isinstance(self.required, bool):
            raise ValueError("Required must be a boolean.")

        validate_details(self.metadata)

    def to_dict(self) -> dict[str, Any]:
        """Convert deployment resource into dictionary."""
        return {
            "name": self.name.strip(),
            "resource_type": normalize_deployment_resource_type(self.resource_type).value,
            "required": self.required,
            "metadata": dict(self.metadata),
        }


@dataclass(frozen=True)
class DeploymentArtifact:
    """Single deployment artifact."""

    name: str
    path: str
    version: str
    required: bool = True
    checksum: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        validate_non_empty_string(self.name, "Artifact name")
        validate_non_empty_string(self.path, "Artifact path")
        validate_non_empty_string(self.version, "Artifact version")

        if not isinstance(self.required, bool):
            raise ValueError("Required must be a boolean.")

        validate_string(self.checksum, "Checksum")
        validate_details(self.metadata)

    def to_dict(self) -> dict[str, Any]:
        """Convert deployment artifact into dictionary."""
        return {
            "name": self.name.strip(),
            "path": self.path.strip(),
            "version": self.version.strip(),
            "required": self.required,
            "checksum": self.checksum.strip(),
            "metadata": dict(self.metadata),
        }


@dataclass(frozen=True)
class DeploymentEnvironmentVariable:
    """Deployment environment variable declaration."""

    name: str
    required: bool = True
    secret: bool = False
    default: str | None = None
    description: str = ""

    def __post_init__(self) -> None:
        validate_environment_variable_name(self.name)

        if not isinstance(self.required, bool):
            raise ValueError("Required must be a boolean.")

        if not isinstance(self.secret, bool):
            raise ValueError("Secret must be a boolean.")

        if self.default is not None:
            validate_string(self.default, "Default")

        validate_string(self.description, "Description")

    def to_dict(self) -> dict[str, Any]:
        """Convert environment variable declaration into dictionary."""
        return {
            "name": self.name.strip(),
            "required": self.required,
            "secret": self.secret,
            "default": self.default,
            "description": self.description.strip(),
        }


@dataclass(frozen=True)
class DeploymentService:
    """Single deployable service definition."""

    name: str
    image: str
    replicas: int = 1
    port: int | None = None
    cpu_limit: float | None = None
    memory_limit_mb: float | None = None
    healthcheck_path: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        validate_non_empty_string(self.name, "Service name")
        validate_non_empty_string(self.image, "Image")
        validate_positive_integer(self.replicas, "Replicas")

        if self.port is not None:
            validate_port(self.port)

        if self.cpu_limit is not None:
            validate_non_negative_float(self.cpu_limit, "CPU limit")

        if self.memory_limit_mb is not None:
            validate_non_negative_float(self.memory_limit_mb, "Memory limit MB")

        validate_string(self.healthcheck_path, "Healthcheck path")
        validate_details(self.metadata)

    def to_dict(self) -> dict[str, Any]:
        """Convert deployment service into dictionary."""
        payload = {
            "name": self.name.strip(),
            "image": self.image.strip(),
            "replicas": self.replicas,
            "port": self.port,
            "cpu_limit": float(self.cpu_limit) if self.cpu_limit is not None else None,
            "memory_limit_mb": float(self.memory_limit_mb)
            if self.memory_limit_mb is not None
            else None,
            "healthcheck_path": self.healthcheck_path.strip(),
            "metadata": dict(self.metadata),
        }

        return {
            key: value
            for key, value in payload.items()
            if value is not None
        }


@dataclass(frozen=True)
class DeploymentManifest:
    """Production deployment manifest."""

    name: str
    version: str
    environment: str
    target: DeploymentTarget | str
    services: list[DeploymentService] = field(default_factory=list)
    resources: list[DeploymentResource] = field(default_factory=list)
    artifacts: list[DeploymentArtifact] = field(default_factory=list)
    environment_variables: list[DeploymentEnvironmentVariable] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)
    generated_at: str = field(default_factory=lambda: datetime.now(UTC).isoformat())

    def __post_init__(self) -> None:
        validate_non_empty_string(self.name, "Manifest name")
        validate_non_empty_string(self.version, "Version")
        validate_non_empty_string(self.environment, "Environment")
        normalize_deployment_target(self.target)
        validate_deployment_services(self.services)
        validate_deployment_resources(self.resources)
        validate_deployment_artifacts(self.artifacts)
        validate_deployment_environment_variables(self.environment_variables)
        validate_details(self.metadata)
        validate_non_empty_string(self.generated_at, "Generated at")

    @property
    def service_names(self) -> list[str]:
        """Return service names."""
        return [
            service.name.strip()
            for service in self.services
        ]

    @property
    def required_resource_names(self) -> list[str]:
        """Return required resource names."""
        return [
            resource.name.strip()
            for resource in self.resources
            if resource.required
        ]

    @property
    def required_artifact_names(self) -> list[str]:
        """Return required artifact names."""
        return [
            artifact.name.strip()
            for artifact in self.artifacts
            if artifact.required
        ]

    @property
    def required_environment_variable_names(self) -> list[str]:
        """Return required environment variable names."""
        return [
            variable.name.strip()
            for variable in self.environment_variables
            if variable.required
        ]

    def to_dict(self) -> dict[str, Any]:
        """Convert deployment manifest into dictionary."""
        return {
            "name": self.name.strip(),
            "version": self.version.strip(),
            "environment": self.environment.strip(),
            "target": normalize_deployment_target(self.target).value,
            "services": [
                service.to_dict()
                for service in self.services
            ],
            "resources": [
                resource.to_dict()
                for resource in self.resources
            ],
            "artifacts": [
                artifact.to_dict()
                for artifact in self.artifacts
            ],
            "environment_variables": [
                variable.to_dict()
                for variable in self.environment_variables
            ],
            "service_names": self.service_names,
            "required_resource_names": self.required_resource_names,
            "required_artifact_names": self.required_artifact_names,
            "required_environment_variable_names": self.required_environment_variable_names,
            "metadata": dict(self.metadata),
            "generated_at": self.generated_at.strip(),
        }


def normalize_deployment_target(target: DeploymentTarget | str) -> DeploymentTarget:
    """Normalize deployment target."""
    if isinstance(target, DeploymentTarget):
        return target

    normalized = validate_non_empty_string(target, "Deployment target").lower()

    try:
        return DeploymentTarget(normalized)
    except ValueError as exc:
        valid = ", ".join(item.value for item in DeploymentTarget)
        raise ValueError(
            f"Invalid deployment target '{target}'. Valid targets: {valid}.",
        ) from exc


def normalize_deployment_resource_type(
    resource_type: DeploymentResourceType | str,
) -> DeploymentResourceType:
    """Normalize deployment resource type."""
    if isinstance(resource_type, DeploymentResourceType):
        return resource_type

    normalized = validate_non_empty_string(resource_type, "Deployment resource type").lower()

    try:
        return DeploymentResourceType(normalized)
    except ValueError as exc:
        valid = ", ".join(item.value for item in DeploymentResourceType)
        raise ValueError(
            f"Invalid deployment resource type '{resource_type}'. Valid resource types: {valid}.",
        ) from exc


def validate_environment_variable_name(name: str) -> str:
    """Validate environment variable name."""
    normalized = validate_non_empty_string(name, "Environment variable name")

    if not normalized.replace("_", "").isalnum():
        raise ValueError("Environment variable name must be alphanumeric or underscore.")

    if normalized[0].isdigit():
        raise ValueError("Environment variable name cannot start with a digit.")

    if normalized.upper() != normalized:
        raise ValueError("Environment variable name must be uppercase.")

    return normalized


def validate_port(port: int) -> int:
    """Validate network port."""
    if isinstance(port, bool) or not isinstance(port, int):
        raise ValueError("Port must be an integer.")

    if port < 1 or port > 65535:
        raise ValueError("Port must be between 1 and 65535.")

    return port


def validate_deployment_services(
    services: list[DeploymentService],
) -> list[DeploymentService]:
    """Validate deployment service list."""
    if not isinstance(services, list):
        raise ValueError("Services must be a list.")

    for service in services:
        if not isinstance(service, DeploymentService):
            raise ValueError("Services must contain DeploymentService objects.")

    return services


def validate_deployment_resources(
    resources: list[DeploymentResource],
) -> list[DeploymentResource]:
    """Validate deployment resource list."""
    if not isinstance(resources, list):
        raise ValueError("Resources must be a list.")

    for resource in resources:
        if not isinstance(resource, DeploymentResource):
            raise ValueError("Resources must contain DeploymentResource objects.")

    return resources


def validate_deployment_artifacts(
    artifacts: list[DeploymentArtifact],
) -> list[DeploymentArtifact]:
    """Validate deployment artifact list."""
    if not isinstance(artifacts, list):
        raise ValueError("Artifacts must be a list.")

    for artifact in artifacts:
        if not isinstance(artifact, DeploymentArtifact):
            raise ValueError("Artifacts must contain DeploymentArtifact objects.")

    return artifacts


def validate_deployment_environment_variables(
    variables: list[DeploymentEnvironmentVariable],
) -> list[DeploymentEnvironmentVariable]:
    """Validate deployment environment variable declarations."""
    if not isinstance(variables, list):
        raise ValueError("Environment variables must be a list.")

    for variable in variables:
        if not isinstance(variable, DeploymentEnvironmentVariable):
            raise ValueError(
                "Environment variables must contain DeploymentEnvironmentVariable objects.",
            )

    return variables


def build_deployment_resource(
    *,
    name: str,
    resource_type: DeploymentResourceType | str,
    required: bool = True,
    metadata: dict[str, Any] | None = None,
) -> DeploymentResource:
    """Build deployment resource."""
    return DeploymentResource(
        name=name,
        resource_type=resource_type,
        required=required,
        metadata=metadata or {},
    )


def build_deployment_artifact(
    *,
    name: str,
    path: str,
    version: str,
    required: bool = True,
    checksum: str = "",
    metadata: dict[str, Any] | None = None,
) -> DeploymentArtifact:
    """Build deployment artifact."""
    return DeploymentArtifact(
        name=name,
        path=path,
        version=version,
        required=required,
        checksum=checksum,
        metadata=metadata or {},
    )


def build_deployment_environment_variable(
    *,
    name: str,
    required: bool = True,
    secret: bool = False,
    default: str | None = None,
    description: str = "",
) -> DeploymentEnvironmentVariable:
    """Build deployment environment variable declaration."""
    return DeploymentEnvironmentVariable(
        name=name,
        required=required,
        secret=secret,
        default=default,
        description=description,
    )


def build_deployment_service(
    *,
    name: str,
    image: str,
    replicas: int = 1,
    port: int | None = None,
    cpu_limit: float | None = None,
    memory_limit_mb: float | None = None,
    healthcheck_path: str = "",
    metadata: dict[str, Any] | None = None,
) -> DeploymentService:
    """Build deployment service."""
    return DeploymentService(
        name=name,
        image=image,
        replicas=replicas,
        port=port,
        cpu_limit=cpu_limit,
        memory_limit_mb=memory_limit_mb,
        healthcheck_path=healthcheck_path,
        metadata=metadata or {},
    )


def build_deployment_manifest(
    *,
    name: str,
    version: str,
    environment: str,
    target: DeploymentTarget | str,
    services: list[DeploymentService] | None = None,
    resources: list[DeploymentResource] | None = None,
    artifacts: list[DeploymentArtifact] | None = None,
    environment_variables: list[DeploymentEnvironmentVariable] | None = None,
    metadata: dict[str, Any] | None = None,
    generated_at: str | None = None,
) -> DeploymentManifest:
    """Build deployment manifest."""
    manifest_kwargs: dict[str, Any] = {
        "name": name,
        "version": version,
        "environment": environment,
        "target": target,
        "services": services or [],
        "resources": resources or [],
        "artifacts": artifacts or [],
        "environment_variables": environment_variables or [],
        "metadata": metadata or {},
    }

    if generated_at is not None:
        manifest_kwargs["generated_at"] = generated_at

    return DeploymentManifest(**manifest_kwargs)


def validate_deployment_manifest_completeness(
    manifest: DeploymentManifest,
    *,
    available_resources: dict[str, bool] | None = None,
    available_artifacts: dict[str, bool] | None = None,
    environment_values: dict[str, str] | None = None,
) -> list[ProductionCheckResult]:
    """Validate deployment manifest completeness."""
    if not isinstance(manifest, DeploymentManifest):
        raise ValueError("Manifest must be a DeploymentManifest.")

    if available_resources is not None:
        validate_details(available_resources)

    if available_artifacts is not None:
        validate_details(available_artifacts)

    if environment_values is not None:
        validate_details(environment_values)

    checks = [
        check_deployment_services(manifest),
        check_deployment_resources(
            manifest,
            available_resources=available_resources or {},
        ),
        check_deployment_artifacts(
            manifest,
            available_artifacts=available_artifacts or {},
        ),
        check_deployment_environment_variables(
            manifest,
            environment_values=environment_values or {},
        ),
    ]

    return checks


def check_deployment_services(
    manifest: DeploymentManifest,
) -> ProductionCheckResult:
    """Check deployment services."""
    if not isinstance(manifest, DeploymentManifest):
        raise ValueError("Manifest must be a DeploymentManifest.")

    if not manifest.services:
        return build_production_check_result(
            name="deployment-services",
            status=ProductionStatus.BLOCKED,
            severity=ProductionSeverity.ERROR,
            passed=False,
            message="No deployment services defined.",
            details={
                "services": [],
            },
        )

    return build_production_check_result(
        name="deployment-services",
        status=ProductionStatus.READY,
        severity=ProductionSeverity.INFO,
        passed=True,
        message="Deployment services are defined.",
        details={
            "services": manifest.service_names,
        },
    )


def check_deployment_resources(
    manifest: DeploymentManifest,
    *,
    available_resources: dict[str, bool],
) -> ProductionCheckResult:
    """Check deployment resources."""
    if not isinstance(manifest, DeploymentManifest):
        raise ValueError("Manifest must be a DeploymentManifest.")

    validate_details(available_resources)

    missing = [
        resource.name.strip()
        for resource in manifest.resources
        if resource.required and available_resources.get(resource.name.strip()) is not True
    ]

    if missing:
        return build_production_check_result(
            name="deployment-resources",
            status=ProductionStatus.BLOCKED,
            severity=ProductionSeverity.ERROR,
            passed=False,
            message="Required deployment resources are missing.",
            details={
                "required": manifest.required_resource_names,
                "missing": missing,
            },
        )

    return build_production_check_result(
        name="deployment-resources",
        status=ProductionStatus.READY,
        severity=ProductionSeverity.INFO,
        passed=True,
        message="Required deployment resources are available.",
        details={
            "required": manifest.required_resource_names,
        },
    )


def check_deployment_artifacts(
    manifest: DeploymentManifest,
    *,
    available_artifacts: dict[str, bool],
) -> ProductionCheckResult:
    """Check deployment artifacts."""
    if not isinstance(manifest, DeploymentManifest):
        raise ValueError("Manifest must be a DeploymentManifest.")

    validate_details(available_artifacts)

    missing = [
        artifact.name.strip()
        for artifact in manifest.artifacts
        if artifact.required and available_artifacts.get(artifact.name.strip()) is not True
    ]

    if missing:
        return build_production_check_result(
            name="deployment-artifacts",
            status=ProductionStatus.BLOCKED,
            severity=ProductionSeverity.ERROR,
            passed=False,
            message="Required deployment artifacts are missing.",
            details={
                "required": manifest.required_artifact_names,
                "missing": missing,
            },
        )

    return build_production_check_result(
        name="deployment-artifacts",
        status=ProductionStatus.READY,
        severity=ProductionSeverity.INFO,
        passed=True,
        message="Required deployment artifacts are available.",
        details={
            "required": manifest.required_artifact_names,
        },
    )


def check_deployment_environment_variables(
    manifest: DeploymentManifest,
    *,
    environment_values: dict[str, str],
) -> ProductionCheckResult:
    """Check deployment environment variables."""
    if not isinstance(manifest, DeploymentManifest):
        raise ValueError("Manifest must be a DeploymentManifest.")

    validate_details(environment_values)

    missing = [
        variable.name.strip()
        for variable in manifest.environment_variables
        if variable.required and not environment_values.get(variable.name.strip())
    ]

    if missing:
        return build_production_check_result(
            name="deployment-environment",
            status=ProductionStatus.BLOCKED,
            severity=ProductionSeverity.CRITICAL,
            passed=False,
            message="Required environment variables are missing.",
            details={
                "required": manifest.required_environment_variable_names,
                "missing": missing,
            },
        )

    return build_production_check_result(
        name="deployment-environment",
        status=ProductionStatus.READY,
        severity=ProductionSeverity.INFO,
        passed=True,
        message="Required environment variables are configured.",
        details={
            "required": manifest.required_environment_variable_names,
        },
    )


def deployment_manifest_to_gate_result(
    manifest: DeploymentManifest,
    *,
    available_resources: dict[str, bool] | None = None,
    available_artifacts: dict[str, bool] | None = None,
    environment_values: dict[str, str] | None = None,
) -> ProductionGateResult:
    """Convert deployment manifest validation into production gate result."""
    checks = validate_deployment_manifest_completeness(
        manifest,
        available_resources=available_resources or {},
        available_artifacts=available_artifacts or {},
        environment_values=environment_values or {},
    )
    status = aggregate_production_status(checks)

    return build_production_gate_result(
        gate_name="deployment-manifest",
        status=status,
        checks=checks,
        message="Deployment manifest passed."
        if status == ProductionStatus.READY
        else "Deployment manifest has issues.",
        metadata={
            "manifest": manifest.to_dict(),
        },
        timestamp=manifest.generated_at,
    )


def build_default_deployment_manifest(
    *,
    version: str = "v0.20.0-dev",
    environment: str = "production",
    target: DeploymentTarget | str = DeploymentTarget.DOCKER,
) -> DeploymentManifest:
    """Build default AQOS deployment manifest."""
    return build_deployment_manifest(
        name="aqos",
        version=version,
        environment=environment,
        target=target,
        services=[
            build_deployment_service(
                name="aqos-api",
                image=f"aqos/api:{version}",
                replicas=1,
                port=8000,
                cpu_limit=1.0,
                memory_limit_mb=1024,
                healthcheck_path="/health",
            ),
        ],
        resources=[
            build_deployment_resource(
                name="postgres",
                resource_type=DeploymentResourceType.DATABASE,
            ),
            build_deployment_resource(
                name="redis",
                resource_type=DeploymentResourceType.CACHE,
                required=False,
            ),
            build_deployment_resource(
                name="model-store",
                resource_type=DeploymentResourceType.STORAGE,
            ),
        ],
        artifacts=[
            build_deployment_artifact(
                name="model-registry",
                path="artifacts/models",
                version=version,
            ),
        ],
        environment_variables=[
            build_deployment_environment_variable(
                name="DATABASE_URL",
                required=True,
                secret=True,
                description="Primary database connection string.",
            ),
            build_deployment_environment_variable(
                name="AQOS_ENV",
                required=True,
                default=environment,
                description="AQOS runtime environment.",
            ),
        ],
        metadata={
            "generated_by": "aqos.production",
        },
    )