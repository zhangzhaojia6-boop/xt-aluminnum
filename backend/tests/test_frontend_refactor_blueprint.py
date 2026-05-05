from __future__ import annotations

from pathlib import Path

import pytest

from tests.path_helpers import REPO_ROOT

pytestmark = pytest.mark.frontend_contract


def _repo_file(relative_path: str) -> Path:
    return REPO_ROOT / relative_path


def _read(relative_path: str) -> str:
    return _repo_file(relative_path).read_text(encoding="utf-8-sig")


def test_navigation_declares_15_center_blueprint_without_roadmap() -> None:
    source = _read("frontend/src/config/navigation.js")

    assert "export const centerNavigation" in source
    required = [
        ("no: '01'", "title: '系统总览主视图'", "zone: 'review'", "path: '/manage/overview'"),
        ("no: '03'", "title: '独立填报端首页'", "zone: 'entry'", "path: '/entry'"),
        ("no: '05'", "title: '工厂作业看板'", "zone: 'review'", "path: '/manage/factory'"),
        ("no: '06'", "title: '数据接入与字段映射中心'", "zone: 'admin'", "path: '/manage/ingestion'"),
        ("no: '07'", "title: '异常与补录'", "zone: 'review'", "path: '/manage/entry-center'"),
        ("no: '08'", "title: '日报与交付中心'", "zone: 'review'", "path: '/manage/reports'"),
        ("no: '09'", "title: '质量与告警中心'", "zone: 'review'", "path: '/manage/quality'"),
        ("no: '10'", "title: '经营效益'", "zone: 'review'", "path: '/manage/factory/cost'"),
        ("no: '11'", "title: 'AI 助手'", "zone: 'review'", "path: '/manage/ai-assistant'"),
        ("no: '12'", "title: '系统运维与观测'", "zone: 'admin'", "path: '/manage/admin/settings'"),
        ("no: '13'", "title: '权限与治理中心'", "zone: 'admin'", "path: '/manage/admin/governance'"),
        ("no: '14'", "title: '主数据与模板中心'", "zone: 'admin'", "path: '/manage/master'"),
    ]
    for tokens in required:
        for token in tokens:
            assert token in source

    assert "no: '02'" not in source
    assert "no: '04'" not in source
    assert "no: '15'" not in source
    assert "no: '16'" not in source
    assert "review-roadmap-center" not in source
    assert "admin-roadmap-center" not in source


def test_refactor_blueprint_documents_canonical_manage_routes() -> None:
    blueprint = _read("docs/REFACTOR_BLUEPRINT.md")

    for current_line in [
        "- `/manage/overview`",
        "- `/manage/factory`",
        "- `/manage/workshop`",
        "- `/manage/entry-center`",
        "- `/manage/reports`",
        "- `/manage/quality`",
        "- `/manage/reconciliation`",
        "- `/manage/factory/cost`",
        "- `/manage/ai-assistant`",
        "- `/manage/ingestion`",
        "- `/manage/admin/settings`",
        "- `/manage/admin/governance`",
        "- `/manage/master`",
        "- `/manage/admin/templates`",
        "- 01 系统总览主视图：`/manage/overview`",
        "- 05 工厂作业看板：`/manage/factory`",
        "- 06 数据接入与字段映射中心：`/manage/ingestion`",
        "- 07 异常与补录：`/manage/entry-center`",
        "- 08 日报与交付中心：`/manage/reports`",
        "- 09 质量与告警中心：`/manage/quality`",
        "- 10 成本核算与效益中心：`/manage/factory/cost`",
        "- 11 AI 助手：`/manage/ai-assistant`",
        "- 12 系统运维与可观测：`/manage/admin/settings`",
        "- 13 权限与治理中心：`/manage/admin/governance`",
        "- 14 主数据与模板中心：`/manage/master`",
        "- `/dashboard/*` -> `/manage/*`",
        "- `/master/*` -> `/manage/*`",
        "- `/review/*` 和 `/admin/*` -> `/manage/*`",
    ]:
        assert current_line in blueprint

    for stale_line in [
        "- `/review/overview`",
        "- `/review/factory`",
        "- `/review/tasks`",
        "- `/review/reports`",
        "- `/review/quality`",
        "- `/review/cost-accounting`",
        "- `/review/brain`",
        "- `/admin/ingestion`",
        "- `/admin/master`",
        "- `/admin/master/templates`",
        "- `/admin/governance`",
        "- `/admin/ops`",
        "- 01 系统总览主视图：`/review/overview`",
        "- 05 工厂作业看板：`/review/factory`",
        "- 06 数据接入与字段映射中心：`/admin/ingestion`",
        "- 07 审阅中心：`/review/tasks`",
        "- 08 日报与交付中心：`/review/reports`",
        "- 09 质量与告警中心：`/review/quality`",
        "- 10 成本核算与效益中心：`/review/cost-accounting`",
        "- 11 AI 总控中心：`/review/brain`",
        "- 12 系统运维与观测：`/admin/ops`",
        "- 13 权限与治理中心：`/admin/governance`",
        "- 14 主数据与模板中心：`/admin/master`",
        "- `/dashboard/*` -> `/review/*`",
        "- `/master/*` -> `/admin/master/*`",
        "- `/review/roadmap` -> `/review/overview`",
    ]:
        assert stale_line not in blueprint


