"""
Unit tests for AQOS security policy engine.
"""

import pytest

from aqos.security import (
    PolicyCondition,
    PolicyEffect,
    PolicyEngine,
    PolicyEvaluationRequest,
    PolicyEvaluationResult,
    PolicyOperator,
    PolicyRule,
    SecurityDecision,
    SecurityPrincipal,
    build_policy_condition,
    build_policy_context,
    build_policy_engine,
    build_policy_evaluation_request,
    build_policy_rule,
    compare_policy_condition,
    get_nested_context_value,
    match_policy_pattern,
    normalize_policy_effect,
    normalize_policy_operator,
    validate_policy_action,
    validate_policy_conditions,
    validate_policy_field,
    validate_policy_name,
    validate_policy_priority,
    validate_policy_resource,
)


def test_policy_effect_values():
    assert PolicyEffect.ALLOW.value == "allow"
    assert PolicyEffect.DENY.value == "deny"


def test_policy_operator_values ():
    assert PolicyOperator.EQ.value == "eq"
    assert PolicyOperator.NE.value == "ne"
    assert PolicyOperator.IN.value == "in"
    assert PolicyOperator.NOT_IN.value == "not_in"
    assert PolicyOperator.EXISTS.value == "exists"
    assert PolicyOperator.NOT_EXISTS.value == "not_exists"
    assert PolicyOperator.CONTAINS.value == "contains"
    assert PolicyOperator.GT.value == "gt"
    assert PolicyOperator.GTE.value == "gte"
    assert PolicyOperator.LT.value == "lt"
    assert PolicyOperator.LTE.value == "lte"


def test_normalize_policy_effect_accepts_enum_and_string():
    assert normalize_policy_effect(PolicyEffect.ALLOW) == PolicyEffect.ALLOW
    assert normalize_policy_effect(" ALLOW ") == PolicyEffect.ALLOW
    assert normalize_policy_effect("deny") == PolicyEffect.DENY


def test_normalize_policy_effect_rejects_invalid_value():
    with pytest.raises(ValueError):
        normalize_policy_effect("bad")

    with pytest.raises(ValueError):
        normalize_policy_effect("")


def test_normalize_policy_operator_accepts_enum_and_string():
    assert normalize_policy_operator(PolicyOperator.EQ) == PolicyOperator.EQ
    assert normalize_policy_operator(" EQ ") == PolicyOperator.EQ
    assert normalize_policy_operator("not_in") == PolicyOperator.NOT_IN
    assert normalize_policy_operator("GTE") == PolicyOperator.GTE


def test_normalize_policy_operator_rejects_invalid_value():
    with pytest.raises(ValueError):
        normalize_policy_operator("bad")

    with pytest.raises(ValueError):
        normalize_policy_operator("")


def test_validate_policy_helpers():
    assert validate_policy_name("allow-trade") == "allow-trade"
    assert validate_policy_action("trade.execute") == "trade.execute"
    assert validate_policy_resource("/api/trade") == "/api/trade"
    assert validate_policy_field("principal.principal_id") == "principal.principal_id"
    assert validate_policy_priority(0) == 0

    with pytest.raises(ValueError):
        validate_policy_name("")

    with pytest.raises(ValueError):
        validate_policy_name("bad name")

    with pytest.raises(ValueError):
        validate_policy_action("bad action")

    with pytest.raises(ValueError):
        validate_policy_resource("bad resource")

    with pytest.raises(ValueError):
        validate_policy_field("bad field")

    with pytest.raises(ValueError):
        validate_policy_priority(True)

    with pytest.raises(ValueError):
        validate_policy_priority("1")


def test_match_policy_pattern():
    assert match_policy_pattern("*", "trade.execute") is True
    assert match_policy_pattern("trade.*", "trade.execute") is True
    assert match_policy_pattern("trade.execute", "trade.execute") is True
    assert match_policy_pattern("trade.read", "trade.execute") is False


def test_get_nested_context_value():
    context = {
        "principal": {
            "principal_id": "user-1",
        },
        "risk": {
            "score": 0.5,
        },
    }

    assert get_nested_context_value(context, "principal.principal_id") == ("user-1", True)
    assert get_nested_context_value(context, "risk.score") == (0.5, True)
    assert get_nested_context_value(context, "risk.missing") == (None, False)


