from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from enum import Enum
from typing import Any, TypeVar

from aqos.http_api.errors import ValidationApiError
from aqos.signal_reasons.models import SignalReason
from aqos.signals.models import SignalEvent, TradingSignal


AQOS_HTTP_READ_SCHEMAS_VERSION = "1.0"

EnumType = TypeVar("EnumType", bound=Enum)


def parse_enum(
    value: str | None,
    enum_type: type[EnumType],
    field_name: str,
) -> EnumType | None:
    """
    Turn a query string into an enum member, or refuse it.

    An unknown value is a validation error rather than a silently ignored
    filter: quietly returning unfiltered results would look like "no matches
    for that status" when the status never existed.
    """

    if value is None:
        return None

    try:
        return enum_type(value)
    except ValueError as error:
        raise ValidationApiError(
            f"Unknown {field_name}: {value!r}.",
            details={
                "field": field_name,
                "value": value,
                "allowed": [member.value for member in enum_type],
            },
        ) from error


def isoformat_or_none(value: datetime | None) -> str | None:
    return value.isoformat() if value is not None else None


def as_number_or_none(value: Any) -> float | None:
    """
    Render a numeric column as a JSON number.

    MySQL returns ``DECIMAL`` as :class:`~decimal.Decimal`, which has no JSON
    form. Converting here keeps the contract explicit rather than leaving it to
    the response encoder to rescue.
    """

    if value is None:
        return None

    if isinstance(value, Decimal):
        return float(value)

    return float(value)


def build_signal_summary(signal: TradingSignal) -> dict[str, Any]:
    """
    A signal as the API describes it in a list.

    An explicit allow list, not the model's own ``to_dict``: a column added to
    the ORM later must not appear on the wire just because it exists.
    """

    return {
        "signal_id": signal.signal_id,
        "user_id": signal.user_id,
        "account_id": signal.account_id,
        "symbol": signal.symbol,
        "timeframe": signal.timeframe,
        "action": signal.action.value,
        "source": signal.source.value,
        "status": signal.status.value,
        "confidence": as_number_or_none(signal.confidence),
        "generated_at_utc": isoformat_or_none(signal.generated_at_utc),
        "expires_at_utc": isoformat_or_none(signal.expires_at_utc),
    }


def build_signal_detail(signal: TradingSignal) -> dict[str, Any]:
    """
    A single signal with its traceability fields.

    ``extra_metadata`` is deliberately absent. It is free-form JSON written by
    internal producers and may carry anything at all, so it is not exposed
    until there is a vetted allow list for what belongs in it.
    """

    detail = build_signal_summary(signal)
    detail.update(
        {
            "entry_price": as_number_or_none(signal.entry_price),
            "stop_loss": as_number_or_none(signal.stop_loss),
            "take_profit": as_number_or_none(signal.take_profit),
            "strategy_name": signal.strategy_name,
            "model_id": signal.model_id,
            "model_version": signal.model_version,
            "status_reason": signal.status_reason,
            "is_open": signal.is_open,
            "created_at_utc": isoformat_or_none(signal.created_at_utc),
            "updated_at_utc": isoformat_or_none(signal.updated_at_utc),
        }
    )

    return detail


def build_signal_event(event: SignalEvent) -> dict[str, Any]:
    """One entry in a signal's lifecycle audit trail."""

    return {
        "event_id": event.event_id,
        "signal_id": event.signal_id,
        "from_status": event.from_status.value if event.from_status else None,
        "to_status": event.to_status.value,
        "occurred_at_utc": isoformat_or_none(event.occurred_at_utc),
        "reason": event.reason,
        "actor": event.actor,
    }


def build_signal_reason(reason: SignalReason) -> dict[str, Any]:
    """One structured reason from the Sprint 045 taxonomy."""

    return {
        "reason_id": reason.reason_id,
        "signal_id": reason.signal_id,
        "user_id": reason.user_id,
        "account_id": reason.account_id,
        "signal_status": reason.signal_status.value,
        "reason_code": reason.reason_code.value,
        "reason_category": reason.reason_category.value,
        "severity": reason.severity.value,
        "message": reason.message,
        "source": reason.source,
        "created_at_utc": isoformat_or_none(reason.created_at_utc),
    }


def build_prediction_summary(run: dict[str, Any]) -> dict[str, Any]:
    """
    One prediction run as the API describes it.

    Filesystem paths and content hashes of local artifacts are withheld: they
    describe the server's disk layout, which a client has no use for and an
    attacker does.
    """

    return {
        "prediction_id": run.get("prediction_id"),
        "created_at_utc": run.get("created_at_utc"),
        "model_name": run.get("model_name"),
        "model_id": run.get("model_id"),
        "model_version": run.get("model_version"),
        "rows": run.get("rows"),
        "prediction_column": run.get("prediction_column"),
        "probability_columns": list(run.get("probability_columns") or ()),
        "input_features_rows": run.get("input_features_rows"),
        "input_features_columns_count": run.get("input_features_columns_count"),
    }


def build_promotion_summary(entry: Any) -> dict[str, Any]:
    """
    One promotion registry entry.

    Artifact, metadata, evaluation and review paths are all withheld for the
    same reason as predictions: they are server-side file locations.
    """

    return {
        "promotion_id": entry.promotion_id,
        "created_at_utc": entry.created_at_utc,
        "model_name": entry.model_name,
        "model_id": entry.model_id,
        "model_version": entry.model_version,
        "target_stage": entry.target_stage.value,
        "status": entry.status.value,
        "approved": entry.approved,
        "dataset_id": entry.dataset_id,
        "dataset_version": entry.dataset_version,
        "experiment_run_id": entry.experiment_run_id,
        "tags": list(entry.tags),
    }


__all__ = [
    "AQOS_HTTP_READ_SCHEMAS_VERSION",
    "as_number_or_none",
    "build_prediction_summary",
    "build_promotion_summary",
    "build_signal_detail",
    "build_signal_event",
    "build_signal_reason",
    "build_signal_summary",
    "isoformat_or_none",
    "parse_enum",
]
