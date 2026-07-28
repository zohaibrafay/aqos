from __future__ import annotations

import json
from dataclasses import dataclass, field as dataclass_field
from datetime import UTC, datetime
from enum import Enum
from pathlib import Path
from typing import Any

from aqos.model_training.model_evaluation import (
    ModelEvaluationStatus,
    ModelPromotionStage,
)


MODEL_PROMOTION_VERSION = "1.0"


class ModelPromotionSeverity(str, Enum):
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"


class ModelPromotionStatus(str, Enum):
    APPROVED = "approved"
    APPROVED_WITH_WARNINGS = "approved_with_warnings"
    REJECTED = "rejected"


class ModelPromotionRule(str, Enum):
    MODEL_METADATA_PRESENT = "model_metadata_present"
    MODEL_ID_PRESENT = "model_id_present"
    MODEL_VERSION_PRESENT = "model_version_present"
    MODEL_ARTIFACT_PRESENT = "model_artifact_present"
    EVALUATION_REPORT_PRESENT = "evaluation_report_present"
    EVALUATION_STATUS_ALLOWED = "evaluation_status_allowed"
    EVALUATION_PROMOTION_READY = "evaluation_promotion_ready"
    MODEL_PROMOTION_READY = "model_promotion_ready"
    MODEL_EVALUATION_LINKED = "model_evaluation_linked"
    MODEL_EVALUATION_ID_MATCH = "model_evaluation_id_match"
    MODEL_EVALUATION_VERSION_MATCH = "model_evaluation_version_match"
    TARGET_STAGE_ALLOWED = "target_stage_allowed"
    TARGET_STAGE_NOT_BLOCKED = "target_stage_not_blocked"
    STAGE_FORWARD_ONLY = "stage_forward_only"


PROMOTION_STAGE_ORDER: dict[ModelPromotionStage, int] = {
    ModelPromotionStage.BLOCKED: -1,
    ModelPromotionStage.RESEARCH: 0,
    ModelPromotionStage.PAPER_TRADING: 1,
    ModelPromotionStage.DEMO: 2,
    ModelPromotionStage.LIMITED_LIVE: 3,
    ModelPromotionStage.LIVE: 4,
}


@dataclass(frozen=True)
class ModelPromotionIssue:
    rule: ModelPromotionRule
    severity: ModelPromotionSeverity
    message: str
    field: str | None = None
    details: dict[str, Any] = dataclass_field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.message.strip():
            raise ValueError("Model promotion issue message cannot be empty.")

    def to_dict(self) -> dict[str, Any]:
        return {
            "rule": self.rule.value,
            "severity": self.severity.value,
            "message": self.message,
            "field": self.field,
            "details": self.details,
        }


@dataclass(frozen=True)
class ModelPromotionCandidate:
    model_name: str
    model_id: str | None
    model_version: str | None
    model_artifact_path: str | None
    model_version_metadata_path: str | None = None
    model_evaluation_report_path: str | None = None
    model_promotion_stage: ModelPromotionStage | None = None
    model_is_promotion_ready: bool | None = None
    evaluation_status: str | None = None
    evaluation_promotion_stage: ModelPromotionStage | None = None
    evaluation_is_promotion_ready: bool | None = None
    dataset_id: str | None = None
    dataset_version: str | None = None
    experiment_run_id: str | None = None

    def __post_init__(self) -> None:
        if not self.model_name.strip():
            raise ValueError("model_name cannot be empty.")

    def to_dict(self) -> dict[str, Any]:
        return {
            "model_name": self.model_name,
            "model_id": self.model_id,
            "model_version": self.model_version,
            "model_artifact_path": self.model_artifact_path,
            "model_version_metadata_path": self.model_version_metadata_path,
            "model_evaluation_report_path": self.model_evaluation_report_path,
            "model_promotion_stage": (
                self.model_promotion_stage.value
                if self.model_promotion_stage is not None
                else None
            ),
            "model_is_promotion_ready": self.model_is_promotion_ready,
            "evaluation_status": self.evaluation_status,
            "evaluation_promotion_stage": (
                self.evaluation_promotion_stage.value
                if self.evaluation_promotion_stage is not None
                else None
            ),
            "evaluation_is_promotion_ready": self.evaluation_is_promotion_ready,
            "dataset_id": self.dataset_id,
            "dataset_version": self.dataset_version,
            "experiment_run_id": self.experiment_run_id,
        }


