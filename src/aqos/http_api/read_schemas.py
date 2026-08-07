from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from enum import Enum
from typing import Any, TypeVar

from aqos.account_analytics.models import AccountAnalyticsSnapshot
from aqos.accounts.models import TradingAccount
from aqos.funded_rules.models import FundedAccountRules
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


def build_account_summary(account: TradingAccount) -> dict[str, Any]:
    """
    An account as the API describes it in a list.

    Broker references are absent by design. ``broker_credential_ref`` points at
    a stored secret, and ``broker_account_ref`` is an external identifier a read
    API has no reason to hand out; neither is needed to render an account.
    """

    return {
        "account_id": account.account_id,
        "user_id": account.user_id,
        "account_name": account.name,
        "account_type": account.account_type.value,
        "venue": account.broker.value,
        "status": account.status.value,
        "currency": account.currency,
        "execution_mode": account.execution_mode.value,
        "auto_trade_enabled": bool(account.auto_trade_enabled),
        "is_default": bool(account.is_default),
        "is_real_money": account.is_real_money,
        "created_at_utc": isoformat_or_none(account.created_at_utc),
    }


def build_account_detail(account: TradingAccount) -> dict[str, Any]:
    """
    One account with its balances.

    ``extra_metadata`` stays off the wire for the same reason as signals: it is
    free-form JSON written by internal producers and has no vetted allow list.
    """

    detail = build_account_summary(account)
    detail.update(
        {
            "initial_balance": as_number_or_none(account.initial_balance),
            "current_balance": as_number_or_none(account.current_balance),
            "equity": as_number_or_none(account.equity),
            "leverage": account.leverage,
            "is_tradable": account.is_tradable,
            "updated_at_utc": isoformat_or_none(account.updated_at_utc),
        }
    )

    return detail


def build_funded_rules(rules: FundedAccountRules) -> dict[str, Any]:
    """
    Funded rule limits as the API describes them.

    The values are the account's own copied limits, never a live template
    lookup: Sprint 043 copies a template at assignment so a later template edit
    cannot silently move an active account's goalposts.
    """

    return {
        "rules_id": rules.rules_id,
        "account_id": rules.account_id,
        "status": rules.status.value if rules.status else None,
        "is_blocking": rules.is_blocking,
        "is_breached": rules.is_breached,
        "breached_at_utc": isoformat_or_none(rules.breached_at_utc),
        "breach_reason": rules.breach_reason,
        "execution_ceiling": rules.execution_ceiling().value,
        "max_daily_loss_fraction": as_number_or_none(
            rules.max_daily_loss_fraction
        ),
        "max_total_drawdown_fraction": as_number_or_none(
            rules.max_total_drawdown_fraction
        ),
        "profit_target_fraction": as_number_or_none(
            rules.profit_target_fraction
        ),
        "max_risk_per_trade_fraction": as_number_or_none(
            rules.max_risk_per_trade_fraction
        ),
        "drawdown_basis": rules.drawdown_basis.value,
        "max_open_positions": rules.max_open_positions,
        "max_daily_trades": rules.max_daily_trades,
        "min_trading_days": rules.min_trading_days,
        "weekend_holding_allowed": bool(rules.weekend_holding_allowed),
        "news_restriction_enabled": bool(rules.news_restriction_enabled),
        # Provenance only: which template the values were copied from, never a
        # re-read of that template's current contents.
        "copied_from_template_id": rules.template_id,
        "created_at_utc": isoformat_or_none(rules.created_at_utc),
        "updated_at_utc": isoformat_or_none(rules.updated_at_utc),
    }


def build_analytics_snapshot_summary(
    snapshot: AccountAnalyticsSnapshot,
) -> dict[str, Any]:
    """
    A stored analytics snapshot.

    ``profit_factor_state`` travels with the number because infinity has no
    JSON form: without it a wins-and-no-losses account is indistinguishable
    from one that never traded.
    """

    return {
        "snapshot_id": snapshot.snapshot_id,
        "user_id": snapshot.user_id,
        "account_id": snapshot.account_id,
        "scope": snapshot.scope.value if snapshot.scope else None,
        "period_start_utc": isoformat_or_none(snapshot.period_start_utc),
        "period_end_utc": isoformat_or_none(snapshot.period_end_utc),
        "calculated_at_utc": isoformat_or_none(snapshot.calculated_at_utc),
        "signals_received": snapshot.signals_received,
        "signals_executed": snapshot.signals_executed,
        "signals_rejected": snapshot.signals_rejected,
        "signals_missed": snapshot.signals_missed,
        "execution_rate": as_number_or_none(snapshot.execution_rate),
        "rejection_rate": as_number_or_none(snapshot.rejection_rate),
        "trade_metrics_available": bool(snapshot.trade_metrics_available),
        "total_trades": snapshot.total_trades,
        "win_rate": as_number_or_none(snapshot.win_rate),
        "net_pnl": as_number_or_none(snapshot.net_pnl),
        "profit_factor": as_number_or_none(snapshot.profit_factor),
        "profit_factor_state": snapshot.profit_factor_state.value,
        "has_infinite_profit_factor": snapshot.has_infinite_profit_factor,
        "max_drawdown": as_number_or_none(snapshot.max_drawdown),
    }


