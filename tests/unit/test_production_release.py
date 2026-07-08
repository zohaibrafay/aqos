"""
Unit tests for AQOS production release gate engine.
"""

import pytest

from aqos.production import (
    ProductionStatus,
    ReleaseDecision,
    ReleaseEvaluation,
    ReleaseGate,
    ReleaseGateEngine,
    ReleaseGateType,
    ReleasePlan,
    ReleaseReport,
    aggregate_release_decision,
    build_production_gate_result,
    build_release_evaluation,
    build_release_gate,
    build_release_gate_engine,
    build_release_plan,
    build_release_report,
    decide_release_from_status,
    evaluate_release_gate,
    normalize_release_decision,
    normalize_release_gate_type,
    run_release_gate_engine,
    validate_evaluator_mapping,
    validate_release_evaluations,
    validate_release_gates,
)


def test_release_gate_type_values():
    assert ReleaseGateType.READINESS.value == "readiness"
    assert ReleaseGateType.PERFORMANCE.value == "performance"
    assert ReleaseGateType.SECURITY.value == "security"
    assert ReleaseGateType.CONFIGURATION.value == "configuration"
    assert ReleaseGateType.DEPLOYMENT.value == "deployment"
    assert ReleaseGateType.CUSTOM.value == "custom"


def test_release_decision_values():
    assert ReleaseDecision.APPROVE.value == "approve"
    assert ReleaseDecision.WARN.value == "warn"
    assert ReleaseDecision.BLOCK.value == "block"


def test_normalize_release_gate_type_accepts_enum_and_string():
    assert normalize_release_gate_type(ReleaseGateType.READINESS) == ReleaseGateType.READINESS
    assert normalize_release_gate_type(" READINESS ") == ReleaseGateType.READINESS
    assert normalize_release_gate_type("performance") == ReleaseGateType.PERFORMANCE
    assert normalize_release_gate_type("SECURITY") == ReleaseGateType.SECURITY


def test_normalize_release_gate_type_rejects_invalid_value():
    with pytest.raises(ValueError):
        normalize_release_gate_type("bad")

    with pytest.raises(ValueError):
        normalize_release_gate_type("")


def test_normalize_release_decision_accepts_enum_and_string():
    assert normalize_release_decision(ReleaseDecision.APPROVE) == ReleaseDecision.APPROVE
    assert normalize_release_decision(" APPROVE ") == ReleaseDecision.APPROVE
    assert normalize_release_decision("warn") == ReleaseDecision.WARN
    assert normalize_release_decision("BLOCK") == ReleaseDecision.BLOCK


def test_normalize_release_decision_rejects_invalid_value():
    with pytest.raises(ValueError):
        normalize_release_decision("bad")

    with pytest.raises(ValueError):
        normalize_release_decision("")


def test_release_gate_to_dict():
    gate = ReleaseGate(
        name=" readiness ",
        gate_type="READINESS",
        required=True,
        description=" Readiness gate. ",
        metadata={
            "scope": "api",
        },
    )

    assert gate.to_dict() == {
        "name": "readiness",
        "gate_type": "readiness",
        "required": True,
        "description": "Readiness gate.",
        "metadata": {
            "scope": "api",
        },
    }


def test_release_gate_rejects_invalid_values():
    with pytest.raises(ValueError):
        ReleaseGate(name="", gate_type="readiness")

    with pytest.raises(ValueError):
        ReleaseGate(name="gate", gate_type="bad")

    with pytest.raises(ValueError):
        ReleaseGate(name="gate", gate_type="readiness", required="yes")

    with pytest.raises(ValueError):
        ReleaseGate(name="gate", gate_type="readiness", description=123)

    with pytest.raises(ValueError):
        ReleaseGate(name="gate", gate_type="readiness", metadata=[])


def test_build_release_gate():
    gate = build_release_gate(
        name="performance",
        gate_type="performance",
        metadata={
            "source": "test",
        },
    )

    assert isinstance(gate, ReleaseGate)
    assert gate.metadata == {
        "source": "test",
    }


