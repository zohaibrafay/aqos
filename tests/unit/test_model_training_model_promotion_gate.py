from __future__ import annotations

import json

import pytest

from aqos.model_training import (
    ModelPromotionGateRule,
    ModelPromotionGateSeverity,
    ModelPromotionGateStatus,
    ModelPromotionPolicy,
    ModelPromotionRegistry,
    ModelPromotionStage,
    build_model_promotion_gate_issue,
    build_model_promotion_gate_status,
    build_model_promotion_registry_entry,
    build_model_promotion_review_from_metadata,
    extract_model_identity_from_metadata,
    find_latest_matching_approved_promotion,
    validate_model_against_promotion_registry,
    validate_model_files_against_promotion_registry,
    write_model_promotion_registry,
)


def build_model_version_metadata(
    *,
    model_id: str | None = "model_123",
    model_version: str | None = "model_v1",
    promotion_stage: str = "paper_trading",
    is_promotion_ready: bool | None = True,
) -> dict[str, object]:
    return {
        "model_name": "baseline_random_forest_signal_model",
        "model_id": model_id,
        "model_version": model_version,
        "model_artifact": {
            "path": "baseline_signal_model.joblib",
            "sha256": "abc123",
            "size_bytes": 123,
        },
        "model_evaluation_report_path": "model_evaluation_report.json",
        "promotion_stage": promotion_stage,
        "is_promotion_ready": is_promotion_ready,
        "dataset_id": "dataset_123",
        "dataset_version": "dataset_v1",
        "experiment_run_id": "run_123",
    }


def build_evaluation_report(
    *,
    model_id: str = "model_123",
    model_version: str = "model_v1",
    promotion_stage: str = "paper_trading",
) -> dict[str, object]:
    return {
        "model_name": "baseline_random_forest_signal_model",
        "model_id": model_id,
        "model_version": model_version,
        "status": "passed",
        "promotion_stage": promotion_stage,
        "is_promotion_ready": True,
    }


def build_registry_entry(
    *,
    model_id: str = "model_123",
    model_version: str = "model_v1",
    promotion_stage: str = "paper_trading",
    target_stage: ModelPromotionStage = ModelPromotionStage.PAPER_TRADING,
    created_at_utc: str = "2026-01-01T00:00:00+00:00",
):
    model_metadata = build_model_version_metadata(
        model_id=model_id,
        model_version=model_version,
        promotion_stage=promotion_stage,
    )
    evaluation_report = build_evaluation_report(
        model_id=model_id,
        model_version=model_version,
        promotion_stage=promotion_stage,
    )
    review = build_model_promotion_review_from_metadata(
        model_version_metadata=model_metadata,
        evaluation_report=evaluation_report,
        policy=ModelPromotionPolicy(target_stage=target_stage),
        created_at_utc=created_at_utc,
    )

    return build_model_promotion_registry_entry(review)


