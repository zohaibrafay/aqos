from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from aqos.model_training.model_evaluation import ModelPromotionStage
from aqos.model_training.model_promotion import (
    ModelPromotionPolicy,
    ModelPromotionReview,
    build_model_promotion_review_from_metadata,
    read_model_promotion_json,
    write_model_promotion_review,
)
from aqos.model_training.model_promotion_registry import (
    ModelPromotionRegistry,
    ModelPromotionRegistryEntry,
    append_model_promotion_to_registry,
    build_model_promotion_registry_entry,
)


@dataclass(frozen=True)
class ModelPromotionRunConfig:
    model_version_metadata_path: Path
    target_stage: ModelPromotionStage
    output_dir: Path | None = None
    evaluation_report_path: Path | None = None
    current_stage: ModelPromotionStage = ModelPromotionStage.RESEARCH
    require_evaluation_report: bool = True
    require_model_promotion_ready: bool = True
    allow_warning_evaluation: bool = True
    allow_same_stage: bool = True
    forward_only: bool = True
    fail_on_rejected: bool = False
    promotion_review_filename: str = "model_promotion_review.json"
    promotion_registry_filename: str = "model_promotion_registry.json"
    notes: str | None = None
    tags: tuple[str, ...] = ("aqos", "model-promotion")

    def __post_init__(self) -> None:
        if self.target_stage == ModelPromotionStage.BLOCKED:
            raise ValueError("target_stage cannot be blocked.")

        if not self.promotion_review_filename.strip():
            raise ValueError("promotion_review_filename cannot be empty.")

        if not self.promotion_registry_filename.strip():
            raise ValueError("promotion_registry_filename cannot be empty.")


@dataclass(frozen=True)
class ModelPromotionRunOutput:
    promotion_review_path: Path
    promotion_registry_path: Path
    review: ModelPromotionReview
    registry_entry: ModelPromotionRegistryEntry
    registry: ModelPromotionRegistry

    def to_dict(self) -> dict[str, Any]:
        return {
            "promotion_review_path": self.promotion_review_path.as_posix(),
            "promotion_registry_path": self.promotion_registry_path.as_posix(),
            "review": self.review.to_dict(),
            "registry_entry": self.registry_entry.to_dict(),
            "registry": self.registry.to_dict(),
        }


def resolve_model_promotion_output_dir(
    run_config: ModelPromotionRunConfig,
) -> Path:
    if run_config.output_dir is not None:
        return Path(run_config.output_dir)

    return Path(run_config.model_version_metadata_path).parent


def resolve_model_promotion_registry_path(
    run_config: ModelPromotionRunConfig,
    output_dir: Path,
) -> Path:
    return output_dir / run_config.promotion_registry_filename


def resolve_model_promotion_review_path(
    run_config: ModelPromotionRunConfig,
    output_dir: Path,
) -> Path:
    return output_dir / run_config.promotion_review_filename


def resolve_metadata_relative_path(
    value: str | Path | None,
    metadata_path: Path,
) -> Path | None:
    if value is None:
        return None

    resolved_path = Path(value)

    if resolved_path.is_absolute():
        return resolved_path

    candidate = metadata_path.parent / resolved_path

    if candidate.exists():
        return candidate

    return resolved_path


def resolve_model_evaluation_report_path(
    run_config: ModelPromotionRunConfig,
    model_version_metadata: dict[str, Any],
) -> Path | None:
    if run_config.evaluation_report_path is not None:
        return Path(run_config.evaluation_report_path)

    metadata_value = model_version_metadata.get("model_evaluation_report_path")

    if metadata_value is None:
        return None

    return resolve_metadata_relative_path(
        value=str(metadata_value),
        metadata_path=Path(run_config.model_version_metadata_path),
    )


def build_model_promotion_policy(
    run_config: ModelPromotionRunConfig,
) -> ModelPromotionPolicy:
    return ModelPromotionPolicy(
        target_stage=run_config.target_stage,
        current_stage=run_config.current_stage,
        require_evaluation_report=run_config.require_evaluation_report,
        require_model_promotion_ready=run_config.require_model_promotion_ready,
        allow_warning_evaluation=run_config.allow_warning_evaluation,
        allow_same_stage=run_config.allow_same_stage,
        forward_only=run_config.forward_only,
    )


def load_model_promotion_inputs(
    run_config: ModelPromotionRunConfig,
) -> tuple[dict[str, Any], dict[str, Any] | None, Path | None]:
    model_version_metadata_path = Path(run_config.model_version_metadata_path)
    model_version_metadata = read_model_promotion_json(model_version_metadata_path)

    evaluation_report_path = resolve_model_evaluation_report_path(
        run_config=run_config,
        model_version_metadata=model_version_metadata,
    )

    evaluation_report = None

    if evaluation_report_path is not None:
        evaluation_report = read_model_promotion_json(evaluation_report_path)

    return model_version_metadata, evaluation_report, evaluation_report_path


def promote_model_from_metadata(
    run_config: ModelPromotionRunConfig,
) -> ModelPromotionRunOutput:
    output_dir = resolve_model_promotion_output_dir(run_config)
    output_dir.mkdir(parents=True, exist_ok=True)

    model_version_metadata, evaluation_report, _ = load_model_promotion_inputs(
        run_config
    )

    policy = build_model_promotion_policy(run_config)

    review = build_model_promotion_review_from_metadata(
        model_version_metadata=model_version_metadata,
        evaluation_report=evaluation_report,
        policy=policy,
        model_version_metadata_path=run_config.model_version_metadata_path,
    )

    promotion_review_path = resolve_model_promotion_review_path(
        run_config=run_config,
        output_dir=output_dir,
    )

    write_model_promotion_review(promotion_review_path, review)

    registry_entry = build_model_promotion_registry_entry(
        review=review,
        model_promotion_review_path=promotion_review_path,
        notes=run_config.notes,
        tags=run_config.tags,
    )

    promotion_registry_path = resolve_model_promotion_registry_path(
        run_config=run_config,
        output_dir=output_dir,
    )

    registry = append_model_promotion_to_registry(
        path=promotion_registry_path,
        entry=registry_entry,
    )

    if run_config.fail_on_rejected:
        review.raise_if_rejected()

    return ModelPromotionRunOutput(
        promotion_review_path=promotion_review_path,
        promotion_registry_path=promotion_registry_path,
        review=review,
        registry_entry=registry_entry,
        registry=registry,
    )


__all__ = [
    "ModelPromotionRunConfig",
    "ModelPromotionRunOutput",
    "build_model_promotion_policy",
    "load_model_promotion_inputs",
    "promote_model_from_metadata",
    "resolve_metadata_relative_path",
    "resolve_model_evaluation_report_path",
    "resolve_model_promotion_output_dir",
    "resolve_model_promotion_registry_path",
    "resolve_model_promotion_review_path",
]