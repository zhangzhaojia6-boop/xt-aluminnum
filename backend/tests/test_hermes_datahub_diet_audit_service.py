from __future__ import annotations

from pathlib import Path

from app.services.hermes_datahub_diet_audit_service import (
    candidate_paths,
    classify_audit_item,
    render_diet_audit_report,
)


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


def test_diet_audit_classifies_mes_and_wms_representatives_as_protect() -> None:
    paths = [
        "backend/app/routers/mes.py",
        "backend/app/models/mes.py",
        "docs/mes-page-table-mapping.md",
        "docs/mes-xtmijd-alignment-matrix.md",
        "artifacts/gstack-mes-audit-20260617/mes-sqlserver/WMS_Stock.sample.json",
    ]

    for path in paths:
        assert classify_audit_item(path)["classification"] == "protect"


def test_diet_audit_candidate_paths_include_hermes_and_models() -> None:
    repo_root = Path(__file__).resolve().parents[2]
    paths = candidate_paths(repo_root)

    assert "backend/app/models/agent_communication.py" in paths
    assert "backend/app/routers/hermes.py" in paths
    assert "docs/superpowers/specs/2026-06-25-hermes-knowledge-and-datahub-diet-design.md" in paths


def test_diet_audit_classifies_hermes_paths_as_protect() -> None:
    assert classify_audit_item("backend/app/routers/hermes.py")["classification"] == "protect"
    assert (
        classify_audit_item(
            "docs/superpowers/specs/2026-06-25-hermes-knowledge-and-datahub-diet-design.md"
        )["classification"]
        == "protect"
    )
