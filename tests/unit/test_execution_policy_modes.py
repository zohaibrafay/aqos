from __future__ import annotations

import pytest

from aqos.execution_policy.modes import (
    AQOS_EXECUTION_POLICY_VERSION,
    EXECUTION_MODE_RANK,
    ExecutionConstraint,
    ExecutionConstraintSource,
    ExecutionMode,
    ExecutionModeDecision,
    build_user_execution_constraint,
    execution_mode_allows_orders,
    execution_mode_rank,
    resolve_execution_mode,
    stricter_execution_mode,
)


def constraint(
    source: ExecutionConstraintSource,
    ceiling: ExecutionMode,
) -> ExecutionConstraint:
    return ExecutionConstraint(source=source, ceiling=ceiling)


def test_execution_policy_version_is_exposed() -> None:
    assert AQOS_EXECUTION_POLICY_VERSION == "1.0"


def test_every_mode_has_a_rank() -> None:
    assert set(EXECUTION_MODE_RANK) == set(ExecutionMode)


def test_rank_order_is_least_to_most_autonomous() -> None:
    assert execution_mode_rank(ExecutionMode.DISABLED) == 0
    assert execution_mode_rank(ExecutionMode.SIGNAL_ONLY) == 1
    assert execution_mode_rank(ExecutionMode.MANUAL_APPROVAL) == 2
    assert execution_mode_rank(ExecutionMode.AUTO_TRADE) == 3


def test_only_manual_and_auto_can_place_orders() -> None:
    assert execution_mode_allows_orders(ExecutionMode.AUTO_TRADE) is True
    assert execution_mode_allows_orders(ExecutionMode.MANUAL_APPROVAL) is True
    assert execution_mode_allows_orders(ExecutionMode.SIGNAL_ONLY) is False
    assert execution_mode_allows_orders(ExecutionMode.DISABLED) is False


def test_stricter_execution_mode() -> None:
    assert stricter_execution_mode(
        ExecutionMode.AUTO_TRADE,
        ExecutionMode.SIGNAL_ONLY,
    ) == ExecutionMode.SIGNAL_ONLY

    assert stricter_execution_mode(
        ExecutionMode.DISABLED,
        ExecutionMode.AUTO_TRADE,
    ) == ExecutionMode.DISABLED

    assert stricter_execution_mode(
        ExecutionMode.MANUAL_APPROVAL,
        ExecutionMode.MANUAL_APPROVAL,
    ) == ExecutionMode.MANUAL_APPROVAL


def test_constraint_payload() -> None:
    item = ExecutionConstraint(
        source=ExecutionConstraintSource.USER_SETTINGS,
        ceiling=ExecutionMode.SIGNAL_ONLY,
        reason="User is in observation mode.",
    )

    assert item.rank == 1
    assert item.to_dict() == {
        "source": "user_settings",
        "ceiling": "signal_only",
        "reason": "User is in observation mode.",
    }


def test_resolver_requires_at_least_one_constraint() -> None:
    """Resolving with no constraints would grant the requested mode unchecked."""

    with pytest.raises(ValueError, match="At least one execution constraint"):
        resolve_execution_mode(ExecutionMode.AUTO_TRADE, ())


def test_resolver_keeps_the_requested_mode_when_nothing_binds() -> None:
    decision = resolve_execution_mode(
        ExecutionMode.MANUAL_APPROVAL,
        (constraint(ExecutionConstraintSource.USER_SETTINGS, ExecutionMode.AUTO_TRADE),),
    )

    assert decision.effective == ExecutionMode.MANUAL_APPROVAL
    assert decision.was_downgraded is False
    assert decision.binding_constraints == ()
    assert decision.allows_orders is True
    assert "was not downgraded" in decision.explain()


