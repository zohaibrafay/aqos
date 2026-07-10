from __future__ import annotations

from aqos.scripts.audit_aqos_reality import build_audit


def test_aqos_codebase_audit_has_no_empty_review_unused_or_missing_dependency_flags() -> None:
    audit = build_audit()

    action_lists = audit["action_lists"]
    dependencies = audit["dependencies"]

    assert action_lists["empty_or_init_files"] == []
    assert action_lists["review_or_upgrade"] == []
    assert action_lists["possible_unused_modules"] == []
    assert dependencies["possible_missing_dependencies"] == []


def test_aqos_codebase_audit_accepts_contracts_and_tooling() -> None:
    audit = build_audit()
    counts = audit["summary"]["classification_counts"]

    assert counts.get("valid_contract", 0) >= 1
    assert counts.get("tooling_script", 0) >= 1