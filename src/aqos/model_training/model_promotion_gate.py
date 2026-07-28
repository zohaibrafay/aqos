from __future__ import annotations

from dataclasses import dataclass, field as dataclass_field
from enum import Enum
from pathlib import Path
from typing import Any

from aqos.model_training.model_evaluation import ModelPromotionStage
from aqos.model_training.model_promotion import (
    promotion_stage_rank,
    read_model_promotion_json,
)
from aqos.model_training.model_promotion_registry import (
    ModelPromotionRegistry,
    ModelPromotionRegistryEntry,
    find_latest_approved_model_for_stage,
    read_model_promotion_registry,
)


class ModelPromotionGateSeverity(str, Enum):
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"


class ModelPromotionGateStatus(str, Enum):
    APPROVED = "approved"
    REJECTED = "rejected"


class ModelPromotionGateRule(str, Enum):
    MODEL_METADATA_PRESENT = "model_metadata_present"
    PROMOTION_REGISTRY_PRESENT = "promotion_registry_present"
    MODEL_ID_PRESENT = "model_id_present"
    MODEL_VERSION_PRESENT = "model_version_present"
    MODEL_PROMOTION_READY = "model_promotion_ready"
    REQUIRED_STAGE_NOT_BLOCKED = "required_stage_not_blocked"
    APPROVED_PROMOTION_FOUND = "approved_promotion_found"
    APPROVED_MODEL_ID_MATCH = "approved_model_id_match"
    APPROVED_MODEL_VERSION_MATCH = "approved_model_version_match"
    APPROVED_STAGE_SUFFICIENT = "approved_stage_sufficient"


@dataclass(frozen=True)
class ModelPromotionGateIssue:
    rule: ModelPromotionGateRule
    severity: ModelPromotionGateSeverity
    message: str
    field: str | None = None
    details: dict[str, Any] = dataclass_field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.message.strip():
            raise ValueError("Model promotion gate issue message cannot be empty.")

    def to_dict(self) -> dict[str, Any]:
        return {
            "rule": self.rule.value,
            "severity": self.severity.value,
            "message": self.message,
            "field": self.field,
            "details": self.details,
        }


@dataclass(frozen=True)
class ModelPromotionGateDecision:
    status: ModelPromotionGateStatus
    approved: bool
    required_stage: ModelPromotionStage
    model_name: str | None
    model_id: str | None
    model_version: str | None
    approved_promotion: ModelPromotionRegistryEntry | None = None
    issues: tuple[ModelPromotionGateIssue, ...] = ()

    @property
    def error_count(self) -> int:
        return sum(
            1
            for issue in self.issues
            if issue.severity == ModelPromotionGateSeverity.ERROR
        )

    @property
    def is_approved(self) -> bool:
        return self.approved

    def raise_if_rejected(self) -> None:
        if self.approved:
            return

        messages = [
            issue.message
            for issue in self.issues
            if issue.severity == ModelPromotionGateSeverity.ERROR
        ]

        raise ValueError("Model promotion gate rejected: " + "; ".join(messages))

    def to_dict(self) -> dict[str, Any]:
        return {
            "status": self.status.value,
            "approved": self.approved,
            "required_stage": self.required_stage.value,
            "model_name": self.model_name,
            "model_id": self.model_id,
            "model_version": self.model_version,
            "approved_promotion": (
                self.approved_promotion.to_dict()
                if self.approved_promotion is not None
                else None
            ),
            "error_count": self.error_count,
            "issues": [issue.to_dict() for issue in self.issues],
        }


def build_model_promotion_gate_issue(
    rule: ModelPromotionGateRule,
    severity: ModelPromotionGateSeverity,
    message: str,
    field: str | None = None,
    details: dict[str, Any] | None = None,
) -> ModelPromotionGateIssue:
    return ModelPromotionGateIssue(
        rule=rule,
        severity=severity,
        message=message,
        field=field,
        details=details or {},
    )


def build_model_promotion_gate_status(
    issues: tuple[ModelPromotionGateIssue, ...],
) -> ModelPromotionGateStatus:
    if any(issue.severity == ModelPromotionGateSeverity.ERROR for issue in issues):
        return ModelPromotionGateStatus.REJECTED

    return ModelPromotionGateStatus.APPROVED


