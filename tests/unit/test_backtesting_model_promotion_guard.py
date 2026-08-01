from __future__ import annotations

import pytest

from aqos.backtesting.model_promotion_guard import (
    BACKTEST_MODEL_PROMOTION_GUARD_VERSION,
    BacktestModelGateConfig,
    BacktestModelGateDecision,
    BacktestModelGateStatus,
    build_skipped_backtest_model_gate_decision,
    collect_promotion_gate_error_messages,
    evaluate_backtest_model_gate,
    read_backtest_model_identity,
    validate_backtest_model_gate,
)
from aqos.model_training.model_evaluation import ModelPromotionStage


def test_guard_version_is_exposed() -> None:
    assert BACKTEST_MODEL_PROMOTION_GUARD_VERSION == "1.0"


def test_enabled_gate_requires_metadata_path() -> None:
    with pytest.raises(ValueError, match="model_version_metadata_path is required"):
        BacktestModelGateConfig(promotion_registry_path="registry.json")


def test_enabled_gate_requires_registry_path(tmp_path) -> None:
    with pytest.raises(ValueError, match="promotion_registry_path is required"):
        BacktestModelGateConfig(model_version_metadata_path=tmp_path / "meta.json")


def test_disabled_gate_requires_explicit_override() -> None:
    with pytest.raises(ValueError, match="allow_unpromoted_model must be enabled"):
        BacktestModelGateConfig(enabled=False)


def test_disabled_gate_is_skipped_and_allowed(promoted_backtest_model_files) -> None:
    config = BacktestModelGateConfig(
        model_version_metadata_path=promoted_backtest_model_files["metadata_path"],
        promotion_registry_path=promoted_backtest_model_files["registry_path"],
        enabled=False,
        allow_unpromoted_model=True,
    )

    decision = evaluate_backtest_model_gate(config)

    assert decision.status == BacktestModelGateStatus.SKIPPED
    assert decision.allowed is True
    assert decision.approved is False
    assert decision.override_applied is True
    assert decision.model_id == promoted_backtest_model_files["model_id"]
    assert decision.promotion_stage == ModelPromotionStage.PAPER_TRADING.value


def test_skipped_decision_without_metadata_has_no_identity() -> None:
    config = BacktestModelGateConfig(enabled=False, allow_unpromoted_model=True)

    decision = build_skipped_backtest_model_gate_decision(config)

    assert decision.model_name is None
    assert decision.model_id is None
    assert decision.model_version is None


def test_promoted_model_is_approved(promoted_backtest_model_files) -> None:
    config = BacktestModelGateConfig(
        model_version_metadata_path=promoted_backtest_model_files["metadata_path"],
        promotion_registry_path=promoted_backtest_model_files["registry_path"],
        required_stage=ModelPromotionStage.PAPER_TRADING,
    )

    decision = evaluate_backtest_model_gate(config)

    assert decision.status == BacktestModelGateStatus.APPROVED
    assert decision.allowed is True
    assert decision.approved is True
    assert decision.blocked is False
    assert decision.override_applied is False
    assert decision.reasons == ()
    assert decision.model_name == promoted_backtest_model_files["model_name"]
    assert decision.model_version == promoted_backtest_model_files["model_version"]
    assert decision.promotion_gate_decision is not None


def test_promoted_model_is_rejected_for_higher_stage(
    promoted_backtest_model_files,
) -> None:
    config = BacktestModelGateConfig(
        model_version_metadata_path=promoted_backtest_model_files["metadata_path"],
        promotion_registry_path=promoted_backtest_model_files["registry_path"],
        required_stage=ModelPromotionStage.LIVE,
    )

    decision = evaluate_backtest_model_gate(config)

    assert decision.status == BacktestModelGateStatus.REJECTED
    assert decision.allowed is False
    assert decision.blocked is True
    assert decision.reasons


def test_unpromoted_model_is_rejected(unpromoted_backtest_model_files) -> None:
    config = BacktestModelGateConfig(
        model_version_metadata_path=unpromoted_backtest_model_files["metadata_path"],
        promotion_registry_path=unpromoted_backtest_model_files["registry_path"],
        required_stage=ModelPromotionStage.PAPER_TRADING,
    )

    decision = evaluate_backtest_model_gate(config)

    assert decision.status == BacktestModelGateStatus.REJECTED
    assert decision.allowed is False
    assert any("promotion ready" in reason for reason in decision.reasons)


