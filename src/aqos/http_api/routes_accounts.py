from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from aqos.account_analytics.service import (
    AccountAnalyticsService,
    AccountAnalyticsSnapshotRepository,
)
from aqos.account_reports.contracts import ReportType
from aqos.account_reports.repositories import (
    AccountPerformanceReportRepository,
)
from aqos.accounts.models import AccountStatus, AccountType, BrokerKind
from aqos.accounts.repositories import TradingAccountRepository
from aqos.execution_policy.modes import (
    ExecutionConstraint,
    ExecutionConstraintSource,
    ExecutionMode,
    resolve_execution_mode,
)
from aqos.funded_rules.repositories import FundedAccountRulesRepository
from aqos.http_api.dependencies import get_session
from aqos.http_api.errors import NotFoundApiError
from aqos.http_api.pagination import (
    MAX_PAGE_LIMIT,
    build_page,
    validate_limit,
    validate_offset,
)
from aqos.http_api.read_schemas import (
    build_account_detail,
    build_account_summary,
    build_analytics_snapshot_summary,
    build_funded_rules,
    build_report_detail,
    build_report_summary,
    parse_enum,
)
from aqos.http_api.responses import json_response
from aqos.trading_settings.repositories import TradingSettingsRepository


AQOS_HTTP_ACCOUNT_ROUTES_VERSION = "1.0"

ACCOUNTS_PREFIX = "/accounts"

#: Why this endpoint reports no trade source.
#:
#: Machine readable so a client can distinguish "this boundary does not supply
#: trades" from "this account has no trades". They are different facts and only
#: one of them is about the account.
TRADE_SOURCE_NOT_CONNECTED_CODE = (
    "paper_trade_source_not_connected_at_api_boundary"
)

TRADE_SOURCE_NOT_CONNECTED_REASON = (
    "This endpoint connects no trade source, so trade results are unknown "
    "rather than zero. Measured trade metrics are available from stored "
    "analytics snapshots."
)


def require_account(session: Session, account_id: str):
    account = TradingAccountRepository(session).get(account_id)

    if account is None:
        raise NotFoundApiError(
            "Account was not found.",
            details={"account_id": account_id},
        )

    return account


def collect_account_constraints(
    session: Session,
    account,
) -> tuple[ExecutionConstraint, ...]:
    """
    Every ceiling that applies to this account today.

    The account always contributes one, so the resolver is never called with an
    empty set and can never hand back the requested mode unchecked.
    """

    constraints = [
        ExecutionConstraint(
            source=ExecutionConstraintSource.ACCOUNT,
            ceiling=account.execution_mode,
            reason="Account execution mode.",
        )
    ]

    settings = TradingSettingsRepository(session).get_for_user(account.user_id)

    if settings is not None:
        constraints.append(
            ExecutionConstraint(
                source=ExecutionConstraintSource.USER_SETTINGS,
                ceiling=settings.execution_mode,
                reason="User trading settings execution mode.",
            )
        )

    rules = FundedAccountRulesRepository(session).get_for_account(
        account.account_id
    )

    if rules is not None:
        constraints.append(rules.execution_constraint())

    return tuple(constraints)


