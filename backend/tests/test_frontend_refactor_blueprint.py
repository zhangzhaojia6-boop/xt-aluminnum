from __future__ import annotations

from pathlib import Path

import pytest

from tests.path_helpers import REPO_ROOT

pytestmark = pytest.mark.frontend_contract


def _repo_file(relative_path: str) -> Path:
    return REPO_ROOT / relative_path


def _read(relative_path: str) -> str:
    return _repo_file(relative_path).read_text(encoding="utf-8-sig")


def test_navigation_declares_current_manage_surfaces_without_removed_centers() -> None:
    source = _read("frontend/src/config/navigation.js")

    required = [
        ("no: '00'", "title: '生产实时'", "path: '/manage/live'", "routeName: 'manage-live'"),
        ("no: '01'", "title: '系统总览主视图'", "path: '/manage/today'", "routeName: 'manage-today'"),
        ("no: '03'", "title: '独立填报端首页'", "path: '/entry'", "routeName: 'mobile-entry'"),
        ("no: '05'", "title: '工厂作业看板'", "path: '/manage/production'", "routeName: 'manage-production'"),
        ("no: '11'", "title: 'AI 助手'", "path: '/manage/ai-assistant'", "routeName: 'factory-ai-assistant'"),
        ("no: '12'", "title: '系统设置'", "path: '/manage/admin/settings'", "routeName: 'admin-ops-reliability'"),
        ("no: '13'", "title: '权限与治理中心'", "path: '/manage/admin/governance'", "routeName: 'admin-governance-center'"),
        ("no: '14'", "title: '主数据中心'", "path: '/manage/master'", "routeName: 'admin-master-workshop'"),
    ]
    for tokens in required:
        for token in tokens:
            assert token in source

    for stale_route in [
        "path: '/manage/factory'",
        "path: '/manage/ingestion'",
        "path: '/manage/entry-center'",
        "path: '/manage/factory/cost'",
        "review-roadmap-center",
        "admin-roadmap-center",
    ]:
        assert stale_route not in source


def test_router_consolidates_daily_report_and_settings_routes() -> None:
    source = _read("frontend/src/router/index.js")

    assert "const LiveDashboardPage = () => import('../views/manage/live/LiveDashboardPage.vue')" in source
    assert "const TodayPage = () => import('../views/manage/today/TodayPage.vue')" in source
    assert "const ProductionPage = () => import('../views/manage/production/ProductionPage.vue')" in source
    assert "const FillDetailsPage = () => import('../views/manage/fill-details/FillDetailsPage.vue')" in source
    assert "const SystemSettingsPage = () => import('../views/manage/admin/SystemSettingsPage.vue')" in source

    assert "{ path: '', redirect: '/manage/today' }" in source
    assert "path: 'daily-report'" in source
    assert "redirect: preserveRouteState('/manage/today', { section: 'daily-report' })" in source
    assert "path: 'admin/setting', redirect: { name: 'admin-ops-reliability' }" in source
    assert "{ path: '/admin/setting', redirect: preserveRouteState('/manage/admin/settings') }" in source
    assert "path: 'admin/settings', name: 'admin-ops-reliability', component: SystemSettingsPage" in source


def test_router_preserves_legacy_handoffs_without_mounting_old_pages() -> None:
    source = _read("frontend/src/router/index.js")

    for redirect in [
        "path: '/review', redirect: preserveRouteState('/manage/today')",
        "path: '/review/factory', redirect: preserveRouteState('/manage/production')",
        "path: '/review/ingestion', name: 'review-ingestion-center', redirect: preserveRouteState('/manage/admin/settings')",
        "path: '/admin/master', redirect: preserveRouteState('/manage/master')",
        "path: '/dashboard/factory', redirect: '/manage/production'",
    ]:
        assert redirect in source

    assert "DynamicEntryForm" not in source
    assert "../views/dashboard/FactoryDirector.vue" not in source
    assert "../reference-command/pages" not in source


def test_unified_design_shell_files_exist_and_use_current_brand() -> None:
    expected_files = [
        "frontend/src/design/xt-tokens.css",
        "frontend/src/design/xt-base.css",
        "frontend/src/design/xt-motion.css",
        "frontend/src/design/xt-hud.css",
        "frontend/src/layout/EntryShell.vue",
        "frontend/src/layout/ManageShell.vue",
        "frontend/src/views/manage/live/LiveDashboardPage.vue",
        "frontend/src/views/manage/today/TodayPage.vue",
        "frontend/src/views/manage/production/ProductionPage.vue",
        "frontend/src/views/manage/fill-details/FillDetailsPage.vue",
        "frontend/src/views/manage/admin/SystemSettingsPage.vue",
    ]
    for relative_path in expected_files:
        assert _repo_file(relative_path).exists(), relative_path

    for relative_path in ["frontend/src/views/Login.vue", "frontend/src/layout/ManageShell.vue"]:
        source = _read(relative_path)
        assert "鑫泰铝业 数据中枢" in source or "数据中枢" in source
        assert "MES 系统" not in source


def test_manage_navigation_exposes_settings_and_core_pages() -> None:
    source = _read("frontend/src/config/manage-navigation.js")

    for token in [
        "path: '/manage/live'",
        "path: '/manage/today'",
        "path: '/manage/production'",
        "path: '/manage/fill-details'",
        "path: '/manage/energy'",
        "path: '/manage/alerts'",
        "path: '/manage/admin/settings'",
        "shortLabel: '设置'",
    ]:
        assert token in source


def test_today_page_owns_yesterday_report_and_daily_wip_reference() -> None:
    today = _read("frontend/src/views/manage/today/TodayPage.vue")
    snapshot = _read("frontend/src/composables/useDashboardSnapshot.js")
    surface = _read("frontend/src/utils/manageDailyReportSurface.js")

    assert "<h1>昨日总览</h1>" in today
    assert "外部 MES 当日快照参考" in today
    assert "inferLastCompletedBusinessDate" in snapshot
    assert "feedingText" in surface
    assert "外部 MES 当前在制" not in today