def extract_model_identity_from_metadata(
    model_version_metadata: dict[str, Any],
) -> tuple[str | None, str | None, str | None, bool | None]:
    model_name = model_version_metadata.get("model_name")
    model_id = model_version_metadata.get("model_id")
    model_version = model_version_metadata.get("model_version")
    is_promotion_ready = model_version_metadata.get("is_promotion_ready")

    return (
        str(model_name) if model_name is not None else None,
        str(model_id) if model_id is not None else None,
        str(model_version) if model_version is not None else None,
        is_promotion_ready if isinstance(is_promotion_ready, bool) else None,
    )


def find_latest_matching_approved_promotion(
    registry: ModelPromotionRegistry,
    required_stage: ModelPromotionStage,
    model_name: str | None,
    model_id: str | None,
    model_version: str | None,
) -> ModelPromotionRegistryEntry | None:
    if model_name is None:
        return None

    candidate = find_latest_approved_model_for_stage(
        registry=registry,
        target_stage=required_stage,
        model_name=model_name,
    )

    if candidate is not None:
        return candidate

    approved_promotions = [
        promotion
        for promotion in registry.promotions
        if promotion.approved
        and promotion.model_name == model_name
        and promotion_stage_rank(promotion.target_stage)
        >= promotion_stage_rank(required_stage)
    ]

    if model_id is not None:
        approved_promotions = [
            promotion
            for promotion in approved_promotions
            if promotion.model_id == model_id
        ]

    if model_version is not None:
        approved_promotions = [
            promotion
            for promotion in approved_promotions
            if promotion.model_version == model_version
        ]

    if not approved_promotions:
        return None

    return max(approved_promotions, key=lambda promotion: promotion.created_at_utc)


def validate_model_against_promotion_registry(
    model_version_metadata: dict[str, Any],
    registry: ModelPromotionRegistry,
    required_stage: ModelPromotionStage,
) -> ModelPromotionGateDecision:
    model_name, model_id, model_version, is_promotion_ready = (
        extract_model_identity_from_metadata(model_version_metadata)
    )

    issues: list[ModelPromotionGateIssue] = []

    if required_stage == ModelPromotionStage.BLOCKED:
        issues.append(
            build_model_promotion_gate_issue(
                rule=ModelPromotionGateRule.REQUIRED_STAGE_NOT_BLOCKED,
                severity=ModelPromotionGateSeverity.ERROR,
                message="Required promotion stage cannot be blocked.",
                field="required_stage",
            )
        )

    if not model_id:
        issues.append(
            build_model_promotion_gate_issue(
                rule=ModelPromotionGateRule.MODEL_ID_PRESENT,
                severity=ModelPromotionGateSeverity.ERROR,
                message="Model metadata must contain model_id.",
                field="model_id",
            )
        )

    if not model_version:
        issues.append(
            build_model_promotion_gate_issue(
                rule=ModelPromotionGateRule.MODEL_VERSION_PRESENT,
                severity=ModelPromotionGateSeverity.ERROR,
                message="Model metadata must contain model_version.",
                field="model_version",
            )
        )

    if is_promotion_ready is not True:
        issues.append(
            build_model_promotion_gate_issue(
                rule=ModelPromotionGateRule.MODEL_PROMOTION_READY,
                severity=ModelPromotionGateSeverity.ERROR,
                message="Model metadata is not marked promotion ready.",
                field="is_promotion_ready",
                details={"actual": is_promotion_ready},
            )
        )

    approved_promotion = find_latest_matching_approved_promotion(
        registry=registry,
        required_stage=required_stage,
        model_name=model_name,
        model_id=model_id,
        model_version=model_version,
    )

    if approved_promotion is None:
        issues.append(
            build_model_promotion_gate_issue(
                rule=ModelPromotionGateRule.APPROVED_PROMOTION_FOUND,
                severity=ModelPromotionGateSeverity.ERROR,
                message="No approved promotion registry entry found for required stage.",
                field="promotion_registry",
                details={
                    "required_stage": required_stage.value,
                    "model_name": model_name,
                    "model_id": model_id,
                    "model_version": model_version,
                },
            )
        )
    else:
        if model_id is not None and approved_promotion.model_id != model_id:
            issues.append(
                build_model_promotion_gate_issue(
                    rule=ModelPromotionGateRule.APPROVED_MODEL_ID_MATCH,
                    severity=ModelPromotionGateSeverity.ERROR,
                    message="Approved promotion model_id does not match model metadata.",
                    field="model_id",
                    details={
                        "metadata_model_id": model_id,
                        "promotion_model_id": approved_promotion.model_id,
                    },
                )
            )

        if model_version is not None and approved_promotion.model_version != model_version:
            issues.append(
                build_model_promotion_gate_issue(
                    rule=ModelPromotionGateRule.APPROVED_MODEL_VERSION_MATCH,
                    severity=ModelPromotionGateSeverity.ERROR,
                    message="Approved promotion model_version does not match model metadata.",
                    field="model_version",
                    details={
                        "metadata_model_version": model_version,
                        "promotion_model_version": approved_promotion.model_version,
                    },
                )
            )

        if promotion_stage_rank(approved_promotion.target_stage) < promotion_stage_rank(
            required_stage
        ):
            issues.append(
                build_model_promotion_gate_issue(
                    rule=ModelPromotionGateRule.APPROVED_STAGE_SUFFICIENT,
                    severity=ModelPromotionGateSeverity.ERROR,
                    message="Approved promotion stage is lower than required stage.",
                    field="target_stage",
                    details={
                        "approved_stage": approved_promotion.target_stage.value,
                        "required_stage": required_stage.value,
                    },
                )
            )

    issue_tuple = tuple(issues)
    status = build_model_promotion_gate_status(issue_tuple)

    return ModelPromotionGateDecision(
        status=status,
        approved=status == ModelPromotionGateStatus.APPROVED,
        required_stage=required_stage,
        model_name=model_name,
        model_id=model_id,
        model_version=model_version,
        approved_promotion=approved_promotion,
        issues=issue_tuple,
    )


