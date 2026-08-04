"""Unit tests for paper trading session contracts and lifecycle."""

from __future__ import annotations

import math
from datetime import datetime

import pytest

from aqos.paper_trading.contracts import PaperTradingError
from aqos.paper_trading.models import PaperSessionRecord
from aqos.paper_trading.sessions import (
    AQOS_PAPER_SESSIONS_VERSION,
    CREATABLE_PAPER_SESSION_STATUSES,
    EXECUTABLE_PAPER_SESSION_STATUSES,
    InvalidPaperSessionTransitionError,
    MODEL_DRIVEN_SESSION_TYPES,
    PAPER_SESSION_TRANSITIONS,
    PaperProfitFactorState,
    PaperSessionResult,
    PaperSessionStatus,
    PaperSessionType,
    STRATEGY_DRIVEN_SESSION_TYPES,
    TERMINAL_PAPER_SESSION_STATUSES,
    can_transition_session,
    finite_profit_factor,
    is_terminal_session_status,
    normalize_session_name,
    resolve_profit_factor_state,
    validate_session_identity,
    validate_session_transition,
)


FIXED_NOW = datetime(2026, 1, 1, 0, 0, 0)


def build_session_record(**overrides) -> PaperSessionRecord:
    payload = {
        "session_id": "session_1",
        "user_id": "user_1",
        "account_id": "account_1",
        "session_name": "Forward test",
        "session_type": PaperSessionType.MANUAL_PAPER_SESSION,
        "initial_balance": 10_000.0,
        "started_at_utc": FIXED_NOW,
        "created_at_utc": FIXED_NOW,
        "updated_at_utc": FIXED_NOW,
    }
    payload.update(overrides)

    return PaperSessionRecord(**payload)


def test_module_version_is_declared() -> None:
    assert AQOS_PAPER_SESSIONS_VERSION == "1.0"


class TestTransitionTable:
    def test_every_status_has_an_entry(self) -> None:
        assert set(PAPER_SESSION_TRANSITIONS) == set(PaperSessionStatus)

    def test_terminal_statuses_lead_nowhere(self) -> None:
        for status in TERMINAL_PAPER_SESSION_STATUSES:
            assert PAPER_SESSION_TRANSITIONS[status] == ()
            assert is_terminal_session_status(status) is True

    def test_open_statuses_are_not_terminal(self) -> None:
        for status in (
            PaperSessionStatus.CREATED,
            PaperSessionStatus.RUNNING,
            PaperSessionStatus.PAUSED,
        ):
            assert is_terminal_session_status(status) is False

    def test_only_created_is_a_starting_status(self) -> None:
        assert CREATABLE_PAPER_SESSION_STATUSES == (PaperSessionStatus.CREATED,)

    def test_only_a_running_session_may_execute(self) -> None:
        assert EXECUTABLE_PAPER_SESSION_STATUSES == (PaperSessionStatus.RUNNING,)

    @pytest.mark.parametrize(
        "from_status, to_status",
        [
            (PaperSessionStatus.CREATED, PaperSessionStatus.RUNNING),
            (PaperSessionStatus.RUNNING, PaperSessionStatus.PAUSED),
            (PaperSessionStatus.PAUSED, PaperSessionStatus.RUNNING),
            (PaperSessionStatus.RUNNING, PaperSessionStatus.COMPLETED),
            (PaperSessionStatus.RUNNING, PaperSessionStatus.FAILED),
            (PaperSessionStatus.RUNNING, PaperSessionStatus.CANCELLED),
            (PaperSessionStatus.PAUSED, PaperSessionStatus.CANCELLED),
        ],
    )
    def test_allowed_transitions(self, from_status, to_status) -> None:
        assert can_transition_session(from_status, to_status) is True

        validate_session_transition(from_status, to_status)

    @pytest.mark.parametrize(
        "from_status, to_status",
        [
            (PaperSessionStatus.CREATED, PaperSessionStatus.PAUSED),
            (PaperSessionStatus.CREATED, PaperSessionStatus.COMPLETED),
            (PaperSessionStatus.PAUSED, PaperSessionStatus.COMPLETED),
            (PaperSessionStatus.COMPLETED, PaperSessionStatus.RUNNING),
            (PaperSessionStatus.CANCELLED, PaperSessionStatus.RUNNING),
            (PaperSessionStatus.FAILED, PaperSessionStatus.RUNNING),
            (PaperSessionStatus.RUNNING, PaperSessionStatus.CREATED),
        ],
    )
    def test_invalid_transitions_are_rejected(self, from_status, to_status) -> None:
        assert can_transition_session(from_status, to_status) is False

        with pytest.raises(InvalidPaperSessionTransitionError, match="cannot move"):
            validate_session_transition(from_status, to_status)

    def test_a_finished_session_can_never_restart(self) -> None:
        """Completed, failed and cancelled are the end of the run."""

        for status in TERMINAL_PAPER_SESSION_STATUSES:
            for target in PaperSessionStatus:
                assert can_transition_session(status, target) is False

    def test_running_is_only_reachable_from_created_or_paused(self) -> None:
        sources = {
            status
            for status, targets in PAPER_SESSION_TRANSITIONS.items()
            if PaperSessionStatus.RUNNING in targets
        }

        assert sources == {PaperSessionStatus.CREATED, PaperSessionStatus.PAUSED}