def test_compare_policy_condition():
    assert compare_policy_condition(actual_value="buy", expected_value="buy", operator="eq") is True
    assert compare_policy_condition(actual_value="buy", expected_value="sell", operator="ne") is True
    assert compare_policy_condition(actual_value="buy", expected_value=["buy", "sell"], operator="in") is True
    assert compare_policy_condition(actual_value="hold", expected_value=["buy", "sell"], operator="not_in") is True
    assert compare_policy_condition(actual_value=None, expected_value=None, operator="exists", exists=True) is True
    assert compare_policy_condition(actual_value=None, expected_value=None, operator="not_exists", exists=False) is True
    assert compare_policy_condition(actual_value="trade.execute", expected_value="trade", operator="contains") is True
    assert compare_policy_condition(actual_value=["trader"], expected_value="trader", operator="contains") is True
    assert compare_policy_condition(actual_value=10, expected_value=5, operator="gt") is True
    assert compare_policy_condition(actual_value=10, expected_value=10, operator="gte") is True
    assert compare_policy_condition(actual_value=5, expected_value=10, operator="lt") is True
    assert compare_policy_condition(actual_value=10, expected_value=10, operator="lte") is True


def test_compare_policy_condition_rejects_invalid_values():
    with pytest.raises(ValueError):
        compare_policy_condition(actual_value="buy", expected_value="buy", operator="bad")

    with pytest.raises(ValueError):
        compare_policy_condition(actual_value="buy", expected_value="buy", operator="in")

    with pytest.raises(ValueError):
        compare_policy_condition(actual_value=123, expected_value="1", operator="contains")


def test_policy_condition_to_dict_and_matches():
    condition = PolicyCondition(
        field="context.side",
        operator="EQ",
        value="buy",
        description="Side must be buy.",
    )

    assert condition.to_dict() == {
        "field": "context.side",
        "operator": "eq",
        "value": "buy",
        "description": "Side must be buy.",
    }

    assert condition.matches(
        {
            "context": {
                "side": "buy",
            },
        },
    ) is True

    assert condition.matches(
        {
            "context": {
                "side": "sell",
            },
        },
    ) is False


def test_policy_condition_rejects_invalid_values():
    with pytest.raises(ValueError):
        PolicyCondition(field="", operator="eq")

    with pytest.raises(ValueError):
        PolicyCondition(field="context.side", operator="bad")

    with pytest.raises(ValueError):
        PolicyCondition(field="context.side", operator="eq", description=123)


def test_build_policy_condition():
    condition = build_policy_condition(
        field="risk.score",
        operator="lte",
        value=0.5,
    )

    assert isinstance(condition, PolicyCondition)
    assert condition.matches(
        {
            "risk": {
                "score": 0.4,
            },
        },
    ) is True


def test_policy_rule_to_dict_and_matches():
    principal = SecurityPrincipal(
        principal_id="user-1",
        roles=[
            "trader",
        ],
    )
    request = PolicyEvaluationRequest(
        principal=principal,
        action="trade.execute",
        resource="/api/trade",
        context={
            "side": "buy",
            "risk": {
                "score": 0.5,
            },
        },
    )

    rule = PolicyRule(
        name="allow-safe-trade",
        effect="ALLOW",
        action="trade.*",
        resource="/api/*",
        conditions=[
            PolicyCondition(
                field="risk.score",
                operator="lte",
                value=0.5,
            ),
        ],
        priority=10,
        enabled=True,
        risk_level="low",
        description="Allow safe trades.",
        metadata={
            "owner": "security",
        },
    )

    assert rule.matches(request) is True
    assert rule.to_dict()["name"] == "allow-safe-trade"
    assert rule.to_dict()["effect"] == "allow"
    assert rule.to_dict()["conditions"][0]["field"] == "risk.score"


