from __future__ import annotations

import json

import pytest

from aqos.model_training import (
    ModelPromotionRunConfig,
    ModelPromotionStage,
    build_model_promotion_policy,
    load_model_promotion_inputs,
    promote_model_from_metadata,
    read_model_promotion_registry,
    read_model_promotion_review,
    resolve_model_evaluation_report_path,
    resolve_model_promotion_output_dir,
    resolve_model_promotion_registry_path,
    resolve_model_promotion_review_path,
)


def build_model_version_metadata(
    *,
    promotion_stage: str = "paper_trading",
    is_promotion_ready: bool = True,
    model_id: str = "model_123",
    model_version: str = "model_v1",
    evaluation_report_path: str | None = "model_evaluation_report.json",
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
        "model_evaluation_report_path": evaluation_report_path,
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


def write_json(path, payload: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")


def test_model_promotion_run_config_rejects_blocked_target(tmp_path) -> None:
    with pytest.raises(ValueError, match="target_stage cannot be blocked"):
        ModelPromotionRunConfig(
            model_version_metadata_path=tmp_path / "model_version_metadata.json",
            target_stage=ModelPromotionStage.BLOCKED,
        )


def test_model_promotion_runner_resolves_default_paths(tmp_path) -> None:
    metadata_path = tmp_path / "artifacts" / "model_version_metadata.json"

    config = ModelPromotionRunConfig(
        model_version_metadata_path=metadata_path,
        target_stage=ModelPromotionStage.PAPER_TRADING,
    )

    output_dir = resolve_model_promotion_output_dir(config)

    assert output_dir == metadata_path.parent
    assert resolve_model_promotion_review_path(
        config,
        output_dir,
    ) == output_dir / "model_promotion_review.json"
    assert resolve_model_promotion_registry_path(
        config,
        output_dir,
    ) == output_dir / "model_promotion_registry.json"


def test_resolve_model_evaluation_report_path_from_metadata(tmp_path) -> None:
    metadata_path = tmp_path / "artifacts" / "model_version_metadata.json"
    evaluation_path = metadata_path.parent / "model_evaluation_report.json"

    write_json(evaluation_path, build_evaluation_report())

    config = ModelPromotionRunConfig(
        model_version_metadata_path=metadata_path,
        target_stage=ModelPromotionStage.PAPER_TRADING,
    )

    resolved = resolve_model_evaluation_report_path(
        run_config=config,
        model_version_metadata=build_model_version_metadata(),
    )

    assert resolved == evaluation_path


def test_load_model_promotion_inputs_reads_metadata_and_evaluation(tmp_path) -> None:
    metadata_path = tmp_path / "artifacts" / "model_version_metadata.json"
    evaluation_path = metadata_path.parent / "model_evaluation_report.json"

    write_json(metadata_path, build_model_version_metadata())
    write_json(evaluation_path, build_evaluation_report())

    config = ModelPromotionRunConfig(
        model_version_metadata_path=metadata_path,
        target_stage=ModelPromotionStage.PAPER_TRADING,
    )

    metadata, evaluation, resolved_evaluation_path = load_model_promotion_inputs(
        config
    )

    assert metadata["model_id"] == "model_123"
    assert evaluation["status"] == "passed"
    assert resolved_evaluation_path == evaluation_path


def test_build_model_promotion_policy_from_config(tmp_path) -> None:
    config = ModelPromotionRunConfig(
        model_version_metadata_path=tmp_path / "model_version_metadata.json",
        target_stage=ModelPromotionStage.DEMO,
        current_stage=ModelPromotionStage.PAPER_TRADING,
        require_evaluation_report=True,
        require_model_promotion_ready=True,
        allow_warning_evaluation=False,
        allow_same_stage=False,
        forward_only=True,
    )

    policy = build_model_promotion_policy(config)

    assert policy.target_stage == ModelPromotionStage.DEMO
    assert policy.current_stage == ModelPromotionStage.PAPER_TRADING
    assert policy.allow_warning_evaluation is False
    assert policy.allow_same_stage is False


def test_promote_model_from_metadata_approves_and_registers_model(tmp_path) -> None:
    metadata_path = tmp_path / "artifacts" / "model_version_metadata.json"
    evaluation_path = metadata_path.parent / "model_evaluation_report.json"

    write_json(metadata_path, build_model_version_metadata())
    write_json(evaluation_path, build_evaluation_report())

    output = promote_model_from_metadata(
        ModelPromotionRunConfig(
            model_version_metadata_path=metadata_path,
            target_stage=ModelPromotionStage.PAPER_TRADING,
            notes="Approved for paper trading.",
            tags=("aqos", "paper"),
        )
    )

    assert output.review.approved is True
    assert output.registry_entry.approved is True
    assert output.promotion_review_path.exists()
    assert output.promotion_registry_path.exists()

    review_payload = read_model_promotion_review(output.promotion_review_path)
    registry = read_model_promotion_registry(output.promotion_registry_path)

    assert review_payload["approved"] is True
    assert review_payload["target_stage"] == "paper_trading"
    assert len(registry.promotions) == 1
    assert registry.promotions[0].approved is True
    assert registry.promotions[0].notes == "Approved for paper trading."
    assert registry.promotions[0].tags == ("aqos", "paper")


def test_promote_model_from_metadata_registers_rejected_attempt_without_raising(
    tmp_path,
) -> None:
    metadata_path = tmp_path / "artifacts" / "model_version_metadata.json"
    evaluation_path = metadata_path.parent / "model_evaluation_report.json"

    write_json(
        metadata_path,
        build_model_version_metadata(
            promotion_stage="blocked",
            is_promotion_ready=False,
        ),
    )
    write_json(
        evaluation_path,
        build_evaluation_report(
            status="failed",
            promotion_stage="blocked",
            is_promotion_ready=False,
        ),
    )

    output = promote_model_from_metadata(
        ModelPromotionRunConfig(
            model_version_metadata_path=metadata_path,
            target_stage=ModelPromotionStage.PAPER_TRADING,
            fail_on_rejected=False,
        )
    )

    registry = read_model_promotion_registry(output.promotion_registry_path)

    assert output.review.approved is False
    assert output.registry_entry.approved is False
    assert len(registry.promotions) == 1
    assert registry.promotions[0].approved is False
    assert registry.promotions[0].status.value == "rejected"


def test_promote_model_from_metadata_can_raise_after_recording_rejection(
    tmp_path,
) -> None:
    metadata_path = tmp_path / "artifacts" / "model_version_metadata.json"
    evaluation_path = metadata_path.parent / "model_evaluation_report.json"

    write_json(
        metadata_path,
        build_model_version_metadata(
            promotion_stage="blocked",
            is_promotion_ready=False,
        ),
    )
    write_json(
        evaluation_path,
        build_evaluation_report(
            status="failed",
            promotion_stage="blocked",
            is_promotion_ready=False,
        ),
    )

    with pytest.raises(ValueError, match="Model promotion rejected"):
        promote_model_from_metadata(
            ModelPromotionRunConfig(
                model_version_metadata_path=metadata_path,
                target_stage=ModelPromotionStage.PAPER_TRADING,
                fail_on_rejected=True,
            )
        )

    registry = read_model_promotion_registry(
        metadata_path.parent / "model_promotion_registry.json"
    )

    assert len(registry.promotions) == 1
    assert registry.promotions[0].approved is False


def test_promote_model_from_metadata_supports_custom_output_dir(tmp_path) -> None:
    metadata_path = tmp_path / "artifacts" / "model_version_metadata.json"
    evaluation_path = metadata_path.parent / "model_evaluation_report.json"
    output_dir = tmp_path / "promotion"

    write_json(metadata_path, build_model_version_metadata())
    write_json(evaluation_path, build_evaluation_report())

    output = promote_model_from_metadata(
        ModelPromotionRunConfig(
            model_version_metadata_path=metadata_path,
            target_stage=ModelPromotionStage.PAPER_TRADING,
            output_dir=output_dir,
            promotion_review_filename="review.json",
            promotion_registry_filename="registry.json",
        )
    )

    assert output.promotion_review_path == output_dir / "review.json"
    assert output.promotion_registry_path == output_dir / "registry.json"
    assert output.promotion_review_path.exists()
    assert output.promotion_registry_path.exists()


def test_model_promotion_run_output_to_dict(tmp_path) -> None:
    metadata_path = tmp_path / "artifacts" / "model_version_metadata.json"
    evaluation_path = metadata_path.parent / "model_evaluation_report.json"

    write_json(metadata_path, build_model_version_metadata())
    write_json(evaluation_path, build_evaluation_report())

    output = promote_model_from_metadata(
        ModelPromotionRunConfig(
            model_version_metadata_path=metadata_path,
            target_stage=ModelPromotionStage.PAPER_TRADING,
        )
    )

    payload = output.to_dict()

    assert payload["promotion_review_path"].endswith("model_promotion_review.json")
    assert payload["promotion_registry_path"].endswith(
        "model_promotion_registry.json"
    )
    assert payload["review"]["approved"] is True
    assert payload["registry_entry"]["approved"] is True
    assert payload["registry"]["registry_version"] == "1.0"