"""
AQOS production integration helpers.

This module combines runtime config validation, deployment manifest validation,
readiness checks, performance budgets, and release gates into a single
production hardening toolkit.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable

from aqos.production.base import (
    ProductionGateResult,
    ProductionStatus,
    aggregate_production_status,
    build_production_check_result,
    build_production_gate_result,
    validate_details,
    validate_non_empty_string,
    validate_string,
)
from aqos.production.config import (
    RuntimeConfigProfile,
    RuntimeConfigValidationResult,
    build_default_runtime_config_profile,
    runtime_config_to_gate_result,
    validate_runtime_config,
)
from aqos.production.deployment import (
    DeploymentManifest,
    build_default_deployment_manifest,
    deployment_manifest_to_gate_result,
)
from aqos.production.performance import (
    PerformanceBudget,
    PerformanceBudgetReport,
    PerformanceMeasurement,
    build_default_performance_budgets,
    evaluate_performance_budgets,
    validate_performance_budgets,
    validate_performance_measurements,
)
from aqos.production.readiness import (
    ReadinessReport,
    ReadinessRequirement,
    build_default_readiness_requirements,
    run_readiness_checks,
    validate_readiness_requirements,
)
from aqos.production.release import (
    ReleaseGate,
    ReleaseGateEngine,
    ReleaseGateType,
    ReleasePlan,
    ReleaseReport,
    build_release_gate,
    build_release_gate_engine,
    build_release_plan,
    run_release_gate_engine,
    validate_release_gates,
)


@dataclass(frozen=True)
class ProductionProfile:
    """Production hardening profile."""

    name: str
    version: str
    environment: str = "production"
    runtime_config_profile: RuntimeConfigProfile = field(
        default_factory=build_default_runtime_config_profile,
    )
    deployment_manifest: DeploymentManifest = field(
        default_factory=build_default_deployment_manifest,
    )
    performance_budgets: list[PerformanceBudget] = field(
        default_factory=build_default_performance_budgets,
    )
    readiness_requirements: list[ReadinessRequirement] = field(
        default_factory=build_default_readiness_requirements,
    )
    release_gates: list[ReleaseGate] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        validate_non_empty_string(self.name, "Profile name")
        validate_non_empty_string(self.version, "Version")
        validate_non_empty_string(self.environment, "Environment")

        if not isinstance(self.runtime_config_profile, RuntimeConfigProfile):
            raise ValueError("Runtime config profile must be a RuntimeConfigProfile.")

        if not isinstance(self.deployment_manifest, DeploymentManifest):
            raise ValueError("Deployment manifest must be a DeploymentManifest.")

        validate_performance_budgets(self.performance_budgets)
        validate_readiness_requirements(self.readiness_requirements)
        validate_release_gates(self.release_gates)
        validate_details(self.metadata)

    @property
    def resolved_release_gates(self) -> list[ReleaseGate]:
        """Return release gates, using default gates when none are provided."""
        if self.release_gates:
            return list(self.release_gates)

        return build_default_release_gates()

    def to_dict(self) -> dict[str, Any]:
        """Convert production profile into dictionary."""
        return {
            "name": self.name.strip(),
            "version": self.version.strip(),
            "environment": self.environment.strip(),
            "runtime_config_profile": self.runtime_config_profile.to_dict(),
            "deployment_manifest": self.deployment_manifest.to_dict(),
            "performance_budgets": [
                budget.to_dict()
                for budget in self.performance_budgets
            ],
            "readiness_requirements": [
                requirement.to_dict()
                for requirement in self.readiness_requirements
            ],
            "release_gates": [
                gate.to_dict()
                for gate in self.resolved_release_gates
            ],
            "metadata": dict(self.metadata),
        }


@dataclass(frozen=True)
class ProductionValidationBundle:
    """Full production validation bundle."""

    profile: ProductionProfile
    config_result: RuntimeConfigValidationResult
    deployment_gate: ProductionGateResult
    readiness_report: ReadinessReport
    performance_report: PerformanceBudgetReport
    release_report: ReleaseReport
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not isinstance(self.profile, ProductionProfile):
            raise ValueError("Profile must be a ProductionProfile.")

        if not isinstance(self.config_result, RuntimeConfigValidationResult):
            raise ValueError(
                "Config result must be a RuntimeConfigValidationResult.",
            )

        if not isinstance(self.deployment_gate, ProductionGateResult):
            raise ValueError("Deployment gate must be a ProductionGateResult.")

        if not isinstance(self.readiness_report, ReadinessReport):
            raise ValueError("Readiness report must be a ReadinessReport.")

        if not isinstance(self.performance_report, PerformanceBudgetReport):
            raise ValueError("Performance report must be a PerformanceBudgetReport.")

        if not isinstance(self.release_report, ReleaseReport):
            raise ValueError("Release report must be a ReleaseReport.")

        validate_details(self.metadata)

    @property
    def gates(self) -> list[ProductionGateResult]:
        """Return all production gate results."""
        return [
            self.config_result.to_gate_result(),
            self.deployment_gate,
            self.readiness_report.to_gate_result(),
            self.performance_report.to_gate_result(),
            self.release_report.to_gate_result(),
        ]

    @property
    def status(self) -> ProductionStatus:
        """Return aggregated production status."""
        return aggregate_production_status(
            [
                check
                for gate in self.gates
                for check in gate.checks
            ],
        )

    @property
    def passed(self) -> bool:
        """Return whether all production checks passed."""
        return self.status == ProductionStatus.READY and self.release_report.approved

    @property
    def failed(self) -> bool:
        """Return whether production validation failed."""
        return not self.passed

    def to_gate_result(self) -> ProductionGateResult:
        """Convert validation bundle into one production gate result."""
        checks = [
            check
            for gate in self.gates
            for check in gate.checks
        ]

        status = aggregate_production_status(checks)

        return build_production_gate_result(
            gate_name="production-hardening",
            status=status,
            checks=checks,
            message="Production hardening passed."
            if self.passed
            else "Production hardening has issues.",
            metadata={
                "profile": self.profile.to_dict(),
                "release_decision": self.release_report.decision.value
                if hasattr(self.release_report.decision, "value")
                else str(self.release_report.decision),
                **self.metadata,
            },
        )

    def to_dict(self) -> dict[str, Any]:
        """Convert validation bundle into dictionary."""
        return {
            "profile": self.profile.to_dict(),
            "status": self.status.value,
            "passed": self.passed,
            "failed": self.failed,
            "config": self.config_result.to_dict(),
            "deployment": self.deployment_gate.to_dict(),
            "readiness": self.readiness_report.to_dict(),
            "performance": self.performance_report.to_dict(),
            "release": self.release_report.to_dict(),
            "metadata": dict(self.metadata),
        }


@dataclass
class ProductionHardeningToolkit:
    """Production hardening toolkit."""

    profile: ProductionProfile
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not isinstance(self.profile, ProductionProfile):
            raise ValueError("Profile must be a ProductionProfile.")

        validate_details(self.metadata)

    def build_release_plan(self) -> ReleasePlan:
        """Build release plan from profile."""
        return create_release_plan_from_profile(self.profile)

    def build_release_engine(
        self,
        evaluators: dict[str, Callable[[], ProductionGateResult]],
    ) -> ReleaseGateEngine:
        """Build release gate engine from profile."""
        validate_details(evaluators)

        return build_release_gate_engine(
            plan=self.build_release_plan(),
            evaluators=evaluators,
            metadata=self.metadata,
        )

    def run(
        self,
        *,
        runtime_values: dict[str, Any],
        available_resources: dict[str, bool] | None = None,
        available_artifacts: dict[str, bool] | None = None,
        environment_values: dict[str, str] | None = None,
        performance_measurements: list[PerformanceMeasurement] | None = None,
        readiness_checks: list[Callable[[], Any]] | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> ProductionValidationBundle:
        """Run full production hardening validation."""
        return run_production_hardening(
            profile=self.profile,
            runtime_values=runtime_values,
            available_resources=available_resources or {},
            available_artifacts=available_artifacts or {},
            environment_values=environment_values or {},
            performance_measurements=performance_measurements or [],
            readiness_checks=readiness_checks or [],
            metadata={
                **self.metadata,
                **(metadata or {}),
            },
        )

    def summary(self) -> dict[str, Any]:
        """Return toolkit summary."""
        return {
            "profile": self.profile.name.strip(),
            "version": self.profile.version.strip(),
            "environment": self.profile.environment.strip(),
            "release_gates": len(self.profile.resolved_release_gates),
            "performance_budgets": len(self.profile.performance_budgets),
            "readiness_requirements": len(self.profile.readiness_requirements),
            "metadata": dict(self.metadata),
        }


def build_default_release_gates() -> list[ReleaseGate]:
    """Build default AQOS production release gates."""
    return [
        build_release_gate(
            name="runtime-configuration",
            gate_type=ReleaseGateType.CONFIGURATION,
            description="Runtime configuration must be valid.",
        ),
        build_release_gate(
            name="deployment-manifest",
            gate_type=ReleaseGateType.DEPLOYMENT,
            description="Deployment manifest must be complete.",
        ),
        build_release_gate(
            name="production-readiness",
            gate_type=ReleaseGateType.READINESS,
            description="Production readiness checks must pass.",
        ),
        build_release_gate(
            name="performance-budget",
            gate_type=ReleaseGateType.PERFORMANCE,
            required=False,
            description="Performance budgets should pass.",
        ),
    ]


def build_production_profile(
    *,
    name: str,
    version: str,
    environment: str = "production",
    runtime_config_profile: RuntimeConfigProfile | None = None,
    deployment_manifest: DeploymentManifest | None = None,
    performance_budgets: list[PerformanceBudget] | None = None,
    readiness_requirements: list[ReadinessRequirement] | None = None,
    release_gates: list[ReleaseGate] | None = None,
    metadata: dict[str, Any] | None = None,
) -> ProductionProfile:
    """Build production hardening profile."""
    return ProductionProfile(
        name=name,
        version=version,
        environment=environment,
        runtime_config_profile=runtime_config_profile
        or build_default_runtime_config_profile(environment=environment),
        deployment_manifest=deployment_manifest
        or build_default_deployment_manifest(
            version=version,
            environment=environment,
        ),
        performance_budgets=performance_budgets or build_default_performance_budgets(),
        readiness_requirements=readiness_requirements
        or build_default_readiness_requirements(),
        release_gates=release_gates or [],
        metadata=metadata or {},
    )


def build_default_production_profile(
    *,
    version: str = "v0.20.0-dev",
    environment: str = "production",
) -> ProductionProfile:
    """Build default AQOS production profile."""
    return build_production_profile(
        name="aqos-production",
        version=version,
        environment=environment,
        metadata={
            "generated_by": "aqos.production",
        },
    )


def build_production_validation_bundle(
    *,
    profile: ProductionProfile,
    config_result: RuntimeConfigValidationResult,
    deployment_gate: ProductionGateResult,
    readiness_report: ReadinessReport,
    performance_report: PerformanceBudgetReport,
    release_report: ReleaseReport,
    metadata: dict[str, Any] | None = None,
) -> ProductionValidationBundle:
    """Build production validation bundle."""
    return ProductionValidationBundle(
        profile=profile,
        config_result=config_result,
        deployment_gate=deployment_gate,
        readiness_report=readiness_report,
        performance_report=performance_report,
        release_report=release_report,
        metadata=metadata or {},
    )


def build_production_hardening_toolkit(
    *,
    profile: ProductionProfile,
    metadata: dict[str, Any] | None = None,
) -> ProductionHardeningToolkit:
    """Build production hardening toolkit."""
    return ProductionHardeningToolkit(
        profile=profile,
        metadata=metadata or {},
    )


def create_release_plan_from_profile(profile: ProductionProfile) -> ReleasePlan:
    """Create release plan from production profile."""
    if not isinstance(profile, ProductionProfile):
        raise ValueError("Profile must be a ProductionProfile.")

    return build_release_plan(
        version=profile.version,
        environment=profile.environment,
        gates=profile.resolved_release_gates,
        metadata={
            "profile": profile.name.strip(),
            **profile.metadata,
        },
    )


def compose_production_metadata(
    *,
    source: str,
    environment: str,
    version: str,
    extra: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Compose standard production metadata."""
    validate_non_empty_string(source, "Source")
    validate_non_empty_string(environment, "Environment")
    validate_non_empty_string(version, "Version")

    if extra is not None:
        validate_details(extra)

    return {
        "source": source.strip(),
        "environment": environment.strip(),
        "version": version.strip(),
        **(extra or {}),
    }


