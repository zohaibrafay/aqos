from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any, Sequence


AQOS_EXECUTION_POLICY_VERSION = "1.0"


class ExecutionMode(str, Enum):
    """How far AQOS may act on a signal without a human in the loop."""

    DISABLED = "disabled"
    SIGNAL_ONLY = "signal_only"
    MANUAL_APPROVAL = "manual_approval"
    AUTO_TRADE = "auto_trade"


class ExecutionConstraintSource(str, Enum):
    """
    Where an execution ceiling comes from.

    Sprint 041 supplies the user setting. Accounts, funded rules, model
    promotion status and the risk engine each add their own ceiling in later
    sprints; the resolver itself does not change when they do.
    """

    USER_SETTINGS = "user_settings"
    ACCOUNT = "account"
    FUNDED_RULE = "funded_rule"
    MODEL_PROMOTION = "model_promotion"
    RISK_ENGINE = "risk_engine"


EXECUTION_MODE_RANK: dict[ExecutionMode, int] = {
    ExecutionMode.DISABLED: 0,
    ExecutionMode.SIGNAL_ONLY: 1,
    ExecutionMode.MANUAL_APPROVAL: 2,
    ExecutionMode.AUTO_TRADE: 3,
}

#: Modes under which an order may be sent to a broker.
ORDER_CAPABLE_EXECUTION_MODES = (
    ExecutionMode.MANUAL_APPROVAL,
    ExecutionMode.AUTO_TRADE,
)


def execution_mode_rank(mode: ExecutionMode) -> int:
    return EXECUTION_MODE_RANK[mode]


def execution_mode_allows_orders(mode: ExecutionMode) -> bool:
    return mode in ORDER_CAPABLE_EXECUTION_MODES


def stricter_execution_mode(
    first: ExecutionMode,
    second: ExecutionMode,
) -> ExecutionMode:
    return first if execution_mode_rank(first) <= execution_mode_rank(second) else second


@dataclass(frozen=True)
class ExecutionConstraint:
    """One ceiling on how autonomously AQOS may act."""

    source: ExecutionConstraintSource
    ceiling: ExecutionMode
    reason: str | None = None

    @property
    def rank(self) -> int:
        return execution_mode_rank(self.ceiling)

    def to_dict(self) -> dict[str, Any]:
        return {
            "source": self.source.value,
            "ceiling": self.ceiling.value,
            "reason": self.reason,
        }


@dataclass(frozen=True)
class ExecutionModeDecision:
    """
    The effective execution mode plus why it ended up there.

    ``binding_constraints`` is the audit trail: it names exactly which sources
    lowered the requested mode, so a rejected or downgraded signal can always be
    explained.
    """

    requested: ExecutionMode
    effective: ExecutionMode
    constraints: tuple[ExecutionConstraint, ...] = ()
    binding_constraints: tuple[ExecutionConstraint, ...] = ()

    @property
    def was_downgraded(self) -> bool:
        return execution_mode_rank(self.effective) < execution_mode_rank(self.requested)

    @property
    def allows_orders(self) -> bool:
        return execution_mode_allows_orders(self.effective)

    @property
    def requires_manual_approval(self) -> bool:
        return self.effective == ExecutionMode.MANUAL_APPROVAL

    @property
    def binding_sources(self) -> tuple[str, ...]:
        return tuple(
            constraint.source.value for constraint in self.binding_constraints
        )

    def explain(self) -> str:
        if not self.was_downgraded:
            return f"Execution mode {self.effective.value} was not downgraded."

        reasons = [
            f"{constraint.source.value}={constraint.ceiling.value}"
            for constraint in self.binding_constraints
        ]

        return (
            f"Execution mode downgraded from {self.requested.value} to "
            f"{self.effective.value} by: " + ", ".join(reasons)
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "requested": self.requested.value,
            "effective": self.effective.value,
            "was_downgraded": self.was_downgraded,
            "allows_orders": self.allows_orders,
            "requires_manual_approval": self.requires_manual_approval,
            "binding_sources": list(self.binding_sources),
            "explanation": self.explain(),
            "constraints": [constraint.to_dict() for constraint in self.constraints],
            "binding_constraints": [
                constraint.to_dict() for constraint in self.binding_constraints
            ],
        }


def resolve_execution_mode(
    requested: ExecutionMode,
    constraints: Sequence[ExecutionConstraint],
) -> ExecutionModeDecision:
    """
    Reduce a requested execution mode to the strictest ceiling that applies.

    At least one constraint is required. A caller that supplies none would
    otherwise get whatever it asked for, which is exactly the shortcut AQOS must
    never take on a real account.
    """

    if not constraints:
        raise ValueError(
            "At least one execution constraint is required; resolving with no "
            "constraints would grant the requested mode unchecked."
        )

    ordered = tuple(constraints)

    effective = requested

    for constraint in ordered:
        effective = stricter_execution_mode(effective, constraint.ceiling)

    binding = tuple(
        constraint
        for constraint in ordered
        if constraint.ceiling == effective
        and execution_mode_rank(constraint.ceiling)
        < execution_mode_rank(requested)
    )

    return ExecutionModeDecision(
        requested=requested,
        effective=effective,
        constraints=ordered,
        binding_constraints=binding,
    )


def build_user_execution_constraint(
    ceiling: ExecutionMode,
    reason: str | None = None,
) -> ExecutionConstraint:
    return ExecutionConstraint(
        source=ExecutionConstraintSource.USER_SETTINGS,
        ceiling=ceiling,
        reason=reason or "User trading settings execution mode.",
    )


__all__ = [
    "AQOS_EXECUTION_POLICY_VERSION",
    "EXECUTION_MODE_RANK",
    "ExecutionConstraint",
    "ExecutionConstraintSource",
    "ExecutionMode",
    "ExecutionModeDecision",
    "ORDER_CAPABLE_EXECUTION_MODES",
    "build_user_execution_constraint",
    "execution_mode_allows_orders",
    "execution_mode_rank",
    "resolve_execution_mode",
    "stricter_execution_mode",
]
