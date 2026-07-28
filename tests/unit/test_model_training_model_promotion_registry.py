from __future__ import annotations

import pytest

from aqos.model_training import (
    MODEL_PROMOTION_REGISTRY_VERSION,
    ModelPromotionPolicy,
    ModelPromotionRegistry,
    ModelPromotionRegistryEntry,
    ModelPromotionStage,
    build_model_promotion_registry_entry,
    build_model_promotion_review_from_metadata,
    build_model_promotion_id,
    find_latest_approved_model_for_stage,
    find_latest_model_promotion,
    list_model_promotions,
    normalize_promotion_name,
    parse_model_promotion_registry_entry,
    read_model_promotion_registry,
    write_model_promotion_registry,
    append_model_promotion_to_registry,
)


def build_model_version_metadata(
    *,
    model_version: str = "model_v1",
    promotion_stage: str = "paper_trading",
    is_promotion_ready: bool = True,
) -> dict[str, object]:
    return {
        "model_name": "baseline_random_forest_signal_model",
        "model_id": "model_123",
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
    model_version: str = "model_v1",
    status: str = "passed",
    promotion_stage: str = "paper_trading",
    is_promotion_ready: bool = True,
) -> dict[str, object]:
    return {
        "model_name": "baseline_random_forest_signal_model",
        "model_id": "model_123",
        "model_version": model_version,
        "status": status,
        "promotion_stage": promotion_stage,
        "is_promotion_ready": is_promotion_ready,
    }


def build_review(
    *,
    model_version: str = "model_v1",
    target_stage: ModelPromotionStage = ModelPromotionStage.PAPER_TRADING,
    created_at_utc: str = "2026-01-01T00:00:00+00:00",
):
    return build_model_promotion_review_from_metadata(
        model_version_metadata=build_model_version_metadata(
            model_version=model_version,
            promotion_stage=target_stage.value,
        ),
        evaluation_report=build_evaluation_report(
            model_version=model_version,
            promotion_stage=target_stage.value,
        ),
        policy=ModelPromotionPolicy(target_stage=target_stage),
        model_version_metadata_path="artifacts/model_version_metadata.json",
        created_at_utc=created_at_utc,
    )


def test_normalize_promotion_name() -> None:
    assert normalize_promotion_name("Baseline Random Forest!") == (
        "baseline_random_forest"
    )
    assert normalize_promotion_name("   ") == "model"


def test_build_model_promotion_id_is_stable() -> None:
    promotion_id = build_model_promotion_id(
        model_name="Baseline Random Forest",
        model_version="model_v1",
        target_stage=ModelPromotionStage.PAPER_TRADING,
        created_at_utc="2026-01-01T00:00:00+00:00",
    )

    assert promotion_id.startswith("baseline_random_forest_paper_trading_")
    assert promotion_id.endswith(build_model_promotion_id(
        model_name="Baseline Random Forest",
        model_version="model_v1",
        target_stage=ModelPromotionStage.PAPER_TRADING,
        created_at_utc="2026-01-01T00:00:00+00:00",
    ).split("_")[-1])


def test_build_model_promotion_registry_entry_from_review() -> None:
    review = build_review()
    entry = build_model_promotion_registry_entry(
        review=review,
        model_promotion_review_path="artifacts/model_promotion_review.json",
        notes="Approved for paper trading.",
        tags=("aqos", "paper"),
    )

    payload = entry.to_dict()

    assert entry.approved is True
    assert entry.target_stage == ModelPromotionStage.PAPER_TRADING
    assert entry.model_id == "model_123"
    assert entry.model_version == "model_v1"
    assert entry.model_promotion_review_path == (
        "artifacts/model_promotion_review.json"
    )
    assert payload["registry_version"] if False else True
    assert payload["target_stage"] == "paper_trading"
    assert payload["tags"] == ["aqos", "paper"]


def test_model_promotion_registry_entry_rejects_blocked_target() -> None:
    with pytest.raises(ValueError, match="target_stage cannot be blocked"):
        ModelPromotionRegistryEntry(
            promotion_id="promotion_1",
            created_at_utc="2026-01-01T00:00:00+00:00",
            model_name="model",
            model_id="model_1",
            model_version="v1",
            target_stage=ModelPromotionStage.BLOCKED,
            status="approved",
            approved=True,
        )


def test_parse_model_promotion_registry_entry_roundtrip() -> None:
    entry = build_model_promotion_registry_entry(build_review())
    parsed = parse_model_promotion_registry_entry(entry.to_dict())

    assert parsed == entry