def test_validate_release_gates():
    gate = build_release_gate(
        name="readiness",
        gate_type="readiness",
    )

    assert validate_release_gates([gate]) == [gate]

    with pytest.raises(ValueError):
        validate_release_gates("bad")

    with pytest.raises(ValueError):
        validate_release_gates(["bad"])


def test_decide_release_from_status():
    assert decide_release_from_status("ready") == ReleaseDecision.APPROVE
    assert decide_release_from_status("warning") == ReleaseDecision.WARN
    assert decide_release_from_status("blocked") == ReleaseDecision.BLOCK
    assert decide_release_from_status("blocked", required=False) == ReleaseDecision.WARN
    assert decide_release_from_status("unknown") == ReleaseDecision.BLOCK
    assert decide_release_from_status("unknown", required=False) == ReleaseDecision.WARN

    with pytest.raises(ValueError):
        decide_release_from_status("ready", required="yes")


def test_release_evaluation_to_dict_and_check_result():
    gate = build_release_gate(
        name="readiness",
        gate_type="readiness",
    )
    gate_result = build_production_gate_result(
        gate_name="readiness",
        status="ready",
        message="Ready.",
        timestamp="2026-01-01T00:00:00+00:00",
    )
    evaluation = ReleaseEvaluation(
        gate=gate,
        gate_result=gate_result,
        decision="APPROVE",
        message=" Approved. ",
        metadata={
            "source": "test",
        },
    )

    assert evaluation.approved is True
    assert evaluation.warning is False
    assert evaluation.blocked is False

    payload = evaluation.to_dict()

    assert payload["decision"] == "approve"
    assert payload["approved"] is True
    assert payload["metadata"] == {
        "source": "test",
    }

    check = evaluation.to_check_result()

    assert check.status == ProductionStatus.READY
    assert check.passed is True


def test_release_evaluation_warning_and_blocked_check_results():
    optional_gate = build_release_gate(
        name="optional",
        gate_type="custom",
        required=False,
    )
    required_gate = build_release_gate(
        name="required",
        gate_type="custom",
    )
    warning_result = build_production_gate_result(
        gate_name="optional",
        status="warning",
    )
    blocked_result = build_production_gate_result(
        gate_name="required",
        status="blocked",
    )

    warning_evaluation = build_release_evaluation(
        gate=optional_gate,
        gate_result=warning_result,
        decision="warn",
    )
    blocked_evaluation = build_release_evaluation(
        gate=required_gate,
        gate_result=blocked_result,
        decision="block",
    )

    assert warning_evaluation.to_check_result().status == ProductionStatus.WARNING
    assert warning_evaluation.to_check_result().passed is True
    assert blocked_evaluation.to_check_result().status == ProductionStatus.BLOCKED
    assert blocked_evaluation.to_check_result().passed is False


def test_release_evaluation_rejects_invalid_values():
    gate = build_release_gate(
        name="readiness",
        gate_type="readiness",
    )
    gate_result = build_production_gate_result(
        gate_name="readiness",
        status="ready",
    )

    with pytest.raises(ValueError):
        ReleaseEvaluation(
            gate="bad",
            gate_result=gate_result,
            decision="approve",
        )

    with pytest.raises(ValueError):
        ReleaseEvaluation(
            gate=gate,
            gate_result="bad",
            decision="approve",
        )

    with pytest.raises(ValueError):
        ReleaseEvaluation(
            gate=gate,
            gate_result=gate_result,
            decision="bad",
        )

    with pytest.raises(ValueError):
        ReleaseEvaluation(
            gate=gate,
            gate_result=gate_result,
            decision="approve",
            message=123,
        )

    with pytest.raises(ValueError):
        ReleaseEvaluation(
            gate=gate,
            gate_result=gate_result,
            decision="approve",
            metadata=[],
        )


