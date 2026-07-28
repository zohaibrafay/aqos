from __future__ import annotations

import pytest

from aqos.model_training import (
    MODEL_PROMOTION_VERSION,
    ModelPromotionPolicy,
    ModelPromotionRule,
    ModelPromotionSeverity,
    ModelPromotionStatus,
    ModelPromotionStage,
    build_model_promotion_candidate,
    build_model_promotion_issue,
    build_model_promotion_review_from_metadata,
    build_model_promotion_status,
    is_target_stage_allowed,
    parse_model_promotion_stage,
    promotion_stage_rank,
    read_model_promotion_review,
    write_model_promotion_review,
)


def build_model_version_metadata(
    *,
    promotion_stage: str = "paper_trading",
    is_promotion_ready: bool = True,
    model_id: str = "model_123",
    model_version: str = "model_v1",
) -> dict[str, object]:
    return {
        "model_name": "baseline_random_forest_signal_model",
        "model_id": model_id,
        "model_version": model_version,
        "model_artifact": {
            "path": "artifacts/baseline_signal_model.joblib",
            "sha256": "abc123",
            "size_bytes": 123,
        },
        "model_evaluation_report_path": "artifacts/model_evaluation_report.json",
        "promotion_stage": promotion_stage,
        "is_promotion_ready": is_promotion_ready,
        "dataset_id": "dataset_123",
        "dataset_version": "dataset_v1",
        "experiment_run_id": "run_123",
    }


def build_evaluation_report(
    *,
    status: str = "passed",
    promotion_stage: str = "paper_trading",
    is_promotion_ready: bool = True,
    model_id: str = "model_123",
    model_version: str = "model_v1",
) -> dict[str, object]:
    return {
        "model_name": "baseline_random_forest_signal_model",
        "model_id": model_id,
        "model_version": model_version,
        "status": status,
        "promotion_stage": promotion_stage,
        "is_promotion_ready": is_promotion_ready,
    }


def test_parse_model_promotion_stage() -> None:
    assert parse_model_promotion_stage("paper_trading") == (
        ModelPromotionStage.PAPER_TRADING
    )
    assert parse_model_promotion_stage(ModelPromotionStage.LIVE) == (
        ModelPromotionStage.LIVE
    )
    assert parse_model_promotion_stage(None) is None


def test_promotion_stage_rank_orders_stages() -> None:
    assert promotion_stage_rank(ModelPromotionStage.RESEARCH) < promotion_stage_rank(
        ModelPromotionStage.PAPER_TRADING
    )
    assert promotion_stage_rank(ModelPromotionStage.PAPER_TRADING) < (
        promotion_stage_rank(ModelPromotionStage.DEMO)
    )
    assert promotion_stage_rank(ModelPromotionStage.DEMO) < promotion_stage_rank(
        ModelPromotionStage.LIMITED_LIVE
    )
    assert promotion_stage_rank(ModelPromotionStage.LIMITED_LIVE) < (
        promotion_stage_rank(ModelPromotionStage.LIVE)
    )


def test_is_target_stage_allowed() -> None:
    assert is_target_stage_allowed(
        ModelPromotionStage.PAPER_TRADING,
        ModelPromotionStage.PAPER_TRADING,
    )
    assert is_target_stage_allowed(
        ModelPromotionStage.PAPER_TRADING,
        ModelPromotionStage.LIVE,
    )
    assert not is_target_stage_allowed(
        ModelPromotionStage.LIVE,
        ModelPromotionStage.PAPER_TRADING,
    )
    assert not is_target_stage_allowed(
        ModelPromotionStage.PAPER_TRADING,
        ModelPromotionStage.BLOCKED,
    )
    assert not is_target_stage_allowed(ModelPromotionStage.PAPER_TRADING, None)


def test_model_promotion_issue_to_dict() -> None:
    issue = build_model_promotion_issue(
        rule=ModelPromotionRule.MODEL_ID_PRESENT,
        severity=ModelPromotionSeverity.ERROR,
        message="Missing model id.",
        field="model_id",
        details={"expected": "non-empty"},
    )

    assert issue.to_dict() == {
        "rule": "model_id_present",
        "severity": "error",
        "message": "Missing model id.",
        "field": "model_id",
        "details": {"expected": "non-empty"},
    }


def test_build_model_promotion_status() -> None:
    warning = build_model_promotion_issue(
        rule=ModelPromotionRule.STAGE_FORWARD_ONLY,
        severity=ModelPromotionSeverity.WARNING,
        message="Warning.",
    )
    error = build_model_promotion_issue(
        rule=ModelPromotionRule.MODEL_ID_PRESENT,
        severity=ModelPromotionSeverity.ERROR,
        message="Error.",
    )

    assert build_model_promotion_status(()) == ModelPromotionStatus.APPROVED
    assert build_model_promotion_status((warning,)) == (
        ModelPromotionStatus.APPROVED_WITH_WARNINGS
    )
    assert build_model_promotion_status((warning, error)) == (
        ModelPromotionStatus.REJECTED
    )


def test_build_model_promotion_candidate_from_metadata() -> None:
    candidate = build_model_promotion_candidate(
        model_version_metadata=build_model_version_metadata(),
        evaluation_report=build_evaluation_report(),
        model_version_metadata_path="artifacts/model_version_metadata.json",
    )

    assert candidate.model_name == "baseline_random_forest_signal_model"
    assert candidate.model_id == "model_123"
    assert candidate.model_version == "model_v1"
    assert candidate.model_artifact_path == "artifacts/baseline_signal_model.joblib"
    assert candidate.model_promotion_stage == ModelPromotionStage.PAPER_TRADING
    assert candidate.evaluation_promotion_stage == ModelPromotionStage.PAPER_TRADING
    assert candidate.model_is_promotion_ready is True
    assert candidate.evaluation_is_promotion_ready is True


