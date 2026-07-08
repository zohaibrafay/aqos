"""
AQOS security policy engine.

This module provides dependency-free policy rules, condition evaluation, and
an in-memory policy engine for governance decisions.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any

from aqos.security.base import (
    SecurityDecision,
    SecurityPrincipal,
    SecurityResult,
    SecurityRiskLevel,
    build_security_result,
    normalize_risk_level,
    validate_attributes,
    validate_non_empty_string,
    validate_string,
    validate_string_list,
)


class PolicyEffect(str, Enum):
    """Supported policy effects."""

    ALLOW = "allow"
    DENY = "deny"


class PolicyOperator(str, Enum):
    """Supported policy condition operators."""

    EQ = "eq"
    NE = "ne"
    IN = "in"
    NOT_IN = "not_in"
    EXISTS = "exists"
    NOT_EXISTS = "not_exists"
    CONTAINS = "contains"
    GT = "gt"
    GTE = "gte"
    LT = "lt"
    LTE = "lte"


@dataclass(frozen=True)
class PolicyCondition:
    """Single policy condition."""

    field: str
    operator: PolicyOperator | str
    value: Any = None
    description: str = ""

    def __post_init__(self) -> None:
        validate_policy_field(self.field)
        normalize_policy_operator(self.operator)
        validate_string(self.description, "Description")

    def matches(self, context: dict[str, Any]) -> bool:
        """Return whether condition matches context."""
        validate_attributes(context)

        actual_value, exists = get_nested_context_value(
            context,
            self.field,
        )

        return compare_policy_condition(
            actual_value=actual_value,
            expected_value=self.value,
            operator=self.operator,
            exists=exists,
        )

    def to_dict(self) -> dict[str, Any]:
        """Convert condition into dictionary."""
        return {
            "field": self.field.strip(),
            "operator": normalize_policy_operator(self.operator).value,
            "value": self.value,
            "description": self.description.strip(),
        }


@dataclass(frozen=True)
class PolicyRule:
    """Policy rule."""

    name: str
    effect: PolicyEffect | str
    action: str
    resource: str = "*"
    conditions: list[PolicyCondition] = field(default_factory=list)
    priority: int = 100
    enabled: bool = True
    risk_level: SecurityRiskLevel | str = SecurityRiskLevel.MEDIUM
    description: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        validate_policy_name(self.name)
        normalize_policy_effect(self.effect)
        validate_policy_action(self.action)
        validate_policy_resource(self.resource)
        validate_policy_conditions(self.conditions)
        validate_policy_priority(self.priority)
        normalize_risk_level(self.risk_level)
        validate_string(self.description, "Description")
        validate_attributes(self.metadata)

        if not isinstance(self.enabled, bool):
            raise ValueError("Enabled must be a boolean.")

    def matches(self, request: "PolicyEvaluationRequest") -> bool:
        """Return whether this rule matches an evaluation request."""
        if not isinstance(request, PolicyEvaluationRequest):
            raise ValueError("Request must be a PolicyEvaluationRequest.")

        if not self.enabled:
            return False

        if not match_policy_pattern(self.action, request.action):
            return False

        if not match_policy_pattern(self.resource, request.resource):
            return False

        context = build_policy_context(request)

        return all(
            condition.matches(context)
            for condition in self.conditions
        )

    def to_dict(self) -> dict[str, Any]:
        """Convert rule into dictionary."""
        return {
            "name": self.name.strip(),
            "effect": normalize_policy_effect(self.effect).value,
            "action": self.action.strip(),
            "resource": self.resource.strip(),
            "conditions": [
                condition.to_dict()
                for condition in self.conditions
            ],
            "priority": self.priority,
            "enabled": self.enabled,
            "risk_level": normalize_risk_level(self.risk_level).value,
            "description": self.description.strip(),
            "metadata": dict(self.metadata),
        }


@dataclass(frozen=True)
class PolicyEvaluationRequest:
    """Policy evaluation request."""

    principal: SecurityPrincipal
    action: str
    resource: str
    context: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not isinstance(self.principal, SecurityPrincipal):
            raise ValueError("Principal must be a SecurityPrincipal.")

        validate_policy_action(self.action)
        validate_policy_resource(self.resource)
        validate_attributes(self.context)

    def to_dict(self) -> dict[str, Any]:
        """Convert evaluation request into dictionary."""
        return {
            "principal": self.principal.to_dict(),
            "action": self.action.strip(),
            "resource": self.resource.strip(),
            "context": dict(self.context),
        }


@dataclass(frozen=True)
class PolicyEvaluationResult:
    """Policy evaluation result."""

    allowed: bool
    decision: SecurityDecision | str
    reason: str
    principal_id: str
    action: str
    resource: str
    matched_rules: list[str] = field(default_factory=list)
    risk_level: SecurityRiskLevel | str = SecurityRiskLevel.LOW
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not isinstance(self.allowed, bool):
            raise ValueError("Allowed must be a boolean.")

        normalize_security_decision_for_policy(self.decision)
        validate_string(self.reason, "Reason")
        validate_non_empty_string(self.principal_id, "Principal ID")
        validate_policy_action(self.action)
        validate_policy_resource(self.resource)
        validate_string_list(self.matched_rules, "Matched rules")
        normalize_risk_level(self.risk_level)
        validate_attributes(self.metadata)

    @property
    def denied(self) -> bool:
        """Return whether result is denied."""
        return not self.allowed

    def to_security_result(self) -> SecurityResult:
        """Convert policy result into security result."""
        return build_security_result(
        decision=normalize_security_decision_for_policy(self.decision),
        reason=self.reason,
        risk_level=self.risk_level,
        principal_id=self.principal_id,
        metadata={
            "action": self.action,
            "resource": self.resource,
            "matched_rules": [
                rule.strip()
                for rule in self.matched_rules
            ],
            **self.metadata,
        },
    )

    def to_dict(self) -> dict[str, Any]:
        """Convert policy result into dictionary."""
        return {
            "allowed": self.allowed,
            "denied": self.denied,
            "decision": normalize_security_decision_for_policy(self.decision).value,
            "reason": self.reason.strip(),
            "principal_id": self.principal_id.strip(),
            "action": self.action.strip(),
            "resource": self.resource.strip(),
            "matched_rules": [
                rule.strip()
                for rule in self.matched_rules
            ],
            "risk_level": normalize_risk_level(self.risk_level).value,
            "metadata": dict(self.metadata),
        }


@dataclass
class PolicyEngine:
    """In-memory policy engine."""

    rules: dict[str, PolicyRule] = field(default_factory=dict)
    default_decision: SecurityDecision | str = SecurityDecision.DENY

    def __post_init__(self) -> None:
        normalize_security_decision_for_policy(self.default_decision)

        for rule in self.rules.values():
            if not isinstance(rule, PolicyRule):
                raise ValueError("Rules must contain PolicyRule objects.")

    def register_rule(self, rule: PolicyRule) -> PolicyRule:
        """Register a policy rule."""
        if not isinstance(rule, PolicyRule):
            raise ValueError("Rule must be a PolicyRule.")

        if rule.name in self.rules:
            raise ValueError("Policy rule already exists.")

        self.rules[rule.name] = rule
        return rule

    def upsert_rule(self, rule: PolicyRule) -> PolicyRule:
        """Create or replace a policy rule."""
        if not isinstance(rule, PolicyRule):
            raise ValueError("Rule must be a PolicyRule.")

        self.rules[rule.name] = rule
        return rule

    def get_rule(self, name: str) -> PolicyRule | None:
        """Get policy rule by name."""
        normalized = validate_policy_name(name)

        return self.rules.get(normalized)

    def get_required_rule(self, name: str) -> PolicyRule:
        """Get policy rule or raise."""
        rule = self.get_rule(name)

        if rule is None:
            raise ValueError("Policy rule not found.")

        return rule

    def list_rules(self, *, enabled_only: bool = False) -> list[PolicyRule]:
        """List policy rules sorted by priority."""
        if not isinstance(enabled_only, bool):
            raise ValueError("Enabled only must be a boolean.")

        rules = list(self.rules.values())

        if enabled_only:
            rules = [
                rule
                for rule in rules
                if rule.enabled
            ]

        return sorted(
            rules,
            key=lambda rule: rule.priority,
        )

    def evaluate(self, request: PolicyEvaluationRequest) -> PolicyEvaluationResult:
        """Evaluate request against policy rules."""
        if not isinstance(request, PolicyEvaluationRequest):
            raise ValueError("Request must be a PolicyEvaluationRequest.")

        matched_rules = [
            rule
            for rule in self.list_rules(enabled_only=True)
            if rule.matches(request)
        ]

        if not matched_rules:
            default = normalize_security_decision_for_policy(self.default_decision)
            allowed = default == SecurityDecision.ALLOW

            return PolicyEvaluationResult(
                allowed=allowed,
                decision=default,
                reason="No policy rule matched.",
                principal_id=request.principal.principal_id,
                action=request.action,
                resource=request.resource,
                matched_rules=[],
                risk_level="low" if allowed else "medium",
                metadata={
                    "default_decision": default.value,
                },
            )

        deny_rules = [
            rule
            for rule in matched_rules
            if normalize_policy_effect(rule.effect) == PolicyEffect.DENY
        ]

        if deny_rules:
            highest = deny_rules[0]

            return PolicyEvaluationResult(
                allowed=False,
                decision=SecurityDecision.DENY,
                reason=f"Denied by policy rule '{highest.name}'.",
                principal_id=request.principal.principal_id,
                action=request.action,
                resource=request.resource,
                matched_rules=[
                    rule.name
                    for rule in matched_rules
                ],
                risk_level=highest.risk_level,
                metadata={
                    "deny_rule": highest.name,
                },
            )

        highest = matched_rules[0]

        return PolicyEvaluationResult(
            allowed=True,
            decision=SecurityDecision.ALLOW,
            reason=f"Allowed by policy rule '{highest.name}'.",
            principal_id=request.principal.principal_id,
            action=request.action,
            resource=request.resource,
            matched_rules=[
                rule.name
                for rule in matched_rules
            ],
            risk_level=highest.risk_level,
            metadata={
                "allow_rule": highest.name,
            },
        )

    def evaluate_action(
        self,
        *,
        principal: SecurityPrincipal,
        action: str,
        resource: str,
        context: dict[str, Any] | None = None,
    ) -> PolicyEvaluationResult:
        """Evaluate action directly."""
        request = build_policy_evaluation_request(
            principal=principal,
            action=action,
            resource=resource,
            context=context or {},
        )

        return self.evaluate(request)

    def summary(self) -> dict[str, Any]:
        """Return policy engine summary."""
        enabled = [
            rule
            for rule in self.rules.values()
            if rule.enabled
        ]

        disabled = [
            rule
            for rule in self.rules.values()
            if not rule.enabled
        ]

        return {
            "rules": len(self.rules),
            "enabled_rules": len(enabled),
            "disabled_rules": len(disabled),
            "default_decision": normalize_security_decision_for_policy(self.default_decision).value,
            "rule_names": list(self.rules.keys()),
        }

    def clear(self) -> None:
        """Clear policy rules."""
        self.rules.clear()


def normalize_policy_effect(effect: PolicyEffect | str) -> PolicyEffect:
    """Normalize policy effect."""
    if isinstance(effect, PolicyEffect):
        return effect

    normalized = validate_non_empty_string(effect, "Policy effect").lower()

    try:
        return PolicyEffect(normalized)
    except ValueError as exc:
        valid = ", ".join(item.value for item in PolicyEffect)
        raise ValueError(f"Invalid policy effect '{effect}'. Valid effects: {valid}.") from exc


def normalize_policy_operator(operator: PolicyOperator | str) -> PolicyOperator:
    """Normalize policy operator."""
    if isinstance(operator, PolicyOperator):
        return operator

    normalized = validate_non_empty_string(operator, "Policy operator").lower()

    try:
        return PolicyOperator(normalized)
    except ValueError as exc:
        valid = ", ".join(item.value for item in PolicyOperator)
        raise ValueError(f"Invalid policy operator '{operator}'. Valid operators: {valid}.") from exc


def normalize_security_decision_for_policy(decision: SecurityDecision | str) -> SecurityDecision:
    """Normalize policy security decision."""
    if isinstance(decision, SecurityDecision):
        return decision

    normalized = validate_non_empty_string(decision, "Security decision").lower()

    try:
        return SecurityDecision(normalized)
    except ValueError as exc:
        valid = ", ".join(item.value for item in SecurityDecision)
        raise ValueError(f"Invalid security decision '{decision}'. Valid decisions: {valid}.") from exc


def validate_policy_name(name: str) -> str:
    """Validate policy name."""
    normalized = validate_non_empty_string(name, "Policy name")

    if " " in normalized:
        raise ValueError("Policy name cannot contain spaces.")

    return normalized


def validate_policy_action(action: str) -> str:
    """Validate policy action."""
    normalized = validate_non_empty_string(action, "Policy action")

    if " " in normalized:
        raise ValueError("Policy action cannot contain spaces.")

    return normalized


def validate_policy_resource(resource: str) -> str:
    """Validate policy resource."""
    normalized = validate_non_empty_string(resource, "Policy resource")

    if " " in normalized:
        raise ValueError("Policy resource cannot contain spaces.")

    return normalized


def validate_policy_field(field: str) -> str:
    """Validate policy condition field."""
    normalized = validate_non_empty_string(field, "Policy field")

    if " " in normalized:
        raise ValueError("Policy field cannot contain spaces.")

    return normalized


def validate_policy_priority(priority: int) -> int:
    """Validate policy priority."""
    if isinstance(priority, bool) or not isinstance(priority, int):
        raise ValueError("Policy priority must be an integer.")

    return priority


def validate_policy_conditions(conditions: list[PolicyCondition]) -> list[PolicyCondition]:
    """Validate policy condition list."""
    if not isinstance(conditions, list):
        raise ValueError("Conditions must be a list.")

    for condition in conditions:
        if not isinstance(condition, PolicyCondition):
            raise ValueError("Conditions must contain PolicyCondition objects.")

    return conditions


def match_policy_pattern(pattern: str, value: str) -> bool:
    """Match policy pattern with wildcard support."""
    normalized_pattern = validate_non_empty_string(pattern, "Policy pattern")
    normalized_value = validate_non_empty_string(value, "Policy value")

    if normalized_pattern == "*":
        return True

    if normalized_pattern.endswith("*"):
        return normalized_value.startswith(normalized_pattern[:-1])

    return normalized_pattern == normalized_value


def get_nested_context_value(
    context: dict[str, Any],
    field: str,
) -> tuple[Any, bool]:
    """Read nested value from context using dot notation."""
    validate_attributes(context)
    normalized_field = validate_policy_field(field)

    current: Any = context

    for part in normalized_field.split("."):
        if not isinstance(current, dict) or part not in current:
            return None, False

        current = current[part]

    return current, True


def compare_policy_condition(
    *,
    actual_value: Any,
    expected_value: Any,
    operator: PolicyOperator | str,
    exists: bool = True,
) -> bool:
    """Compare policy condition values."""
    normalized_operator = normalize_policy_operator(operator)

    if normalized_operator == PolicyOperator.EXISTS:
        return exists

    if normalized_operator == PolicyOperator.NOT_EXISTS:
        return not exists

    if not exists:
        return False

    if normalized_operator == PolicyOperator.EQ:
        return actual_value == expected_value

    if normalized_operator == PolicyOperator.NE:
        return actual_value != expected_value

    if normalized_operator == PolicyOperator.IN:
        if not isinstance(expected_value, list | tuple | set):
            raise ValueError("Expected value must be a collection for 'in'.")
        return actual_value in expected_value

    if normalized_operator == PolicyOperator.NOT_IN:
        if not isinstance(expected_value, list | tuple | set):
            raise ValueError("Expected value must be a collection for 'not_in'.")
        return actual_value not in expected_value

    if normalized_operator == PolicyOperator.CONTAINS:
        if isinstance(actual_value, str):
            return str(expected_value) in actual_value

        if isinstance(actual_value, list | tuple | set):
            return expected_value in actual_value

        raise ValueError("Actual value must be a string or collection for 'contains'.")

    if normalized_operator == PolicyOperator.GT:
        return actual_value > expected_value

    if normalized_operator == PolicyOperator.GTE:
        return actual_value >= expected_value

    if normalized_operator == PolicyOperator.LT:
        return actual_value < expected_value

    if normalized_operator == PolicyOperator.LTE:
        return actual_value <= expected_value

    raise ValueError("Unsupported policy operator.")


def build_policy_context(request: PolicyEvaluationRequest) -> dict[str, Any]:
    """Build full policy context for condition evaluation."""
    if not isinstance(request, PolicyEvaluationRequest):
        raise ValueError("Request must be a PolicyEvaluationRequest.")

    return {
        "principal": request.principal.to_dict(),
        "action": request.action,
        "resource": request.resource,
        **request.context,
    }


def build_policy_condition(
    *,
    field: str,
    operator: PolicyOperator | str,
    value: Any = None,
    description: str = "",
) -> PolicyCondition:
    """Build policy condition."""
    return PolicyCondition(
        field=field,
        operator=operator,
        value=value,
        description=description,
    )


def build_policy_rule(
    *,
    name: str,
    effect: PolicyEffect | str,
    action: str,
    resource: str = "*",
    conditions: list[PolicyCondition] | None = None,
    priority: int = 100,
    enabled: bool = True,
    risk_level: SecurityRiskLevel | str = SecurityRiskLevel.MEDIUM,
    description: str = "",
    metadata: dict[str, Any] | None = None,
) -> PolicyRule:
    """Build policy rule."""
    return PolicyRule(
        name=name,
        effect=effect,
        action=action,
        resource=resource,
        conditions=conditions or [],
        priority=priority,
        enabled=enabled,
        risk_level=risk_level,
        description=description,
        metadata=metadata or {},
    )


def build_policy_evaluation_request(
    *,
    principal: SecurityPrincipal,
    action: str,
    resource: str,
    context: dict[str, Any] | None = None,
) -> PolicyEvaluationRequest:
    """Build policy evaluation request."""
    return PolicyEvaluationRequest(
        principal=principal,
        action=action,
        resource=resource,
        context=context or {},
    )


def build_policy_engine(
    *,
    rules: list[PolicyRule] | None = None,
    default_decision: SecurityDecision | str = SecurityDecision.DENY,
) -> PolicyEngine:
    """Build policy engine."""
    engine = PolicyEngine(
        default_decision=default_decision,
    )

    for rule in rules or []:
        engine.register_rule(rule)

    return engine