def build_report_summary(record: Any) -> dict[str, Any]:
    """
    A stored report.

    ``artifact_path`` is a server-side file location and never leaves the
    process. The checksum is withheld too: nothing can download the artifact
    yet, so the digest has no consumer and exposing an unused value is all
    downside.
    """

    return {
        "report_id": record.report_id,
        "user_id": record.user_id,
        "account_id": record.account_id,
        "account_type": record.account_type.value,
        "report_type": record.report_type.value,
        "analytics_snapshot_id": record.analytics_snapshot_id,
        "period_start_utc": isoformat_or_none(record.period_start_utc),
        "period_end_utc": isoformat_or_none(record.period_end_utc),
        "generated_at_utc": isoformat_or_none(record.generated_at_utc),
        "trade_metrics_available": bool(record.trade_metrics_available),
        "artifact_format": record.artifact_format.value,
        "has_artifact": record.artifact_path is not None,
    }


def build_report_detail(record: Any) -> dict[str, Any]:
    """The report plus its already JSON-safe stored payload."""

    detail = build_report_summary(record)
    detail["payload"] = record.payload_json or {}

    return detail


def build_paper_session_summary(record: Any) -> dict[str, Any]:
    """
    A paper session as the API describes it in a list.

    ``profit_factor_state`` travels beside the number because infinity has no
    JSON form: without it a wins-and-no-losses run is indistinguishable from
    one that measured nothing.
    """

    return {
        "session_id": record.session_id,
        "user_id": record.user_id,
        "account_id": record.account_id,
        "session_name": record.session_name,
        "session_type": record.session_type.value,
        "status": record.status.value,
        "is_terminal": record.is_terminal,
        "started_at_utc": isoformat_or_none(record.started_at_utc),
        "ended_at_utc": isoformat_or_none(record.ended_at_utc),
        "total_trades": record.total_trades,
        "net_pnl": as_number_or_none(record.net_pnl),
        "profit_factor": as_number_or_none(record.profit_factor),
        "profit_factor_state": record.profit_factor_state.value,
    }


def build_paper_session_detail(record: Any) -> dict[str, Any]:
    """
    One paper session with its identity and balances.

    ``extra_metadata`` stays off the wire: free-form JSON written by internal
    producers, with no vetted allow list.
    """

    detail = build_paper_session_summary(record)
    detail.update(
        {
            "status_reason": record.status_reason,
            "strategy_name": record.strategy_name,
            "model_id": record.model_id,
            "model_version": record.model_version,
            "symbol": record.symbol,
            "timeframe": record.timeframe,
            "initial_balance": as_number_or_none(record.initial_balance),
            "final_balance": as_number_or_none(record.final_balance),
            "realized_pnl": record.realized_pnl,
            "max_drawdown": as_number_or_none(record.max_drawdown),
            "has_infinite_profit_factor": record.has_infinite_profit_factor,
            "created_at_utc": isoformat_or_none(record.created_at_utc),
            "updated_at_utc": isoformat_or_none(record.updated_at_utc),
        }
    )

    return detail


def build_paper_session_result(result: Any) -> dict[str, Any]:
    """
    A measured session result.

    The contract already reports unknowns as ``None``; this hands them through
    unchanged rather than substituting zeros the run did not earn.
    """

    payload = result.to_dict()
    payload.pop("metadata", None)

    return payload


def build_paper_order(record: Any) -> dict[str, Any]:
    """One persisted paper order, with its rejection reason when refused."""

    return {
        "order_id": record.order_id,
        "session_id": record.session_id,
        "account_id": record.account_id,
        "signal_id": record.signal_id,
        "symbol": record.symbol,
        "action": record.action.value,
        "order_type": record.order_type.value,
        "status": record.status.value,
        "quantity": as_number_or_none(record.quantity),
        "filled_quantity": as_number_or_none(record.filled_quantity),
        "average_fill_price": as_number_or_none(record.average_fill_price),
        "requested_price": as_number_or_none(record.requested_price),
        "stop_loss": as_number_or_none(record.stop_loss),
        "take_profit": as_number_or_none(record.take_profit),
        "rejection_reason": (
            record.rejection_reason.value if record.rejection_reason else None
        ),
        "rejection_message": record.rejection_message,
        "created_at_utc": isoformat_or_none(record.created_at_utc),
        "updated_at_utc": isoformat_or_none(record.updated_at_utc),
    }


