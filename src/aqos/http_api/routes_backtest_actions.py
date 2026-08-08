"""
Backtest execution endpoint.

Historical replay only. The run goes through
:class:`aqos.backtesting.commands.BacktestCommandService`, the one approved way
into backtesting from outside the package; the runner, the simulator, the data
loader and the adapters are unreachable from here, and a guard test proves it.

Nothing in a request names a file, a module or a URL, so no request can make
this process read or execute something the deployment did not configure.
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends

from aqos.backtesting.commands import (
    BacktestCommandError,
    BacktestCommandService,
    BacktestDatasetError,
    BacktestRunCommand,
    BacktestCommandResult,
)
from aqos.http_api.auth import AuthenticatedCaller
from aqos.http_api.backtest_action_schemas import BacktestRunRequest
from aqos.http_api.config import ApiConfig
from aqos.http_api.dependencies import get_api_config
from aqos.http_api.errors import ApiErrorCode, AqosApiError, ValidationApiError
from aqos.http_api.responses import json_response
from aqos.http_api.routes_auth import get_current_caller
from aqos.http_api.routes_backtests import BACKTESTS_PREFIX


AQOS_HTTP_BACKTEST_ACTION_ROUTES_VERSION = "1.0"

BACKTESTS_NOT_CONFIGURED_MESSAGE = (
    "This deployment cannot run backtests: no dataset directory, output "
    "directory or result registry is configured."
)


def require_backtest_service(config: ApiConfig) -> BacktestCommandService:
    """
    The command service, or a refusal.

    A deployment that has not been given somewhere to read bars from, somewhere
    to write artifacts and a registry to record runs in cannot run a backtest.
    That is reported as unavailable rather than defaulted to a directory nobody
    chose.
    """

    if not config.can_run_backtests:
        raise AqosApiError(
            ApiErrorCode.NOT_READY,
            BACKTESTS_NOT_CONFIGURED_MESSAGE,
            details={
                "has_datasets": config.has_backtest_datasets,
                "has_output": config.has_backtest_output,
                "has_registry": config.has_backtest_registry,
            },
        )

    return BacktestCommandService(
        dataset_dir=config.backtest_dataset_dir,
        output_dir=config.backtest_output_dir,
        registry_path=config.backtest_registry_path,
    )


def refuse_unknown_dataset(
    error: BacktestDatasetError,
    service: BacktestCommandService,
) -> ValidationApiError:
    """
    Refuse a dataset, and say which ones exist.

    Listing the configured names is safe and useful: they are names the
    deployment chose, not locations, and a caller who cannot discover them
    cannot use the endpoint at all.
    """

    return ValidationApiError(
        str(error),
        details={
            "available_datasets": [
                dataset.name for dataset in service.list_datasets()
            ]
        },
    )


def build_backtest_result(result: BacktestCommandResult) -> dict[str, Any]:
    """
    One completed or failed run, as the API describes it.

    No paths: the read endpoints serve the artifacts themselves, and where they
    sit on disk is not a client's business. ``status`` is only ever
    ``completed`` or ``failed``, because the run happened inside this request
    and there is no queue to report.
    """

    return {
        "backtest": {
            "backtest_id": result.backtest_id,
            "user_id": result.user_id,
            "status": result.status,
            "strategy_name": result.strategy_name,
            "dataset": result.dataset,
            "symbol": result.symbol,
            "timeframe": result.timeframe,
            "period_start": result.period_start,
            "period_end": result.period_end,
            "rows_loaded": result.rows_loaded,
            "metrics": result.metrics,
            # A null profit factor is ambiguous without this: it means
            # either "won every trade" or "nothing to divide", never zero.
            "profit_factor_state": result.profit_factor_state,
            "model_identity": result.model_identity,
            "created_at_utc": result.created_at_utc,
            "completed_at_utc": result.completed_at_utc,
            "failure_reason": result.failure_reason,
        }
    }


def build_backtest_actions_router() -> APIRouter:
    router = APIRouter(prefix=BACKTESTS_PREFIX, tags=["backtest-actions"])

    @router.post("", status_code=201)
    def run_backtest(
        payload: BacktestRunRequest,
        config: ApiConfig = Depends(get_api_config),
        caller: AuthenticatedCaller = Depends(get_current_caller),
    ):
        """
        Run one historical backtest and register its result.

        Synchronous: by the time this returns the artifacts exist and the run
        is readable through the backtest read endpoints. A simulation that
        breaks comes back as a ``failed`` run rather than an error, because the
        attempt is a fact; a request that could not be run at all is refused
        before anything happens.
        """

        service = require_backtest_service(config)

        try:
            result = service.run(
                BacktestRunCommand(
                    # Never from the body: a run belongs to whoever asked for
                    # it, and the token is the only thing that says who that is.
                    user_id=caller.user_id,
                    strategy_name=payload.strategy_name,
                    dataset=payload.dataset,
                    symbol=payload.symbol,
                    timeframe=payload.timeframe,
                    period_start=payload.period_start,
                    period_end=payload.period_end,
                    initial_balance=payload.initial_balance,
                    risk_fraction=payload.risk_fraction,
                    fixed_quantity=payload.fixed_quantity,
                    spread_points=payload.spread_points,
                    slippage_points=payload.slippage_points,
                    commission_per_trade=payload.commission_per_trade,
                    allow_short=payload.allow_short,
                    max_open_positions=payload.max_open_positions,
                    model_id=payload.model_id,
                    model_version=payload.model_version,
                )
            )
        except BacktestDatasetError as error:
            raise refuse_unknown_dataset(error, service) from error
        except BacktestCommandError as error:
            raise ValidationApiError(str(error)) from error

        return json_response(build_backtest_result(result), status_code=201)

    return router


__all__ = [
    "AQOS_HTTP_BACKTEST_ACTION_ROUTES_VERSION",
    "BACKTESTS_NOT_CONFIGURED_MESSAGE",
    "build_backtest_actions_router",
    "build_backtest_result",
    "refuse_unknown_dataset",
    "require_backtest_service",
]