def test_validate_release_evaluations():
    gate = build_release_gate(
        name="readiness",
        gate_type="readiness",
    )
    gate_result = build_production_gate_result(
        gate_name="readiness",
        status="ready",
    )
    evaluation = build_release_evaluation(
        gate=gate,
        gate_result=gate_result,
        decision="approve",
    )

    assert validate_release_evaluations([evaluation]) == [evaluation]

    with pytest.raises(ValueError):
        validate_release_evaluations("bad")

    with pytest.raises(ValueError):
        validate_release_evaluations(["bad"])


def test_release_plan_to_dict():
    gate = build_release_gate(
        name="readiness",
        gate_type="readiness",
    )
    plan = ReleasePlan(
        version=" v0.20.0-dev ",
        environment=" production ",
        gates=[gate],
        metadata={
            "branch": "main",
        },
    )

    payload = plan.to_dict()

    assert payload["version"] == "v0.20.0-dev"
    assert payload["environment"] == "production"
    assert payload["gate_names"] == ["readiness"]
    assert payload["metadata"] == {
        "branch": "main",
    }


def test_release_plan_rejects_invalid_values():
    with pytest.raises(ValueError):
        ReleasePlan(version="", environment="production")

    with pytest.raises(ValueError):
        ReleasePlan(version="v1", environment="")

    with pytest.raises(ValueError):
        ReleasePlan(version="v1", environment="production", gates=["bad"])

    with pytest.raises(ValueError):
        ReleasePlan(version="v1", environment="production", metadata=[])


def test_build_release_plan():
    gate = build_release_gate(
        name="readiness",
        gate_type="readiness",
    )
    plan = build_release_plan(
        version="v0.20.0-dev",
        environment="production",
        gates=[gate],
        metadata={
            "source": "test",
        },
    )

    assert isinstance(plan, ReleasePlan)
    assert plan.gate_names == ["readiness"]


def test_aggregate_release_decision():
    gate = build_release_gate(
        name="readiness",
        gate_type="readiness",
    )
    ready_result = build_production_gate_result(
        gate_name="readiness",
        status="ready",
    )
    warning_result = build_production_gate_result(
        gate_name="warning",
        status="warning",
    )
    blocked_result = build_production_gate_result(
        gate_name="blocked",
        status="blocked",
    )

    approved = build_release_evaluation(
        gate=gate,
        gate_result=ready_result,
        decision="approve",
    )
    warning = build_release_evaluation(
        gate=gate,
        gate_result=warning_result,
        decision="warn",
    )
    blocked = build_release_evaluation(
        gate=gate,
        gate_result=blocked_result,
        decision="block",
    )

    assert aggregate_release_decision([]) == ReleaseDecision.BLOCK
    assert aggregate_release_decision([approved]) == ReleaseDecision.APPROVE
    assert aggregate_release_decision([approved, warning]) == ReleaseDecision.WARN
    assert aggregate_release_decision([approved, blocked]) == ReleaseDecision.BLOCK


def test_release_report_to_dict_and_gate_result():
    gate = build_release_gate(
        name="readiness",
        gate_type="readiness",
    )
    plan = build_release_plan(
        version="v0.20.0-dev",
        environment="production",
        gates=[gate],
    )
    gate_result = build_production_gate_result(
        gate_name="readiness",
        status="ready",
    )
    evaluation = build_release_evaluation(
        gate=gate,
        gate_result=gate_result,
        decision="approve",
    )
    report = ReleaseReport(
        plan=plan,
        evaluations=[evaluation],
        decision="APPROVE",
        generated_at="2026-01-01T00:00:00+00:00",
        metadata={
            "source": "test",
        },
    )

    assert report.approved is True
    assert report.warning is False
    assert report.blocked is False

    payload = report.to_dict()

    assert payload["decision"] == "approve"
    assert payload["approved"] is True
    assert payload["metadata"] == {
        "source": "test",
    }

    gate_result = report.to_gate_result()

    assert gate_result.gate_name == "release-gate"
    assert gate_result.status == ProductionStatus.READY
    assert gate_result.passed is True


