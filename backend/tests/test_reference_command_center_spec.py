from __future__ import annotations

from pathlib import Path

import pytest

from tests.path_helpers import REPO_ROOT

pytestmark = pytest.mark.frontend_contract


def _resolve_repo_root() -> Path:
    if (REPO_ROOT / "frontend").exists() and (REPO_ROOT / "README.md").exists():
        return REPO_ROOT
    return Path(__file__).resolve().parents[2]


def _read_repo_file(relative_path: str) -> str:
    return (_resolve_repo_root() / relative_path).read_text(encoding="utf-8-sig")


def _repo_file(relative_path: str) -> Path:
    return _resolve_repo_root() / relative_path


def _ui_boundary_files() -> list[Path]:
    roots = [
        _repo_file("frontend/src/components/reference"),
        _repo_file("frontend/src/components/xt"),
        _repo_file("frontend/src/design"),
        _repo_file("frontend/src/layout"),
        _repo_file("frontend/src/views/manage"),
        _repo_file("frontend/src/views/mobile"),
    ]
    files: list[Path] = []
    for root in roots:
        if root.exists():
            files.extend(path for path in root.rglob("*") if path.is_file() and path.suffix in {".css", ".js", ".vue"})
    return files


def test_current_ui_boundary_files_are_declared() -> None:
    expected = [
        "frontend/src/design/xt-tokens.css",
        "frontend/src/design/xt-base.css",
        "frontend/src/design/xt-motion.css",
        "frontend/src/design/xt-hud.css",
        "frontend/src/layout/EntryShell.vue",
        "frontend/src/layout/ManageShell.vue",
        "frontend/src/components/reference/ReferencePageFrame.vue",
        "frontend/src/components/reference/ReferenceModuleCard.vue",
        "frontend/src/components/reference/ReferenceKpiTile.vue",
        "frontend/src/components/reference/ReferenceStatusTag.vue",
        "frontend/src/components/reference/ReferenceDataTable.vue",
        "frontend/src/components/reference/ReferenceFlowGraphic.vue",
        "frontend/src/views/manage/live/LiveDashboardPage.vue",
        "frontend/src/views/manage/today/TodayPage.vue",
        "frontend/src/views/manage/production/ProductionPage.vue",
        "frontend/src/views/manage/fill-details/FillDetailsPage.vue",
        "frontend/src/views/manage/admin/SystemSettingsPage.vue",
    ]
    for path in expected:
        assert _repo_file(path).exists(), path


def test_current_ui_uses_dense_copy_without_forbidden_helper_fields() -> None:
    files = _ui_boundary_files()
    assert files, "current frontend UI boundary must contain rebuilt files"

    forbidden = [
        "(Review Center)",
        "(Hero Overview)",
        "(Login",
        "description:",
        "explanation:",
        "helperText",
        "rationale",
    ]
    for path in files:
        text = path.read_text(encoding="utf-8-sig")
        for token in forbidden:
            assert token not in text, f"{token} in {path}"


def test_industrial_blue_theme_tokens_are_current_source_of_truth() -> None:
    tokens = _read_repo_file("frontend/src/design/xt-tokens.css")
    hud = _read_repo_file("frontend/src/design/xt-hud.css")

    for token in [
        "--xt-bg-page:",
        "--xt-bg-panel:",
        "--xt-border:",
        "--xt-primary:",
        "--xt-success:",
        "--xt-warning:",
        "--xt-danger:",
        "--xt-text:",
    ]:
        assert token in tokens

    assert '[data-xt-theme="hud"]' in hud
    assert "!important" not in hud
    assert "purple" not in tokens.lower()


def test_manage_shell_keeps_three_primary_pages_and_admin_entries() -> None:
    router = _read_repo_file("frontend/src/router/index.js")
    manage_nav = _read_repo_file("frontend/src/config/manage-navigation.js")
    shell = _read_repo_file("frontend/src/layout/ManageShell.vue")

    for path in [
        "/manage/live",
        "/manage/today",
        "/manage/production",
        "/manage/fill-details",
        "/manage/energy",
        "/manage/alerts",
        "/manage/admin/settings",
    ]:
        assert path in router or path in manage_nav

    assert "manageNavGroups" in shell
    assert "数据中枢" in shell
    assert "现场填报" not in shell


def test_removed_reference_prototype_pages_stay_removed() -> None:
    router = _read_repo_file("frontend/src/router/index.js")

    assert not _repo_file("frontend/src/reference-command").exists()
    assert "../reference-command/pages" not in router


def test_today_page_connects_algorithm_daily_report_and_wip_snapshot() -> None:
    today = _read_repo_file("frontend/src/views/manage/today/TodayPage.vue")
    surface = _read_repo_file("frontend/src/utils/manageDailyReportSurface.js")
    snapshot = _read_repo_file("frontend/src/composables/useDashboardSnapshot.js")

    assert "昨日总览" in today
    assert "算法与填报对照" in today
    assert "外部 MES 当日快照参考" in today
    assert "feedingText" in today
    assert "buildDailyWipRows" in surface
    assert "inferLastCompletedBusinessDate" in snapshot


def test_live_page_remains_realtime_wip_surface() -> None:
    live = _read_repo_file("frontend/src/views/manage/live/LiveDashboardPage.vue")
    live_utils = _read_repo_file("frontend/src/utils/liveDashboardPhase2.js")

    assert "全厂实时调度墙" in live
    assert "实时连接正常" in live
    assert "外部 MES" in live_utils
    assert "machineMatrix" in live
    assert "外部 MES 当日快照参考" not in live


def test_system_settings_page_is_the_single_admin_settings_surface() -> None:
    settings = _read_repo_file("frontend/src/views/manage/admin/SystemSettingsPage.vue")
    router = _read_repo_file("frontend/src/router/index.js")

    assert "data-testid=\"system-settings-page\"" in settings
    assert "系统设置" in settings
    assert "path: 'admin/settings', name: 'admin-ops-reliability'" in router
    assert "path: 'admin/setting', redirect: { name: 'admin-ops-reliability' }" in router


def test_cancelled_team_lead_surface_stays_cancelled() -> None:
    router = _read_repo_file("frontend/src/router/index.js")
    auth = _read_repo_file("frontend/src/stores/auth.js")

    assert "path: '/team-lead',\n    redirect:" in router
    assert "team-lead" not in auth
    assert "shift_leader" not in auth
