from __future__ import annotations

import json
from dataclasses import dataclass, field as dataclass_field
from datetime import UTC, datetime
from enum import Enum
from pathlib import Path
from typing import Any


MODEL_EVALUATION_VERSION = "1.0"


class ModelEvaluationSeverity(str, Enum):
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"


class ModelEvaluationStatus(str, Enum):
    PASSED = "passed"
    PASSED_WITH_WARNINGS = "passed_with_warnings"
    FAILED = "failed"


class ModelPromotionStage(str, Enum):
    RESEARCH = "research"
    PAPER_TRADING = "paper_trading"
    LIMITED_LIVE = "limited_live"
    LIVE = "live"
    BLOCKED = "blocked"


class ModelEvaluationRule(str, Enum):
    METRIC_PRESENT = "metric_present"
    MIN_ACCURACY = "min_accuracy"
    MIN_MACRO_F1 = "min_macro_f1"
    MAX_LOG_LOSS = "max_log_loss"
    MIN_TEST_SAMPLES = "min_test_samples"
    REQUIRED_CLASSES_PRESENT = "required_classes_present"
    PROMOTION_STAGE_ALLOWED = "promotion_stage_allowed"


@dataclass(frozen=True)
class ModelEvaluationThresholds:
    min_accuracy: float = 0.45
    min_macro_f1: float | None = None
    max_log_loss: float | None = None
    min_test_samples: int = 20
    required_classes: tuple[str, ...] = ()
    allowed_promotion_stage: ModelPromotionStage = ModelPromotionStage.RESEARCH

    def __post_init__(self) -> None:
        if not 0.0 <= self.min_accuracy <= 1.0:
            raise ValueError("min_accuracy must be between 0 and 1.")

        if self.min_macro_f1 is not None and not 0.0 <= self.min_macro_f1 <= 1.0:
            raise ValueError("min_macro_f1 must be between 0 and 1.")

        if self.max_log_loss is not None and self.max_log_loss < 0.0:
            raise ValueError("max_log_loss cannot be negative.")

        if self.min_test_samples < 0:
            raise ValueError("min_test_samples cannot be negative.")

    def to_dict(self) -> dict[str, Any]:
        return {
            "min_accuracy": self.min_accuracy,
            "min_macro_f1": self.min_macro_f1,
            "max_log_loss": self.max_log_loss,
            "min_test_samples": self.min_test_samples,
            "required_classes": list(self.required_classes),
            "allowed_promotion_stage": self.allowed_promotion_stage.value,
        }


@dataclass(frozen=True)
class ModelEvaluationIssue:
    rule: ModelEvaluationRule
    severity: ModelEvaluationSeverity
    message: str
    metric_name: str | None = None
    details: dict[str, Any] = dataclass_field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.message.strip():
            raise ValueError("Model evaluation issue message cannot be empty.")

    def to_dict(self) -> dict[str, Any]:
        return {
            "rule": self.rule.value,
            "severity": self.severity.value,
            "message": self.message,
            "metric_name": self.metric_name,
            "details": self.details,
        }


@dataclass(frozen=True)
class ModelEvaluationReport:
    model_name: str
    created_at_utc: str
    metrics: dict[str, Any]
    thresholds: ModelEvaluationThresholds
    status: ModelEvaluationStatus
    promotion_stage: ModelPromotionStage
    is_promotion_ready: bool
    issues: tuple[ModelEvaluationIssue, ...] = ()
    model_id: str | None = None
    model_version: str | None = None
    dataset_id: str | None = None
    dataset_version: str | None = None
    experiment_run_id: str | None = None
    notes: str | None = None
    metadata_version: str = MODEL_EVALUATION_VERSION

    def __post_init__(self) -> None:
        if not self.model_name.strip():
            raise ValueError("model_name cannot be empty.")

        if not self.created_at_utc.strip():
            raise ValueError("created_at_utc cannot be empty.")

    @property
    def error_count(self) -> int:
        return sum(
            1
            for issue in self.issues
            if issue.severity == ModelEvaluationSeverity.ERROR
        )

    @property
    def warning_count(self) -> int:
        return sum(
            1
            for issue in self.issues
            if issue.severity == ModelEvaluationSeverity.WARNING
        )

    @property
    def info_count(self) -> int:
        return sum(
            1
            for issue in self.issues
            if issue.severity == ModelEvaluationSeverity.INFO
        )

    @property
    def is_valid(self) -> bool:
        return self.status != ModelEvaluationStatus.FAILED

    def raise_if_invalid(self) -> None:
        if self.is_valid:
            return

        messages = [
            issue.message
            for issue in self.issues
            if issue.severity == ModelEvaluationSeverity.ERROR
        ]

        raise ValueError("Model evaluation failed: " + "; ".join(messages))

    def to_dict(self) -> dict[str, Any]:
        return {
            "metadata_version": self.metadata_version,
            "model_name": self.model_name,
            "model_id": self.model_id,
            "model_version": self.model_version,
            "dataset_id": self.dataset_id,
            "dataset_version": self.dataset_version,
            "experiment_run_id": self.experiment_run_id,
            "created_at_utc": self.created_at_utc,
            "status": self.status.value,
            "is_valid": self.is_valid,
            "promotion_stage": self.promotion_stage.value,
            "is_promotion_ready": self.is_promotion_ready,
            "metrics": self.metrics,
            "thresholds": self.thresholds.to_dict(),
            "error_count": self.error_count,
            "warning_count": self.warning_count,
            "info_count": self.info_count,
            "issues": [issue.to_dict() for issue in self.issues],
            "notes": self.notes,
        }


