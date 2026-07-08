"""
Unit tests for AQOS security scaffold.
"""

import pytest

from aqos.security import (
    SecurityDecision,
    SecurityPrincipal,
    SecurityResult,
    SecurityRiskLevel,
    build_security_principal,
    build_security_result,
    normalize_risk_level,
    normalize_security_decision,
    validate_attributes,
    validate_non_empty_string,
    validate_string,
    validate_string_list,
)


def test_security_decision_values():
    assert SecurityDecision.ALLOW.value == "allow"
    assert SecurityDecision.DENY.value == "deny"


def test_security_risk_level_values():
    assert SecurityRiskLevel.LOW.value == "low"
    assert SecurityRiskLevel.MEDIUM.value == "medium"
    assert SecurityRiskLevel.HIGH.value == "high"
    assert SecurityRiskLevel.CRITICAL.value == "critical"


def test_normalize_security_decision_accepts_enum_and_string():
    assert normalize_security_decision(SecurityDecision.ALLOW) == SecurityDecision.ALLOW
    assert normalize_security_decision(" ALLOW ") == SecurityDecision.ALLOW
    assert normalize_security_decision("deny") == SecurityDecision.DENY


def test_normalize_security_decision_rejects_invalid_value():
    with pytest.raises(ValueError):
        normalize_security_decision("bad")

    with pytest.raises(ValueError):
        normalize_security_decision("")


def test_normalize_risk_level_accepts_enum_and_string():
    assert normalize_risk_level(SecurityRiskLevel.LOW) == SecurityRiskLevel.LOW
    assert normalize_risk_level(" LOW ") == SecurityRiskLevel.LOW
    assert normalize_risk_level("medium") == SecurityRiskLevel.MEDIUM
    assert normalize_risk_level("HIGH") == SecurityRiskLevel.HIGH
    assert normalize_risk_level("critical") == SecurityRiskLevel.CRITICAL


def test_normalize_risk_level_rejects_invalid_value():
    with pytest.raises(ValueError):
        normalize_risk_level("bad")

    with pytest.raises(ValueError):
        normalize_risk_level("")


def test_validate_string_accepts_string():
    assert validate_string("", "Field") == ""
    assert validate_string("value", "Field") == "value"


def test_validate_string_rejects_non_string():
    with pytest.raises(ValueError):
        validate_string(123, "Field")


def test_validate_non_empty_string_accepts_trimmed_value():
    assert validate_non_empty_string(" value ", "Field") == "value"


def test_validate_non_empty_string_rejects_empty_value():
    with pytest.raises(ValueError):
        validate_non_empty_string("", "Field")

    with pytest.raises(ValueError):
        validate_non_empty_string("   ", "Field")


def test_validate_attributes_accepts_dictionary():
    attributes = {
        "ip": "127.0.0.1",
    }

    assert validate_attributes(attributes) == attributes


def test_validate_attributes_rejects_non_dictionary():
    with pytest.raises(ValueError):
        validate_attributes([])


def test_validate_string_list_accepts_list_of_strings():
    assert validate_string_list(
        [
            " admin ",
            "trader",
        ],
        "Roles",
    ) == [
        "admin",
        "trader",
    ]


def test_validate_string_list_rejects_invalid_values():
    with pytest.raises(ValueError):
        validate_string_list("admin", "Roles")

    with pytest.raises(ValueError):
        validate_string_list(["admin", ""], "Roles")

    with pytest.raises(ValueError):
        validate_string_list(["admin", 123], "Roles")


def test_security_principal_to_dict():
    principal = SecurityPrincipal(
        principal_id=" user-1 ",
        principal_type=" user ",
        roles=[
            " admin ",
            " trader ",
        ],
        attributes={
            "email": "zohaib@example.com",
        },
    )

    assert principal.to_dict() == {
        "principal_id": "user-1",
        "principal_type": "user",
        "roles": [
            "admin",
            "trader",
        ],
        "attributes": {
            "email": "zohaib@example.com",
        },
    }