@dataclass(frozen=True)
class ModelPromotionPolicy:
    target_stage: ModelPromotionStage
    current_stage: ModelPromotionStage = ModelPromotionStage.RESEARCH
    require_evaluation_report: bool = True
    require_model_promotion_ready: bool = True
    allow_warning_evaluation: bool = True
    allow_same_stage: bool = True
    forward_only: bool = True

    def __post_init__(self) -> None:
        if self.target_stage == ModelPromotionStage.BLOCKED:
            raise ValueError("target_stage cannot be blocked.")

    def to_dict(self) -> dict[str, Any]:
        return {
            "target_stage": self.target_stage.value,
            "current_stage": self.current_stage.value,
            "require_evaluation_report": self.require_evaluation_report,
            "require_model_promotion_ready": self.require_model_promotion_ready,
            "allow_warning_evaluation": self.allow_warning_evaluation,
            "allow_same_stage": self.allow_same_stage,
            "forward_only": self.forward_only,
        }


@dataclass(frozen=True)
class ModelPromotionReview:
    created_at_utc: str
    candidate: ModelPromotionCandidate
    policy: ModelPromotionPolicy
    status: ModelPromotionStatus
    target_stage: ModelPromotionStage
    approved: bool
    issues: tuple[ModelPromotionIssue, ...] = ()
    metadata_version: str = MODEL_PROMOTION_VERSION

    @property
    def error_count(self) -> int:
        return sum(
            1
            for issue in self.issues
            if issue.severity == ModelPromotionSeverity.ERROR
        )

    @property
    def warning_count(self) -> int:
        return sum(
            1
            for issue in self.issues
            if issue.severity == ModelPromotionSeverity.WARNING
        )

    @property
    def info_count(self) -> int:
        return sum(
            1
            for issue in self.issues
            if issue.severity == ModelPromotionSeverity.INFO
        )

    def raise_if_rejected(self) -> None:
        if self.approved:
            return

        messages = [
            issue.message
            for issue in self.issues
            if issue.severity == ModelPromotionSeverity.ERROR
        ]

        raise ValueError("Model promotion rejected: " + "; ".join(messages))

    def to_dict(self) -> dict[str, Any]:
        return {
            "metadata_version": self.metadata_version,
            "created_at_utc": self.created_at_utc,
            "status": self.status.value,
            "approved": self.approved,
            "target_stage": self.target_stage.value,
            "candidate": self.candidate.to_dict(),
            "policy": self.policy.to_dict(),
            "error_count": self.error_count,
            "warning_count": self.warning_count,
            "info_count": self.info_count,
            "issues": [issue.to_dict() for issue in self.issues],
        }


def model_promotion_utc_now_iso() -> str:
    return datetime.now(tz=UTC).replace(microsecond=0).isoformat()


def parse_model_promotion_stage(value: str | ModelPromotionStage | None) -> ModelPromotionStage | None:
    if value is None:
        return None

    if isinstance(value, ModelPromotionStage):
        return value

    return ModelPromotionStage(value)


def promotion_stage_rank(stage: ModelPromotionStage) -> int:
    return PROMOTION_STAGE_ORDER[stage]


def is_target_stage_allowed(
    target_stage: ModelPromotionStage,
    allowed_stage: ModelPromotionStage | None,
) -> bool:
    if allowed_stage is None:
        return False

    if allowed_stage == ModelPromotionStage.BLOCKED:
        return False

    return promotion_stage_rank(target_stage) <= promotion_stage_rank(allowed_stage)