def test_disabled_policy_rule_does_not_match():
    principal = SecurityPrincipal(principal_id="user-1")

    request = PolicyEvaluationRequest(
        principal=principal,
        action="trade.execute",
        resource="/api/trade",
    )

    rule = PolicyRule(
        name="disabled",
        effect="allow",
        action="*",
        enabled=False,
    )

    assert rule.matches(request) is False


def test_policy_rule_rejects_invalid_values():
    with pytest.raises(ValueError):
        PolicyRule(name="", effect="allow", action="trade.execute")

    with pytest.raises(ValueError):
        PolicyRule(name="rule", effect="bad", action="trade.execute")

    with pytest.raises(ValueError):
        PolicyRule(name="rule", effect="allow", action="")

    with pytest.raises(ValueError):
        PolicyRule(name="rule", effect="allow", action="bad action")

    with pytest.raises(ValueError):
        PolicyRule(name="rule", effect="allow", action="trade.execute", resource="bad resource")

    with pytest.raises(ValueError):
        PolicyRule(name="rule", effect="allow", action="trade.execute", conditions=["bad"])

    with pytest.raises(ValueError):
        PolicyRule(name="rule", effect="allow", action="trade.execute", priority=True)

    with pytest.raises(ValueError):
        PolicyRule(name="rule", effect="allow", action="trade.execute", enabled="yes")

    with pytest.raises(ValueError):
        PolicyRule(name="rule", effect="allow", action="trade.execute", risk_level="bad")

    with pytest.raises(ValueError):
        PolicyRule(name="rule", effect="allow", action="trade.execute", description=123)

    with pytest.raises(ValueError):
        PolicyRule(name="rule", effect="allow", action="trade.execute", metadata=[])


def test_build_policy_rule():
    rule = build_policy_rule(
        name="allow-market-read",
        effect="allow",
        action="market.read",
        resource="/api/market",
    )

    assert isinstance(rule, PolicyRule)
    assert rule.effect == "allow"


def test_policy_evaluation_request_to_dict():
    principal = SecurityPrincipal(
        principal_id="user-1",
        roles=[
            "trader",
        ],
    )

    request = PolicyEvaluationRequest(
        principal=principal,
        action="trade.execute",
        resource="/api/trade",
        context={
            "side": "buy",
        },
    )

    assert request.to_dict() == {
        "principal": principal.to_dict(),
        "action": "trade.execute",
        "resource": "/api/trade",
        "context": {
            "side": "buy",
        },
    }


def test_policy_evaluation_request_rejects_invalid_values():
    principal = SecurityPrincipal(principal_id="user-1")

    with pytest.raises(ValueError):
        PolicyEvaluationRequest(
            principal="bad",
            action="trade.execute",
            resource="/api/trade",
        )

    with pytest.raises(ValueError):
        PolicyEvaluationRequest(
            principal=principal,
            action="",
            resource="/api/trade",
        )

    with pytest.raises(ValueError):
        PolicyEvaluationRequest(
            principal=principal,
            action="trade.execute",
            resource="",
        )

    with pytest.raises(ValueError):
        PolicyEvaluationRequest(
            principal=principal,
            action="trade.execute",
            resource="/api/trade",
            context=[],
        )


def test_build_policy_context():
    principal = SecurityPrincipal(
        principal_id="user-1",
        roles=[
            "trader",
        ],
    )
    request = build_policy_evaluation_request(
        principal=principal,
        action="trade.execute",
        resource="/api/trade",
        context={
            "side": "buy",
        },
    )

    context = build_policy_context(request)

    assert context["principal"] == principal.to_dict()
    assert context["action"] == "trade.execute"
    assert context["resource"] == "/api/trade"
    assert context["side"] == "buy"


def test_policy_evaluation_result_to_dict_and_security_result():
    result = PolicyEvaluationResult(
        allowed=True,
        decision="ALLOW",
        reason="Allowed.",
        principal_id="user-1",
        action="trade.execute",
        resource="/api/trade",
        matched_rules=[
            "allow-trade",
        ],
        risk_level="LOW",
        metadata={
            "source": "test",
        },
    )

    assert result.denied is False

    assert result.to_dict() == {
        "allowed": True,
        "denied": False,
        "decision": "allow",
        "reason": "Allowed.",
        "principal_id": "user-1",
        "action": "trade.execute",
        "resource": "/api/trade",
        "matched_rules": [
            "allow-trade",
        ],
        "risk_level": "low",
        "metadata": {
            "source": "test",
        },
    }

    security_result = result.to_security_result()

    assert security_result.decision == SecurityDecision.ALLOW
    assert security_result.allowed is True
    assert security_result.principal_id == "user-1"