def test_security_principal_has_role():
    principal = SecurityPrincipal(
        principal_id="user-1",
        roles=[
            "admin",
            "trader",
        ],
    )

    assert principal.has_role("admin") is True
    assert principal.has_role("trader") is True
    assert principal.has_role("viewer") is False


def test_security_principal_defaults():
    principal = SecurityPrincipal(
        principal_id="anonymous",
    )

    assert principal.to_dict() == {
        "principal_id": "anonymous",
        "principal_type": "user",
        "roles": [],
        "attributes": {},
    }


def test_security_principal_rejects_invalid_values():
    with pytest.raises(ValueError):
        SecurityPrincipal(principal_id="")

    with pytest.raises(ValueError):
        SecurityPrincipal(
            principal_id="user-1",
            principal_type="",
        )

    with pytest.raises(ValueError):
        SecurityPrincipal(
            principal_id="user-1",
            roles="admin",
        )

    with pytest.raises(ValueError):
        SecurityPrincipal(
            principal_id="user-1",
            roles=[""],
        )

    with pytest.raises(ValueError):
        SecurityPrincipal(
            principal_id="user-1",
            attributes=[],
        )

    principal = SecurityPrincipal(principal_id="user-1")

    with pytest.raises(ValueError):
        principal.has_role("")


def test_build_security_principal():
    principal = build_security_principal(
        principal_id="user-1",
        principal_type="service",
        roles=[
            "agent",
        ],
        attributes={
            "service": "market-agent",
        },
    )

    assert isinstance(principal, SecurityPrincipal)
    assert principal.to_dict() == {
        "principal_id": "user-1",
        "principal_type": "service",
        "roles": [
            "agent",
        ],
        "attributes": {
            "service": "market-agent",
        },
    }


def test_security_result_allow_to_dict():
    result = SecurityResult(
        decision="ALLOW",
        reason="User has permission.",
        risk_level="LOW",
        principal_id="user-1",
        metadata={
            "permission": "trade.execute",
        },
    )

    assert result.allowed is True
    assert result.denied is False
    assert result.to_dict() == {
        "decision": "allow",
        "allowed": True,
        "denied": False,
        "reason": "User has permission.",
        "risk_level": "low",
        "principal_id": "user-1",
        "metadata": {
            "permission": "trade.execute",
        },
    }


def test_security_result_deny_to_dict():
    result = SecurityResult(
        decision=SecurityDecision.DENY,
        reason="Missing permission.",
        risk_level=SecurityRiskLevel.HIGH,
    )

    assert result.allowed is False
    assert result.denied is True
    assert result.to_dict() == {
        "decision": "deny",
        "allowed": False,
        "denied": True,
        "reason": "Missing permission.",
        "risk_level": "high",
        "metadata": {},
    }


def test_security_result_rejects_invalid_values():
    with pytest.raises(ValueError):
        SecurityResult(decision="bad")

    with pytest.raises(ValueError):
        SecurityResult(
            decision="allow",
            reason=123,
        )

    with pytest.raises(ValueError):
        SecurityResult(
            decision="allow",
            risk_level="bad",
        )

    with pytest.raises(ValueError):
        SecurityResult(
            decision="allow",
            principal_id="",
        )

    with pytest.raises(ValueError):
        SecurityResult(
            decision="allow",
            metadata=[],
        )


def test_build_security_result():
    result = build_security_result(
        decision="deny",
        reason="Token expired.",
        risk_level="medium",
        principal_id="user-1",
        metadata={
            "token": "expired",
        },
    )

    assert isinstance(result, SecurityResult)
    assert result.to_dict() == {
        "decision": "deny",
        "allowed": False,
        "denied": True,
        "reason": "Token expired.",
        "risk_level": "medium",
        "principal_id": "user-1",
        "metadata": {
            "token": "expired",
        },
    }


def test_security_exports_are_sorted():
    import aqos.security as security

    assert security.__all__ == sorted(security.__all__)


def test_security_exports_exist():
    import aqos.security as security

    for export_name in security.__all__:
        assert hasattr(security, export_name), export_name