def test_model_promotion_review_approves_valid_paper_model() -> None:
    review = build_model_promotion_review_from_metadata(
        model_version_metadata=build_model_version_metadata(),
        evaluation_report=build_evaluation_report(),
        policy=ModelPromotionPolicy(target_stage=ModelPromotionStage.PAPER_TRADING),
        created_at_utc="2026-01-01T00:00:00+00:00",
    )

    payload = review.to_dict()

    assert review.status == ModelPromotionStatus.APPROVED
    assert review.approved is True
    assert review.error_count == 0
    assert payload["metadata_version"] == MODEL_PROMOTION_VERSION
    assert payload["target_stage"] == "paper_trading"
    assert payload["candidate"]["model_id"] == "model_123"


def test_model_promotion_review_rejects_failed_evaluation() -> None:
    review = build_model_promotion_review_from_metadata(
        model_version_metadata=build_model_version_metadata(
            promotion_stage="blocked",
            is_promotion_ready=False,
        ),
        evaluation_report=build_evaluation_report(
            status="failed",
            promotion_stage="blocked",
            is_promotion_ready=False,
        ),
        policy=ModelPromotionPolicy(target_stage=ModelPromotionStage.PAPER_TRADING),
        created_at_utc="2026-01-01T00:00:00+00:00",
    )

    assert review.status == ModelPromotionStatus.REJECTED
    assert review.approved is False
    assert any(
        issue.rule == ModelPromotionRule.EVALUATION_STATUS_ALLOWED
        for issue in review.issues
    )
    assert any(
        issue.rule == ModelPromotionRule.EVALUATION_PROMOTION_READY
        for issue in review.issues
    )

    with pytest.raises(ValueError, match="Model promotion rejected"):
        review.raise_if_rejected()


def test_model_promotion_review_rejects_stage_above_evaluation_limit() -> None:
    review = build_model_promotion_review_from_metadata(
        model_version_metadata=build_model_version_metadata(
            promotion_stage="paper_trading",
        ),
        evaluation_report=build_evaluation_report(
            promotion_stage="paper_trading",
        ),
        policy=ModelPromotionPolicy(target_stage=ModelPromotionStage.LIVE),
        created_at_utc="2026-01-01T00:00:00+00:00",
    )

    assert review.status == ModelPromotionStatus.REJECTED
    assert any(
        issue.rule == ModelPromotionRule.TARGET_STAGE_ALLOWED
        for issue in review.issues
    )


def test_model_promotion_review_rejects_backward_stage_when_forward_only() -> None:
    review = build_model_promotion_review_from_metadata(
        model_version_metadata=build_model_version_metadata(
            promotion_stage="live",
        ),
        evaluation_report=build_evaluation_report(
            promotion_stage="live",
        ),
        policy=ModelPromotionPolicy(
            current_stage=ModelPromotionStage.LIVE,
            target_stage=ModelPromotionStage.PAPER_TRADING,
            forward_only=True,
        ),
        created_at_utc="2026-01-01T00:00:00+00:00",
    )

    assert review.status == ModelPromotionStatus.REJECTED
    assert any(
        issue.rule == ModelPromotionRule.STAGE_FORWARD_ONLY
        for issue in review.issues
    )


def test_model_promotion_review_rejects_model_evaluation_id_mismatch() -> None:
    review = build_model_promotion_review_from_metadata(
        model_version_metadata=build_model_version_metadata(model_id="model_123"),
        evaluation_report=build_evaluation_report(model_id="model_999"),
        policy=ModelPromotionPolicy(target_stage=ModelPromotionStage.PAPER_TRADING),
        created_at_utc="2026-01-01T00:00:00+00:00",
    )

    assert review.status == ModelPromotionStatus.REJECTED
    assert any(
        issue.rule == ModelPromotionRule.MODEL_EVALUATION_ID_MATCH
        for issue in review.issues
    )


def test_model_promotion_review_requires_evaluation_report_when_enabled() -> None:
    review = build_model_promotion_review_from_metadata(
        model_version_metadata=build_model_version_metadata(),
        evaluation_report=None,
        policy=ModelPromotionPolicy(
            target_stage=ModelPromotionStage.PAPER_TRADING,
            require_evaluation_report=True,
        ),
        created_at_utc="2026-01-01T00:00:00+00:00",
    )

    assert review.status == ModelPromotionStatus.REJECTED
    assert any(
        issue.rule == ModelPromotionRule.EVALUATION_REPORT_PRESENT
        for issue in review.issues
    )


def test_write_and_read_model_promotion_review_roundtrip(tmp_path) -> None:
    review = build_model_promotion_review_from_metadata(
        model_version_metadata=build_model_version_metadata(),
        evaluation_report=build_evaluation_report(),
        policy=ModelPromotionPolicy(target_stage=ModelPromotionStage.PAPER_TRADING),
        created_at_utc="2026-01-01T00:00:00+00:00",
    )

    output_path = tmp_path / "promotion" / "model_promotion_review.json"
    written_path = write_model_promotion_review(output_path, review)
    payload = read_model_promotion_review(written_path)

    assert written_path == output_path
    assert payload["metadata_version"] == MODEL_PROMOTION_VERSION
    assert payload["approved"] is True
    assert payload["target_stage"] == "paper_trading"


def test_model_promotion_policy_rejects_blocked_target() -> None:
    with pytest.raises(ValueError, match="target_stage cannot be blocked"):
        ModelPromotionPolicy(target_stage=ModelPromotionStage.BLOCKED)