from __future__ import annotations

from enum import Enum
from pathlib import Path
from typing import Any

from fastapi import APIRouter, Depends, Query

from aqos.http_api.config import ApiConfig
from aqos.http_api.dependencies import get_api_config
from aqos.http_api.errors import ApiErrorCode, AqosApiError, NotFoundApiError
from aqos.http_api.pagination import (
    MAX_PAGE_LIMIT,
    apply_offset_limit,
    build_page,
    validate_limit,
    validate_offset,
)
from aqos.http_api.read_schemas import (
    build_prediction_summary,
    build_promotion_summary,
)
from aqos.http_api.responses import json_response
from aqos.model_training.model_promotion_registry import (
    read_model_promotion_registry,
)
from aqos.model_training.prediction_registry import (
    find_prediction_registry_run,
    list_prediction_registry_runs,
)


AQOS_HTTP_MODEL_ROUTES_VERSION = "1.0"

PREDICTIONS_PREFIX = "/predictions"
MODELS_PREFIX = "/models"


class PromotionState(str, Enum):
    """
    Whether a model may be used, as far as the API can tell.

    ``UNKNOWN`` is a first-class answer, not a failure. When no registry is
    configured or the model has no entry, AQOS says so rather than implying the
    model is unpromoted — and never that it is promoted.
    """

    PROMOTED = "promoted"
    NOT_PROMOTED = "not_promoted"
    UNKNOWN = "unknown"


#: Said when a registry is not configured for this deployment.
REGISTRY_UNAVAILABLE_MESSAGE = (
    "This deployment has no {registry} registry configured, so the data is "
    "unavailable rather than empty."
)


def require_registry_path(
    configured: str | None,
    registry: str,
) -> Path:
    """
    Resolve a configured registry path, or refuse the request.

    A missing registry is reported as unavailable rather than as an empty list:
    "nothing configured" and "configured and empty" are different facts and a
    client must be able to tell them apart.
    """

    if not configured or not configured.strip():
        raise AqosApiError(
            ApiErrorCode.NOT_READY,
            REGISTRY_UNAVAILABLE_MESSAGE.format(registry=registry),
            details={"registry": registry, "configured": False},
        )

    return Path(configured)


def read_promotion_entries(config: ApiConfig) -> tuple[Any, ...]:
    path = require_registry_path(
        config.model_promotion_registry_path,
        "model promotion",
    )

    if not path.exists():
        # Configured but absent: still unavailable, never silently empty.
        raise AqosApiError(
            ApiErrorCode.NOT_READY,
            REGISTRY_UNAVAILABLE_MESSAGE.format(registry="model promotion"),
            details={"registry": "model promotion", "configured": True},
        )

    return read_model_promotion_registry(path).promotions


def resolve_promotion_state(
    entries: tuple[Any, ...],
    model_id: str,
) -> dict[str, Any]:
    """
    Describe a model's promotion standing.

    An approved entry makes it promoted; entries that exist but were not
    approved make it explicitly not promoted; no entry at all leaves it
    unknown. Nothing here upgrades silence into approval.
    """

    matching = tuple(
        entry for entry in entries if entry.model_id == model_id
    )

    if not matching:
        return {
            "model_id": model_id,
            "state": PromotionState.UNKNOWN.value,
            "is_promoted": False,
            "reason": "No promotion record exists for this model.",
            "latest_promotion": None,
            "promotion_count": 0,
        }

    approved = tuple(entry for entry in matching if entry.approved)
    latest = sorted(matching, key=lambda entry: entry.created_at_utc)[-1]

    if approved:
        newest_approved = sorted(
            approved,
            key=lambda entry: entry.created_at_utc,
        )[-1]

        return {
            "model_id": model_id,
            "state": PromotionState.PROMOTED.value,
            "is_promoted": True,
            "reason": None,
            "latest_promotion": build_promotion_summary(newest_approved),
            "promotion_count": len(matching),
        }

    return {
        "model_id": model_id,
        "state": PromotionState.NOT_PROMOTED.value,
        "is_promoted": False,
        "reason": "Promotion records exist but none was approved.",
        "latest_promotion": build_promotion_summary(latest),
        "promotion_count": len(matching),
    }