def test_release_report_rejects_invalid_values():
    gate = build_release_gate(
        name="readiness",
        gate_type="readiness",
    )
    plan = build_release_plan(
        version="v1",
        environment="production",
        gates=[gate],
    )

    with pytest.raises(ValueError):
        ReleaseReport(plan="bad")

    with pytest.raises(ValueError):
        ReleaseReport(plan=plan, evaluations=["bad"])

    with pytest.raises(ValueError):
        ReleaseReport(plan=plan, decision="bad")

    with pytest.raises(ValueError):
        ReleaseReport(plan=plan, generated_at="")

    with pytest.raises(ValueError):
        ReleaseReport(plan=plan, metadata=[])


def test_build_release_report_aggregates_decision():
    gate = build_release_gate(
        name="readiness",
        gate_type="readiness",
    )
    plan = build_release_plan(
        version="v1",
        environment="production",
        gates=[gate],
    )
    gate_result = build_production_gate_result(
        gate_name="readiness",
        status="ready",
    )
    evaluation = build_release_evaluation(
        gate=gate,
        gate_result=gate_result,
        decision="approve",
    )

    report = build_release_report(
        plan=plan,
        evaluations=[evaluation],
        generated_at="2026-01-01T00:00:00+00:00",
    )

    assert isinstance(report, ReleaseReport)
    assert report.decision == ReleaseDecision.APPROVE


def test_evaluate_release_gate_ready_missing_optional_and_failure():
    ready_gate = build_release_gate(
        name="readiness",
        gate_type="readiness",
    )
    optional_gate = build_release_gate(
        name="optional",
        gate_type="custom",
        required=False,
    )

    ready_evaluation = evaluate_release_gate(
        gate=ready_gate,
        evaluator=lambda: build_production_gate_result(
            gate_name="readiness",
            status="ready",
        ),
    )

    missing_optional = evaluate_release_gate(
        gate=optional_gate,
        evaluator=None,
    )

    def fail():
        raise RuntimeError("boom")

    failed_evaluation = evaluate_release_gate(
        gate=ready_gate,
        evaluator=fail,
    )

    assert ready_evaluation.decision == ReleaseDecision.APPROVE
    assert missing_optional.decision == ReleaseDecision.WARN
    assert failed_evaluation.decision == ReleaseDecision.BLOCK
    assert failed_evaluation.gate_result.status == ProductionStatus.BLOCKED


def test_evaluate_release_gate_rejects_invalid_values():
    gate = build_release_gate(
        name="readiness",
        gate_type="readiness",
    )

    with pytest.raises(ValueError):
        evaluate_release_gate(
            gate="bad",
            evaluator=lambda: build_production_gate_result(
                gate_name="readiness",
                status="ready",
            ),
        )

    with pytest.raises(ValueError):
        evaluate_release_gate(
            gate=gate,
            evaluator="bad",
        )


def test_validate_evaluator_mapping():
    evaluators = {
        "readiness": lambda: build_production_gate_result(
            gate_name="readiness",
            status="ready",
        ),
    }

    assert validate_evaluator_mapping(evaluators) == evaluators

    with pytest.raises(ValueError):
        validate_evaluator_mapping("bad")

    with pytest.raises(ValueError):
        validate_evaluator_mapping({"": lambda: None})

    with pytest.raises(ValueError):
        validate_evaluator_mapping({"readiness": "bad"})


def test_release_gate_engine_evaluate_all_success_warning_and_blocked():
    readiness_gate = build_release_gate(
        name="readiness",
        gate_type="readiness",
    )
    performance_gate = build_release_gate(
        name="performance",
        gate_type="performance",
        required=False,
    )
    security_gate = build_release_gate(
        name="security",
        gate_type="security",
    )
    plan = build_release_plan(
        version="v0.20.0-dev",
        environment="production",
        gates=[
            readiness_gate,
            performance_gate,
            security_gate,
        ],
    )
    engine = build_release_gate_engine(
        plan=plan,
        evaluators={
            "readiness": lambda: build_production_gate_result(
                gate_name="readiness",
                status="ready",
            ),
            "performance": lambda: build_production_gate_result(
                gate_name="performance",
                status="warning",
            ),
            "security": lambda: build_production_gate_result(
                gate_name="security",
                status="ready",
            ),
        },
        metadata={
            "source": "test",
        },
    )

    report = engine.evaluate_all()

    assert isinstance(engine, ReleaseGateEngine)
    assert report.warning is True
    assert report.decision == ReleaseDecision.WARN
    assert len(report.evaluations) == 3
    assert engine.summary()["evaluations"] == 3

    engine.clear()

    assert engine.summary()["evaluations"] == 0