class TestSessionName:
    def test_whitespace_is_collapsed(self) -> None:
        assert normalize_session_name("  Forward   test  ") == "Forward test"

    @pytest.mark.parametrize("value", ["", "   ", "\t\n"])
    def test_an_empty_name_is_rejected(self, value: str) -> None:
        with pytest.raises(PaperTradingError, match="cannot be empty"):
            normalize_session_name(value)

    def test_an_overlong_name_is_rejected(self) -> None:
        with pytest.raises(PaperTradingError, match="191 characters"):
            normalize_session_name("x" * 192)


class TestSessionIdentity:
    def test_a_model_forward_test_must_name_its_model(self) -> None:
        """An unattributed run could never be reproduced or compared."""

        with pytest.raises(PaperTradingError, match="must name the model"):
            validate_session_identity(
                session_type=PaperSessionType.MODEL_FORWARD_TEST,
                model_id=None,
                strategy_name="Breakout",
            )

    def test_a_strategy_forward_test_must_name_its_strategy(self) -> None:
        with pytest.raises(PaperTradingError, match="must name the strategy"):
            validate_session_identity(
                session_type=PaperSessionType.STRATEGY_FORWARD_TEST,
                model_id="model_1",
                strategy_name="  ",
            )

    def test_a_named_model_forward_test_is_accepted(self) -> None:
        validate_session_identity(
            session_type=PaperSessionType.MODEL_FORWARD_TEST,
            model_id="model_1",
            strategy_name=None,
        )

    def test_other_session_types_need_no_identity(self) -> None:
        for session_type in PaperSessionType:
            if session_type in MODEL_DRIVEN_SESSION_TYPES:
                continue

            if session_type in STRATEGY_DRIVEN_SESSION_TYPES:
                continue

            validate_session_identity(
                session_type=session_type,
                model_id=None,
                strategy_name=None,
            )