def run_production_hardening(
    *,
    profile: ProductionProfile,
    runtime_values: dict[str, Any],
    available_resources: dict[str, bool] | None = None,
    available_artifacts: dict[str, bool] | None = None,
    environment_values: dict[str, str] | None = None,
    performance_measurements: list[PerformanceMeasurement] | None = None,
    readiness_checks: list[Callable[[], Any]] | None = None,
    metadata: dict[str, Any] | None = None,
) -> ProductionValidationBundle:
    """Run full AQOS production hardening validation."""
    if not isinstance(profile, ProductionProfile):
        raise ValueError("Profile must be a ProductionProfile.")

    validate_details(runtime_values)

    if available_resources is not None:
        validate_details(available_resources)

    if available_artifacts is not None:
        validate_details(available_artifacts)

    if environment_values is not None:
        validate_details(environment_values)

    if performance_measurements is not None:
        validate_performance_measurements(performance_measurements)

    if readiness_checks is not None and not isinstance(readiness_checks, list):
        raise ValueError("Readiness checks must be a list.")

    if metadata is not None:
        validate_details(metadata)

    config_result = validate_runtime_config(
        profile=profile.runtime_config_profile,
        values=runtime_values,
        metadata=metadata or {},
    )

    deployment_gate = deployment_manifest_to_gate_result(
        profile.deployment_manifest,
        available_resources=available_resources or {},
        available_artifacts=available_artifacts or {},
        environment_values=environment_values or {},
    )

    resolved_readiness_checks = readiness_checks or [
    lambda: build_production_check_result(
        name="default-readiness",
        status=ProductionStatus.READY,
        passed=True,
        message="Default production readiness check passed.",
    ),
]

    readiness_report = run_readiness_checks(
        resolved_readiness_checks,
        environment=profile.environment,
        requirements=profile.readiness_requirements,
        metadata=metadata or {},
    )

    performance_report = evaluate_performance_budgets(
        budgets=profile.performance_budgets,
        measurements=performance_measurements or [],
        environment=profile.environment,
        metadata=metadata or {},
    )

    release_plan = create_release_plan_from_profile(profile)
    release_report = run_release_gate_engine(
        plan=release_plan,
        evaluators={
            "runtime-configuration": config_result.to_gate_result,
            "deployment-manifest": lambda: deployment_gate,
            "production-readiness": readiness_report.to_gate_result,
            "performance-budget": performance_report.to_gate_result,
        },
        metadata=metadata or {},
    )

    return build_production_validation_bundle(
        profile=profile,
        config_result=config_result,
        deployment_gate=deployment_gate,
        readiness_report=readiness_report,
        performance_report=performance_report,
        release_report=release_report,
        metadata=metadata or {},
    )