def test_policy_evaluation_result_rejects_invalid_values():
    with pytest.raises(ValueError):
        PolicyEvaluationResult(
            allowed="yes",
            decision="allow",
            reason="Allowed.",
            principal_id="user-1",
            action="trade.execute",
            resource="/api/trade",
        )

    with pytest.raises(ValueError):
        PolicyEvaluationResult(
            allowed=True,
            decision="bad",
            reason="Allowed.",
            principal_id="user-1",
            action="trade.execute",
            resource="/api/trade",
        )

    with pytest.raises(ValueError):
        PolicyEvaluationResult(
            allowed=True,
            decision="allow",
            reason=123,
            principal_id="user-1",
            action="trade.execute",
            resource="/api/trade",
        )

    with pytest.raises(ValueError):
        PolicyEvaluationResult(
            allowed=True,
            decision="allow",
            reason="Allowed.",
            principal_id="",
            action="trade.execute",
            resource="/api/trade",
        )

    with pytest.raises(ValueError):
        PolicyEvaluationResult(
            allowed=True,
            decision="allow",
            reason="Allowed.",
            principal_id="user-1",
            action="",
            resource="/api/trade",
        )

    with pytest.raises(ValueError):
        PolicyEvaluationResult(
            allowed=True,
            decision="allow",
            reason="Allowed.",
            principal_id="user-1",
            action="trade.execute",
            resource="",
        )

    with pytest.raises(ValueError):
        PolicyEvaluationResult(
            allowed=True,
            decision="allow",
            reason="Allowed.",
            principal_id="user-1",
            action="trade.execute",
            resource="/api/trade",
            matched_rules=[""],
        )

    with pytest.raises(ValueError):
        PolicyEvaluationResult(
            allowed=True,
            decision="allow",
            reason="Allowed.",
            principal_id="user-1",
            action="trade.execute",
            resource="/api/trade",
            risk_level="bad",
        )

    with pytest.raises(ValueError):
        PolicyEvaluationResult(
            allowed=True,
            decision="allow",
            reason="Allowed.",
            principal_id="user-1",
            action="trade.execute",
            resource="/api/trade",
            metadata=[],
        )


def test_policy_engine_register_evaluate_allow_and_deny():
    principal = SecurityPrincipal(
        principal_id="user-1",
        roles=[
            "trader",
        ],
    )

    allow_rule = build_policy_rule(
        name="allow-safe-trade",
        effect="allow",
        action="trade.execute",
        resource="/api/trade",
        conditions=[
            build_policy_condition(
                field="risk.score",
                operator="lte",
                value=0.5,
            ),
        ],
        priority=20,
        risk_level="low",
    )

    deny_rule = build_policy_rule(
        name="deny-high-risk-trade",
        effect="deny",
        action="trade.execute",
        resource="/api/trade",
        conditions=[
            build_policy_condition(
                field="risk.score",
                operator="gt",
                value=0.5,
            ),
        ],
        priority=10,
        risk_level="high",
    )

    engine = build_policy_engine(
        rules=[
            allow_rule,
            deny_rule,
        ],
    )

    allowed = engine.evaluate_action(
        principal=principal,
        action="trade.execute",
        resource="/api/trade",
        context={
            "risk": {
                "score": 0.4,
            },
        },
    )

    denied = engine.evaluate_action(
        principal=principal,
        action="trade.execute",
        resource="/api/trade",
        context={
            "risk": {
                "score": 0.9,
            },
        },
    )

    assert allowed.allowed is True
    assert allowed.reason == "Allowed by policy rule 'allow-safe-trade'."
    assert denied.allowed is False
    assert denied.reason == "Denied by policy rule 'deny-high-risk-trade'."