def build_model_promotion_issue(
    rule: ModelPromotionRule,
    severity: ModelPromotionSeverity,
    message: str,
    field: str | None = None,
    details: dict[str, Any] | None = None,
) -> ModelPromotionIssue:
    return ModelPromotionIssue(
        rule=rule,
        severity=severity,
        message=message,
        field=field,
        details=details or {},
    )


def build_model_promotion_status(
    issues: tuple[ModelPromotionIssue, ...],
) -> ModelPromotionStatus:
    if any(issue.severity == ModelPromotionSeverity.ERROR for issue in issues):
        return ModelPromotionStatus.REJECTED

    if any(issue.severity == ModelPromotionSeverity.WARNING for issue in issues):
        return ModelPromotionStatus.APPROVED_WITH_WARNINGS

    return ModelPromotionStatus.APPROVED


def extract_model_artifact_path(
    model_version_metadata: dict[str, Any],
) -> str | None:
    model_artifact = model_version_metadata.get("model_artifact")

    if not isinstance(model_artifact, dict):
        return None

    path = model_artifact.get("path")

    if path is None:
        return None

    return str(path)


def build_model_promotion_candidate(
    model_version_metadata: dict[str, Any],
    evaluation_report: dict[str, Any] | None = None,
    model_version_metadata_path: str | Path | None = None,
) -> ModelPromotionCandidate:
    model_name = str(
        model_version_metadata.get("model_name")
        or (evaluation_report or {}).get("model_name")
        or ""
    )

    if not model_name.strip():
        raise ValueError("model_name is required in model version metadata.")

    evaluation_promotion_stage = None

    if evaluation_report is not None:
        evaluation_promotion_stage = parse_model_promotion_stage(
            evaluation_report.get("promotion_stage")
        )

    return ModelPromotionCandidate(
        model_name=model_name,
        model_id=model_version_metadata.get("model_id"),
        model_version=model_version_metadata.get("model_version"),
        model_artifact_path=extract_model_artifact_path(model_version_metadata),
        model_version_metadata_path=(
            Path(model_version_metadata_path).as_posix()
            if model_version_metadata_path is not None
            else None
        ),
        model_evaluation_report_path=model_version_metadata.get(
            "model_evaluation_report_path"
        ),
        model_promotion_stage=parse_model_promotion_stage(
            model_version_metadata.get("promotion_stage")
        ),
        model_is_promotion_ready=model_version_metadata.get("is_promotion_ready"),
        evaluation_status=(
            str(evaluation_report.get("status"))
            if evaluation_report is not None
            else None
        ),
        evaluation_promotion_stage=evaluation_promotion_stage,
        evaluation_is_promotion_ready=(
            evaluation_report.get("is_promotion_ready")
            if evaluation_report is not None
            else None
        ),
        dataset_id=model_version_metadata.get("dataset_id"),
        dataset_version=model_version_metadata.get("dataset_version"),
        experiment_run_id=model_version_metadata.get("experiment_run_id"),
    )


