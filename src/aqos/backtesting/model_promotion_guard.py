from __future__ import annotations

from dataclasses import dataclass, field as dataclass_field
from enum import Enum
from pathlib import Path
from typing import Any

from aqos.model_training.model_evaluation import ModelPromotionStage
from aqos.model_training.model_promotion_gate import (
    ModelPromotionGateDecision,
    extract_model_identity_from_metadata,
    validate_model_files_against_promotion_registry,
)
from aqos.model_training.model_versioning import read_model_version_metadata


BACKTEST_MODEL_PROMOTION_GUARD_VERSION = "1.0"


class BacktestModelGateStatus(str, Enum):
    APPROVED = "approved"
    REJECTED = "rejected"
    OVERRIDDEN = "overridden"
    SKIPPED = "skipped"


@dataclass(frozen=True)
class BacktestModelGateConfig:
    """
    Promotion gate configuration for model-driven backtests.

    An unpromoted model can only be executed when the caller explicitly opts in,
    either by allowing overrides (``allow_unpromoted_model``) or by disabling the
    gate entirely (which itself requires ``allow_unpromoted_model``).
    """

    model_version_metadata_path: str | Path | None = None
    promotion_registry_path: str | Path | None = None
    required_stage: ModelPromotionStage = ModelPromotionStage.RESEARCH
    enabled: bool = True
    allow_unpromoted_model: bool = False
    metadata: dict[str, Any] = dataclass_field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.enabled and not self.allow_unpromoted_model:
            raise ValueError(
                "allow_unpromoted_model must be enabled to disable the backtest "
                "model promotion gate."
            )

        if self.enabled and self.model_version_metadata_path is None:
            raise ValueError(
                "model_version_metadata_path is required when the backtest model "
                "promotion gate is enabled."
            )

        if self.enabled and self.promotion_registry_path is None:
            raise ValueError(
                "promotion_registry_path is required when the backtest model "
                "promotion gate is enabled."
            )

    def to_dict(self) -> dict[str, Any]:
        return {
            "model_version_metadata_path": (
                Path(self.model_version_metadata_path).as_posix()
                if self.model_version_metadata_path is not None
                else None
            ),
            "promotion_registry_path": (
                Path(self.promotion_registry_path).as_posix()
                if self.promotion_registry_path is not None
                else None
            ),
            "required_stage": self.required_stage.value,
            "enabled": self.enabled,
            "allow_unpromoted_model": self.allow_unpromoted_model,
            "metadata": self.metadata,
        }


@dataclass(frozen=True)
class BacktestModelGateDecision:
    status: BacktestModelGateStatus
    allowed: bool
    required_stage: ModelPromotionStage
    model_name: str | None = None
    model_id: str | None = None
    model_version: str | None = None
    promotion_stage: str | None = None
    override_applied: bool = False
    reasons: tuple[str, ...] = ()
    promotion_gate_decision: ModelPromotionGateDecision | None = None

    @property
    def approved(self) -> bool:
        return self.status == BacktestModelGateStatus.APPROVED

    @property
    def blocked(self) -> bool:
        return not self.allowed

    def raise_if_blocked(self) -> None:
        if self.allowed:
            return

        raise ValueError(
            "Backtest model promotion gate rejected the model: "
            + "; ".join(self.reasons)
        )

    def model_identity(self) -> dict[str, Any]:
        return {
            "model_name": self.model_name,
            "model_id": self.model_id,
            "model_version": self.model_version,
            "promotion_stage": self.promotion_stage,
            "required_stage": self.required_stage.value,
            "gate_status": self.status.value,
        }

    def to_dict(self) -> dict[str, Any]:
        return {
            "status": self.status.value,
            "allowed": self.allowed,
            "approved": self.approved,
            "required_stage": self.required_stage.value,
            "model_name": self.model_name,
            "model_id": self.model_id,
            "model_version": self.model_version,
            "promotion_stage": self.promotion_stage,
            "override_applied": self.override_applied,
            "reasons": list(self.reasons),
            "promotion_gate_decision": (
                self.promotion_gate_decision.to_dict()
                if self.promotion_gate_decision is not None
                else None
            ),
        }