class TestSessionRecord:
    def test_defaults_are_applied_before_any_flush(self) -> None:
        record = build_session_record()

        assert record.status == PaperSessionStatus.CREATED
        assert record.extra_metadata == {}
        assert record.is_terminal is False
        assert record.is_running is False

    def test_the_name_is_normalised_on_assignment(self) -> None:
        assert build_session_record(
            session_name="  Run   one "
        ).session_name == "Run one"

    def test_realized_pnl_is_unknown_without_a_final_balance(self) -> None:
        assert build_session_record().realized_pnl is None

    def test_realized_pnl_uses_the_final_balance(self) -> None:
        record = build_session_record(final_balance=10_150.0)

        assert record.realized_pnl == pytest.approx(150.0)

    def test_a_terminal_session_must_be_timestamped(self) -> None:
        record = build_session_record(status=PaperSessionStatus.COMPLETED)

        with pytest.raises(PaperTradingError, match="must record an end time"):
            record.assert_lifecycle_is_consistent()

    def test_an_open_session_must_not_carry_an_end_time(self) -> None:
        record = build_session_record(
            status=PaperSessionStatus.RUNNING,
            ended_at_utc=FIXED_NOW,
        )

        with pytest.raises(PaperTradingError, match="cannot carry an end time"):
            record.assert_lifecycle_is_consistent()

    def test_an_end_before_the_start_is_rejected(self) -> None:
        record = build_session_record(
            status=PaperSessionStatus.COMPLETED,
            ended_at_utc=datetime(2025, 12, 31),
        )

        with pytest.raises(PaperTradingError, match="cannot be before"):
            record.assert_lifecycle_is_consistent()

    def test_a_consistent_terminal_session_is_accepted(self) -> None:
        build_session_record(
            status=PaperSessionStatus.COMPLETED,
            ended_at_utc=datetime(2026, 1, 2),
        ).assert_lifecycle_is_consistent()

    def test_the_identity_rule_is_enforced_on_the_record(self) -> None:
        record = build_session_record(
            session_type=PaperSessionType.MODEL_FORWARD_TEST,
        )

        with pytest.raises(PaperTradingError, match="must name the model"):
            record.assert_identity_is_recorded()

    def test_to_dict_carries_the_session(self) -> None:
        payload = build_session_record(
            model_id="model_1",
            final_balance=10_150.0,
        ).to_dict()

        assert payload["session_id"] == "session_1"
        assert payload["session_type"] == "manual_paper_session"
        assert payload["status"] == "created"
        assert payload["initial_balance"] == pytest.approx(10_000.0)
        assert payload["realized_pnl"] == pytest.approx(150.0)
        assert payload["ended_at_utc"] is None
        assert payload["total_trades"] is None

    def test_the_profit_factor_state_defaults_to_unavailable(self) -> None:
        record = build_session_record()

        assert record.profit_factor is None
        assert record.profit_factor_state == PaperProfitFactorState.UNAVAILABLE
        assert record.has_infinite_profit_factor is False

        record.assert_profit_factor_is_explained()

    def test_a_finite_state_must_carry_its_value(self) -> None:
        record = build_session_record(
            profit_factor_state=PaperProfitFactorState.FINITE,
        )

        with pytest.raises(PaperTradingError, match="must carry its value"):
            record.assert_profit_factor_is_explained()

    def test_an_infinite_state_must_not_carry_a_number(self) -> None:
        record = build_session_record(
            profit_factor=2.5,
            profit_factor_state=PaperProfitFactorState.INFINITE_NO_LOSSES,
        )

        with pytest.raises(PaperTradingError, match="cannot carry a numeric"):
            record.assert_profit_factor_is_explained()

    def test_an_unavailable_state_must_not_carry_a_number(self) -> None:
        record = build_session_record(
            profit_factor=2.5,
            profit_factor_state=PaperProfitFactorState.UNAVAILABLE,
        )

        with pytest.raises(PaperTradingError, match="cannot carry a numeric"):
            record.assert_profit_factor_is_explained()

    def test_a_wins_only_session_row_stays_distinguishable(self) -> None:
        """NULL plus a state is what keeps it from reading as unmeasured."""

        record = build_session_record(
            total_trades=2,
            profit_factor=None,
            profit_factor_state=PaperProfitFactorState.INFINITE_NO_LOSSES,
        )
        record.assert_profit_factor_is_explained()

        payload = record.to_dict()

        assert payload["profit_factor"] is None
        assert payload["profit_factor_state"] == "infinite_no_losses"
        assert payload["has_infinite_profit_factor"] is True

    def test_repr_names_the_session(self) -> None:
        assert "session_1" in repr(build_session_record())


