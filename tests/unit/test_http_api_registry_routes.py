"""
Prediction and model-promotion endpoints against real registry files.

These registries are JSON files on disk rather than MySQL tables, so the tests
write real ones with the production writers and read them back through the API.
"""

from __future__ import annotations

import json

import pytest
from fastapi.testclient import TestClient

from aqos.http_api.app import create_aqos_api_app
from aqos.http_api.config import API_V1_PREFIX, ApiConfig, ApiEnvironment
from datetime import datetime, timedelta

from aqos.http_api.auth import AuthenticatedCaller
from aqos.http_api.authz import get_read_only_caller
from aqos.users.models import UserProfile, UserRole, UserSession, UserStatus

from aqos.model_training.model_evaluation import ModelPromotionStage
from aqos.model_training.model_promotion import ModelPromotionStatus
from aqos.model_training.model_promotion_registry import (
    ModelPromotionRegistry,
    ModelPromotionRegistryEntry,
    write_model_promotion_registry,
)


SECRET_PATH = "/srv/aqos/models/secret-artifact.joblib"


def build_stub_caller() -> AuthenticatedCaller:
    """
    A caller for tests that have no database.

    These suites exercise route behaviour, not authentication. The real token
    path is covered end to end by the MySQL protection tests; overriding the
    dependency here keeps these fast without pretending auth does not exist.
    """

    now = datetime(2026, 1, 1, 0, 0, 0)
    profile = UserProfile(
        user_id="user_stub",
        email="stub@example.com",
        display_name="Stub",
        role=UserRole.TRADER,
        status=UserStatus.ACTIVE,
        created_at_utc=now,
        updated_at_utc=now,
    )
    user_session = UserSession(
        session_id="session_stub",
        user_id="user_stub",
        token_hash="a" * 64,
        created_at_utc=now,
        expires_at_utc=now + timedelta(hours=1),
    )

    return AuthenticatedCaller(user=profile, session=user_session)


def authenticate(app) -> None:
    app.dependency_overrides[get_read_only_caller] = build_stub_caller


def build_entry(**overrides) -> ModelPromotionRegistryEntry:
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
    }
    payload.update(overrides)

    return ModelPromotionRegistryEntry(**payload)


@pytest.fixture
def promotion_registry(tmp_path):
    path = tmp_path / "model_promotions.json"

    write_model_promotion_registry(
        path,
        ModelPromotionRegistry(
            promotions=(
                build_entry(),
                build_entry(
                    promotion_id="promotion_2",
                    created_at_utc="2026-02-01T00:00:00",
                    model_id="model_2",
                    approved=False,
                    status=ModelPromotionStatus.REJECTED,
                ),
            )
        ),
    )

    return path


@pytest.fixture
def prediction_registry(tmp_path):
    path = tmp_path / "predictions.json"

    path.write_text(
        json.dumps(
            {
                "registry_version": "1.0",
                "runs": [
                    {
                        "prediction_id": "prediction_1",
                        "created_at_utc": "2026-01-01T00:00:00",
                        "model_name": "baseline",
                        "model_id": "model_1",
                        "model_version": "1.0",
                        "rows": 80,
                        "prediction_column": "signal",
                        "probability_columns": ["p_buy"],
                        "metadata_path": SECRET_PATH,
                        "prediction_path": SECRET_PATH,
                        "input_features_rows": 80,
                        "input_features_columns_count": 12,
                    },
                    {
                        "prediction_id": "prediction_2",
                        "created_at_utc": "2026-02-01T00:00:00",
                        "model_name": "baseline",
                        "model_id": "model_2",
                        "rows": 40,
                    },
                ],
            }
        ),
        encoding="utf-8",
    )

    return path


def build_client(**overrides) -> TestClient:
    payload = {"environment": ApiEnvironment.TEST}
    payload.update(overrides)

    app = create_aqos_api_app(ApiConfig(**payload))
    authenticate(app)

    return TestClient(app)


