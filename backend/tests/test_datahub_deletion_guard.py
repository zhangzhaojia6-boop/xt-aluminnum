from __future__ import annotations

from pathlib import Path

from app.services.hermes_datahub_diet_audit_service import check_candidate_delete_paths
from scripts.check_datahub_deletion_guard import main


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


def test_deletion_guard_blocks_vue_candidate_referenced_by_runtime_ts_file(tmp_path: Path) -> None:
    candidate = tmp_path / "frontend/src/views/review/UnusedPanel.vue"
    caller = tmp_path / "frontend/src/router/runtime-panels.ts"
    candidate.parent.mkdir(parents=True)
    caller.parent.mkdir(parents=True)
    candidate.write_text("<template><div /></template>\n", encoding="utf-8")
    caller.write_text("import UnusedPanel from '../views/review/UnusedPanel.vue'\n", encoding="utf-8")

    result = check_candidate_delete_paths(tmp_path, ["frontend/src/views/review/UnusedPanel.vue"])

    assert result["passed"] is False
    assert result["items"][0]["status"] == "blocked"
    assert result["items"][0]["reason"] == "referenced_by_runtime_file"
    assert "frontend/src/router/runtime-panels.ts" in result["items"][0]["references"]


def test_deletion_guard_allows_candidate_referenced_only_by_tests(tmp_path: Path) -> None:
    candidate = tmp_path / "backend/app/services/old_service.py"
    test_reference = tmp_path / "backend/tests/test_old_service.py"
    candidate.parent.mkdir(parents=True)
    test_reference.parent.mkdir(parents=True)
    candidate.write_text("def old_service():\n    return 1\n", encoding="utf-8")
    test_reference.write_text("from app.services.old_service import old_service\n", encoding="utf-8")

    result = check_candidate_delete_paths(tmp_path, ["backend/app/services/old_service.py"])

    assert result["passed"] is True
    assert result["items"][0]["status"] == "delete_allowed"
    assert result["items"][0]["references"] == []


def test_deletion_guard_cli_text_output_prints_references(tmp_path: Path, capsys) -> None:
    candidate = tmp_path / "backend/app/services/old_service.py"
    caller = tmp_path / "backend/app/routers/old_router.py"
    candidate.parent.mkdir(parents=True)
    caller.parent.mkdir(parents=True)
    candidate.write_text("def old_service():\n    return 1\n", encoding="utf-8")
    caller.write_text("from app.services.old_service import old_service\n", encoding="utf-8")

    exit_code = main(
        [
            str(candidate.relative_to(tmp_path)).replace("\\", "/"),
        ],
        repo_root=tmp_path,
    )

    captured = capsys.readouterr()

    assert exit_code == 1
    assert "blocked backend/app/services/old_service.py referenced_by_runtime_file" in captured.out
    assert "backend/app/routers/old_router.py" in captured.out


def test_deletion_guard_reports_missing_candidate(tmp_path: Path) -> None:
    result = check_candidate_delete_paths(tmp_path, ["backend/app/services/missing.py"])

    assert result["passed"] is False
    assert result["items"][0]["status"] == "blocked"
    assert result["items"][0]["reason"] == "candidate_missing"