def build_paper_fill(record: Any) -> dict[str, Any]:
    return {
        "fill_id": record.fill_id,
        "session_id": record.session_id,
        "order_id": record.order_id,
        "account_id": record.account_id,
        "position_id": record.position_id,
        "quantity": as_number_or_none(record.quantity),
        "price": as_number_or_none(record.price),
        "commission": as_number_or_none(record.commission),
        "filled_at_utc": isoformat_or_none(record.filled_at_utc),
    }


def build_paper_position(record: Any) -> dict[str, Any]:
    return {
        "position_id": record.position_id,
        "session_id": record.session_id,
        "account_id": record.account_id,
        "order_id": record.order_id,
        "signal_id": record.signal_id,
        "symbol": record.symbol,
        "side": record.side.value,
        "status": record.status.value,
        "quantity": as_number_or_none(record.quantity),
        "closed_quantity": as_number_or_none(record.closed_quantity),
        "entry_price": as_number_or_none(record.entry_price),
        "stop_loss": as_number_or_none(record.stop_loss),
        "take_profit": as_number_or_none(record.take_profit),
        "realized_pnl": as_number_or_none(record.realized_pnl),
        "opened_at_utc": isoformat_or_none(record.opened_at_utc),
        "closed_at_utc": isoformat_or_none(record.closed_at_utc),
    }


def build_paper_trade(record: Any) -> dict[str, Any]:
    return {
        "trade_id": record.trade_id,
        "session_id": record.session_id,
        "account_id": record.account_id,
        "position_id": record.position_id,
        "signal_id": record.signal_id,
        "symbol": record.symbol,
        "side": record.side.value,
        "quantity": as_number_or_none(record.quantity),
        "entry_price": as_number_or_none(record.entry_price),
        "exit_price": as_number_or_none(record.exit_price),
        "gross_pnl": as_number_or_none(record.gross_pnl),
        "commission": as_number_or_none(record.commission),
        "net_pnl": as_number_or_none(record.net_pnl),
        "exit_reason": record.exit_reason.value,
        "risk_amount": as_number_or_none(record.risk_amount),
        "reward_amount": as_number_or_none(record.reward_amount),
        "balance_after": as_number_or_none(record.balance_after),
        "opened_at_utc": isoformat_or_none(record.opened_at_utc),
        "closed_at_utc": isoformat_or_none(record.closed_at_utc),
    }


def build_paper_decision(record: Any) -> dict[str, Any]:
    """
    One recorded eligibility decision.

    Refusals keep their structured reason code so a blocked attempt is
    explainable without reading a server log.
    """

    return {
        "decision_id": record.decision_id,
        "session_id": record.session_id,
        "account_id": record.account_id,
        "signal_id": record.signal_id,
        "order_id": record.order_id,
        "symbol": record.symbol,
        "is_allowed": bool(record.is_allowed),
        "requested_execution_mode": record.requested_execution_mode.value,
        "effective_execution_mode": record.effective_execution_mode.value,
        "primary_reason_code": record.primary_reason_code,
        "blocking_reason_count": record.blocking_reason_count,
        "blocking_sources": list(record.blocking_sources_json or ()),
        "reasons": [
            {
                "code": reason.get("code"),
                "source": reason.get("source"),
                "category": reason.get("category"),
                "severity": reason.get("severity"),
                "message": reason.get("message"),
                "is_blocking": reason.get("is_blocking"),
            }
            for reason in (record.reasons_json or ())
        ],
        "decided_at_utc": isoformat_or_none(record.decided_at_utc),
    }


def build_backtest_summary(entry: Any) -> dict[str, Any]:
    """
    One registered backtest run.

    Report, manifest and analytics paths are all withheld: they describe the
    server's disk layout, which a client has no use for.
    """

    return {
        "backtest_id": entry.run_id,
        "created_at_utc": entry.created_at_utc,
        "kind": entry.kind.value,
        "strategy_name": entry.strategy_name,
        "symbol": entry.symbol,
        "timeframe": entry.timeframe,
        "model_id": entry.model_identity.get("model_id"),
        "model_version": entry.model_identity.get("model_version"),
        "metrics": entry.metrics or {},
        "tags": list(entry.tags),
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
    "build_account_detail",
    "build_account_summary",
    "build_analytics_snapshot_summary",
    "build_funded_rules",
    "build_report_detail",
    "build_report_summary",
    "build_backtest_summary",
    "build_paper_decision",
    "build_paper_fill",
    "build_paper_order",
    "build_paper_position",
    "build_paper_session_detail",
    "build_paper_session_result",
    "build_paper_session_summary",
    "build_paper_trade",
    "build_prediction_summary",
    "build_promotion_summary",
    "build_signal_detail",
    "build_signal_event",
    "build_signal_reason",
    "build_signal_summary",
    "isoformat_or_none",
    "parse_enum",
]