def model_evaluation_utc_now_iso() -> str:
    return datetime.now(tz=UTC).replace(microsecond=0).isoformat()


def build_model_evaluation_issue(
    rule: ModelEvaluationRule,
    severity: ModelEvaluationSeverity,
    message: str,
    metric_name: str | None = None,
    details: dict[str, Any] | None = None,
) -> ModelEvaluationIssue:
    return ModelEvaluationIssue(
        rule=rule,
        severity=severity,
        message=message,
        metric_name=metric_name,
        details=details or {},
    )


def build_model_evaluation_status(
    issues: tuple[ModelEvaluationIssue, ...],
) -> ModelEvaluationStatus:
    if any(issue.severity == ModelEvaluationSeverity.ERROR for issue in issues):
        return ModelEvaluationStatus.FAILED

    if any(issue.severity == ModelEvaluationSeverity.WARNING for issue in issues):
        return ModelEvaluationStatus.PASSED_WITH_WARNINGS

    return ModelEvaluationStatus.PASSED


def get_numeric_metric(
    metrics: dict[str, Any],
    *metric_names: str,
) -> float | None:
    for metric_name in metric_names:
        if metric_name not in metrics:
            continue

        value = metrics[metric_name]

        if value is None:
            continue

        try:
            return float(value)
        except (TypeError, ValueError):
            return None

    return None


def get_sequence_metric(
    metrics: dict[str, Any],
    *metric_names: str,
) -> tuple[str, ...]:
    for metric_name in metric_names:
        if metric_name not in metrics:
            continue

        value = metrics[metric_name]

        if value is None:
            continue

        if isinstance(value, (list, tuple, set)):
            return tuple(str(item) for item in value)

    return ()


def validate_required_metric_present(
    metrics: dict[str, Any],
    metric_name: str,
) -> tuple[ModelEvaluationIssue, ...]:
    if metric_name in metrics and metrics[metric_name] is not None:
        return ()

    return (
        build_model_evaluation_issue(
            rule=ModelEvaluationRule.METRIC_PRESENT,
            severity=ModelEvaluationSeverity.ERROR,
            message=f"Required evaluation metric is missing: {metric_name}",
            metric_name=metric_name,
        ),
    )