def write_json(path, payload: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")


def test_model_promotion_gate_issue_to_dict() -> None:
    issue = build_model_promotion_gate_issue(
        rule=ModelPromotionGateRule.APPROVED_PROMOTION_FOUND,
        severity=ModelPromotionGateSeverity.ERROR,
        message="No approved promotion found.",
        field="promotion_registry",
        details={"required_stage": "paper_trading"},
    )

    assert issue.to_dict() == {
        "rule": "approved_promotion_found",
        "severity": "error",
        "message": "No approved promotion found.",
        "field": "promotion_registry",
        "details": {"required_stage": "paper_trading"},
    }


def test_build_model_promotion_gate_status() -> None:
    issue = build_model_promotion_gate_issue(
        rule=ModelPromotionGateRule.MODEL_ID_PRESENT,
        severity=ModelPromotionGateSeverity.ERROR,
        message="Missing model id.",
    )

    assert build_model_promotion_gate_status(()) == (
        ModelPromotionGateStatus.APPROVED
    )
    assert build_model_promotion_gate_status((issue,)) == (
        ModelPromotionGateStatus.REJECTED
    )


def test_extract_model_identity_from_metadata() -> None:
    identity = extract_model_identity_from_metadata(build_model_version_metadata())

    assert identity == (
        "baseline_random_forest_signal_model",
        "model_123",
        "model_v1",
        True,
    )


def test_validate_model_against_promotion_registry_approves_matching_model() -> None:
    entry = build_registry_entry()
    registry = ModelPromotionRegistry(promotions=(entry,))

    decision = validate_model_against_promotion_registry(
        model_version_metadata=build_model_version_metadata(),
        registry=registry,
        required_stage=ModelPromotionStage.PAPER_TRADING,
    )

    assert decision.approved is True
    assert decision.status == ModelPromotionGateStatus.APPROVED
    assert decision.approved_promotion == entry
    assert decision.error_count == 0


def test_validate_model_against_promotion_registry_rejects_missing_promotion() -> None:
    decision = validate_model_against_promotion_registry(
        model_version_metadata=build_model_version_metadata(),
        registry=ModelPromotionRegistry(),
        required_stage=ModelPromotionStage.PAPER_TRADING,
    )

    assert decision.approved is False
    assert any(
        issue.rule == ModelPromotionGateRule.APPROVED_PROMOTION_FOUND
        for issue in decision.issues
    )

    with pytest.raises(ValueError, match="Model promotion gate rejected"):
        decision.raise_if_rejected()


def test_validate_model_against_promotion_registry_rejects_not_ready_metadata() -> None:
    entry = build_registry_entry()
    registry = ModelPromotionRegistry(promotions=(entry,))

    decision = validate_model_against_promotion_registry(
        model_version_metadata=build_model_version_metadata(is_promotion_ready=False),
        registry=registry,
        required_stage=ModelPromotionStage.PAPER_TRADING,
    )

    assert decision.approved is False
    assert any(
        issue.rule == ModelPromotionGateRule.MODEL_PROMOTION_READY
        for issue in decision.issues
    )


def test_validate_model_against_promotion_registry_rejects_missing_model_identity() -> None:
    decision = validate_model_against_promotion_registry(
        model_version_metadata=build_model_version_metadata(
            model_id=None,
            model_version=None,
        ),
        registry=ModelPromotionRegistry(),
        required_stage=ModelPromotionStage.PAPER_TRADING,
    )

    assert decision.approved is False
    assert any(
        issue.rule == ModelPromotionGateRule.MODEL_ID_PRESENT
        for issue in decision.issues
    )
    assert any(
        issue.rule == ModelPromotionGateRule.MODEL_VERSION_PRESENT
        for issue in decision.issues
    )


def test_validate_model_against_promotion_registry_accepts_higher_approved_stage() -> None:
    live_entry = build_registry_entry(
        promotion_stage="live",
        target_stage=ModelPromotionStage.LIVE,
        created_at_utc="2026-01-02T00:00:00+00:00",
    )
    registry = ModelPromotionRegistry(promotions=(live_entry,))

    decision = validate_model_against_promotion_registry(
        model_version_metadata=build_model_version_metadata(
            promotion_stage="live",
        ),
        registry=registry,
        required_stage=ModelPromotionStage.PAPER_TRADING,
    )

    assert decision.approved is True
    assert decision.approved_promotion == live_entry


def test_find_latest_matching_approved_promotion_returns_latest() -> None:
    first = build_registry_entry(
        model_version="model_v1",
        created_at_utc="2026-01-01T00:00:00+00:00",
    )
    latest = build_registry_entry(
        model_version="model_v1",
        created_at_utc="2026-01-02T00:00:00+00:00",
    )
    registry = ModelPromotionRegistry(promotions=(first, latest))

    found = find_latest_matching_approved_promotion(
        registry=registry,
        required_stage=ModelPromotionStage.PAPER_TRADING,
        model_name="baseline_random_forest_signal_model",
        model_id="model_123",
        model_version="model_v1",
    )

    assert found == latest


def test_validate_model_files_against_promotion_registry_approves_files(tmp_path) -> None:
    metadata_path = tmp_path / "model_version_metadata.json"
    registry_path = tmp_path / "model_promotion_registry.json"

    write_json(metadata_path, build_model_version_metadata())
    registry = ModelPromotionRegistry(promotions=(build_registry_entry(),))
    write_model_promotion_registry(registry_path, registry)

    decision = validate_model_files_against_promotion_registry(
        model_version_metadata_path=metadata_path,
        promotion_registry_path=registry_path,
        required_stage=ModelPromotionStage.PAPER_TRADING,
    )

    assert decision.approved is True
    assert decision.approved_promotion is not None


def test_validate_model_files_against_promotion_registry_rejects_missing_metadata(
    tmp_path,
) -> None:
    decision = validate_model_files_against_promotion_registry(
        model_version_metadata_path=tmp_path / "missing_model_version_metadata.json",
        promotion_registry_path=tmp_path / "model_promotion_registry.json",
        required_stage=ModelPromotionStage.PAPER_TRADING,
    )

    assert decision.approved is False
    assert any(
        issue.rule == ModelPromotionGateRule.MODEL_METADATA_PRESENT
        for issue in decision.issues
    )


def test_validate_model_files_against_promotion_registry_rejects_missing_registry(
    tmp_path,
) -> None:
    metadata_path = tmp_path / "model_version_metadata.json"
    write_json(metadata_path, build_model_version_metadata())

    decision = validate_model_files_against_promotion_registry(
        model_version_metadata_path=metadata_path,
        promotion_registry_path=tmp_path / "missing_registry.json",
        required_stage=ModelPromotionStage.PAPER_TRADING,
    )

    assert decision.approved is False
    assert any(
        issue.rule == ModelPromotionGateRule.PROMOTION_REGISTRY_PRESENT
        for issue in decision.issues
    )