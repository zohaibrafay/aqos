"""Unit tests for the read-only API layer: pagination, schemas, promotion state."""

from __future__ import annotations

import json
from datetime import datetime

import pytest

from aqos.http_api.errors import ValidationApiError
from aqos.http_api.pagination import (
    AQOS_HTTP_PAGINATION_VERSION,
    DEFAULT_PAGE_LIMIT,
    MAX_PAGE_LIMIT,
    Page,
    apply_offset_limit,
    build_page,
    validate_limit,
    validate_offset,
)
from aqos.http_api.read_schemas import (
    AQOS_HTTP_READ_SCHEMAS_VERSION,
    build_prediction_summary,
    build_promotion_summary,
    build_signal_detail,
    build_signal_event,
    build_signal_reason,
    build_signal_summary,
    parse_enum,
)
from aqos.http_api.routes_models import PromotionState, resolve_promotion_state
from aqos.model_training.model_evaluation import ModelPromotionStage
from aqos.model_training.model_promotion import ModelPromotionStatus
from aqos.model_training.model_promotion_registry import (
    ModelPromotionRegistryEntry,
)
from aqos.signal_reasons.models import SignalReason
from aqos.signal_reasons.taxonomy import (
    SignalReasonCategory,
    SignalReasonCode,
    SignalReasonSeverity,
)
from aqos.signals.models import (
    SignalAction,
    SignalEvent,
    SignalSource,
    SignalStatus,
    TradingSignal,
)


FIXED_NOW = datetime(2026, 1, 1, 0, 0, 0)

SECRET_PATH = "/srv/aqos/models/secret-artifact.joblib"


def build_signal(**overrides) -> TradingSignal:
    payload = {
        "signal_id": "signal_1",
        "user_id": "user_1",
        "account_id": "account_1",
        "symbol": "XAUUSD",
        "timeframe": "H1",
        "action": SignalAction.BUY,
        "status": SignalStatus.APPROVED,
        "source": SignalSource.ML_MODEL,
        "confidence": 0.75,
        "entry_price": 100.0,
        "stop_loss": 96.0,
        "take_profit": 110.0,
        "strategy_name": "Breakout",
        "model_id": "model_1",
        "model_version": "1.0",
        "generated_at_utc": FIXED_NOW,
        "created_at_utc": FIXED_NOW,
        "updated_at_utc": FIXED_NOW,
        "extra_metadata": {"internal_note": "do-not-expose"},
    }
    payload.update(overrides)

    return TradingSignal(**payload)


def build_promotion_entry(**overrides) -> ModelPromotionRegistryEntry:
    payload = {
        "promotion_id": "promotion_1",
        "created_at_utc": "2026-01-01T00:00:00",
        "model_name": "baseline",
        "model_id": "model_1",
        "model_version": "1.0",
        "target_stage": ModelPromotionStage.PAPER_TRADING,
        "status": ModelPromotionStatus.APPROVED,
        "approved": True,
        "model_artifact_path": SECRET_PATH,
        "model_evaluation_report_path": SECRET_PATH,
    }
    payload.update(overrides)

    return ModelPromotionRegistryEntry(**payload)


def test_module_versions_are_declared() -> None:
    assert AQOS_HTTP_PAGINATION_VERSION == "1.0"
    assert AQOS_HTTP_READ_SCHEMAS_VERSION == "1.0"


class TestPagination:
    def test_an_absent_limit_uses_the_default(self) -> None:
        assert validate_limit(None) == DEFAULT_PAGE_LIMIT

    def test_an_absent_offset_starts_at_zero(self) -> None:
        assert validate_offset(None) == 0

    def test_a_valid_limit_is_kept(self) -> None:
        assert validate_limit(10) == 10

    def test_a_limit_above_the_maximum_is_refused(self) -> None:
        """Unbounded reads would turn a GET into a denial of service."""

        with pytest.raises(ValidationApiError, match="cannot exceed"):
            validate_limit(MAX_PAGE_LIMIT + 1)

    def test_a_zero_limit_is_refused(self) -> None:
        with pytest.raises(ValidationApiError, match="at least"):
            validate_limit(0)

    def test_a_negative_limit_is_refused(self) -> None:
        with pytest.raises(ValidationApiError, match="at least"):
            validate_limit(-5)

    def test_a_negative_offset_is_refused(self) -> None:
        with pytest.raises(ValidationApiError, match="cannot be negative"):
            validate_offset(-1)

    def test_the_error_names_the_bound(self) -> None:
        with pytest.raises(ValidationApiError) as caught:
            validate_limit(9_999)

        assert caught.value.details["maximum"] == MAX_PAGE_LIMIT
        assert caught.value.status_code == 422

    def test_a_page_reports_its_shape(self) -> None:
        page = build_page(items=[1, 2, 3], limit=50, offset=0, total=3)

        assert page.to_dict() == {
            "items": [1, 2, 3],
            "limit": 50,
            "offset": 0,
            "total": 3,
            "count": 3,
        }

    def test_an_unmeasured_total_stays_null(self) -> None:
        """A guessed total is worse than an absent one."""

        page = Page(items=[1], limit=50, offset=0)

        assert page.total is None
        assert page.has_total is False
        assert page.to_dict()["total"] is None

    def test_apply_offset_limit_windows_the_sequence(self) -> None:
        items = list(range(10))

        assert apply_offset_limit(items, limit=3, offset=2) == (2, 3, 4)
        assert apply_offset_limit(items, limit=3, offset=9) == (9,)
        assert apply_offset_limit(items, limit=3, offset=20) == ()