def test_core_routes_have_zone_access_title_center_and_canonical_meta() -> None:
    source = _read("frontend/src/router/index.js")

    for meta in [
        "const entryMeta = { requiresAuth: true, zone: 'entry', access: 'entry' }",
        "const reviewMeta = { requiresAuth: true, zone: 'manage', access: 'review' }",
        "const adminMeta = { requiresAuth: true, zone: 'manage', access: 'admin' }",
    ]:
        assert meta in source

    core = [
        ("path: '/login'", "zone: 'public'", "access: 'public'", "canonical: '/login'"),
        ("path: '/entry'", "component: EntryShell", "canonical: '/entry'"),
        ("path: '/manage'", "component: ManageShell", "canonical: '/manage'"),
        ("path: 'admin'", "name: 'admin-overview'", "redirect: '/manage/admin/settings'", "canonical: '/manage/admin/settings'"),
    ]
    for tokens in core:
        anchor = source.index(tokens[0])
        block = source[anchor : anchor + 700]
        for token in tokens[1:]:
            assert token in block

    for center_no in ["01", "03", "05", "06", "07", "08", "09", "10", "11", "12", "13", "14"]:
        assert f"centerNo: '{center_no}'" in source

    assert "moduleId: '16'" not in source
    assert "component: CommandModulePage,\n        props: { moduleId: '16' }" not in source


def test_ai_center_is_formal_and_roadmap_is_isolated_redirect() -> None:
    source = _read("frontend/src/router/index.js")
    manage_start = source.index("path: '/manage'")
    manage_end = source.index("{ path: '/review'", manage_start)
    manage_routes = source[manage_start:manage_end]

    brain_anchor = manage_routes.index("path: 'ai',")
    brain_block = manage_routes[brain_anchor : brain_anchor + 320]
    assert "redirect: '/manage/ai-assistant'" in brain_block
    assert "centerNo: '11'" in brain_block
    assert "canonical: '/manage/ai-assistant'" in brain_block

    assistant_anchor = manage_routes.index("path: 'ai-assistant',")
    assistant_block = manage_routes[assistant_anchor : assistant_anchor + 320]
    assert "component: AiWorkstation" in assistant_block
    assert "centerNo: '11'" in assistant_block
    assert "canonical: '/manage/ai-assistant'" in assistant_block

    assert "path: '/roadmap/next', redirect: '/manage/overview'" in source
    assert "name: 'review-roadmap-center'" not in source