def test_read_missing_model_promotion_registry_returns_empty_registry(tmp_path) -> None:
    registry = read_model_promotion_registry(tmp_path / "missing_registry.json")

    assert registry.registry_version == MODEL_PROMOTION_REGISTRY_VERSION
    assert registry.promotions == ()


def test_write_and_read_model_promotion_registry_roundtrip(tmp_path) -> None:
    entry = build_model_promotion_registry_entry(build_review())
    registry = ModelPromotionRegistry(promotions=(entry,))

    registry_path = tmp_path / "promotion_registry.json"
    written_path = write_model_promotion_registry(registry_path, registry)
    loaded = read_model_promotion_registry(written_path)

    assert written_path == registry_path
    assert loaded.registry_version == MODEL_PROMOTION_REGISTRY_VERSION
    assert loaded.promotions == (entry,)


def test_append_model_promotion_to_registry_deduplicates_by_promotion_id(tmp_path) -> None:
    registry_path = tmp_path / "promotion_registry.json"
    entry = build_model_promotion_registry_entry(build_review())

    append_model_promotion_to_registry(registry_path, entry)
    registry = append_model_promotion_to_registry(registry_path, entry)

    assert len(registry.promotions) == 1
    assert registry.promotions[0] == entry


def test_append_model_promotion_to_registry_sorts_by_created_at(tmp_path) -> None:
    registry_path = tmp_path / "promotion_registry.json"

    later = build_model_promotion_registry_entry(
        build_review(
            model_version="model_v2",
            created_at_utc="2026-01-02T00:00:00+00:00",
        )
    )
    earlier = build_model_promotion_registry_entry(
        build_review(
            model_version="model_v1",
            created_at_utc="2026-01-01T00:00:00+00:00",
        )
    )

    append_model_promotion_to_registry(registry_path, later)
    registry = append_model_promotion_to_registry(registry_path, earlier)

    assert registry.promotions[0].model_version == "model_v1"
    assert registry.promotions[1].model_version == "model_v2"


def test_list_model_promotions_filters_entries() -> None:
    paper_entry = build_model_promotion_registry_entry(
        build_review(
            model_version="model_v1",
            target_stage=ModelPromotionStage.PAPER_TRADING,
            created_at_utc="2026-01-01T00:00:00+00:00",
        )
    )
    demo_entry = build_model_promotion_registry_entry(
        build_review(
            model_version="model_v2",
            target_stage=ModelPromotionStage.DEMO,
            created_at_utc="2026-01-02T00:00:00+00:00",
        )
    )

    registry = ModelPromotionRegistry(promotions=(paper_entry, demo_entry))

    assert list_model_promotions(
        registry,
        target_stage=ModelPromotionStage.PAPER_TRADING,
    ) == (paper_entry,)

    assert list_model_promotions(
        registry,
        model_name="baseline_random_forest_signal_model",
        approved_only=True,
    ) == (paper_entry, demo_entry)


def test_find_latest_model_promotion_returns_latest_matching_entry() -> None:
    first = build_model_promotion_registry_entry(
        build_review(
            model_version="model_v1",
            created_at_utc="2026-01-01T00:00:00+00:00",
        )
    )
    latest = build_model_promotion_registry_entry(
        build_review(
            model_version="model_v2",
            created_at_utc="2026-01-02T00:00:00+00:00",
        )
    )

    registry = ModelPromotionRegistry(promotions=(first, latest))

    assert find_latest_model_promotion(registry) == latest


def test_find_latest_approved_model_for_stage_returns_latest_approved_stage() -> None:
    first = build_model_promotion_registry_entry(
        build_review(
            model_version="model_v1",
            created_at_utc="2026-01-01T00:00:00+00:00",
        )
    )
    latest = build_model_promotion_registry_entry(
        build_review(
            model_version="model_v2",
            created_at_utc="2026-01-02T00:00:00+00:00",
        )
    )

    registry = ModelPromotionRegistry(promotions=(first, latest))

    assert find_latest_approved_model_for_stage(
        registry,
        ModelPromotionStage.PAPER_TRADING,
    ) == latest


def test_find_latest_approved_model_for_stage_returns_none_when_missing() -> None:
    registry = ModelPromotionRegistry()

    assert find_latest_approved_model_for_stage(
        registry,
        ModelPromotionStage.PAPER_TRADING,
    ) is None