def read_backtest_model_identity(
    model_version_metadata_path: str | Path | None,
) -> tuple[str | None, str | None, str | None, str | None]:
    """
    Return ``(model_name, model_id, model_version, promotion_stage)`` for a model
    version metadata file, tolerating a missing or unset path.
    """

    if model_version_metadata_path is None:
        return None, None, None, None

    metadata_path = Path(model_version_metadata_path)

    if not metadata_path.exists():
        return None, None, None, None

    metadata = read_model_version_metadata(metadata_path)
    model_name, model_id, model_version, _ = extract_model_identity_from_metadata(
        metadata
    )
    promotion_stage = metadata.get("promotion_stage")

    return (
        model_name,
        model_id,
        model_version,
        str(promotion_stage) if promotion_stage is not None else None,
    )


def collect_promotion_gate_error_messages(
    decision: ModelPromotionGateDecision,
) -> tuple[str, ...]:
    return tuple(
        issue.message
        for issue in decision.issues
        if issue.severity.value == "error"
    )


def build_skipped_backtest_model_gate_decision(
    config: BacktestModelGateConfig,
) -> BacktestModelGateDecision:
    model_name, model_id, model_version, promotion_stage = (
        read_backtest_model_identity(config.model_version_metadata_path)
    )

    return BacktestModelGateDecision(
        status=BacktestModelGateStatus.SKIPPED,
        allowed=True,
        required_stage=config.required_stage,
        model_name=model_name,
        model_id=model_id,
        model_version=model_version,
        promotion_stage=promotion_stage,
        override_applied=True,
        reasons=(
            "Backtest model promotion gate is disabled by explicit configuration.",
        ),
    )


def evaluate_backtest_model_gate(
    config: BacktestModelGateConfig,
) -> BacktestModelGateDecision:
    if not config.enabled:
        return build_skipped_backtest_model_gate_decision(config)

    assert config.model_version_metadata_path is not None
    assert config.promotion_registry_path is not None

    promotion_decision = validate_model_files_against_promotion_registry(
        model_version_metadata_path=config.model_version_metadata_path,
        promotion_registry_path=config.promotion_registry_path,
        required_stage=config.required_stage,
    )

    _, _, _, promotion_stage = read_backtest_model_identity(
        config.model_version_metadata_path
    )

    if promotion_decision.approved_promotion is not None:
        promotion_stage = promotion_decision.approved_promotion.target_stage.value

    if promotion_decision.is_approved:
        return BacktestModelGateDecision(
            status=BacktestModelGateStatus.APPROVED,
            allowed=True,
            required_stage=config.required_stage,
            model_name=promotion_decision.model_name,
            model_id=promotion_decision.model_id,
            model_version=promotion_decision.model_version,
            promotion_stage=promotion_stage,
            override_applied=False,
            reasons=(),
            promotion_gate_decision=promotion_decision,
        )

    reasons = collect_promotion_gate_error_messages(promotion_decision)

    if config.allow_unpromoted_model:
        return BacktestModelGateDecision(
            status=BacktestModelGateStatus.OVERRIDDEN,
            allowed=True,
            required_stage=config.required_stage,
            model_name=promotion_decision.model_name,
            model_id=promotion_decision.model_id,
            model_version=promotion_decision.model_version,
            promotion_stage=promotion_stage,
            override_applied=True,
            reasons=reasons,
            promotion_gate_decision=promotion_decision,
        )

    return BacktestModelGateDecision(
        status=BacktestModelGateStatus.REJECTED,
        allowed=False,
        required_stage=config.required_stage,
        model_name=promotion_decision.model_name,
        model_id=promotion_decision.model_id,
        model_version=promotion_decision.model_version,
        promotion_stage=promotion_stage,
        override_applied=False,
        reasons=reasons,
        promotion_gate_decision=promotion_decision,
    )


def validate_backtest_model_gate(
    config: BacktestModelGateConfig,
) -> BacktestModelGateDecision:
    decision = evaluate_backtest_model_gate(config)
    decision.raise_if_blocked()
    return decision


__all__ = [
    "BACKTEST_MODEL_PROMOTION_GUARD_VERSION",
    "BacktestModelGateConfig",
    "BacktestModelGateDecision",
    "BacktestModelGateStatus",
    "build_skipped_backtest_model_gate_decision",
    "collect_promotion_gate_error_messages",
    "evaluate_backtest_model_gate",
    "read_backtest_model_identity",
    "validate_backtest_model_gate",
]