class TestSessionResult:
    def build(self, **overrides) -> PaperSessionResult:
        payload = {"session_id": "session_1", "account_id": "account_1"}
        payload.update(overrides)

        return PaperSessionResult(**payload)

    def test_an_empty_result_reports_unknowns_not_zeros(self) -> None:
        """A session with no trades has an unknown win rate, not a zero one."""

        result = self.build()

        assert result.has_trades is False
        assert result.total_trades == 0
        assert result.win_rate is None
        assert result.net_pnl is None
        assert result.profit_factor is None
        assert result.profit_factor_state == PaperProfitFactorState.UNAVAILABLE
        assert result.max_drawdown is None
        assert result.ending_balance is None

    def test_a_win_rate_without_trades_is_refused(self) -> None:
        with pytest.raises(PaperTradingError, match="must stay unset"):
            self.build(total_trades=0, win_rate=0.0)

    def test_counted_trades_may_carry_a_rate(self) -> None:
        result = self.build(
            total_trades=4,
            winning_trades=3,
            losing_trades=1,
            win_rate=0.75,
            net_pnl=120.0,
        )

        assert result.has_trades is True
        assert result.win_rate == pytest.approx(0.75)

    def test_the_outcome_counts_cannot_exceed_the_total(self) -> None:
        with pytest.raises(PaperTradingError, match="cannot exceed total_trades"):
            self.build(total_trades=2, winning_trades=2, losing_trades=1)

    @pytest.mark.parametrize(
        "field",
        [
            "total_orders",
            "total_fills",
            "total_trades",
            "winning_trades",
            "losing_trades",
            "decisions_allowed",
            "decisions_rejected",
        ],
    )
    def test_negative_counts_are_rejected(self, field: str) -> None:
        with pytest.raises(PaperTradingError, match="cannot be negative"):
            self.build(**{field: -1})

    def test_a_breakeven_trade_counts_in_neither_column(self) -> None:
        result = self.build(
            total_trades=3,
            winning_trades=1,
            losing_trades=1,
            win_rate=1 / 3,
        )

        assert result.winning_trades + result.losing_trades < result.total_trades

    def test_the_rejection_rate_is_unknown_without_decisions(self) -> None:
        assert self.build().rejection_rate is None

    def test_the_rejection_rate_is_measured_from_decisions(self) -> None:
        result = self.build(decisions_allowed=3, decisions_rejected=1)

        assert result.total_decisions == 4
        assert result.rejection_rate == pytest.approx(0.25)

    def test_an_all_allowed_run_has_a_zero_rejection_rate(self) -> None:
        """Zero here is measured: decisions were made and none were refused."""

        result = self.build(decisions_allowed=5, decisions_rejected=0)

        assert result.rejection_rate == pytest.approx(0.0)

    def test_a_missing_session_id_is_rejected(self) -> None:
        with pytest.raises(PaperTradingError, match="session_id cannot be empty"):
            PaperSessionResult(session_id="  ", account_id="account_1")

    def test_to_dict_reports_unknowns_as_null(self) -> None:
        payload = self.build().to_dict()

        assert payload["win_rate"] is None
        assert payload["net_pnl"] is None
        assert payload["profit_factor"] is None
        assert payload["profit_factor_state"] == "unavailable"
        assert payload["has_infinite_profit_factor"] is False
        assert payload["rejection_rate"] is None
        assert payload["symbols_traded"] == []
        assert payload["top_rejection_reasons"] == []

    def test_to_dict_lists_the_top_rejection_reasons(self) -> None:
        payload = self.build(
            decisions_allowed=1,
            decisions_rejected=3,
            top_rejection_reasons=(("symbol_blocked", 2), ("duplicate_signal", 1)),
        ).to_dict()

        assert payload["top_rejection_reasons"] == [
            {"reason_code": "symbol_blocked", "total": 2},
            {"reason_code": "duplicate_signal", "total": 1},
        ]


