from __future__ import annotations

from app.services.hermes_datahub_diet_audit_service import classify_audit_item, render_diet_audit_report


def test_diet_audit_protects_evidence_paths() -> None:
    item = classify_audit_item("backend/app/models/agent_communication.py")

    assert item["classification"] == "protect"
    assert "证据" in item["reason"] or "审计" in item["reason"]


def test_diet_audit_freezes_legacy_routes_before_delete() -> None:
    item = classify_audit_item("frontend/src/reference-command/pages/README.md")

    assert item["classification"] in {"freeze", "candidate_delete"}
    assert item["action"] != "delete_now"


def test_diet_audit_report_contains_no_delete_now() -> None:
    report = render_diet_audit_report([
        "backend/app/models/agent_communication.py",
        "frontend/src/reference-command/pages/README.md",
    ])

    assert "delete_now" not in report
    assert "protect" in report
    assert "freeze" in report or "candidate_delete" in report