def test_release_gate_engine_missing_required_blocks():
    gate = build_release_gate(
        name="readiness",
        gate_type="readiness",
    )
    plan = build_release_plan(
        version="v1",
        environment="production",
        gates=[gate],
    )
    engine = build_release_gate_engine(
        plan=plan,
    )

    report = engine.evaluate_all()

    assert report.blocked is True
    assert report.decision == ReleaseDecision.BLOCK
    assert report.evaluations[0].message == "Release gate evaluator is missing."


def test_release_gate_engine_register_evaluator_and_run_helper():
    gate = build_release_gate(
        name="readiness",
        gate_type="readiness",
    )
    plan = build_release_plan(
        version="v1",
        environment="production",
        gates=[gate],
    )
    engine = build_release_gate_engine(
        plan=plan,
    )

    engine.register_evaluator(
        "readiness",
        lambda: build_production_gate_result(
            gate_name="readiness",
            status="ready",
        ),
    )

    report = engine.evaluate_all()

    assert report.approved is True

    helper_report = run_release_gate_engine(
        plan=plan,
        evaluators={
            "readiness": lambda: build_production_gate_result(
                gate_name="readiness",
                status="ready",
            ),
        },
        metadata={
            "source": "helper",
        },
    )

    assert helper_report.approved is True
    assert helper_report.metadata == {
        "source": "helper",
    }


def test_release_gate_engine_rejects_invalid_values():
    gate = build_release_gate(
        name="readiness",
        gate_type="readiness",
    )
    plan = build_release_plan(
        version="v1",
        environment="production",
        gates=[gate],
    )

    with pytest.raises(ValueError):
        ReleaseGateEngine(plan="bad")

    with pytest.raises(ValueError):
        ReleaseGateEngine(plan=plan, evaluators={"readiness": "bad"})

    with pytest.raises(ValueError):
        ReleaseGateEngine(plan=plan, evaluations=["bad"])

    with pytest.raises(ValueError):
        ReleaseGateEngine(plan=plan, metadata=[])

    engine = build_release_gate_engine(plan=plan)

    with pytest.raises(ValueError):
        engine.register_evaluator("", lambda: None)

    with pytest.raises(ValueError):
        engine.register_evaluator("readiness", "bad")


def test_build_release_gate_engine():
    gate = build_release_gate(
        name="readiness",
        gate_type="readiness",
    )
    plan = build_release_plan(
        version="v1",
        environment="production",
        gates=[gate],
    )
    engine = build_release_gate_engine(
        plan=plan,
        metadata={
            "source": "test",
        },
    )

    assert isinstance(engine, ReleaseGateEngine)
    assert engine.metadata == {
        "source": "test",
    }


def test_production_release_exports_exist():
    import aqos.production as production

    expected_exports = [
        "ReleaseDecision",
        "ReleaseEvaluation",
        "ReleaseGate",
        "ReleaseGateEngine",
        "ReleaseGateType",
        "ReleasePlan",
        "ReleaseReport",
        "aggregate_release_decision",
        "build_release_evaluation",
        "build_release_gate",
        "build_release_gate_engine",
        "build_release_plan",
        "build_release_report",
        "decide_release_from_status",
        "evaluate_release_gate",
        "normalize_release_decision",
        "normalize_release_gate_type",
        "run_release_gate_engine",
        "validate_evaluator_mapping",
        "validate_release_evaluations",
        "validate_release_gates",
    ]

    for export_name in expected_exports:
        assert hasattr(production, export_name), export_name