class TestEnumParsing:
    def test_a_known_value_parses(self) -> None:
        assert parse_enum("approved", SignalStatus, "status") == (
            SignalStatus.APPROVED
        )

    def test_none_stays_none(self) -> None:
        assert parse_enum(None, SignalStatus, "status") is None

    def test_an_unknown_value_is_refused(self) -> None:
        """
        Silently ignoring it would read as "no matches for that status".

        A caller filtering on a typo deserves to be told, not handed an
        unfiltered list that looks like a real answer.
        """

        with pytest.raises(ValidationApiError, match="Unknown status"):
            parse_enum("almost_approved", SignalStatus, "status")

    def test_the_error_lists_the_allowed_values(self) -> None:
        with pytest.raises(ValidationApiError) as caught:
            parse_enum("nope", SignalAction, "action")

        assert set(caught.value.details["allowed"]) == {
            member.value for member in SignalAction
        }


class TestSignalSchemas:
    def test_the_summary_is_an_allow_list(self) -> None:
        assert set(build_signal_summary(build_signal())) == {
            "signal_id",
            "user_id",
            "account_id",
            "symbol",
            "timeframe",
            "action",
            "source",
            "status",
            "confidence",
            "generated_at_utc",
            "expires_at_utc",
        }

    def test_the_detail_adds_traceability_fields(self) -> None:
        detail = build_signal_detail(build_signal())

        assert detail["model_id"] == "model_1"
        assert detail["model_version"] == "1.0"
        assert detail["strategy_name"] == "Breakout"
        assert detail["entry_price"] == 100.0

    def test_raw_metadata_is_never_exposed(self) -> None:
        """
        Free-form JSON written by internal producers may carry anything.

        It stays off the wire until there is a vetted allow list for it.
        """

        rendered = json.dumps(build_signal_detail(build_signal()))

        assert "internal_note" not in rendered
        assert "do-not-expose" not in rendered
        assert "metadata" not in rendered

    def test_enums_render_as_their_values(self) -> None:
        summary = build_signal_summary(build_signal())

        assert summary["action"] == "buy"
        assert summary["status"] == "approved"
        assert summary["source"] == "ml_model"

    def test_an_absent_expiry_stays_null(self) -> None:
        assert build_signal_summary(build_signal())["expires_at_utc"] is None

    def test_the_payload_is_strict_json(self) -> None:
        rendered = json.dumps(
            build_signal_detail(build_signal()),
            allow_nan=False,
        )

        for token in ("Infinity", "-Infinity", "NaN"):
            assert token not in rendered


class TestSignalEventSchema:
    def test_an_event_renders_its_transition(self) -> None:
        event = SignalEvent(
            event_id="event_1",
            signal_id="signal_1",
            from_status=SignalStatus.GENERATED,
            to_status=SignalStatus.APPROVED,
            occurred_at_utc=FIXED_NOW,
            reason="Approved by user.",
            actor="user_1",
            created_at_utc=FIXED_NOW,
        )

        payload = build_signal_event(event)

        assert payload["from_status"] == "generated"
        assert payload["to_status"] == "approved"
        assert set(payload) == {
            "event_id",
            "signal_id",
            "from_status",
            "to_status",
            "occurred_at_utc",
            "reason",
            "actor",
        }

    def test_a_creation_event_has_no_previous_status(self) -> None:
        event = SignalEvent(
            event_id="event_1",
            signal_id="signal_1",
            from_status=None,
            to_status=SignalStatus.GENERATED,
            occurred_at_utc=FIXED_NOW,
            created_at_utc=FIXED_NOW,
        )

        assert build_signal_event(event)["from_status"] is None


