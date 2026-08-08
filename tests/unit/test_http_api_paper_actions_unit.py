"""
Unit tests for the paper action layer that need no database.

The lifecycle rules belong to Sprint 052, the eligibility gate to Sprint 050
and the simulator to Sprint 049; each is tested where it lives. What is tested
here is the edge: what a client is allowed to send, what the command surface
offers, and what comes back.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

import pytest
from pydantic import ValidationError

from aqos.execution_policy.modes import ExecutionMode
from aqos.http_api.errors import ApiErrorCode, AqosApiError, ValidationApiError
from aqos.http_api.paper_action_schemas import (
    MAX_ORDER_QUANTITY,
    MAX_PRICE,
    PaperMarketBarRequest,
    PaperOrderRequest,
    PaperPositionCloseRequest,
    PaperSessionActionRequest,
    PaperSessionCreateRequest,
)
from aqos.http_api.routes_paper_actions import (
    PAPER_ACTION_COMMANDS,
    build_order_outcome,
    build_session_transition,
    refuse_paper_command,
    require_enum,
)
from aqos.paper_trading.commands import (
    COMMANDED_EXECUTION_MODE,
    PAPER_SESSION_COMMANDS,
    REASON_REQUIRED_SESSION_COMMANDS,
    PaperCommandError,
    PaperOrderOutcome,
)
from aqos.paper_trading.contracts import PaperAction, PaperOrderType
from aqos.paper_trading.sessions import (
    PAPER_SESSION_TRANSITIONS,
    PaperSessionStatus,
    PaperSessionType,
)


FIXED_NOW = datetime(2026, 1, 1, 12, 0, 0)

VALID_BAR = {
    "symbol": "XAUUSD",
    "timestamp_utc": FIXED_NOW,
    "open": 100.0,
    "high": 101.0,
    "low": 99.0,
    "close": 100.5,
}

VALID_ORDER = {
    "symbol": "XAUUSD",
    "action": "buy",
    "order_type": "market",
    "quantity": 1.0,
    "market": VALID_BAR,
}


@dataclass
class FakeSession:
    status: PaperSessionStatus = PaperSessionStatus.RUNNING
    status_reason: str | None = None
    updated_at_utc: datetime | None = FIXED_NOW
    ended_at_utc: datetime | None = None


class TestCommandSurface:
    def test_the_session_commands_are_exactly_these(self) -> None:
        assert set(PAPER_SESSION_COMMANDS) == {
            "start",
            "pause",
            "resume",
            "complete",
            "cancel",
            "fail",
        }

    def test_the_routes_offer_the_same_commands(self) -> None:
        """The HTTP surface and the command surface cannot drift apart."""

        assert set(PAPER_ACTION_COMMANDS) == set(PAPER_SESSION_COMMANDS)

    def test_every_command_targets_a_real_status(self) -> None:
        for status in PAPER_SESSION_COMMANDS.values():
            assert status in PAPER_SESSION_TRANSITIONS

    def test_stopping_a_run_always_says_why(self) -> None:
        assert set(REASON_REQUIRED_SESSION_COMMANDS) == {"cancel", "fail"}

    def test_a_command_never_claims_to_be_autonomous(self) -> None:
        """
        Somebody chose to send this order, so it is not auto-trading.

        Claiming otherwise would let a manual submission satisfy rules written
        for an account that is allowed to trade by itself.
        """

        assert COMMANDED_EXECUTION_MODE is ExecutionMode.MANUAL_APPROVAL
        assert COMMANDED_EXECUTION_MODE is not ExecutionMode.AUTO_TRADE


class TestSessionCreateRequest:
    def test_a_minimal_request_is_accepted(self) -> None:
        payload = PaperSessionCreateRequest(
            account_id="account_1",
            session_name="Run",
            session_type=PaperSessionType.MANUAL_PAPER_SESSION.value,
        )

        assert payload.model_id is None
        assert payload.strategy_name is None

    @pytest.mark.parametrize(
        "field",
        ["account_id", "session_name", "session_type"],
    )
    def test_every_required_field_is_required(self, field: str) -> None:
        payload = {
            "account_id": "account_1",
            "session_name": "Run",
            "session_type": PaperSessionType.MANUAL_PAPER_SESSION.value,
        }
        payload.pop(field)

        with pytest.raises(ValidationError):
            PaperSessionCreateRequest(**payload)

    @pytest.mark.parametrize(
        "field, value",
        [
            ("user_id", "user_someone_else"),
            ("initial_balance", 1_000_000.0),
            ("status", "running"),
            ("metadata", {"anything": True}),
            ("extra_metadata", {"anything": True}),
        ],
    )
    def test_smuggling_an_extra_field_is_refused(
        self,
        field: str,
        value,
    ) -> None:
        """
        The owner, the balance and the starting status are not the client's.

        Ownership comes from the token, the balance from the account and the
        status from the lifecycle; accepting any of them here would let a
        caller open a run that never matched its account.
        """

        with pytest.raises(ValidationError):
            PaperSessionCreateRequest(
                account_id="account_1",
                session_name="Run",
                session_type=PaperSessionType.MANUAL_PAPER_SESSION.value,
                **{field: value},
            )

    def test_an_empty_name_is_refused(self) -> None:
        with pytest.raises(ValidationError):
            PaperSessionCreateRequest(
                account_id="account_1",
                session_name="",
                session_type=PaperSessionType.MANUAL_PAPER_SESSION.value,
            )


class TestMarketBarRequest:
    def test_a_valid_bar_is_accepted(self) -> None:
        assert PaperMarketBarRequest(**VALID_BAR).volume == 0.0

    @pytest.mark.parametrize("field", ["open", "high", "low", "close"])
    def test_a_non_positive_price_is_refused(self, field: str) -> None:
        payload = dict(VALID_BAR)
        payload[field] = 0.0

        with pytest.raises(ValidationError):
            PaperMarketBarRequest(**payload)

    def test_a_negative_volume_is_refused(self) -> None:
        with pytest.raises(ValidationError):
            PaperMarketBarRequest(**VALID_BAR, volume=-1.0)

    def test_an_absurd_price_is_refused(self) -> None:
        """A bound at the edge, so nothing silly reaches the arithmetic."""

        payload = dict(VALID_BAR)
        payload["close"] = MAX_PRICE * 10

        with pytest.raises(ValidationError):
            PaperMarketBarRequest(**payload)


class TestOrderRequest:
    def test_a_minimal_order_is_accepted(self) -> None:
        payload = PaperOrderRequest(**VALID_ORDER)

        assert payload.signal_id is None
        assert payload.stop_loss is None

    def test_the_market_is_required(self) -> None:
        """
        A replayed run has no feed, so the bar has to come with the order.

        Without one there is nothing to price against, and inventing a price
        server-side would be fabricating market data.
        """

        payload = dict(VALID_ORDER)
        payload.pop("market")

        with pytest.raises(ValidationError):
            PaperOrderRequest(**payload)

    @pytest.mark.parametrize("quantity", [0.0, -1.0, MAX_ORDER_QUANTITY * 10])
    def test_an_impossible_quantity_is_refused(self, quantity: float) -> None:
        with pytest.raises(ValidationError):
            PaperOrderRequest(**{**VALID_ORDER, "quantity": quantity})

    @pytest.mark.parametrize(
        "field, value",
        [
            ("account_id", "account_someone_else"),
            ("user_id", "user_someone_else"),
            ("session_id", "papersession_other"),
            ("status", "filled"),
            ("commission", 0.0),
            ("extra_metadata", {"anything": True}),
        ],
    )
    def test_smuggling_an_extra_field_is_refused(
        self,
        field: str,
        value,
    ) -> None:
        """
        The account and the session come from the path and the token.

        Accepting either in the body would let an order be booked somewhere the
        caller was never checked against.
        """

        with pytest.raises(ValidationError):
            PaperOrderRequest(**{**VALID_ORDER, field: value})

    def test_a_close_needs_a_positive_price(self) -> None:
        with pytest.raises(ValidationError):
            PaperPositionCloseRequest(exit_price=0.0)

        assert PaperPositionCloseRequest(exit_price=101.5).closed_at_utc is None


class TestSessionActionRequest:
    def test_the_reason_is_optional_at_the_schema_level(self) -> None:
        """
        Required-ness depends on the command, so it is checked there.

        ``cancel`` and ``fail`` need one; ``start`` does not, and one schema
        cannot say both.
        """

        assert PaperSessionActionRequest().reason is None

    def test_an_unknown_field_is_refused(self) -> None:
        with pytest.raises(ValidationError):
            PaperSessionActionRequest(status="completed")


class TestRefusals:
    def test_a_refused_command_is_a_conflict(self) -> None:
        error = refuse_paper_command(
            PaperCommandError("Paper session is completed.")
        )

        assert isinstance(error, AqosApiError)
        assert error.code is ApiErrorCode.CONFLICT
        assert error.status_code == 409

    def test_a_refusal_names_no_internals(self) -> None:
        error = refuse_paper_command(
            PaperCommandError("Paper trading only runs on paper accounts.")
        )

        for fragment in (
            "PaperCommandError",
            "PaperTradingError",
            "Traceback",
            "sqlalchemy",
            "SELECT",
        ):
            assert fragment not in error.message

    def test_an_unknown_enum_value_is_refused(self) -> None:
        with pytest.raises(ValidationApiError):
            require_enum("teleport", PaperAction, "action")

    def test_a_known_enum_value_is_accepted(self) -> None:
        assert require_enum("buy", PaperAction, "action") is PaperAction.BUY
        assert require_enum(
            "market",
            PaperOrderType,
            "order_type",
        ) is PaperOrderType.MARKET


class TestResponseShapes:
    def test_a_transition_reports_both_ends(self) -> None:
        record = FakeSession(
            status=PaperSessionStatus.COMPLETED,
            status_reason="Run finished.",
            ended_at_utc=FIXED_NOW,
        )
        payload = build_session_transition(record, "complete", "running")

        assert payload["command"] == "complete"
        assert payload["from_status"] == "running"
        assert payload["to_status"] == "completed"
        assert payload["reason"] == "Run finished."
        assert payload["ended_at_utc"] == FIXED_NOW.isoformat()

    def test_a_running_session_has_no_end(self) -> None:
        """Unset is null, never a stand-in timestamp."""

        payload = build_session_transition(FakeSession(), "start", "created")

        assert payload["ended_at_utc"] is None

    def test_a_refused_order_still_reports_its_decision(self) -> None:
        """
        A rejection is an answer, not an absence.

        Everything an accepted order would carry is explicitly null or empty,
        so a client can tell "refused" from "not attempted".
        """

        decision = object.__new__(_FakeDecision)
        outcome = PaperOrderOutcome(
            accepted=False,
            decision=decision,
            rejection_reason="symbol_blocked",
            rejection_message="Symbol is blocked for this user.",
        )
        payload = build_order_outcome(outcome)

        assert payload["accepted"] is False
        assert payload["order"] is None
        assert payload["fills"] == []
        assert payload["position"] is None
        assert payload["trade"] is None
        assert payload["rejection_reason"] == "symbol_blocked"
        assert payload["decision"]["decision_id"] == "paperdecision_1"

    def test_the_outcome_keys_are_stable(self) -> None:
        payload = build_order_outcome(
            PaperOrderOutcome(
                accepted=False,
                decision=object.__new__(_FakeDecision),
                rejection_reason="symbol_blocked",
            )
        )

        assert set(payload) == {
            "accepted",
            "decision",
            "order",
            "fills",
            "position",
            "trade",
            "rejection_reason",
            "rejection_message",
        }


class _FakeDecision:
    """The fields ``build_paper_decision`` reads, and nothing else."""

    decision_id = "paperdecision_1"
    session_id = "papersession_1"
    account_id = "account_1"
    user_id = "user_1"
    signal_id = None
    order_id = None
    symbol = "GBPUSD"
    is_allowed = False
    requested_execution_mode = ExecutionMode.MANUAL_APPROVAL
    effective_execution_mode = ExecutionMode.MANUAL_APPROVAL
    primary_reason_code = "symbol_blocked"
    blocking_reason_count = 1
    blocking_sources_json = ["symbol"]
    reasons_json = []
    decided_at_utc = FIXED_NOW
