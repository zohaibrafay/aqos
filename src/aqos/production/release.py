"""
AQOS production release gate engine.

This module provides dependency-free release gate primitives for approving,
warning, or blocking production releases from readiness, performance,
deployment, security, configuration, and custom gates.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import Enum
from typing import Any, Callable

from aqos.production.base import (
    ProductionCheckResult,
    ProductionGateResult,
    ProductionSeverity,
    ProductionStatus,
    build_production_check_result,
    build_production_gate_result,
    normalize_production_status,
    validate_details,
    validate_non_empty_string,
    validate_string,
)


class ReleaseGateType(str, Enum):
    """Supported release gate types."""

    READINESS = "readiness"
    PERFORMANCE = "performance"
    SECURITY = "security"
    CONFIGURATION = "configuration"
    DEPLOYMENT = "deployment"
    CUSTOM = "custom"


class ReleaseDecision(str, Enum):
    """Supported release decisions."""

    APPROVE = "approve"
    WARN = "warn"
    BLOCK = "block"


@dataclass(frozen=True)
class ReleaseGate:
    """Single release gate definition."""

    name: str
    gate_type: ReleaseGateType | str
    required: bool = True
    description: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        validate_non_empty_string(self.name, "Release gate name")
        normalize_release_gate_type(self.gate_type)

        if not isinstance(self.required, bool):
            raise ValueError("Required must be a boolean.")

        validate_string(self.description, "Description")
        validate_details(self.metadata)

    def to_dict(self) -> dict[str, Any]:
        """Convert release gate into dictionary."""
        return {
            "name": self.name.strip(),
            "gate_type": normalize_release_gate_type(self.gate_type).value,
            "required": self.required,
            "description": self.description.strip(),
            "metadata": dict(self.metadata),
        }


@dataclass(frozen=True)
class ReleaseEvaluation:
    """Single release gate evaluation."""

    gate: ReleaseGate
    gate_result: ProductionGateResult
    decision: ReleaseDecision | str
    message: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not isinstance(self.gate, ReleaseGate):
            raise ValueError("Gate must be a ReleaseGate.")

        if not isinstance(self.gate_result, ProductionGateResult):
            raise ValueError("Gate result must be a ProductionGateResult.")

        normalize_release_decision(self.decision)
        validate_string(self.message, "Message")
        validate_details(self.metadata)

    @property
    def approved(self) -> bool:
        """Return whether gate was approved."""
        return normalize_release_decision(self.decision) == ReleaseDecision.APPROVE

    @property
    def warning(self) -> bool:
        """Return whether gate has warning."""
        return normalize_release_decision(self.decision) == ReleaseDecision.WARN

    @property
    def blocked(self) -> bool:
        """Return whether gate is blocked."""
        return normalize_release_decision(self.decision) == ReleaseDecision.BLOCK

    def to_check_result(self) -> ProductionCheckResult:
        """Convert release evaluation into a production check result."""
        decision = normalize_release_decision(self.decision)

        if decision == ReleaseDecision.APPROVE:
            status = ProductionStatus.READY
            severity = ProductionSeverity.INFO
            passed = True
        elif decision == ReleaseDecision.WARN:
            status = ProductionStatus.WARNING
            severity = ProductionSeverity.WARNING
            passed = True
        else:
            status = ProductionStatus.BLOCKED
            severity = ProductionSeverity.CRITICAL
            passed = False

        return build_production_check_result(
            name=f"release-{self.gate.name.strip()}",
            status=status,
            severity=severity,
            passed=passed,
            message=self.message or self.gate_result.message,
            details=self.to_dict(),
        )

    def to_dict(self) -> dict[str, Any]:
        """Convert release evaluation into dictionary."""
        return {
            "gate": self.gate.to_dict(),
            "gate_result": self.gate_result.to_dict(),
            "decision": normalize_release_decision(self.decision).value,
            "approved": self.approved,
            "warning": self.warning,
            "blocked": self.blocked,
            "message": self.message.strip(),
            "metadata": dict(self.metadata),
        }


@dataclass(frozen=True)
class ReleasePlan:
    """Production release plan."""

    version: str
    environment: str
    gates: list[ReleaseGate] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        validate_non_empty_string(self.version, "Version")
        validate_non_empty_string(self.environment, "Environment")
        validate_release_gates(self.gates)
        validate_details(self.metadata)

    @property
    def gate_names(self) -> list[str]:
        """Return release gate names."""
        return [
            gate.name.strip()
            for gate in self.gates
        ]

    def to_dict(self) -> dict[str, Any]:
        """Convert release plan into dictionary."""
        return {
            "version": self.version.strip(),
            "environment": self.environment.strip(),
            "gates": [
                gate.to_dict()
                for gate in self.gates
            ],
            "gate_names": self.gate_names,
            "metadata": dict(self.metadata),
        }


@dataclass(frozen=True)
class ReleaseReport:
    """Aggregated production release report."""

    plan: ReleasePlan
    evaluations: list[ReleaseEvaluation] = field(default_factory=list)
    decision: ReleaseDecision | str = ReleaseDecision.BLOCK
    generated_at: str = field(default_factory=lambda: datetime.now(UTC).isoformat())
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not isinstance(self.plan, ReleasePlan):
            raise ValueError("Plan must be a ReleasePlan.")

        validate_release_evaluations(self.evaluations)
        normalize_release_decision(self.decision)
        validate_non_empty_string(self.generated_at, "Generated at")
        validate_details(self.metadata)

    @property
    def approved(self) -> bool:
        """Return whether release is approved."""
        return normalize_release_decision(self.decision) == ReleaseDecision.APPROVE

    @property
    def warning(self) -> bool:
        """Return whether release has warnings."""
        return normalize_release_decision(self.decision) == ReleaseDecision.WARN

    @property
    def blocked(self) -> bool:
        """Return whether release is blocked."""
        return normalize_release_decision(self.decision) == ReleaseDecision.BLOCK

    def to_gate_result(self) -> ProductionGateResult:
        """Convert release report into production gate result."""
        return build_production_gate_result(
            gate_name="release-gate",
            status=release_decision_to_status(self.decision),
            checks=[
                evaluation.to_check_result()
                for evaluation in self.evaluations
            ],
            message="Release approved."
            if self.approved
            else "Release has warnings."
            if self.warning
            else "Release blocked.",
            metadata={
                "version": self.plan.version.strip(),
                "environment": self.plan.environment.strip(),
                "decision": normalize_release_decision(self.decision).value,
                **self.metadata,
            },
            timestamp=self.generated_at,
        )

    def to_dict(self) -> dict[str, Any]:
        """Convert release report into dictionary."""
        return {
            "plan": self.plan.to_dict(),
            "evaluations": [
                evaluation.to_dict()
                for evaluation in self.evaluations
            ],
            "decision": normalize_release_decision(self.decision).value,
            "approved": self.approved,
            "warning": self.warning,
            "blocked": self.blocked,
            "generated_at": self.generated_at.strip(),
            "metadata": dict(self.metadata),
        }


@dataclass
class ReleaseGateEngine:
    """Production release gate engine."""

    plan: ReleasePlan
    evaluators: dict[str, Callable[[], ProductionGateResult]] = field(default_factory=dict)
    evaluations: list[ReleaseEvaluation] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not isinstance(self.plan, ReleasePlan):
            raise ValueError("Plan must be a ReleasePlan.")

        validate_evaluator_mapping(self.evaluators)
        validate_release_evaluations(self.evaluations)
        validate_details(self.metadata)

    def register_evaluator(
        self,
        gate_name: str,
        evaluator: Callable[[], ProductionGateResult],
    ) -> None:
        """Register evaluator for a release gate."""
        normalized_gate_name = validate_non_empty_string(gate_name, "Gate name")

        if not callable(evaluator):
            raise ValueError("Evaluator must be callable.")

        self.evaluators[normalized_gate_name] = evaluator

    def evaluate_gate(self, gate: ReleaseGate) -> ReleaseEvaluation:
        """Evaluate one release gate."""
        evaluation = evaluate_release_gate(
            gate=gate,
            evaluator=self.evaluators.get(gate.name.strip()),
        )
        self.evaluations.append(evaluation)

        return evaluation

    def evaluate_all(self) -> ReleaseReport:
        """Evaluate all release gates."""
        self.evaluations.clear()

        for gate in self.plan.gates:
            self.evaluate_gate(gate)

        decision = aggregate_release_decision(self.evaluations)

        return build_release_report(
            plan=self.plan,
            evaluations=list(self.evaluations),
            decision=decision,
            metadata=self.metadata,
        )

    def summary(self) -> dict[str, Any]:
        """Return release gate engine summary."""
        return {
            "version": self.plan.version.strip(),
            "environment": self.plan.environment.strip(),
            "gates": len(self.plan.gates),
            "evaluators": len(self.evaluators),
            "evaluations": len(self.evaluations),
            "metadata": dict(self.metadata),
        }

    def clear(self) -> None:
        """Clear evaluations."""
        self.evaluations.clear()


def normalize_release_gate_type(gate_type: ReleaseGateType | str) -> ReleaseGateType:
    """Normalize release gate type."""
    if isinstance(gate_type, ReleaseGateType):
        return gate_type

    normalized = validate_non_empty_string(gate_type, "Release gate type").lower()

    try:
        return ReleaseGateType(normalized)
    except ValueError as exc:
        valid = ", ".join(item.value for item in ReleaseGateType)
        raise ValueError(
            f"Invalid release gate type '{gate_type}'. Valid gate types: {valid}.",
        ) from exc


def normalize_release_decision(decision: ReleaseDecision | str) -> ReleaseDecision:
    """Normalize release decision."""
    if isinstance(decision, ReleaseDecision):
        return decision

    normalized = validate_non_empty_string(decision, "Release decision").lower()

    try:
        return ReleaseDecision(normalized)
    except ValueError as exc:
        valid = ", ".join(item.value for item in ReleaseDecision)
        raise ValueError(
            f"Invalid release decision '{decision}'. Valid decisions: {valid}.",
        ) from exc


def release_decision_to_status(decision: ReleaseDecision | str) -> ProductionStatus:
    """Convert release decision into production status."""
    normalized = normalize_release_decision(decision)

    if normalized == ReleaseDecision.APPROVE:
        return ProductionStatus.READY

    if normalized == ReleaseDecision.WARN:
        return ProductionStatus.WARNING

    return ProductionStatus.BLOCKED


def decide_release_from_status(
    status: ProductionStatus | str,
    *,
    required: bool = True,
) -> ReleaseDecision:
    """Create release decision from production status."""
    if not isinstance(required, bool):
        raise ValueError("Required must be a boolean.")

    normalized = normalize_production_status(status)

    if normalized == ProductionStatus.READY:
        return ReleaseDecision.APPROVE

    if normalized == ProductionStatus.WARNING:
        return ReleaseDecision.WARN

    if normalized == ProductionStatus.BLOCKED:
        return ReleaseDecision.BLOCK if required else ReleaseDecision.WARN

    return ReleaseDecision.BLOCK if required else ReleaseDecision.WARN


def aggregate_release_decision(
    evaluations: list[ReleaseEvaluation],
) -> ReleaseDecision:
    """Aggregate release decision from evaluations."""
    validate_release_evaluations(evaluations)

    if not evaluations:
        return ReleaseDecision.BLOCK

    if any(evaluation.blocked for evaluation in evaluations):
        return ReleaseDecision.BLOCK

    if any(evaluation.warning for evaluation in evaluations):
        return ReleaseDecision.WARN

    return ReleaseDecision.APPROVE


def validate_release_gates(gates: list[ReleaseGate]) -> list[ReleaseGate]:
    """Validate release gates."""
    if not isinstance(gates, list):
        raise ValueError("Gates must be a list.")

    for gate in gates:
        if not isinstance(gate, ReleaseGate):
            raise ValueError("Gates must contain ReleaseGate objects.")

    return gates


def validate_release_evaluations(
    evaluations: list[ReleaseEvaluation],
) -> list[ReleaseEvaluation]:
    """Validate release evaluations."""
    if not isinstance(evaluations, list):
        raise ValueError("Evaluations must be a list.")

    for evaluation in evaluations:
        if not isinstance(evaluation, ReleaseEvaluation):
            raise ValueError("Evaluations must contain ReleaseEvaluation objects.")

    return evaluations


def validate_evaluator_mapping(
    evaluators: dict[str, Callable[[], ProductionGateResult]],
) -> dict[str, Callable[[], ProductionGateResult]]:
    """Validate evaluator mapping."""
    if not isinstance(evaluators, dict):
        raise ValueError("Evaluators must be a dictionary.")

    for gate_name, evaluator in evaluators.items():
        validate_non_empty_string(gate_name, "Gate name")

        if not callable(evaluator):
            raise ValueError("Evaluator values must be callable.")

    return evaluators


def build_release_gate(
    *,
    name: str,
    gate_type: ReleaseGateType | str,
    required: bool = True,
    description: str = "",
    metadata: dict[str, Any] | None = None,
) -> ReleaseGate:
    """Build release gate."""
    return ReleaseGate(
        name=name,
        gate_type=gate_type,
        required=required,
        description=description,
        metadata=metadata or {},
    )


def build_release_evaluation(
    *,
    gate: ReleaseGate,
    gate_result: ProductionGateResult,
    decision: ReleaseDecision | str,
    message: str = "",
    metadata: dict[str, Any] | None = None,
) -> ReleaseEvaluation:
    """Build release evaluation."""
    return ReleaseEvaluation(
        gate=gate,
        gate_result=gate_result,
        decision=decision,
        message=message,
        metadata=metadata or {},
    )


def build_release_plan(
    *,
    version: str,
    environment: str,
    gates: list[ReleaseGate] | None = None,
    metadata: dict[str, Any] | None = None,
) -> ReleasePlan:
    """Build release plan."""
    return ReleasePlan(
        version=version,
        environment=environment,
        gates=gates or [],
        metadata=metadata or {},
    )


def build_release_report(
    *,
    plan: ReleasePlan,
    evaluations: list[ReleaseEvaluation] | None = None,
    decision: ReleaseDecision | str | None = None,
    generated_at: str | None = None,
    metadata: dict[str, Any] | None = None,
) -> ReleaseReport:
    """Build release report."""
    normalized_evaluations = evaluations or []
    resolved_decision = decision or aggregate_release_decision(normalized_evaluations)

    report_kwargs: dict[str, Any] = {
        "plan": plan,
        "evaluations": normalized_evaluations,
        "decision": resolved_decision,
        "metadata": metadata or {},
    }

    if generated_at is not None:
        report_kwargs["generated_at"] = generated_at

    return ReleaseReport(**report_kwargs)


def evaluate_release_gate(
    *,
    gate: ReleaseGate,
    evaluator: Callable[[], ProductionGateResult] | None,
) -> ReleaseEvaluation:
    """Evaluate one release gate safely."""
    if not isinstance(gate, ReleaseGate):
        raise ValueError("Gate must be a ReleaseGate.")

    if evaluator is None:
        status = ProductionStatus.BLOCKED if gate.required else ProductionStatus.WARNING
        gate_result = build_production_gate_result(
            gate_name=gate.name,
            status=status,
            checks=[
                build_production_check_result(
                    name=f"{gate.name.strip()}-missing-evaluator",
                    status=status,
                    severity=ProductionSeverity.CRITICAL
                    if gate.required
                    else ProductionSeverity.WARNING,
                    passed=not gate.required,
                    message="Release gate evaluator is missing.",
                ),
            ],
            message="Release gate evaluator is missing.",
        )

        return build_release_evaluation(
            gate=gate,
            gate_result=gate_result,
            decision=decide_release_from_status(status, required=gate.required),
            message="Release gate evaluator is missing.",
        )

    if not callable(evaluator):
        raise ValueError("Evaluator must be callable.")

    try:
        gate_result = evaluator()

        if not isinstance(gate_result, ProductionGateResult):
            raise ValueError("Evaluator must return ProductionGateResult.")
    except Exception as exc:  # noqa: BLE001
        gate_result = build_production_gate_result(
            gate_name=gate.name,
            status=ProductionStatus.BLOCKED,
            checks=[
                build_production_check_result(
                    name=f"{gate.name.strip()}-evaluator-error",
                    status=ProductionStatus.BLOCKED,
                    severity=ProductionSeverity.ERROR,
                    passed=False,
                    message="Release gate evaluator failed.",
                    details={
                        "error": str(exc),
                        "error_type": exc.__class__.__name__,
                    },
                ),
            ],
            message="Release gate evaluator failed.",
        )

    decision = decide_release_from_status(
        gate_result.status,
        required=gate.required,
    )

    return build_release_evaluation(
        gate=gate,
        gate_result=gate_result,
        decision=decision,
        message=gate_result.message,
    )


def build_release_gate_engine(
    *,
    plan: ReleasePlan,
    evaluators: dict[str, Callable[[], ProductionGateResult]] | None = None,
    evaluations: list[ReleaseEvaluation] | None = None,
    metadata: dict[str, Any] | None = None,
) -> ReleaseGateEngine:
    """Build release gate engine."""
    return ReleaseGateEngine(
        plan=plan,
        evaluators=evaluators or {},
        evaluations=evaluations or [],
        metadata=metadata or {},
    )


def run_release_gate_engine(
    *,
    plan: ReleasePlan,
    evaluators: dict[str, Callable[[], ProductionGateResult]] | None = None,
    metadata: dict[str, Any] | None = None,
) -> ReleaseReport:
    """Run release gate engine."""
    engine = build_release_gate_engine(
        plan=plan,
        evaluators=evaluators or {},
        metadata=metadata or {},
    )

    return engine.evaluate_all()