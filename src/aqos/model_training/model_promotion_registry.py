from __future__ import annotations

import json
import re
from dataclasses import dataclass, field as dataclass_field
from pathlib import Path
from typing import Any

from aqos.model_training.dataset_versioning import sha256_text
from aqos.model_training.model_evaluation import ModelPromotionStage
from aqos.model_training.model_promotion import (
    ModelPromotionReview,
    ModelPromotionStatus,
)


MODEL_PROMOTION_REGISTRY_VERSION = "1.0"


@dataclass(frozen=True)
class ModelPromotionRegistryEntry:
    promotion_id: str
    created_at_utc: str
    model_name: str
    model_id: str | None
    model_version: str | None
    target_stage: ModelPromotionStage
    status: ModelPromotionStatus
    approved: bool
    model_artifact_path: str | None = None
    model_version_metadata_path: str | None = None
    model_evaluation_report_path: str | None = None
    model_promotion_review_path: str | None = None
    dataset_id: str | None = None
    dataset_version: str | None = None
    experiment_run_id: str | None = None
    notes: str | None = None
    tags: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if not self.promotion_id.strip():
            raise ValueError("promotion_id cannot be empty.")

        if not self.created_at_utc.strip():
            raise ValueError("created_at_utc cannot be empty.")

        if not self.model_name.strip():
            raise ValueError("model_name cannot be empty.")

        if self.target_stage == ModelPromotionStage.BLOCKED:
            raise ValueError("target_stage cannot be blocked in promotion registry.")

    def to_dict(self) -> dict[str, Any]:
        return {
            "promotion_id": self.promotion_id,
            "created_at_utc": self.created_at_utc,
            "model_name": self.model_name,
            "model_id": self.model_id,
            "model_version": self.model_version,
            "target_stage": self.target_stage.value,
            "status": self.status.value,
            "approved": self.approved,
            "model_artifact_path": self.model_artifact_path,
            "model_version_metadata_path": self.model_version_metadata_path,
            "model_evaluation_report_path": self.model_evaluation_report_path,
            "model_promotion_review_path": self.model_promotion_review_path,
            "dataset_id": self.dataset_id,
            "dataset_version": self.dataset_version,
            "experiment_run_id": self.experiment_run_id,
            "notes": self.notes,
            "tags": list(self.tags),
        }


@dataclass(frozen=True)
class ModelPromotionRegistry:
    promotions: tuple[ModelPromotionRegistryEntry, ...] = ()
    registry_version: str = MODEL_PROMOTION_REGISTRY_VERSION

    def to_dict(self) -> dict[str, Any]:
        return {
            "registry_version": self.registry_version,
            "promotions": [promotion.to_dict() for promotion in self.promotions],
        }


def normalize_promotion_name(value: str) -> str:
    normalized = re.sub(r"[^a-zA-Z0-9]+", "_", value.strip().lower())
    normalized = re.sub(r"_+", "_", normalized).strip("_")
    return normalized or "model"


def build_model_promotion_id(
    model_name: str,
    model_version: str | None,
    target_stage: ModelPromotionStage,
    created_at_utc: str,
) -> str:
    name = normalize_promotion_name(model_name)
    timestamp = (
        created_at_utc.replace("-", "")
        .replace(":", "")
        .replace("+00:00", "Z")
        .replace(".", "")
    )
    short_hash = sha256_text(
        "|".join(
            [
                model_name,
                model_version or "",
                target_stage.value,
                created_at_utc,
            ]
        )
    )[:12]

    return f"{name}_{target_stage.value}_{timestamp}_{short_hash}"


def build_model_promotion_registry_entry(
    review: ModelPromotionReview,
    model_promotion_review_path: str | Path | None = None,
    notes: str | None = None,
    tags: tuple[str, ...] = (),
) -> ModelPromotionRegistryEntry:
    candidate = review.candidate

    return ModelPromotionRegistryEntry(
        promotion_id=build_model_promotion_id(
            model_name=candidate.model_name,
            model_version=candidate.model_version,
            target_stage=review.target_stage,
            created_at_utc=review.created_at_utc,
        ),
        created_at_utc=review.created_at_utc,
        model_name=candidate.model_name,
        model_id=candidate.model_id,
        model_version=candidate.model_version,
        target_stage=review.target_stage,
        status=review.status,
        approved=review.approved,
        model_artifact_path=candidate.model_artifact_path,
        model_version_metadata_path=candidate.model_version_metadata_path,
        model_evaluation_report_path=candidate.model_evaluation_report_path,
        model_promotion_review_path=(
            Path(model_promotion_review_path).as_posix()
            if model_promotion_review_path is not None
            else None
        ),
        dataset_id=candidate.dataset_id,
        dataset_version=candidate.dataset_version,
        experiment_run_id=candidate.experiment_run_id,
        notes=notes,
        tags=tags,
    )