def test_unpromoted_model_can_be_overridden(unpromoted_backtest_model_files) -> None:
    config = BacktestModelGateConfig(
        model_version_metadata_path=unpromoted_backtest_model_files["metadata_path"],
        promotion_registry_path=unpromoted_backtest_model_files["registry_path"],
        required_stage=ModelPromotionStage.PAPER_TRADING,
        allow_unpromoted_model=True,
    )

    decision = evaluate_backtest_model_gate(config)

    assert decision.status == BacktestModelGateStatus.OVERRIDDEN
    assert decision.allowed is True
    assert decision.approved is False
    assert decision.override_applied is True
    assert decision.reasons


def test_validate_raises_for_rejected_model(unpromoted_backtest_model_files) -> None:
    config = BacktestModelGateConfig(
        model_version_metadata_path=unpromoted_backtest_model_files["metadata_path"],
        promotion_registry_path=unpromoted_backtest_model_files["registry_path"],
        required_stage=ModelPromotionStage.PAPER_TRADING,
    )

    with pytest.raises(ValueError, match="Backtest model promotion gate rejected"):
        validate_backtest_model_gate(config)


def test_validate_returns_decision_for_promoted_model(
    promoted_backtest_model_files,
) -> None:
    config = BacktestModelGateConfig(
        model_version_metadata_path=promoted_backtest_model_files["metadata_path"],
        promotion_registry_path=promoted_backtest_model_files["registry_path"],
        required_stage=ModelPromotionStage.PAPER_TRADING,
    )

    decision = validate_backtest_model_gate(config)

    assert decision.approved is True


def test_missing_metadata_file_is_rejected(tmp_path) -> None:
    config = BacktestModelGateConfig(
        model_version_metadata_path=tmp_path / "missing_metadata.json",
        promotion_registry_path=tmp_path / "missing_registry.json",
    )

    decision = evaluate_backtest_model_gate(config)

    assert decision.allowed is False
    assert any("does not exist" in reason for reason in decision.reasons)


def test_read_model_identity_tolerates_missing_paths(tmp_path) -> None:
    assert read_backtest_model_identity(None) == (None, None, None, None)
    assert read_backtest_model_identity(tmp_path / "nope.json") == (
        None,
        None,
        None,
        None,
    )


def test_collect_error_messages_only_returns_errors(
    unpromoted_backtest_model_files,
) -> None:
    config = BacktestModelGateConfig(
        model_version_metadata_path=unpromoted_backtest_model_files["metadata_path"],
        promotion_registry_path=unpromoted_backtest_model_files["registry_path"],
    )

    decision = evaluate_backtest_model_gate(config)

    assert decision.promotion_gate_decision is not None
    messages = collect_promotion_gate_error_messages(decision.promotion_gate_decision)

    assert len(messages) == decision.promotion_gate_decision.error_count


def test_gate_decision_serialization(promoted_backtest_model_files) -> None:
    config = BacktestModelGateConfig(
        model_version_metadata_path=promoted_backtest_model_files["metadata_path"],
        promotion_registry_path=promoted_backtest_model_files["registry_path"],
        required_stage=ModelPromotionStage.PAPER_TRADING,
    )

    decision = evaluate_backtest_model_gate(config)
    payload = decision.to_dict()

    assert payload["status"] == "approved"
    assert payload["allowed"] is True
    assert payload["required_stage"] == "paper_trading"
    assert payload["model_id"] == promoted_backtest_model_files["model_id"]
    assert payload["reasons"] == []
    assert payload["promotion_gate_decision"]["approved"] is True

    identity = decision.model_identity()

    assert identity["model_version"] == promoted_backtest_model_files["model_version"]
    assert identity["gate_status"] == "approved"


def test_gate_config_serialization(promoted_backtest_model_files) -> None:
    config = BacktestModelGateConfig(
        model_version_metadata_path=promoted_backtest_model_files["metadata_path"],
        promotion_registry_path=promoted_backtest_model_files["registry_path"],
        required_stage=ModelPromotionStage.DEMO,
        metadata={"origin": "unit_test"},
    )

    payload = config.to_dict()

    assert payload["required_stage"] == "demo"
    assert payload["enabled"] is True
    assert payload["allow_unpromoted_model"] is False
    assert payload["metadata"] == {"origin": "unit_test"}
    assert payload["model_version_metadata_path"].endswith(
        "model_version_metadata.json"
    )


def test_raise_if_blocked_is_noop_when_allowed() -> None:
    decision = BacktestModelGateDecision(
        status=BacktestModelGateStatus.APPROVED,
        allowed=True,
        required_stage=ModelPromotionStage.RESEARCH,
    )

    decision.raise_if_blocked()