def validate_model_promotion_candidate(
    candidate: ModelPromotionCandidate,
    policy: ModelPromotionPolicy,
    evaluation_report: dict[str, Any] | None = None,
) -> tuple[ModelPromotionIssue, ...]:
    issues: list[ModelPromotionIssue] = []

    if not candidate.model_id:
        issues.append(
            build_model_promotion_issue(
                rule=ModelPromotionRule.MODEL_ID_PRESENT,
                severity=ModelPromotionSeverity.ERROR,
                message="Model promotion requires model_id.",
                field="model_id",
            )
        )

    if not candidate.model_version:
        issues.append(
            build_model_promotion_issue(
                rule=ModelPromotionRule.MODEL_VERSION_PRESENT,
                severity=ModelPromotionSeverity.ERROR,
                message="Model promotion requires model_version.",
                field="model_version",
            )
        )

    if not candidate.model_artifact_path:
        issues.append(
            build_model_promotion_issue(
                rule=ModelPromotionRule.MODEL_ARTIFACT_PRESENT,
                severity=ModelPromotionSeverity.ERROR,
                message="Model promotion requires a model artifact path.",
                field="model_artifact.path",
            )
        )

    if policy.require_evaluation_report and evaluation_report is None:
        issues.append(
            build_model_promotion_issue(
                rule=ModelPromotionRule.EVALUATION_REPORT_PRESENT,
                severity=ModelPromotionSeverity.ERROR,
                message="Model promotion requires an evaluation report.",
                field="model_evaluation_report",
            )
        )

    if policy.require_model_promotion_ready and candidate.model_is_promotion_ready is not True:
        issues.append(
            build_model_promotion_issue(
                rule=ModelPromotionRule.MODEL_PROMOTION_READY,
                severity=ModelPromotionSeverity.ERROR,
                message="Model version metadata is not promotion ready.",
                field="is_promotion_ready",
                details={"actual": candidate.model_is_promotion_ready},
            )
        )

    if evaluation_report is not None:
        evaluation_status = str(evaluation_report.get("status"))

        allowed_statuses = {ModelEvaluationStatus.PASSED.value}

        if policy.allow_warning_evaluation:
            allowed_statuses.add(ModelEvaluationStatus.PASSED_WITH_WARNINGS.value)

        if evaluation_status not in allowed_statuses:
            issues.append(
                build_model_promotion_issue(
                    rule=ModelPromotionRule.EVALUATION_STATUS_ALLOWED,
                    severity=ModelPromotionSeverity.ERROR,
                    message="Evaluation status is not allowed for model promotion.",
                    field="evaluation.status",
                    details={
                        "actual": evaluation_status,
                        "allowed": sorted(allowed_statuses),
                    },
                )
            )

        if evaluation_report.get("is_promotion_ready") is not True:
            issues.append(
                build_model_promotion_issue(
                    rule=ModelPromotionRule.EVALUATION_PROMOTION_READY,
                    severity=ModelPromotionSeverity.ERROR,
                    message="Evaluation report is not promotion ready.",
                    field="evaluation.is_promotion_ready",
                    details={"actual": evaluation_report.get("is_promotion_ready")},
                )
            )

        evaluation_model_id = evaluation_report.get("model_id")
        evaluation_model_version = evaluation_report.get("model_version")

        if (
            candidate.model_id
            and evaluation_model_id
            and candidate.model_id != evaluation_model_id
        ):
            issues.append(
                build_model_promotion_issue(
                    rule=ModelPromotionRule.MODEL_EVALUATION_ID_MATCH,
                    severity=ModelPromotionSeverity.ERROR,
                    message="Model version metadata and evaluation report model_id do not match.",
                    field="model_id",
                    details={
                        "model_metadata_model_id": candidate.model_id,
                        "evaluation_model_id": evaluation_model_id,
                    },
                )
            )

        if (
            candidate.model_version
            and evaluation_model_version
            and candidate.model_version != evaluation_model_version
        ):
            issues.append(
                build_model_promotion_issue(
                    rule=ModelPromotionRule.MODEL_EVALUATION_VERSION_MATCH,
                    severity=ModelPromotionSeverity.ERROR,
                    message="Model version metadata and evaluation report model_version do not match.",
                    field="model_version",
                    details={
                        "model_metadata_model_version": candidate.model_version,
                        "evaluation_model_version": evaluation_model_version,
                    },
                )
            )

    if policy.target_stage == ModelPromotionStage.BLOCKED:
        issues.append(
            build_model_promotion_issue(
                rule=ModelPromotionRule.TARGET_STAGE_NOT_BLOCKED,
                severity=ModelPromotionSeverity.ERROR,
                message="Cannot promote a model to blocked stage.",
                field="target_stage",
            )
        )

    allowed_stage = candidate.evaluation_promotion_stage or candidate.model_promotion_stage

    if not is_target_stage_allowed(policy.target_stage, allowed_stage):
        issues.append(
            build_model_promotion_issue(
                rule=ModelPromotionRule.TARGET_STAGE_ALLOWED,
                severity=ModelPromotionSeverity.ERROR,
                message="Target promotion stage is higher than the evaluated allowed stage.",
                field="target_stage",
                details={
                    "target_stage": policy.target_stage.value,
                    "allowed_stage": allowed_stage.value if allowed_stage else None,
                },
            )
        )

    if policy.forward_only:
        current_rank = promotion_stage_rank(policy.current_stage)
        target_rank = promotion_stage_rank(policy.target_stage)

        if target_rank < current_rank:
            issues.append(
                build_model_promotion_issue(
                    rule=ModelPromotionRule.STAGE_FORWARD_ONLY,
                    severity=ModelPromotionSeverity.ERROR,
                    message="Model promotion cannot move backwards when forward_only is enabled.",
                    field="target_stage",
                    details={
                        "current_stage": policy.current_stage.value,
                        "target_stage": policy.target_stage.value,
                    },
                )
            )

        if target_rank == current_rank and not policy.allow_same_stage:
            issues.append(
                build_model_promotion_issue(
                    rule=ModelPromotionRule.STAGE_FORWARD_ONLY,
                    severity=ModelPromotionSeverity.ERROR,
                    message="Model promotion cannot stay on the same stage when allow_same_stage is false.",
                    field="target_stage",
                    details={
                        "current_stage": policy.current_stage.value,
                        "target_stage": policy.target_stage.value,
                    },
                )
            )

    return tuple(issues)