class TestProfitFactorSemantics:
    """
    Sprint 046 owns this definition and Sprint 052 must not diverge from it.

    Infinity means "won and never lost", which is a real result. None means
    there was nothing to divide. Collapsing the first into the second would
    make a perfect run look unmeasured.
    """

    def build(self, **overrides) -> PaperSessionResult:
        payload = {"session_id": "session_1", "account_id": "account_1"}
        payload.update(overrides)

        return PaperSessionResult(**payload)

    def test_no_trades_is_unavailable(self) -> None:
        result = self.build()

        assert result.profit_factor is None
        assert result.profit_factor_state == PaperProfitFactorState.UNAVAILABLE
        assert result.has_infinite_profit_factor is False

    def test_wins_and_no_losses_is_infinite(self) -> None:
        result = self.build(
            total_trades=2,
            winning_trades=2,
            win_rate=1.0,
            gross_profit=30.0,
            gross_loss=0.0,
            profit_factor=math.inf,
        )

        assert math.isinf(result.profit_factor)
        assert result.profit_factor_state == (
            PaperProfitFactorState.INFINITE_NO_LOSSES
        )
        assert result.has_infinite_profit_factor is True

    def test_losses_give_a_finite_ratio(self) -> None:
        result = self.build(
            total_trades=2,
            winning_trades=1,
            losing_trades=1,
            win_rate=0.5,
            gross_profit=30.0,
            gross_loss=10.0,
            profit_factor=3.0,
        )

        assert result.profit_factor == pytest.approx(3.0)
        assert result.profit_factor_state == PaperProfitFactorState.FINITE

    def test_breakeven_only_trades_stay_unavailable(self) -> None:
        """No profit and no loss leaves nothing to divide."""

        result = self.build(
            total_trades=2,
            win_rate=0.0,
            gross_profit=0.0,
            gross_loss=0.0,
            profit_factor=None,
        )

        assert result.profit_factor is None
        assert result.profit_factor_state == PaperProfitFactorState.UNAVAILABLE

    def test_infinity_is_not_stored_as_a_number(self) -> None:
        result = self.build(
            total_trades=1,
            winning_trades=1,
            win_rate=1.0,
            gross_profit=10.0,
            gross_loss=0.0,
            profit_factor=math.inf,
        )

        assert result.persisted_profit_factor is None

    def test_a_finite_factor_persists_its_value(self) -> None:
        result = self.build(
            total_trades=2,
            winning_trades=1,
            losing_trades=1,
            win_rate=0.5,
            profit_factor=2.5,
        )

        assert result.persisted_profit_factor == pytest.approx(2.5)

    def test_the_payload_keeps_infinity_meaningful(self) -> None:
        """JSON cannot hold infinity, so the state must carry it."""

        payload = self.build(
            total_trades=1,
            winning_trades=1,
            win_rate=1.0,
            gross_profit=10.0,
            gross_loss=0.0,
            profit_factor=math.inf,
        ).to_dict()

        assert payload["profit_factor"] is None
        assert payload["profit_factor_state"] == "infinite_no_losses"
        assert payload["has_infinite_profit_factor"] is True

    def test_a_wins_only_session_is_never_reported_as_unmeasured(self) -> None:
        wins_only = self.build(
            total_trades=1,
            winning_trades=1,
            win_rate=1.0,
            gross_profit=10.0,
            gross_loss=0.0,
            profit_factor=math.inf,
        ).to_dict()
        nothing_traded = self.build().to_dict()

        assert wins_only["profit_factor"] == nothing_traded["profit_factor"]
        # The numbers match, so only the state tells them apart.
        assert (
            wins_only["profit_factor_state"]
            != nothing_traded["profit_factor_state"]
        )


class TestProfitFactorHelpers:
    @pytest.mark.parametrize(
        "value, expected",
        [
            (None, PaperProfitFactorState.UNAVAILABLE),
            (0.0, PaperProfitFactorState.FINITE),
            (2.5, PaperProfitFactorState.FINITE),
            (math.inf, PaperProfitFactorState.INFINITE_NO_LOSSES),
        ],
    )
    def test_resolve_profit_factor_state(self, value, expected) -> None:
        assert resolve_profit_factor_state(value) == expected

    @pytest.mark.parametrize(
        "value, expected",
        [(None, None), (math.inf, None), (2.5, 2.5), (0.0, 0.0)],
    )
    def test_finite_profit_factor(self, value, expected) -> None:
        assert finite_profit_factor(value) == expected