def validate_model_evaluation_thresholds(
    metrics: dict[str, Any],
    thresholds: ModelEvaluationThresholds,
) -> tuple[ModelEvaluationIssue, ...]:
    issues: list[ModelEvaluationIssue] = []

    accuracy = get_numeric_metric(metrics, "accuracy", "test_accuracy")

    if accuracy is None:
        issues.extend(validate_required_metric_present(metrics, "accuracy"))
    elif accuracy < thresholds.min_accuracy:
        issues.append(
            build_model_evaluation_issue(
                rule=ModelEvaluationRule.MIN_ACCURACY,
                severity=ModelEvaluationSeverity.ERROR,
                message="Model accuracy is below the minimum required threshold.",
                metric_name="accuracy",
                details={
                    "actual": accuracy,
                    "minimum": thresholds.min_accuracy,
                },
            )
        )

    if thresholds.min_macro_f1 is not None:
        macro_f1 = get_numeric_metric(metrics, "macro_f1", "f1_macro", "test_macro_f1")

        if macro_f1 is None:
            issues.extend(validate_required_metric_present(metrics, "macro_f1"))
        elif macro_f1 < thresholds.min_macro_f1:
            issues.append(
                build_model_evaluation_issue(
                    rule=ModelEvaluationRule.MIN_MACRO_F1,
                    severity=ModelEvaluationSeverity.ERROR,
                    message="Model macro F1 is below the minimum required threshold.",
                    metric_name="macro_f1",
                    details={
                        "actual": macro_f1,
                        "minimum": thresholds.min_macro_f1,
                    },
                )
            )

    if thresholds.max_log_loss is not None:
        log_loss = get_numeric_metric(metrics, "log_loss", "test_log_loss")

        if log_loss is None:
            issues.extend(validate_required_metric_present(metrics, "log_loss"))
        elif log_loss > thresholds.max_log_loss:
            issues.append(
                build_model_evaluation_issue(
                    rule=ModelEvaluationRule.MAX_LOG_LOSS,
                    severity=ModelEvaluationSeverity.ERROR,
                    message="Model log loss is above the maximum allowed threshold.",
                    metric_name="log_loss",
                    details={
                        "actual": log_loss,
                        "maximum": thresholds.max_log_loss,
                    },
                )
            )

    test_samples = get_numeric_metric(
        metrics,
        "test_samples",
        "n_test_samples",
        "test_row_count",
    )

    if test_samples is not None and int(test_samples) < thresholds.min_test_samples:
        issues.append(
            build_model_evaluation_issue(
                rule=ModelEvaluationRule.MIN_TEST_SAMPLES,
                severity=ModelEvaluationSeverity.WARNING,
                message="Evaluation test sample count is below the recommended minimum.",
                metric_name="test_samples",
                details={
                    "actual": int(test_samples),
                    "minimum": thresholds.min_test_samples,
                },
            )
        )

    observed_classes = set(
        get_sequence_metric(
            metrics,
            "classes",
            "observed_classes",
            "target_classes",
            "labels",
        )
    )

    if thresholds.required_classes:
        missing_classes = [
            class_name
            for class_name in thresholds.required_classes
            if class_name not in observed_classes
        ]

        if missing_classes:
            issues.append(
                build_model_evaluation_issue(
                    rule=ModelEvaluationRule.REQUIRED_CLASSES_PRESENT,
                    severity=ModelEvaluationSeverity.ERROR,
                    message="Evaluation metrics are missing required target classes.",
                    metric_name="classes",
                    details={
                        "missing_classes": missing_classes,
                        "required_classes": list(thresholds.required_classes),
                        "observed_classes": sorted(observed_classes),
                    },
                )
            )

    return tuple(issues)


def resolve_promotion_stage(
    status: ModelEvaluationStatus,
    thresholds: ModelEvaluationThresholds,
) -> ModelPromotionStage:
    if status == ModelEvaluationStatus.FAILED:
        return ModelPromotionStage.BLOCKED

    return thresholds.allowed_promotion_stage


def build_model_evaluation_report(
    model_name: str,
    metrics: dict[str, Any],
    thresholds: ModelEvaluationThresholds | None = None,
    model_id: str | None = None,
    model_version: str | None = None,
    dataset_id: str | None = None,
    dataset_version: str | None = None,
    experiment_run_id: str | None = None,
    notes: str | None = None,
    created_at_utc: str | None = None,
) -> ModelEvaluationReport:
    evaluation_thresholds = thresholds or ModelEvaluationThresholds()
    issues = validate_model_evaluation_thresholds(metrics, evaluation_thresholds)
    status = build_model_evaluation_status(issues)
    promotion_stage = resolve_promotion_stage(status, evaluation_thresholds)

    return ModelEvaluationReport(
        model_name=model_name,
        model_id=model_id,
        model_version=model_version,
        dataset_id=dataset_id,
        dataset_version=dataset_version,
        experiment_run_id=experiment_run_id,
        created_at_utc=created_at_utc or model_evaluation_utc_now_iso(),
        metrics=metrics,
        thresholds=evaluation_thresholds,
        status=status,
        promotion_stage=promotion_stage,
        is_promotion_ready=promotion_stage != ModelPromotionStage.BLOCKED,
        issues=issues,
        notes=notes,
    )


def write_model_evaluation_report(
    path: str | Path,
    report: ModelEvaluationReport,
) -> Path:
    output_path = Path(path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    output_path.write_text(
        json.dumps(report.to_dict(), indent=2, sort_keys=True),
        encoding="utf-8",
    )

    return output_path


def read_model_evaluation_report(path: str | Path) -> dict[str, Any]:
    report_path = Path(path)

    if not report_path.exists():
        raise FileNotFoundError(
            f"Model evaluation report does not exist: {report_path}"
        )

    return json.loads(report_path.read_text(encoding="utf-8"))


__all__ = [
    "MODEL_EVALUATION_VERSION",
    "ModelEvaluationIssue",
    "ModelEvaluationReport",
    "ModelEvaluationRule",
    "ModelEvaluationSeverity",
    "ModelEvaluationStatus",
    "ModelEvaluationThresholds",
    "ModelPromotionStage",
    "build_model_evaluation_issue",
    "build_model_evaluation_report",
    "build_model_evaluation_status",
    "get_numeric_metric",
    "get_sequence_metric",
    "model_evaluation_utc_now_iso",
    "read_model_evaluation_report",
    "resolve_promotion_stage",
    "validate_model_evaluation_thresholds",
    "validate_required_metric_present",
    "write_model_evaluation_report",
]