def build_model_promotion_review(
    candidate: ModelPromotionCandidate,
    policy: ModelPromotionPolicy,
    evaluation_report: dict[str, Any] | None = None,
    created_at_utc: str | None = None,
) -> ModelPromotionReview:
    issues = validate_model_promotion_candidate(
        candidate=candidate,
        policy=policy,
        evaluation_report=evaluation_report,
    )
    status = build_model_promotion_status(issues)

    return ModelPromotionReview(
        created_at_utc=created_at_utc or model_promotion_utc_now_iso(),
        candidate=candidate,
        policy=policy,
        status=status,
        target_stage=policy.target_stage,
        approved=status != ModelPromotionStatus.REJECTED,
        issues=issues,
    )


def build_model_promotion_review_from_metadata(
    model_version_metadata: dict[str, Any],
    evaluation_report: dict[str, Any] | None,
    policy: ModelPromotionPolicy,
    model_version_metadata_path: str | Path | None = None,
    created_at_utc: str | None = None,
) -> ModelPromotionReview:
    candidate = build_model_promotion_candidate(
        model_version_metadata=model_version_metadata,
        evaluation_report=evaluation_report,
        model_version_metadata_path=model_version_metadata_path,
    )

    return build_model_promotion_review(
        candidate=candidate,
        policy=policy,
        evaluation_report=evaluation_report,
        created_at_utc=created_at_utc,
    )


def read_model_promotion_json(path: str | Path) -> dict[str, Any]:
    input_path = Path(path)

    if not input_path.exists():
        raise FileNotFoundError(f"Model promotion input does not exist: {input_path}")

    return json.loads(input_path.read_text(encoding="utf-8"))


def write_model_promotion_review(
    path: str | Path,
    review: ModelPromotionReview,
) -> Path:
    output_path = Path(path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(review.to_dict(), indent=2, sort_keys=True),
        encoding="utf-8",
    )
    return output_path


def read_model_promotion_review(path: str | Path) -> dict[str, Any]:
    return read_model_promotion_json(path)


__all__ = [
    "MODEL_PROMOTION_VERSION",
    "PROMOTION_STAGE_ORDER",
    "ModelPromotionCandidate",
    "ModelPromotionIssue",
    "ModelPromotionPolicy",
    "ModelPromotionReview",
    "ModelPromotionRule",
    "ModelPromotionSeverity",
    "ModelPromotionStatus",
    "build_model_promotion_candidate",
    "build_model_promotion_issue",
    "build_model_promotion_review",
    "build_model_promotion_review_from_metadata",
    "build_model_promotion_status",
    "is_target_stage_allowed",
    "model_promotion_utc_now_iso",
    "parse_model_promotion_stage",
    "promotion_stage_rank",
    "read_model_promotion_json",
    "read_model_promotion_review",
    "validate_model_promotion_candidate",
    "write_model_promotion_review",
]