def test_policy_engine_deny_takes_precedence():
    principal = SecurityPrincipal(principal_id="user-1")

    allow_rule = build_policy_rule(
        name="allow-all-trades",
        effect="allow",
        action="trade.execute",
        resource="/api/trade",
        priority=20,
    )
    deny_rule = build_policy_rule(
        name="deny-all-trades",
        effect="deny",
        action="trade.execute",
        resource="/api/trade",
        priority=10,
    )

    engine = build_policy_engine(
        rules=[
            allow_rule,
            deny_rule,
        ],
    )

    result = engine.evaluate_action(
        principal=principal,
        action="trade.execute",
        resource="/api/trade",
    )

    assert result.allowed is False
    assert result.metadata["deny_rule"] == "deny-all-trades"
    assert result.matched_rules == [
        "deny-all-trades",
        "allow-all-trades",
    ]


def test_policy_engine_default_decision():
    principal = SecurityPrincipal(principal_id="user-1")

    deny_engine = build_policy_engine()
    deny_result = deny_engine.evaluate_action(
        principal=principal,
        action="market.read",
        resource="/api/market",
    )

    assert deny_result.allowed is False
    assert deny_result.reason == "No policy rule matched."

    allow_engine = build_policy_engine(default_decision="allow")
    allow_result = allow_engine.evaluate_action(
        principal=principal,
        action="market.read",
        resource="/api/market",
    )

    assert allow_result.allowed is True
    assert allow_result.metadata["default_decision"] == "allow"


def test_policy_engine_summary_clear_and_list_rules():
    disabled_rule = build_policy_rule(
        name="disabled",
        effect="allow",
        action="market.read",
        enabled=False,
        priority=10,
    )
    enabled_rule = build_policy_rule(
        name="enabled",
        effect="allow",
        action="market.read",
        priority=5,
    )

    engine = build_policy_engine(
        rules=[
            disabled_rule,
            enabled_rule,
        ],
    )

    assert engine.list_rules() == [
        enabled_rule,
        disabled_rule,
    ]
    assert engine.list_rules(enabled_only=True) == [
        enabled_rule,
    ]

    assert engine.summary() == {
        "rules": 2,
        "enabled_rules": 1,
        "disabled_rules": 1,
        "default_decision": "deny",
        "rule_names": [
            "disabled",
            "enabled",
        ],
    }

    engine.clear()

    assert engine.summary()["rules"] == 0


def test_policy_engine_rejects_invalid_values():
    engine = PolicyEngine()

    with pytest.raises(ValueError):
        PolicyEngine(default_decision="bad")

    with pytest.raises(ValueError):
        PolicyEngine(rules={"bad": "bad"})

    with pytest.raises(ValueError):
        engine.register_rule("bad")

    with pytest.raises(ValueError):
        engine.upsert_rule("bad")

    rule = build_policy_rule(
        name="allow-market",
        effect="allow",
        action="market.read",
    )

    engine.register_rule(rule)

    with pytest.raises(ValueError):
        engine.register_rule(rule)

    with pytest.raises(ValueError):
        engine.get_required_rule("missing-rule")

    with pytest.raises(ValueError):
        engine.list_rules(enabled_only="yes")

    with pytest.raises(ValueError):
        engine.evaluate("bad")


def test_security_policy_exports_exist():
    import aqos.security as security

    expected_exports = [
        "PolicyCondition",
        "PolicyEffect",
        "PolicyEngine",
        "PolicyEvaluationRequest",
        "PolicyEvaluationResult",
        "PolicyOperator",
        "PolicyRule",
        "build_policy_condition",
        "build_policy_context",
        "build_policy_engine",
        "build_policy_evaluation_request",
        "build_policy_rule",
        "compare_policy_condition",
        "get_nested_context_value",
        "match_policy_pattern",
        "normalize_policy_effect",
        "normalize_policy_operator",
        "validate_policy_action",
        "validate_policy_conditions",
        "validate_policy_field",
        "validate_policy_name",
        "validate_policy_priority",
        "validate_policy_resource",
    ]

    for export_name in expected_exports:
        assert hasattr(security, export_name), export_name