def build_predictions_router() -> APIRouter:
    router = APIRouter(prefix=PREDICTIONS_PREFIX, tags=["predictions"])

    @router.get("")
    def list_predictions(
        config: ApiConfig = Depends(get_api_config),
        model_id: str | None = None,
        limit: int | None = Query(default=None, le=MAX_PAGE_LIMIT * 10),
        offset: int | None = None,
    ):
        """
        Recorded prediction runs.

        The registry is a file, so the whole list is already in memory and a
        real total can be reported honestly.
        """

        resolved_limit = validate_limit(limit)
        resolved_offset = validate_offset(offset)

        path = require_registry_path(
            config.prediction_registry_path,
            "prediction",
        )

        if not path.exists():
            raise AqosApiError(
                ApiErrorCode.NOT_READY,
                REGISTRY_UNAVAILABLE_MESSAGE.format(registry="prediction"),
                details={"registry": "prediction", "configured": True},
            )

        runs = list_prediction_registry_runs(path)

        if model_id is not None:
            runs = tuple(run for run in runs if run.get("model_id") == model_id)

        window = apply_offset_limit(runs, resolved_limit, resolved_offset)

        page = build_page(
            items=[build_prediction_summary(run) for run in window],
            limit=resolved_limit,
            offset=resolved_offset,
            total=len(runs),
        )

        return json_response(page.to_dict())

    @router.get("/{prediction_id}")
    def get_prediction(
        prediction_id: str,
        config: ApiConfig = Depends(get_api_config),
    ):
        path = require_registry_path(
            config.prediction_registry_path,
            "prediction",
        )

        run = find_prediction_registry_run(path, prediction_id) if path.exists() else None

        if run is None:
            raise NotFoundApiError(
                "Prediction run was not found.",
                details={"prediction_id": prediction_id},
            )

        return json_response(build_prediction_summary(run))

    return router


def build_models_router() -> APIRouter:
    router = APIRouter(prefix=MODELS_PREFIX, tags=["models"])

    @router.get("/promotions")
    def list_promotions(
        config: ApiConfig = Depends(get_api_config),
        model_id: str | None = None,
        approved_only: bool = False,
        limit: int | None = Query(default=None, le=MAX_PAGE_LIMIT * 10),
        offset: int | None = None,
    ):
        resolved_limit = validate_limit(limit)
        resolved_offset = validate_offset(offset)

        entries = read_promotion_entries(config)

        if model_id is not None:
            entries = tuple(
                entry for entry in entries if entry.model_id == model_id
            )

        if approved_only:
            entries = tuple(entry for entry in entries if entry.approved)

        window = apply_offset_limit(entries, resolved_limit, resolved_offset)

        page = build_page(
            items=[build_promotion_summary(entry) for entry in window],
            limit=resolved_limit,
            offset=resolved_offset,
            total=len(entries),
        )

        return json_response(page.to_dict())

    @router.get("/{model_id}/promotion-status")
    def get_promotion_status(
        model_id: str,
        config: ApiConfig = Depends(get_api_config),
    ):
        """
        Whether this model is promoted, not promoted, or unknown.

        Read-only, and deliberately unable to answer "promoted" without an
        approved record behind it.
        """

        return json_response(
            resolve_promotion_state(read_promotion_entries(config), model_id)
        )

    return router


__all__ = [
    "AQOS_HTTP_MODEL_ROUTES_VERSION",
    "MODELS_PREFIX",
    "PREDICTIONS_PREFIX",
    "PromotionState",
    "REGISTRY_UNAVAILABLE_MESSAGE",
    "build_models_router",
    "build_predictions_router",
    "read_promotion_entries",
    "require_registry_path",
    "resolve_promotion_state",
]
