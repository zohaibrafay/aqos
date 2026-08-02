from __future__ import annotations

from datetime import datetime
from typing import Any, Sequence

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from aqos.account_analytics.metrics import (
    AccountTradeRecord,
    ReasonMetrics,
    SignalMetrics,
    TradeMetrics,
    calculate_reason_metrics,
    calculate_signal_metrics,
    calculate_trade_metrics,
)
from aqos.account_analytics.models import (
    AccountAnalytics,
    AccountAnalyticsSnapshot,
    AnalyticsScope,
)
from aqos.database.repository import AqosRepository
from aqos.database.types import database_utc_now
from aqos.signals.models import SignalStatus, TradingSignal
from aqos.signal_reasons.models import SignalReason
from aqos.users.repositories import build_entity_id


AQOS_ACCOUNT_ANALYTICS_SERVICE_VERSION = "1.0"

NO_TRADE_SOURCE_REASON = (
    "No trade source is connected yet; paper trading lands in a later sprint."
)


class AccountAnalyticsSnapshotRepository(AqosRepository[AccountAnalyticsSnapshot]):
    """Persisted analytics results."""

    model = AccountAnalyticsSnapshot

    def save_snapshot(
        self,
        analytics: AccountAnalytics,
        snapshot_id: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> AccountAnalyticsSnapshot:
        trade_metrics = analytics.trade_metrics
        available = trade_metrics.is_available

        snapshot = AccountAnalyticsSnapshot(
            snapshot_id=snapshot_id or build_entity_id("analytics"),
            user_id=analytics.user_id,
            account_id=analytics.account_id,
            scope=analytics.scope,
            period_start_utc=analytics.period_start_utc,
            period_end_utc=analytics.period_end_utc,
            calculated_at_utc=analytics.calculated_at_utc,
            signals_received=analytics.signal_metrics.signals_received,
            signals_approved=analytics.signal_metrics.signals_approved,
            signals_rejected=analytics.signal_metrics.signals_rejected,
            signals_missed=analytics.signal_metrics.signals_missed,
            signals_expired=analytics.signal_metrics.signals_expired,
            signals_executed=analytics.signal_metrics.signals_executed,
            signals_failed=analytics.signal_metrics.signals_failed,
            execution_rate=analytics.signal_metrics.execution_rate,
            rejection_rate=analytics.signal_metrics.rejection_rate,
            missed_rate=analytics.signal_metrics.missed_rate,
            reason_total=analytics.reason_metrics.total,
            reason_blocking_total=analytics.reason_metrics.blocking_total,
            reason_critical_total=analytics.reason_metrics.critical_total,
            trade_metrics_available=available,
            total_trades=trade_metrics.total_trades if available else None,
            win_rate=trade_metrics.win_rate if available else None,
            net_pnl=trade_metrics.net_pnl if available else None,
            profit_factor=(
                trade_metrics.profit_factor
                if available and trade_metrics.profit_factor not in (float("inf"),)
                else None
            ),
            max_drawdown=trade_metrics.max_drawdown if available else None,
            payload_json=analytics.to_dict(),
            extra_metadata=metadata or {},
        )
        snapshot.assert_trade_metrics_are_honest()

        self.add(snapshot)
        self.flush()

        return snapshot

    def list_snapshots(
        self,
        user_id: str | None = None,
        account_id: str | None = None,
        scope: AnalyticsScope | None = None,
    ) -> tuple[AccountAnalyticsSnapshot, ...]:
        statement = select(AccountAnalyticsSnapshot)

        if user_id is not None:
            statement = statement.where(
                AccountAnalyticsSnapshot.user_id == user_id
            )

        if account_id is not None:
            statement = statement.where(
                AccountAnalyticsSnapshot.account_id == account_id
            )

        if scope is not None:
            statement = statement.where(AccountAnalyticsSnapshot.scope == scope)

        statement = statement.order_by(
            AccountAnalyticsSnapshot.calculated_at_utc,
            AccountAnalyticsSnapshot.snapshot_id,
        )

        return tuple(self.session.execute(statement).scalars().all())

    def latest_snapshot(
        self,
        account_id: str,
    ) -> AccountAnalyticsSnapshot | None:
        snapshots = self.list_snapshots(account_id=account_id)

        return snapshots[-1] if snapshots else None


class AccountAnalyticsService:
    """
    Calculates account analytics from the real lifecycle and reason tables.

    Trade metrics are reported as unavailable until a trade source exists.
    Nothing here invents a trade.
    """

    def __init__(
        self,
        session: Session,
        trade_source: Sequence[AccountTradeRecord] | None = None,
    ) -> None:
        if session is None:
            raise ValueError("A SQLAlchemy session is required.")

        self.session = session
        self.trade_source = trade_source

    def signal_status_counts(
        self,
        user_id: str | None = None,
        account_id: str | None = None,
        period_start_utc: datetime | None = None,
        period_end_utc: datetime | None = None,
    ) -> dict[str, int]:
        statement = select(TradingSignal.status, func.count()).group_by(
            TradingSignal.status
        )

        if user_id is not None:
            statement = statement.where(TradingSignal.user_id == user_id)

        if account_id is not None:
            statement = statement.where(TradingSignal.account_id == account_id)

        if period_start_utc is not None:
            statement = statement.where(
                TradingSignal.generated_at_utc >= period_start_utc
            )

        if period_end_utc is not None:
            statement = statement.where(
                TradingSignal.generated_at_utc <= period_end_utc
            )

        rows = self.session.execute(statement).all()

        return {
            (row[0].value if hasattr(row[0], "value") else str(row[0])): int(row[1])
            for row in rows
        }

    def calculate_signal_metrics(
        self,
        user_id: str | None = None,
        account_id: str | None = None,
        period_start_utc: datetime | None = None,
        period_end_utc: datetime | None = None,
    ) -> SignalMetrics:
        return calculate_signal_metrics(
            self.signal_status_counts(
                user_id=user_id,
                account_id=account_id,
                period_start_utc=period_start_utc,
                period_end_utc=period_end_utc,
            )
        )

    def load_reasons(
        self,
        user_id: str | None = None,
        account_id: str | None = None,
        period_start_utc: datetime | None = None,
        period_end_utc: datetime | None = None,
    ) -> tuple[SignalReason, ...]:
        statement = select(SignalReason)

        if user_id is not None:
            statement = statement.where(SignalReason.user_id == user_id)

        if account_id is not None:
            statement = statement.where(SignalReason.account_id == account_id)

        if period_start_utc is not None:
            statement = statement.where(
                SignalReason.created_at_utc >= period_start_utc
            )

        if period_end_utc is not None:
            statement = statement.where(
                SignalReason.created_at_utc <= period_end_utc
            )

        return tuple(self.session.execute(statement).scalars().all())

    def calculate_reason_metrics(
        self,
        user_id: str | None = None,
        account_id: str | None = None,
        period_start_utc: datetime | None = None,
        period_end_utc: datetime | None = None,
    ) -> ReasonMetrics:
        return calculate_reason_metrics(
            self.load_reasons(
                user_id=user_id,
                account_id=account_id,
                period_start_utc=period_start_utc,
                period_end_utc=period_end_utc,
            )
        )

    def resolve_trade_metrics(
        self,
        starting_balance: float | None = None,
    ) -> TradeMetrics:
        """
        Trade metrics from the configured trade source.

        With no source, the result is explicitly unavailable rather than a set
        of zeros that would read as a measured result.
        """

        if self.trade_source is None:
            return TradeMetrics.unavailable(NO_TRADE_SOURCE_REASON)

        return calculate_trade_metrics(
            self.trade_source,
            starting_balance=starting_balance,
        )

    def build_account_analytics(
        self,
        user_id: str,
        account_id: str,
        period_start_utc: datetime | None = None,
        period_end_utc: datetime | None = None,
        starting_balance: float | None = None,
        calculated_at_utc: datetime | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> AccountAnalytics:
        return AccountAnalytics(
            scope=AnalyticsScope.ACCOUNT,
            user_id=user_id,
            account_id=account_id,
            period_start_utc=period_start_utc,
            period_end_utc=period_end_utc,
            calculated_at_utc=calculated_at_utc or database_utc_now(),
            signal_metrics=self.calculate_signal_metrics(
                user_id=user_id,
                account_id=account_id,
                period_start_utc=period_start_utc,
                period_end_utc=period_end_utc,
            ),
            reason_metrics=self.calculate_reason_metrics(
                user_id=user_id,
                account_id=account_id,
                period_start_utc=period_start_utc,
                period_end_utc=period_end_utc,
            ),
            trade_metrics=self.resolve_trade_metrics(starting_balance),
            extra_metadata=metadata or {},
        )

    def build_user_analytics(
        self,
        user_id: str,
        period_start_utc: datetime | None = None,
        period_end_utc: datetime | None = None,
        starting_balance: float | None = None,
        calculated_at_utc: datetime | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> AccountAnalytics:
        return AccountAnalytics(
            scope=AnalyticsScope.USER,
            user_id=user_id,
            period_start_utc=period_start_utc,
            period_end_utc=period_end_utc,
            calculated_at_utc=calculated_at_utc or database_utc_now(),
            signal_metrics=self.calculate_signal_metrics(
                user_id=user_id,
                period_start_utc=period_start_utc,
                period_end_utc=period_end_utc,
            ),
            reason_metrics=self.calculate_reason_metrics(
                user_id=user_id,
                period_start_utc=period_start_utc,
                period_end_utc=period_end_utc,
            ),
            trade_metrics=self.resolve_trade_metrics(starting_balance),
            extra_metadata=metadata or {},
        )


__all__ = [
    "AQOS_ACCOUNT_ANALYTICS_SERVICE_VERSION",
    "AccountAnalyticsService",
    "AccountAnalyticsSnapshotRepository",
    "NO_TRADE_SOURCE_REASON",
]
