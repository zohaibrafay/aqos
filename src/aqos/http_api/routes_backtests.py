from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from fastapi import APIRouter, Depends, Query

from aqos.backtesting.registry import (
    BacktestKind,
    read_backtest_result_registry,
)
from aqos.http_api.config import ApiConfig
from aqos.http_api.auth import AuthenticatedCaller
from aqos.http_api.authz import get_read_only_caller
from aqos.http_api.dependencies import get_api_config
from aqos.http_api.errors import ApiErrorCode, AqosApiError, NotFoundApiError
from aqos.http_api.pagination import (
    MAX_PAGE_LIMIT,
    apply_offset_limit,
    build_page,
    validate_limit,
    validate_offset,
)
from aqos.http_api.read_schemas import build_backtest_summary, parse_enum
from aqos.http_api.responses import json_response


AQOS_HTTP_BACKTEST_ROUTES_VERSION = "1.0"

BACKTESTS_PREFIX = "/backtests"

REGISTRY_UNAVAILABLE_MESSAGE = (
    "This deployment has no backtest registry configured, so backtest results "
    "are unavailable rather than empty."
)

#: Sections of a stored report that may be served.
#:
#: Everything else in a report file is withheld: reports carry absolute paths
#: and run configuration that a client has no use for.
SERVABLE_REPORT_SECTIONS = ("trades", "orders", "equity_curve")


def require_registry(config: ApiConfig):
    """
    Read the configured registry, or refuse the request.

    An unconfigured or missing registry is reported as unavailable rather than
    as an empty list: "nothing configured" and "configured with no runs" are
    different facts a client must be able to tell apart.
    """

    if not config.has_backtest_registry:
        raise AqosApiError(
            ApiErrorCode.NOT_READY,
            REGISTRY_UNAVAILABLE_MESSAGE,
            details={"registry": "backtest", "configured": False},
        )

    path = Path(config.backtest_registry_path)

    if not path.exists():
        raise AqosApiError(
            ApiErrorCode.NOT_READY,
            REGISTRY_UNAVAILABLE_MESSAGE,
            details={"registry": "backtest", "configured": True},
        )

    return read_backtest_result_registry(path)


def owner_of(entry: Any) -> str | None:
    """
    Whose run this was, if anybody's.

    Runs started through the API carry the caller's id in their registry
    metadata. Runs produced outside it — by the CLI, or by a research script —
    carry none, and are treated as deployment-level artifacts rather than as
    belonging to nobody and therefore hidden from everybody.
    """

    metadata = getattr(entry, "metadata", None) or {}
    user_id = metadata.get("user_id")

    return str(user_id) if user_id else None


def visible_to(entry: Any, caller: AuthenticatedCaller) -> bool:
    owner = owner_of(entry)

    return owner is None or owner == caller.user_id


def require_entry(config: ApiConfig, backtest_id: str, caller: AuthenticatedCaller):
    """
    Load a run the caller may see, or refuse.

    Another user's run answers exactly like one that does not exist, so run ids
    cannot be probed across accounts.
    """

    for entry in require_registry(config).results:
        if entry.run_id != backtest_id:
            continue

        if visible_to(entry, caller):
            return entry

        break

    raise NotFoundApiError(
        "Backtest result was not found.",
        details={"backtest_id": backtest_id},
    )


def read_report_section(entry: Any, section: str) -> list[dict[str, Any]]:
    """
    Read one section out of a run's stored report.

    The report path comes from the registry and is never returned; only the
    rows are. A report that is registered but no longer on disk is reported as
    unavailable rather than as an empty section, because an empty list would
    claim the run produced nothing.
    """

    if section not in SERVABLE_REPORT_SECTIONS:
        raise NotFoundApiError(
            "Unknown backtest section.",
            details={"section": section},
        )

    path = Path(entry.report_path)

    if not path.exists():
        raise AqosApiError(
            ApiErrorCode.NOT_READY,
            "The stored report for this backtest is not available.",
            details={"backtest_id": entry.run_id},
        )

    payload = json.loads(path.read_text(encoding="utf-8"))
    rows = payload.get(section)

    if rows is None:
        return []

    return [row for row in rows if isinstance(row, dict)]