class TestPredictionEndpoints:
    def test_it_lists_recorded_runs(self, prediction_registry) -> None:
        client = build_client(
            prediction_registry_path=str(prediction_registry)
        )
        payload = client.get(f"{API_V1_PREFIX}/predictions").json()

        assert payload["count"] == 2
        assert payload["total"] == 2
        assert {item["prediction_id"] for item in payload["items"]} == {
            "prediction_1",
            "prediction_2",
        }

    def test_a_file_backed_total_is_real(self, prediction_registry) -> None:
        """The whole registry is in memory, so the count is measured."""

        client = build_client(
            prediction_registry_path=str(prediction_registry)
        )
        payload = client.get(f"{API_V1_PREFIX}/predictions?limit=1").json()

        assert payload["count"] == 1
        assert payload["total"] == 2

    def test_it_filters_by_model(self, prediction_registry) -> None:
        client = build_client(
            prediction_registry_path=str(prediction_registry)
        )
        payload = client.get(
            f"{API_V1_PREFIX}/predictions?model_id=model_2"
        ).json()

        assert payload["total"] == 1
        assert payload["items"][0]["prediction_id"] == "prediction_2"

    def test_it_returns_one_run(self, prediction_registry) -> None:
        client = build_client(
            prediction_registry_path=str(prediction_registry)
        )
        response = client.get(f"{API_V1_PREFIX}/predictions/prediction_1")

        assert response.status_code == 200
        assert response.json()["rows"] == 80

    def test_an_unknown_run_is_not_found(self, prediction_registry) -> None:
        client = build_client(
            prediction_registry_path=str(prediction_registry)
        )
        response = client.get(f"{API_V1_PREFIX}/predictions/nope")

        assert response.status_code == 404
        assert response.json()["error"]["code"] == "not_found"

    def test_no_filesystem_path_is_exposed(self, prediction_registry) -> None:
        client = build_client(
            prediction_registry_path=str(prediction_registry)
        )
        body = client.get(f"{API_V1_PREFIX}/predictions").text

        assert SECRET_PATH not in body
        assert str(prediction_registry) not in body

    def test_a_missing_registry_file_is_unavailable(self, tmp_path) -> None:
        """Configured but absent is still unavailable, never empty."""

        client = build_client(
            prediction_registry_path=str(tmp_path / "missing.json")
        )
        response = client.get(f"{API_V1_PREFIX}/predictions")

        assert response.status_code == 503
        assert response.json()["error"]["details"]["configured"] is True

    def test_an_invalid_limit_is_refused(self, prediction_registry) -> None:
        client = build_client(
            prediction_registry_path=str(prediction_registry)
        )

        assert client.get(
            f"{API_V1_PREFIX}/predictions?limit=0"
        ).status_code == 422


class TestPromotionEndpoints:
    def test_it_lists_promotions(self, promotion_registry) -> None:
        client = build_client(
            model_promotion_registry_path=str(promotion_registry)
        )
        payload = client.get(f"{API_V1_PREFIX}/models/promotions").json()

        assert payload["total"] == 2

    def test_it_can_filter_to_approved_only(self, promotion_registry) -> None:
        client = build_client(
            model_promotion_registry_path=str(promotion_registry)
        )
        payload = client.get(
            f"{API_V1_PREFIX}/models/promotions?approved_only=true"
        ).json()

        assert payload["total"] == 1
        assert payload["items"][0]["model_id"] == "model_1"

    def test_no_artifact_path_is_exposed(self, promotion_registry) -> None:
        client = build_client(
            model_promotion_registry_path=str(promotion_registry)
        )
        body = client.get(f"{API_V1_PREFIX}/models/promotions").text

        assert SECRET_PATH not in body

    def test_an_approved_model_reports_promoted(
        self,
        promotion_registry,
    ) -> None:
        client = build_client(
            model_promotion_registry_path=str(promotion_registry)
        )
        payload = client.get(
            f"{API_V1_PREFIX}/models/model_1/promotion-status"
        ).json()

        assert payload["state"] == "promoted"
        assert payload["is_promoted"] is True

    def test_a_rejected_model_reports_not_promoted(
        self,
        promotion_registry,
    ) -> None:
        client = build_client(
            model_promotion_registry_path=str(promotion_registry)
        )
        payload = client.get(
            f"{API_V1_PREFIX}/models/model_2/promotion-status"
        ).json()

        assert payload["state"] == "not_promoted"
        assert payload["is_promoted"] is False
        assert payload["reason"]

    def test_an_unrecorded_model_reports_unknown(
        self,
        promotion_registry,
    ) -> None:
        """
        Silence is not evidence of anything.

        A model nobody ever reviewed is unknown, and never "promoted".
        """

        client = build_client(
            model_promotion_registry_path=str(promotion_registry)
        )
        payload = client.get(
            f"{API_V1_PREFIX}/models/model_unheard_of/promotion-status"
        ).json()

        assert payload["state"] == "unknown"
        assert payload["is_promoted"] is False
        assert payload["latest_promotion"] is None

    def test_an_unconfigured_registry_never_answers_promoted(self) -> None:
        client = build_client()

        for path in (
            f"{API_V1_PREFIX}/models/promotions",
            f"{API_V1_PREFIX}/models/model_1/promotion-status",
        ):
            response = client.get(path)

            assert response.status_code == 503
            assert "promoted" not in response.json()["error"]["message"]

    def test_every_registry_response_is_strict_json(
        self,
        promotion_registry,
        prediction_registry,
    ) -> None:
        client = build_client(
            model_promotion_registry_path=str(promotion_registry),
            prediction_registry_path=str(prediction_registry),
        )

        for path in (
            f"{API_V1_PREFIX}/models/promotions",
            f"{API_V1_PREFIX}/models/model_1/promotion-status",
            f"{API_V1_PREFIX}/predictions",
            f"{API_V1_PREFIX}/predictions/prediction_1",
        ):
            body = client.get(path).text

            for token in ("Infinity", "-Infinity", "NaN"):
                assert token not in body

            json.loads(body)


class TestSystemInfoRegistryReporting:
    def test_it_reports_configuration_without_the_path(
        self,
        promotion_registry,
    ) -> None:
        client = build_client(
            model_promotion_registry_path=str(promotion_registry)
        )
        payload = client.get(f"{API_V1_PREFIX}/system/info").json()

        assert payload["api"]["has_model_promotion_registry"] is True
        assert payload["api"]["has_prediction_registry"] is False
        assert str(promotion_registry) not in json.dumps(payload)