def parse_model_promotion_registry_entry(
    payload: dict[str, Any],
) -> ModelPromotionRegistryEntry:
    return ModelPromotionRegistryEntry(
        promotion_id=str(payload["promotion_id"]),
        created_at_utc=str(payload["created_at_utc"]),
        model_name=str(payload["model_name"]),
        model_id=payload.get("model_id"),
        model_version=payload.get("model_version"),
        target_stage=ModelPromotionStage(str(payload["target_stage"])),
        status=ModelPromotionStatus(str(payload["status"])),
        approved=bool(payload["approved"]),
        model_artifact_path=payload.get("model_artifact_path"),
        model_version_metadata_path=payload.get("model_version_metadata_path"),
        model_evaluation_report_path=payload.get("model_evaluation_report_path"),
        model_promotion_review_path=payload.get("model_promotion_review_path"),
        dataset_id=payload.get("dataset_id"),
        dataset_version=payload.get("dataset_version"),
        experiment_run_id=payload.get("experiment_run_id"),
        notes=payload.get("notes"),
        tags=tuple(str(tag) for tag in payload.get("tags", ())),
    )


def read_model_promotion_registry(path: str | Path) -> ModelPromotionRegistry:
    registry_path = Path(path)

    if not registry_path.exists():
        return ModelPromotionRegistry()

    payload = json.loads(registry_path.read_text(encoding="utf-8"))

    promotions = tuple(
        parse_model_promotion_registry_entry(item)
        for item in payload.get("promotions", ())
    )

    return ModelPromotionRegistry(
        promotions=promotions,
        registry_version=str(
            payload.get("registry_version", MODEL_PROMOTION_REGISTRY_VERSION)
        ),
    )


def write_model_promotion_registry(
    path: str | Path,
    registry: ModelPromotionRegistry,
) -> Path:
    output_path = Path(path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(registry.to_dict(), indent=2, sort_keys=True),
        encoding="utf-8",
    )
    return output_path


def append_model_promotion_to_registry(
    path: str | Path,
    entry: ModelPromotionRegistryEntry,
) -> ModelPromotionRegistry:
    registry = read_model_promotion_registry(path)

    existing = {
        promotion.promotion_id: promotion
        for promotion in registry.promotions
    }
    existing[entry.promotion_id] = entry

    updated_promotions = tuple(
        sorted(
            existing.values(),
            key=lambda promotion: promotion.created_at_utc,
        )
    )

    updated_registry = ModelPromotionRegistry(promotions=updated_promotions)
    write_model_promotion_registry(path, updated_registry)

    return updated_registry


def list_model_promotions(
    registry: ModelPromotionRegistry,
    model_name: str | None = None,
    target_stage: ModelPromotionStage | None = None,
    approved_only: bool = False,
) -> tuple[ModelPromotionRegistryEntry, ...]:
    promotions = registry.promotions

    if model_name is not None:
        promotions = tuple(
            promotion
            for promotion in promotions
            if promotion.model_name == model_name
        )

    if target_stage is not None:
        promotions = tuple(
            promotion
            for promotion in promotions
            if promotion.target_stage == target_stage
        )

    if approved_only:
        promotions = tuple(
            promotion
            for promotion in promotions
            if promotion.approved
        )

    return promotions


def find_latest_model_promotion(
    registry: ModelPromotionRegistry,
    model_name: str | None = None,
    target_stage: ModelPromotionStage | None = None,
    approved_only: bool = True,
) -> ModelPromotionRegistryEntry | None:
    promotions = list_model_promotions(
        registry=registry,
        model_name=model_name,
        target_stage=target_stage,
        approved_only=approved_only,
    )

    if not promotions:
        return None

    return max(promotions, key=lambda promotion: promotion.created_at_utc)


def find_latest_approved_model_for_stage(
    registry: ModelPromotionRegistry,
    target_stage: ModelPromotionStage,
    model_name: str | None = None,
) -> ModelPromotionRegistryEntry | None:
    return find_latest_model_promotion(
        registry=registry,
        model_name=model_name,
        target_stage=target_stage,
        approved_only=True,
    )


__all__ = [
    "MODEL_PROMOTION_REGISTRY_VERSION",
    "ModelPromotionRegistry",
    "ModelPromotionRegistryEntry",
    "append_model_promotion_to_registry",
    "build_model_promotion_id",
    "build_model_promotion_registry_entry",
    "find_latest_approved_model_for_stage",
    "find_latest_model_promotion",
    "list_model_promotions",
    "normalize_promotion_name",
    "parse_model_promotion_registry_entry",
    "read_model_promotion_registry",
    "write_model_promotion_registry",
]