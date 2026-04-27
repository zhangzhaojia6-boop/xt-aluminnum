from __future__ import annotations

from pathlib import Path

from tests.path_helpers import REPO_ROOT


def _repo_file(relative_path: str) -> Path:
    return REPO_ROOT / relative_path


def _read(relative_path: str) -> str:
    return _repo_file(relative_path).read_text(encoding="utf-8-sig")


def test_navigation_declares_15_center_blueprint_without_roadmap() -> None:
    source = _read("frontend/src/config/navigation.js")

    assert "export const centerNavigation" in source
    required = [
        ("no: '01'", "title: '系统总览主视图'", "zone: 'review'", "path: '/review/overview'"),
        ("no: '03'", "title: '独立填报端首页'", "zone: 'entry'", "path: '/entry'"),
        ("no: '05'", "title: '工厂作业看板'", "zone: 'review'", "path: '/review/factory'"),
        ("no: '06'", "title: '数据接入与字段映射中心'", "zone: 'admin'", "path: '/admin/ingestion'"),
        ("no: '07'", "title: '审阅中心'", "zone: 'review'", "path: '/review/tasks'"),
        ("no: '08'", "title: '日报与交付中心'", "zone: 'review'", "path: '/review/reports'"),
        ("no: '09'", "title: '质量与告警中心'", "zone: 'review'", "path: '/review/quality'"),
        ("no: '10'", "title: '成本核算与效益中心'", "zone: 'review'", "path: '/review/cost-accounting'"),
        ("no: '11'", "title: 'AI 总控中心'", "zone: 'review'", "path: '/review/brain'"),
        ("no: '12'", "title: '系统运维与观测'", "zone: 'admin'", "path: '/admin/ops'"),
        ("no: '13'", "title: '权限与治理中心'", "zone: 'admin'", "path: '/admin/governance'"),
        ("no: '14'", "title: '主数据与模板中心'", "zone: 'admin'", "path: '/admin/master'"),
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


def test_core_routes_have_zone_access_title_center_and_canonical_meta() -> None:
    source = _read("frontend/src/router/index.js")

    core = [
        ("path: '/login'", "zone: 'public'", "access: 'public'", "canonical: '/login'"),
        ("path: '/entry'", "zone: 'entry'", "access: 'entry'", "canonical: '/entry'"),
        ("path: '/review'", "zone: 'review'", "access: 'review'", "canonical: '/review/overview'"),
        ("path: '/admin'", "zone: 'admin'", "access: 'admin'", "canonical: '/admin'"),
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
    review_start = source.index("path: '/review'")
    review_end = source.index("{ path: '/factory'", review_start)
    review_routes = source[review_start:review_end]

    brain_anchor = review_routes.index("path: 'brain',")
    brain_block = review_routes[brain_anchor : brain_anchor + 320]
    assert "component: CommandModulePage" in brain_block
    assert "moduleId: '11'" in brain_block
    assert "canonical: '/review/brain'" in brain_block

    roadmap_anchor = review_routes.index("path: 'roadmap',")
    roadmap_block = review_routes[roadmap_anchor : roadmap_anchor + 260]
    assert "redirect: { name: 'review-overview-home' }" in roadmap_block
    assert "name: 'review-roadmap-center'" not in review_routes


def test_legacy_paths_redirect_to_canonical_three_surfaces() -> None:
    source = _read("frontend/src/router/index.js")

    for legacy, canonical in [
        ("path: '/mobile'", "path: '/entry'"),
        ("path: '/dashboard'", "path: '/review/overview'"),
        ("path: '/master'", "path: '/admin/master'"),
        ("path: 'ingestion'", "name: 'admin-ingestion-center'"),
        ("path: 'template-center'", "name: 'admin-template-center'"),
        ("path: 'governance'", "name: 'admin-governance-center'"),
        ("path: 'ops-reliability'", "name: 'admin-ops-reliability'"),
    ]:
        anchor = source.index(legacy)
        block = source[anchor : anchor + 380]
        assert canonical in block


def test_unified_design_shell_and_app_components_exist() -> None:
    expected_files = [
        "frontend/src/design/tokens.css",
        "frontend/src/design/status.js",
        "frontend/src/design/centerTheme.js",
        "frontend/src/layout/AppShell.vue",
        "frontend/src/layout/EntryShell.vue",
        "frontend/src/layout/ReviewShell.vue",
        "frontend/src/layout/AdminShell.vue",
        "frontend/src/components/app/CenterPageShell.vue",
        "frontend/src/components/app/AppKpiCard.vue",
        "frontend/src/components/app/KpiStrip.vue",
        "frontend/src/components/app/ActionTile.vue",
        "frontend/src/components/app/StatusBadge.vue",
        "frontend/src/components/app/DataTableShell.vue",
        "frontend/src/components/app/SectionCard.vue",
        "frontend/src/components/app/FixedActionBar.vue",
        "frontend/src/components/app/SourceBadge.vue",
        "frontend/src/components/app/MockDataNotice.vue",
    ]
    for relative_path in expected_files:
        assert _repo_file(relative_path).exists(), relative_path

    tokens = _read("frontend/src/design/tokens.css")
    for token in [
        "--app-bg",
        "--card-bg",
        "--card-border",
        "--primary",
        "--success",
        "--warning",
        "--danger",
        "--text-main",
        "--text-muted",
        "--radius-card",
        "--shadow-card",
        "--space-page",
        "--space-card",
    ]:
        assert token in tokens


def test_first_round_core_pages_use_app_components_and_mock_notice() -> None:
    checks = {
        "frontend/src/reference-command/pages/CommandLogin.vue": [
            "cmd-login__surface-list",
            "录入端",
            "审阅端",
            "管理端",
            "auth.login",
            "auth.dingtalkLogin",
        ],
        "frontend/src/reference-command/pages/CommandEntryHome.vue": [
            "CenterPageShell",
            "最近提交状态",
            "已提交",
            "异常待补",
            "快速填报",
            "高级填报",
            "历史记录",
            "草稿箱",
            "MockDataNotice",
        ],
        "frontend/src/reference-command/pages/CommandOverview.vue": [
            "CenterPageShell",
            "今日产量",
            "订单达成率",
            "综合成品率",
            "在制产线",
            "异常数",
            "待审核",
            "已交付",
            "系统状态",
            "MockDataNotice",
        ],
        "frontend/src/reference-command/components/CommandPage.vue": [
            "showReviewTasks",
            "待审",
            "已审",
            "已驳回",
            "录入车间",
            "AI 建议",
            "风险等级",
            "批量通过",
            "批量驳回",
            "导出清单",
            "MockDataNotice",
        ],
    }
    for relative_path, tokens in checks.items():
        source = _read(relative_path)
        for token in tokens:
            assert token in source


def test_mock_data_is_centralized_for_first_round_centers() -> None:
    source = _read("frontend/src/mocks/centerMockData.js")

    for export_name in [
        "entryHomeMock",
        "reviewOverviewMock",
        "reviewTaskMock",
    ]:
        assert f"export const {export_name}" in source

    for forbidden in ["最终结论", "财务结算"]:
        assert forbidden not in source