def test_resolver_takes_the_strictest_ceiling() -> None:
    decision = resolve_execution_mode(
        ExecutionMode.AUTO_TRADE,
        (
            constraint(
                ExecutionConstraintSource.USER_SETTINGS,
                ExecutionMode.AUTO_TRADE,
            ),
            constraint(
                ExecutionConstraintSource.ACCOUNT,
                ExecutionMode.MANUAL_APPROVAL,
            ),
            constraint(
                ExecutionConstraintSource.FUNDED_RULE,
                ExecutionMode.SIGNAL_ONLY,
            ),
        ),
    )

    assert decision.effective == ExecutionMode.SIGNAL_ONLY
    assert decision.was_downgraded is True
    assert decision.allows_orders is False
    assert decision.binding_sources == ("funded_rule",)


def test_resolver_reports_every_binding_constraint() -> None:
    decision = resolve_execution_mode(
        ExecutionMode.AUTO_TRADE,
        (
            constraint(
                ExecutionConstraintSource.MODEL_PROMOTION,
                ExecutionMode.SIGNAL_ONLY,
            ),
            constraint(
                ExecutionConstraintSource.RISK_ENGINE,
                ExecutionMode.SIGNAL_ONLY,
            ),
            constraint(
                ExecutionConstraintSource.ACCOUNT,
                ExecutionMode.AUTO_TRADE,
            ),
        ),
    )

    assert decision.effective == ExecutionMode.SIGNAL_ONLY
    assert set(decision.binding_sources) == {"model_promotion", "risk_engine"}
    assert "model_promotion=signal_only" in decision.explain()


def test_disabled_constraint_wins_over_everything() -> None:
    decision = resolve_execution_mode(
        ExecutionMode.AUTO_TRADE,
        (
            constraint(ExecutionConstraintSource.ACCOUNT, ExecutionMode.AUTO_TRADE),
            constraint(ExecutionConstraintSource.RISK_ENGINE, ExecutionMode.DISABLED),
        ),
    )

    assert decision.effective == ExecutionMode.DISABLED
    assert decision.allows_orders is False
    assert decision.binding_sources == ("risk_engine",)


def test_resolver_never_raises_the_requested_mode() -> None:
    decision = resolve_execution_mode(
        ExecutionMode.SIGNAL_ONLY,
        (constraint(ExecutionConstraintSource.ACCOUNT, ExecutionMode.AUTO_TRADE),),
    )

    assert decision.effective == ExecutionMode.SIGNAL_ONLY


def test_requires_manual_approval_flag() -> None:
    decision = resolve_execution_mode(
        ExecutionMode.AUTO_TRADE,
        (
            constraint(
                ExecutionConstraintSource.ACCOUNT,
                ExecutionMode.MANUAL_APPROVAL,
            ),
        ),
    )

    assert decision.requires_manual_approval is True
    assert decision.allows_orders is True


def test_decision_payload_carries_the_audit_trail() -> None:
    decision = resolve_execution_mode(
        ExecutionMode.AUTO_TRADE,
        (
            constraint(
                ExecutionConstraintSource.USER_SETTINGS,
                ExecutionMode.SIGNAL_ONLY,
            ),
        ),
    )

    payload = decision.to_dict()

    assert payload["requested"] == "auto_trade"
    assert payload["effective"] == "signal_only"
    assert payload["was_downgraded"] is True
    assert payload["allows_orders"] is False
    assert payload["binding_sources"] == ["user_settings"]
    assert len(payload["constraints"]) == 1
    assert "downgraded" in payload["explanation"]


def test_empty_decision_defaults() -> None:
    decision = ExecutionModeDecision(
        requested=ExecutionMode.SIGNAL_ONLY,
        effective=ExecutionMode.SIGNAL_ONLY,
    )

    assert decision.was_downgraded is False
    assert decision.binding_sources == ()


def test_build_user_execution_constraint() -> None:
    item = build_user_execution_constraint(ExecutionMode.MANUAL_APPROVAL)

    assert item.source == ExecutionConstraintSource.USER_SETTINGS
    assert item.ceiling == ExecutionMode.MANUAL_APPROVAL
    assert item.reason


def test_constraint_sources_cover_the_planned_layers() -> None:
    """042/043 and later add their own sources; the resolver stays unchanged."""

    assert {source.value for source in ExecutionConstraintSource} == {
        "user_settings",
        "account",
        "funded_rule",
        "model_promotion",
        "risk_engine",
    }