def build_accounts_router() -> APIRouter:
    router = APIRouter(prefix=ACCOUNTS_PREFIX, tags=["accounts"])

    @router.get("")
    def list_accounts(
        session: Session = Depends(get_session),
        user_id: str | None = None,
        account_type: str | None = None,
        venue: str | None = None,
        status: str | None = None,
        execution_mode: str | None = None,
        limit: int | None = Query(default=None, le=MAX_PAGE_LIMIT * 10),
        offset: int | None = None,
    ):
        resolved_limit = validate_limit(limit)
        resolved_offset = validate_offset(offset)

        records = TradingAccountRepository(session).list_accounts(
            user_id=user_id,
            account_type=parse_enum(account_type, AccountType, "account_type"),
            status=parse_enum(status, AccountStatus, "status"),
            broker=parse_enum(venue, BrokerKind, "venue"),
            execution_mode=parse_enum(
                execution_mode,
                ExecutionMode,
                "execution_mode",
            ),
        )
        window = records[resolved_offset : resolved_offset + resolved_limit]

        page = build_page(
            items=[build_account_summary(record) for record in window],
            limit=resolved_limit,
            offset=resolved_offset,
            total=None,
        )

        return json_response(page.to_dict())

    @router.get("/{account_id}")
    def get_account(
        account_id: str,
        session: Session = Depends(get_session),
    ):
        return json_response(
            build_account_detail(require_account(session, account_id))
        )

    @router.get("/{account_id}/execution-constraints")
    def get_execution_constraints(
        account_id: str,
        session: Session = Depends(get_session),
    ):
        """
        Why this account may or may not act autonomously.

        Read-only, and deliberately paired with no endpoint that changes the
        mode: raising an execution ceiling is a decision, not a GET.
        """

        account = require_account(session, account_id)
        constraints = collect_account_constraints(session, account)

        decision = resolve_execution_mode(
            requested=ExecutionMode.AUTO_TRADE,
            constraints=constraints,
        )

        return json_response(
            {
                "account_id": account.account_id,
                "stored_execution_mode": account.execution_mode.value,
                "auto_trade_enabled": bool(account.auto_trade_enabled),
                "requested_execution_mode": decision.requested.value,
                "effective_execution_mode": decision.effective.value,
                "was_downgraded": decision.was_downgraded,
                "allows_orders": decision.allows_orders,
                "requires_manual_approval": decision.requires_manual_approval,
                "binding_sources": list(decision.binding_sources),
                "explanation": decision.explain(),
                "constraints": [
                    constraint.to_dict() for constraint in decision.constraints
                ],
            }
        )

    @router.get("/{account_id}/funded-rules")
    def get_funded_rules(
        account_id: str,
        session: Session = Depends(get_session),
    ):
        account = require_account(session, account_id)
        rules = FundedAccountRulesRepository(session).get_for_account(
            account.account_id
        )

        if rules is None:
            raise NotFoundApiError(
                "This account has no funded rules assigned.",
                details={"account_id": account_id},
            )

        return json_response(build_funded_rules(rules))

    @router.get("/{account_id}/analytics")
    def get_account_analytics(
        account_id: str,
        session: Session = Depends(get_session),
    ):
        """
        Analytics calculated now from the account's real lifecycle rows.

        Signal and reason metrics are measured; trade metrics report as
        unavailable because this endpoint connects no trade source. Wiring the
        simulated-trade source in would make this package depend on the paper
        simulator, which the isolation guard forbids so the simulator stays a
        leaf no execution path can reach into. Stored snapshots under
        ``/analytics/snapshots`` do carry measured trade metrics.
        """

        account = require_account(session, account_id)

        analytics = AccountAnalyticsService(
            session,
        ).build_account_analytics(
            user_id=account.user_id,
            account_id=account.account_id,
            starting_balance=float(account.initial_balance),
        )

        payload = analytics.to_dict()
        # Stated explicitly so "unavailable" can never be read as a measured
        # zero, and so a client knows where the real numbers do live.
        payload["trade_metrics_source"] = {
            "connected": False,
            "reason_code": TRADE_SOURCE_NOT_CONNECTED_CODE,
            "reason": TRADE_SOURCE_NOT_CONNECTED_REASON,
            "measured_metrics_endpoint": (
                f"{ACCOUNTS_PREFIX}/{account.account_id}/analytics/snapshots"
            ),
        }

        return json_response(payload)

    @router.get("/{account_id}/analytics/snapshots")
    def list_analytics_snapshots(
        account_id: str,
        session: Session = Depends(get_session),
        limit: int | None = Query(default=None, le=MAX_PAGE_LIMIT * 10),
        offset: int | None = None,
    ):
        resolved_limit = validate_limit(limit)
        resolved_offset = validate_offset(offset)

        account = require_account(session, account_id)

        records = AccountAnalyticsSnapshotRepository(session).list_snapshots(
            account_id=account.account_id,
        )
        window = records[resolved_offset : resolved_offset + resolved_limit]

        page = build_page(
            items=[
                build_analytics_snapshot_summary(record) for record in window
            ],
            limit=resolved_limit,
            offset=resolved_offset,
            total=len(records),
        )

        return json_response(page.to_dict())

    @router.get("/{account_id}/reports")
    def list_reports(
        account_id: str,
        session: Session = Depends(get_session),
        report_type: str | None = None,
        limit: int | None = Query(default=None, le=MAX_PAGE_LIMIT * 10),
        offset: int | None = None,
    ):
        resolved_limit = validate_limit(limit)
        resolved_offset = validate_offset(offset)

        account = require_account(session, account_id)

        records = AccountPerformanceReportRepository(session).list_reports(
            account_id=account.account_id,
            report_type=parse_enum(report_type, ReportType, "report_type"),
        )
        window = records[resolved_offset : resolved_offset + resolved_limit]

        page = build_page(
            items=[build_report_summary(record) for record in window],
            limit=resolved_limit,
            offset=resolved_offset,
            total=len(records),
        )

        return json_response(page.to_dict())

    @router.get("/{account_id}/reports/{report_id}")
    def get_report(
        account_id: str,
        report_id: str,
        session: Session = Depends(get_session),
    ):
        account = require_account(session, account_id)

        record = AccountPerformanceReportRepository(session).get(report_id)

        # Scoped to the account in the path: a report id alone must not reach
        # across into another account's data.
        if record is None or record.account_id != account.account_id:
            raise NotFoundApiError(
                "Report was not found for this account.",
                details={"account_id": account_id, "report_id": report_id},
            )

        return json_response(build_report_detail(record))

    return router


__all__ = [
    "ACCOUNTS_PREFIX",
    "TRADE_SOURCE_NOT_CONNECTED_CODE",
    "TRADE_SOURCE_NOT_CONNECTED_REASON",
    "AQOS_HTTP_ACCOUNT_ROUTES_VERSION",
    "build_accounts_router",
    "collect_account_constraints",
    "require_account",
]