def validate_model_files_against_promotion_registry(
    model_version_metadata_path: str | Path,
    promotion_registry_path: str | Path,
    required_stage: ModelPromotionStage,
) -> ModelPromotionGateDecision:
    metadata_path = Path(model_version_metadata_path)
    registry_path = Path(promotion_registry_path)

    if not metadata_path.exists():
        issue = build_model_promotion_gate_issue(
            rule=ModelPromotionGateRule.MODEL_METADATA_PRESENT,
            severity=ModelPromotionGateSeverity.ERROR,
            message=f"Model version metadata file does not exist: {metadata_path}",
            field="model_version_metadata_path",
        )
        return ModelPromotionGateDecision(
            status=ModelPromotionGateStatus.REJECTED,
            approved=False,
            required_stage=required_stage,
            model_name=None,
            model_id=None,
            model_version=None,
            issues=(issue,),
        )

    if not registry_path.exists():
        model_metadata = read_model_promotion_json(metadata_path)
        model_name, model_id, model_version, _ = extract_model_identity_from_metadata(
            model_metadata
        )

        issue = build_model_promotion_gate_issue(
            rule=ModelPromotionGateRule.PROMOTION_REGISTRY_PRESENT,
            severity=ModelPromotionGateSeverity.ERROR,
            message=f"Model promotion registry file does not exist: {registry_path}",
            field="promotion_registry_path",
        )
        return ModelPromotionGateDecision(
            status=ModelPromotionGateStatus.REJECTED,
            approved=False,
            required_stage=required_stage,
            model_name=model_name,
            model_id=model_id,
            model_version=model_version,
            issues=(issue,),
        )

    return validate_model_against_promotion_registry(
        model_version_metadata=read_model_promotion_json(metadata_path),
        registry=read_model_promotion_registry(registry_path),
        required_stage=required_stage,
    )


__all__ = [
    "ModelPromotionGateDecision",
    "ModelPromotionGateIssue",
    "ModelPromotionGateRule",
    "ModelPromotionGateSeverity",
    "ModelPromotionGateStatus",
    "build_model_promotion_gate_issue",
    "build_model_promotion_gate_status",
    "extract_model_identity_from_metadata",
    "find_latest_matching_approved_promotion",
    "validate_model_against_promotion_registry",
    "validate_model_files_against_promotion_registry",
]