def test_legacy_paths_redirect_to_canonical_three_surfaces() -> None:
    source = _read("frontend/src/router/index.js")

    for legacy, canonical in [
        ("path: '/mobile'", "path: '/entry'"),
        ("path: '/dashboard'", "redirect: '/manage/overview'"),
        ("path: '/master'", "redirect: '/manage/master'"),
        ("path: 'ingestion'", "name: 'admin-ingestion-center'"),
        ("path: 'admin/templates'", "name: 'admin-template-center'"),
        ("path: 'admin/governance'", "name: 'admin-governance-center'"),
        ("path: 'admin/settings'", "name: 'admin-ops-reliability'"),
    ]:
        anchor = source.index(legacy)
        block = source[anchor : anchor + 380]
        assert canonical in block


def test_unified_design_shell_and_app_components_exist() -> None:
    expected_files = [
        "frontend/src/design/xt-tokens.css",
        "frontend/src/design/xt-base.css",
        "frontend/src/design/xt-motion.css",
        "frontend/src/design/industrial.css",
        "frontend/src/design/theme.css",
        "frontend/src/layout/AppShell.vue",
        "frontend/src/layout/EntryShell.vue",
        "frontend/src/layout/ManageShell.vue",
        "frontend/src/components/xt/XtActionBar.vue",
        "frontend/src/components/xt/XtBatchAction.vue",
        "frontend/src/components/xt/XtCard.vue",
        "frontend/src/components/xt/XtEmpty.vue",
        "frontend/src/components/xt/XtExport.vue",
        "frontend/src/components/xt/XtFilter.vue",
        "frontend/src/components/xt/XtGrid.vue",
        "frontend/src/components/xt/XtKpi.vue",
        "frontend/src/components/xt/XtLogo.vue",
        "frontend/src/components/xt/XtNotification.vue",
        "frontend/src/components/xt/XtPageHeader.vue",
        "frontend/src/components/xt/XtSearch.vue",
        "frontend/src/components/xt/XtSkeleton.vue",
        "frontend/src/components/xt/XtStatus.vue",
        "frontend/src/components/xt/XtTable.vue",
    ]
    for relative_path in expected_files:
        assert _repo_file(relative_path).exists(), relative_path

    tokens = _read("frontend/src/design/xt-tokens.css")
    for token in [
        "--xt-bg-page",
        "--xt-bg-panel",
        "--xt-border",
        "--xt-primary",
        "--xt-success",
        "--xt-warning",
        "--xt-danger",
        "--xt-text",
        "--xt-text-muted",
        "--xt-radius-xl",
        "--xt-shadow-md",
        "--xt-space-6",
        "--xt-sidebar-width",
    ]:
        assert token in tokens


def test_first_round_core_pages_use_app_components_and_mock_notice() -> None:
    checks = {
        "frontend/src/views/Login.vue": [
            "login-stage__role-grid",
            "录入端",
            "审阅端",
            "管理端",
            "auth.login",
            "auth.dingtalkLogin",
        ],
        "frontend/src/views/mobile/MobileEntry.vue": [
            "data-testid=\"mobile-entry\"",
            "开始填报",
            "填报",
            "历史记录",
        ],
        "frontend/src/views/review/OverviewCenter.vue": [
            "ReferencePageFrame",
            "今日产量",
            "AI 今日摘要",
            "AI 风险摘要",
        ],
        "frontend/src/views/review/ReviewTaskCenter.vue": [
            "ReferencePageFrame",
            "异常与补录",
            "缺报",
            "退回",
            "差异",
            "同步滞后",
        ],
    }
    for relative_path, tokens in checks.items():
        source = _read(relative_path)
        for token in tokens:
            assert token in source


def test_center_mock_data_only_keeps_mes_wip_snapshot_fallback() -> None:
    source = _read("frontend/src/mocks/centerMockData.js")

    assert "export const mesWipSnapshotMock" in source
    assert "MES截图口径 / 待正式对接" in source

    for removed_export in [
        "entryHomeMock",
        "reviewOverviewMock",
        "reviewTaskMock",
        "factoryBoardMock",
        "reportsCenterMock",
        "qualityCenterMock",
        "costCenterMock",
        "ingestionCenterMock",
        "brainCenterMock",
        "opsCenterMock",
        "governanceCenterMock",
    ]:
        assert f"export const {removed_export}" not in source

    for forbidden in ["最终结论", "财务结算"]:
        assert forbidden not in source