def production_summary(bundle: ProductionValidationBundle) -> dict[str, Any]:
    """Build compact production validation summary."""
    if not isinstance(bundle, ProductionValidationBundle):
        raise ValueError("Bundle must be a ProductionValidationBundle.")

    return {
        "profile": bundle.profile.name.strip(),
        "version": bundle.profile.version.strip(),
        "environment": bundle.profile.environment.strip(),
        "status": bundle.status.value,
        "passed": bundle.passed,
        "failed": bundle.failed,
        "release_decision": bundle.release_report.decision.value
        if hasattr(bundle.release_report.decision, "value")
        else str(bundle.release_report.decision),
        "gates": len(bundle.gates),
        "checks": sum(len(gate.checks) for gate in bundle.gates),
    }


def validate_production_profile_name(name: str) -> str:
    """Validate production profile name."""
    normalized = validate_non_empty_string(name, "Production profile name")

    if " " in normalized:
        raise ValueError("Production profile name cannot contain spaces.")

    return normalized


def validate_release_version(version: str) -> str:
    """Validate release version."""
    normalized = validate_non_empty_string(version, "Release version")

    if not normalized.startswith("v"):
        raise ValueError("Release version must start with 'v'.")

    return normalized


def validate_environment_name(environment: str) -> str:
    """Validate environment name."""
    normalized = validate_non_empty_string(environment, "Environment")

    allowed = {
        "local",
        "development",
        "staging",
        "production",
    }

    if normalized not in allowed:
        raise ValueError(
            "Environment must be one of: development, local, production, staging.",
        )

    return normalized


def validate_metadata_source(source: str) -> str:
    """Validate metadata source."""
    validate_string(source, "Source")
    return validate_non_empty_string(source, "Source")