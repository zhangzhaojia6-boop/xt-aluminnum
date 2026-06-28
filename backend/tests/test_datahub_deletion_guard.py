from __future__ import annotations

from pathlib import Path

from app.services.hermes_datahub_diet_audit_service import check_candidate_delete_paths


def test_deletion_guard_blocks_protected_hermes_path(tmp_path: Path) -> None:
    path = tmp_path / "backend/app/services/hermes_root_owner_production_orchestrator.py"
    path.parent.mkdir(parents=True)
    path.write_text("print('protected')", encoding="utf-8")

    result = check_candidate_delete_paths(tmp_path, ["backend/app/services/hermes_root_owner_production_orchestrator.py"])

    assert result["passed"] is False
    assert result["items"][0]["status"] == "blocked"
    assert result["items"][0]["reason"] == "protected_marker"


def test_deletion_guard_blocks_referenced_candidate(tmp_path: Path) -> None:
    candidate = tmp_path / "backend/app/services/old_service.py"
    caller = tmp_path / "backend/app/routers/old_router.py"
    candidate.parent.mkdir(parents=True)
    caller.parent.mkdir(parents=True)
    candidate.write_text("def old_service():\n    return 1\n", encoding="utf-8")
    caller.write_text("from app.services.old_service import old_service\n", encoding="utf-8")

    result = check_candidate_delete_paths(tmp_path, ["backend/app/services/old_service.py"])

    assert result["passed"] is False
    assert result["items"][0]["status"] == "blocked"
    assert result["items"][0]["reason"] == "referenced_by_runtime_file"
    assert "backend/app/routers/old_router.py" in result["items"][0]["references"]


def test_deletion_guard_allows_unreferenced_review_file(tmp_path: Path) -> None:
    candidate = tmp_path / "frontend/src/views/review/UnusedPanel.vue"
    candidate.parent.mkdir(parents=True)
    candidate.write_text("<template><div /></template>\n", encoding="utf-8")

    result = check_candidate_delete_paths(tmp_path, ["frontend/src/views/review/UnusedPanel.vue"])

    assert result["passed"] is True
    assert result["items"][0]["status"] == "delete_allowed"


def test_deletion_guard_reports_missing_candidate(tmp_path: Path) -> None:
    result = check_candidate_delete_paths(tmp_path, ["backend/app/services/missing.py"])

    assert result["passed"] is False
    assert result["items"][0]["status"] == "blocked"
    assert result["items"][0]["reason"] == "candidate_missing"