def build_backtests_router() -> APIRouter:
    router = APIRouter(prefix=BACKTESTS_PREFIX, tags=["backtests"])

    def section_response(
        backtest_id: str,
        section: str,
        config: ApiConfig,
        caller: AuthenticatedCaller,
        limit: int | None,
        offset: int | None,
    ):
        resolved_limit = validate_limit(limit)
        resolved_offset = validate_offset(offset)

        entry = require_entry(config, backtest_id, caller)
        rows = read_report_section(entry, section)
        window = apply_offset_limit(rows, resolved_limit, resolved_offset)

        payload = build_page(
            items=list(window),
            limit=resolved_limit,
            offset=resolved_offset,
            total=len(rows),
        ).to_dict()
        payload["backtest_id"] = backtest_id

        return json_response(payload)

    @router.get("")
    def list_backtests(
        config: ApiConfig = Depends(get_api_config),
        caller: AuthenticatedCaller = Depends(get_read_only_caller),
        kind: str | None = None,
        symbol: str | None = None,
        strategy_name: str | None = None,
        limit: int | None = Query(default=None, le=MAX_PAGE_LIMIT * 10),
        offset: int | None = None,
    ):
        resolved_limit = validate_limit(limit)
        resolved_offset = validate_offset(offset)

        entries = tuple(
            entry
            for entry in require_registry(config).results
            if visible_to(entry, caller)
        )
        resolved_kind = parse_enum(kind, BacktestKind, "kind")

        if resolved_kind is not None:
            entries = tuple(
                entry for entry in entries if entry.kind == resolved_kind
            )

        if symbol is not None:
            entries = tuple(
                entry for entry in entries if entry.symbol == symbol
            )

        if strategy_name is not None:
            entries = tuple(
                entry
                for entry in entries
                if entry.strategy_name == strategy_name
            )

        window = apply_offset_limit(entries, resolved_limit, resolved_offset)

        page = build_page(
            items=[build_backtest_summary(entry) for entry in window],
            limit=resolved_limit,
            offset=resolved_offset,
            total=len(entries),
        )

        return json_response(page.to_dict())

    @router.get("/{backtest_id}")
    def get_backtest(
        backtest_id: str,
        config: ApiConfig = Depends(get_api_config),
        caller: AuthenticatedCaller = Depends(get_read_only_caller),
    ):
        return json_response(
            build_backtest_summary(require_entry(config, backtest_id, caller))
        )

    @router.get("/{backtest_id}/trades")
    def get_backtest_trades(
        backtest_id: str,
        config: ApiConfig = Depends(get_api_config),
        caller: AuthenticatedCaller = Depends(get_read_only_caller),
        limit: int | None = Query(default=None, le=MAX_PAGE_LIMIT * 10),
        offset: int | None = None,
    ):
        return section_response(
            backtest_id,
            "trades",
            config,
            caller,
            limit,
            offset,
        )

    @router.get("/{backtest_id}/orders")
    def get_backtest_orders(
        backtest_id: str,
        config: ApiConfig = Depends(get_api_config),
        caller: AuthenticatedCaller = Depends(get_read_only_caller),
        limit: int | None = Query(default=None, le=MAX_PAGE_LIMIT * 10),
        offset: int | None = None,
    ):
        return section_response(
            backtest_id,
            "orders",
            config,
            caller,
            limit,
            offset,
        )

    @router.get("/{backtest_id}/equity")
    def get_backtest_equity(
        backtest_id: str,
        config: ApiConfig = Depends(get_api_config),
        caller: AuthenticatedCaller = Depends(get_read_only_caller),
        limit: int | None = Query(default=None, le=MAX_PAGE_LIMIT * 10),
        offset: int | None = None,
    ):
        return section_response(
            backtest_id,
            "equity_curve",
            config,
            caller,
            limit,
            offset,
        )

    return router


__all__ = [
    "AQOS_HTTP_BACKTEST_ROUTES_VERSION",
    "BACKTESTS_PREFIX",
    "REGISTRY_UNAVAILABLE_MESSAGE",
    "SERVABLE_REPORT_SECTIONS",
    "build_backtests_router",
    "owner_of",
    "read_report_section",
    "require_entry",
    "require_registry",
    "visible_to",
]