class TestSignalReasonSchema:
    def test_a_reason_renders_its_taxonomy_fields(self) -> None:
        reason = SignalReason(
            reason_id="reason_1",
            signal_id="signal_1",
            user_id="user_1",
            account_id="account_1",
            signal_status=SignalStatus.REJECTED,
            reason_code=SignalReasonCode.SPREAD_TOO_HIGH,
            reason_category=SignalReasonCategory.MARKET_CONDITION,
            severity=SignalReasonSeverity.WARNING,
            message="Spread was wider than the allowed maximum.",
            source="risk_engine",
            created_at_utc=FIXED_NOW,
        )

        payload = build_signal_reason(reason)

        assert payload["reason_code"] == "spread_too_high"
        assert payload["reason_category"] == "market_condition"
        assert payload["severity"] == "warning"
        assert "metadata" not in payload


class TestPredictionSchema:
    def test_filesystem_paths_are_withheld(self) -> None:
        """Server-side file locations are of no use to a client."""

        run = {
            "prediction_id": "prediction_1",
            "created_at_utc": "2026-01-01T00:00:00",
            "model_name": "baseline",
            "model_id": "model_1",
            "model_version": "1.0",
            "rows": 80,
            "prediction_column": "signal",
            "probability_columns": ["p_buy", "p_sell"],
            "metadata_path": SECRET_PATH,
            "prediction_path": SECRET_PATH,
            "prediction_sha256": "abc123",
            "input_features_sha256": "def456",
            "input_features_rows": 80,
            "input_features_columns_count": 12,
        }

        payload = build_prediction_summary(run)
        rendered = json.dumps(payload)

        assert SECRET_PATH not in rendered
        assert "metadata_path" not in payload
        assert "prediction_path" not in payload
        assert payload["rows"] == 80
        assert payload["model_id"] == "model_1"

    def test_a_missing_field_stays_null(self) -> None:
        """A run without a model id reports null, not a guess."""

        payload = build_prediction_summary({"prediction_id": "prediction_1"})

        assert payload["model_id"] is None
        assert payload["rows"] is None
        assert payload["probability_columns"] == []


class TestPromotionSchema:
    def test_artifact_paths_are_withheld(self) -> None:
        rendered = json.dumps(build_promotion_summary(build_promotion_entry()))

        assert SECRET_PATH not in rendered
        assert "artifact_path" not in rendered
        assert "review_path" not in rendered

    def test_the_summary_reports_stage_and_approval(self) -> None:
        payload = build_promotion_summary(build_promotion_entry())

        assert payload["target_stage"] == "paper_trading"
        assert payload["status"] == "approved"
        assert payload["approved"] is True


class TestPromotionState:
    def test_no_record_is_unknown_not_unpromoted(self) -> None:
        """
        Silence is not evidence.

        With no record AQOS says it does not know, and never that the model is
        cleared for use.
        """

        state = resolve_promotion_state((), "model_missing")

        assert state["state"] == PromotionState.UNKNOWN.value
        assert state["is_promoted"] is False
        assert state["latest_promotion"] is None
        assert state["promotion_count"] == 0

    def test_an_approved_record_is_promoted(self) -> None:
        state = resolve_promotion_state((build_promotion_entry(),), "model_1")

        assert state["state"] == PromotionState.PROMOTED.value
        assert state["is_promoted"] is True
        assert state["latest_promotion"]["promotion_id"] == "promotion_1"

    def test_records_without_approval_are_explicitly_not_promoted(self) -> None:
        entry = build_promotion_entry(
            approved=False,
            status=ModelPromotionStatus.REJECTED,
        )
        state = resolve_promotion_state((entry,), "model_1")

        assert state["state"] == PromotionState.NOT_PROMOTED.value
        assert state["is_promoted"] is False
        assert state["reason"]

    def test_one_approval_among_rejections_promotes(self) -> None:
        entries = (
            build_promotion_entry(
                promotion_id="promotion_old",
                created_at_utc="2025-01-01T00:00:00",
                approved=False,
                status=ModelPromotionStatus.REJECTED,
            ),
            build_promotion_entry(
                promotion_id="promotion_new",
                created_at_utc="2026-06-01T00:00:00",
            ),
        )
        state = resolve_promotion_state(entries, "model_1")

        assert state["state"] == PromotionState.PROMOTED.value
        assert state["latest_promotion"]["promotion_id"] == "promotion_new"
        assert state["promotion_count"] == 2

    def test_another_models_approval_does_not_leak_across(self) -> None:
        entries = (build_promotion_entry(model_id="other_model"),)
        state = resolve_promotion_state(entries, "model_1")

        assert state["state"] == PromotionState.UNKNOWN.value

    def test_the_state_payload_is_strict_json(self) -> None:
        rendered = json.dumps(
            resolve_promotion_state((build_promotion_entry(),), "model_1"),
            allow_nan=False,
        )

        for token in ("Infinity", "-Infinity", "NaN"):
            assert token not in rendered
