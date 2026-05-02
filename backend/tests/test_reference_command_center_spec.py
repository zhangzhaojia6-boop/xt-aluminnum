from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

from tests.path_helpers import REPO_ROOT


def _resolve_repo_root() -> Path:
    if (REPO_ROOT / "frontend").exists() and (REPO_ROOT / "README.md").exists():
        return REPO_ROOT
    return Path(__file__).resolve().parents[2]


def _read_repo_file(relative_path: str) -> str:
    return (_resolve_repo_root() / relative_path).read_text(encoding="utf-8-sig")


def _repo_file(relative_path: str) -> Path:
    return _resolve_repo_root() / relative_path


VISUAL_AUDIT_TOOL = "frontend/tools/visual-audit/command-center-audit.cjs"


def _ui_boundary_files() -> list[Path]:
    roots = [
        _repo_file("frontend/src/components/reference"),
        _repo_file("frontend/src/components/xt"),
        _repo_file("frontend/src/design"),
        _repo_file("frontend/src/layout"),
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
        "frontend/src/design/industrial.css",
        "frontend/src/design/theme.css",
        "frontend/src/layout/AppShell.vue",
        "frontend/src/layout/EntryShell.vue",
        "frontend/src/layout/ManageShell.vue",
        "frontend/src/components/reference/ReferencePageFrame.vue",
        "frontend/src/components/reference/ReferenceModuleCard.vue",
        "frontend/src/components/reference/ReferenceKpiTile.vue",
        "frontend/src/components/reference/ReferenceStatusTag.vue",
        "frontend/src/components/reference/ReferenceDataTable.vue",
        "frontend/src/components/reference/ReferenceFlowGraphic.vue",
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
    for path in expected:
        assert _repo_file(path).exists(), path


def test_current_ui_uses_chinese_dense_copy_without_helper_fields() -> None:
    files = _ui_boundary_files()
    assert files, "current frontend UI boundary must contain rebuilt files"

    forbidden = [
        "(Review Center)",
        "(Hero Overview)",
        "(Login",
        "description:",
        "explanation:",
        "helperText",
        "tooltip",
        "rationale",
    ]
    for path in files:
        text = path.read_text(encoding="utf-8-sig")
        for token in forbidden:
            assert token not in text, f"{token} in {path}"


def test_reference_command_catalog_declares_15_target_modules_without_roadmap_page() -> None:
    catalog = _read_repo_file("frontend/src/reference-command/data/moduleCatalog.js")

    for module_id in [f"{index:02d}" for index in range(1, 16)]:
        assert f"moduleId: '{module_id}'" in catalog
    assert "moduleId: '16'" not in catalog

    for title in [
        "系统总览主视图",
        "登录与角色入口",
        "独立填报端首页",
        "填报流程页",
        "工厂作业看板",
        "数据接入与字段映射中心",
        "审阅中心",
        "日报与交付中心",
        "质量与告警中心",
        "成本核算与效益中心",
        "AI 总控中心",
        "系统运维与观测",
        "权限与治理中心",
        "主数据与模板中心",
        "响应式录入体验",
    ]:
        assert title in catalog

    for surface in ["surface: 'entry'", "surface: 'review'", "surface: 'admin'", "surface: 'system'"]:
        assert surface in catalog


def test_xt_tokens_match_target_image_rules() -> None:
    tokens = _read_repo_file("frontend/src/design/xt-tokens.css")

    for token in [
        "--xt-bg-page:",
        "--xt-bg-panel:",
        "--xt-border:",
        "--xt-primary:",
        "--xt-success:",
        "--xt-warning:",
        "--xt-danger:",
        "--xt-text:",
        "--xt-radius-xl:",
    ]:
        assert token in tokens
    assert "oklch(97.3% 0.008 248)" in tokens
    assert "#ffffff" in tokens
    assert "rgba(15, 23, 42, 0.10)" in tokens
    assert "oklch(51% 0.17 255)" in tokens
    assert "Bahnschrift" in tokens
    assert "DIN Alternate" in tokens
    assert "Microsoft YaHei" in tokens


def test_current_components_expose_target_css_hooks() -> None:
    hooks = {
        "frontend/src/components/xt/XtCard.vue": ["xt-card", "xt-card__header", "xt-card__title"],
        "frontend/src/components/xt/XtGrid.vue": ["xt-grid"],
        "frontend/src/components/xt/XtKpi.vue": ["xt-kpi", "xt-kpi__value"],
        "frontend/src/components/xt/XtActionBar.vue": ["xt-action-bar"],
        "frontend/src/components/reference/ReferencePageFrame.vue": ["reference-page", "reference-page__header"],
    }
    for relative_path, expected_hooks in hooks.items():
        source = _read_repo_file(relative_path)
        for hook in expected_hooks:
            assert hook in source


def test_reference_command_keeps_legacy_routes_and_route_names() -> None:
    router = _read_repo_file("frontend/src/router/index.js")

    for route_name in [
        "mobile-entry",
        "mobile-report-form-advanced",
        "review-overview-home",
        "factory-dashboard",
        "review-task-center",
        "review-report-center",
        "review-quality-center",
        "review-cost-accounting",
        "review-brain-center",
        "admin-ops-reliability",
        "admin-governance-center",
        "admin-master-workshop",
        "admin-template-center",
    ]:
        assert f"name: '{route_name}'" in router

    for legacy_path in ["/mobile", "/dashboard", "/master", "/ops/reliability"]:
        assert legacy_path in router


def test_login_route_uses_three_surface_handoff() -> None:
    router = _read_repo_file("frontend/src/router/index.js")
    login = _read_repo_file("frontend/src/views/Login.vue")

    assert "component: Login" in router
    for role in ["录入端", "审阅端", "管理端"]:
        assert role in login
    assert "loginRoleHandoffImage" not in login
    assert "cmd-login-reference" not in login
    assert "login-stage" in login
    assert "login-card" in login
    assert "(Login" not in login


def test_shells_keep_entry_and_manage_surfaces_separate() -> None:
    entry = _read_repo_file("frontend/src/layout/EntryShell.vue")
    app_shell = _read_repo_file("frontend/src/layout/AppShell.vue")
    manage = _read_repo_file("frontend/src/layout/ManageShell.vue")

    assert "现场填报" in entry
    assert "审阅中心" not in entry
    assert "主数据" not in entry
    assert "AI 助手" in app_shell
    assert "数据中枢" in manage
    assert "现场填报" not in manage


def test_review_overview_uses_single_reference_module_01() -> None:
    overview = _read_repo_file("frontend/src/reference-command/pages/CommandOverview.vue")
    router = _read_repo_file("frontend/src/router/index.js")

    assert "XtPageHeader" in overview
    assert 'title="系统总览主视图"' in overview
    assert "XtGrid" in overview
    assert "XtKpi" in overview
    assert "XtTable" in overview
    assert "name: 'review-overview-home'" in router
    assert "component: OverviewCenter" in router
    assert "canonical: '/manage/overview'" in router


def test_entry_surface_is_entry_only_and_matches_modules_03_04() -> None:
    home = _read_repo_file("frontend/src/reference-command/pages/CommandEntryHome.vue")
    flow = _read_repo_file("frontend/src/reference-command/pages/CommandEntryFlow.vue")
    router = _read_repo_file("frontend/src/router/index.js")
    audit = _read_repo_file(VISUAL_AUDIT_TOOL)

    assert 'title="独立填报端首页"' in home
    assert 'eyebrow="03 ENTRY"' in home
    assert 'title="填报流程页"' in flow
    assert 'eyebrow="04 ENTRY FLOW"' in flow
    assert "XtPageHeader" in home
    assert "XtKpi" in home
    assert "XtActionBar" in flow
    assert "entryFlowImage" not in flow
    assert "cmd-entry-flow__visual" not in flow
    assert "cmd-entry-flow__functional" not in flow
    assert "cmd-entry-flow__visual" not in audit
    assert "快速填报" in home
    assert "产量录入" in flow
    assert "name: 'mobile-entry'" in router
    assert "name: 'dynamic-entry-form'" in router
    for forbidden in ["权限治理", "主数据", "审阅任务"]:
        assert forbidden not in home
        assert forbidden not in flow


def test_review_modules_are_schema_driven_command_pages() -> None:
    router = _read_repo_file("frontend/src/router/index.js")
    manage_start = router.index("path: '/manage'")
    manage_end = router.index("{ path: '/review'", manage_start)
    manage_routes = router[manage_start:manage_end]
    expected = [
        ("name: 'review-task-center'", "component: ReviewTaskCenter", "centerNo: '07'", "canonical: '/manage/entry-center'"),
        ("name: 'factory-dashboard'", "component: FactoryDirector", "centerNo: '05'", "canonical: '/manage/factory'"),
        ("name: 'review-report-center'", "component: ReportList", "centerNo: '08'", "canonical: '/manage/reports'"),
        ("name: 'review-quality-center'", "component: QualityCenter", "centerNo: '09'", "canonical: '/manage/quality'"),
        ("name: 'review-cost-accounting'", "component: CostAccountingCenter", "centerNo: '10'", "canonical: '/manage/cost'"),
        ("name: 'review-brain-center'", "component: AiWorkstation", "centerNo: '11'", "canonical: '/manage/ai'"),
    ]
    for tokens in expected:
        route_index = manage_routes.index(tokens[0])
        route_slice = manage_routes[route_index: route_index + 420]
        for token in tokens[1:]:
            assert token in route_slice


def test_admin_modules_are_schema_driven_command_pages() -> None:
    router = _read_repo_file("frontend/src/router/index.js")
    manage_start = router.index("path: '/manage'")
    manage_end = router.index("{ path: '/review'", manage_start)
    manage_routes = router[manage_start:manage_end]
    expected = [
        ("name: 'admin-ingestion-center'", "component: IngestionCenter", "centerNo: '06'", "canonical: '/manage/ingestion'"),
        ("name: 'admin-ops-reliability'", "component: LiveDashboard", "centerNo: '12'", "canonical: '/manage/admin/settings'"),
        ("name: 'admin-governance-center'", "component: GovernanceCenter", "centerNo: '13'", "canonical: '/manage/admin/governance'"),
        ("name: 'admin-users'", "component: UserManagement", "centerNo: '13'", "canonical: '/manage/admin/users'"),
        ("name: 'admin-master-workshop'", "component: Workshop", "centerNo: '14'", "canonical: '/manage/master'"),
        ("name: 'admin-template-center'", "component: WorkshopTemplateConfig", "centerNo: '14'", "canonical: '/manage/admin/templates'"),
    ]
    for tokens in expected:
        route_index = manage_routes.index(tokens[0])
        route_slice = manage_routes[route_index: route_index + 420]
        for token in tokens[1:]:
            assert token in route_slice


def test_ui_replica_spec_locks_reference_module_granularity() -> None:
    spec = _read_repo_file("docs/ui-replica-spec.md")

    assert "# UI 复刻规范（参考图级生产指挥中心执行规格）" in spec
    required_rows = [
        "| 01 | 系统总览主视图 | 审阅端 | `/review/overview` |",
        "| 02 | 登录与角色入口 | 公共入口 | `/login` |",
        "| 03 | 独立填报端首页 | 录入端 | `/entry` |",
        "| 04 | 填报流程页 | 录入端 | `/entry/report/*`、`/entry/advanced/*` |",
        "| 05 | 工厂作业看板 | 审阅端 | `/review/factory` |",
        "| 06 | 数据接入与字段映射中心 | 管理端 | `/admin/ingestion` |",
        "| 07 | 审阅中心 | 审阅端 | `/review/tasks` |",
        "| 08 | 日报与交付中心 | 审阅端 | `/review/reports` |",
        "| 09 | 质量与告警中心 | 审阅端 | `/review/quality` |",
        "| 10 | 成本核算与效益中心 | 审阅端 | `/review/cost-accounting` |",
        "| 11 | AI 总控中心 | 审阅端 | `/review/brain` |",
        "| 12 | 系统运维与观测 | 管理端 | `/admin/ops` |",
        "| 13 | 权限与治理中心 | 管理端 | `/admin/governance` |",
        "| 14 | 主数据与模板中心 | 管理端 | `/admin/master`、`/admin/master/templates` |",
        "| 15 | 响应式录入体验 | 全局验收 | `/entry` 全链路 |",
    ]
    for row in required_rows:
        assert row in spec

    assert "移动端预览模块取消" in spec
    assert "| 16 |" not in spec
    assert "/review/roadmap" not in spec
    assert "/admin/roadmap" not in spec
    assert "每个中心页至少包含：编号标题区、KPI 摘要区、主表格或主图形区、摘要/风险/趋势区、固定操作区。" in spec


def test_ui_replica_spec_defines_executable_build_and_data_contracts() -> None:
    spec = _read_repo_file("docs/ui-replica-spec.md")

    for component in [
        "ReferencePageFrame",
        "ReferenceModuleCard",
        "ReferenceKpiTile",
        "ReferenceStatusTag",
        "ReferenceDataTable",
        "ReferenceFlowGraphic",
    ]:
        assert component in spec

    for forbidden_prop in ["description", "explanation", "helperText", "tooltip", "note", "rationale"]:
        assert f"`{forbidden_prop}`" in spec

    for contract_field in [
        "`module_id`",
        "`title`",
        "`kpis`",
        "`primary_rows`",
        "`trend_series`",
        "`actions`",
        "`freshness`",
    ]:
        assert contract_field in spec

    assert "TDD 红绿循环" in spec
    assert "`python -m pytest backend/tests -q`" in spec
    assert "`npm --prefix frontend run e2e`" in spec
    assert "`npm --prefix frontend run build`" in spec


def test_ui_replica_spec_keeps_three_surface_execution_boundaries() -> None:
    spec = _read_repo_file("docs/ui-replica-spec.md")

    assert "录入端只负责录入" in spec
    assert "审阅端只负责看数、审阅、处置和交付" in spec
    assert "管理端只负责配置、治理、主数据和运维" in spec
    assert "fill-only 用户不得看到审阅端或管理端导航" in spec
    assert "旧 URL 和 route name 保持兼容" in spec
    assert "不使用英文小字副标题" in spec
    assert "高科技感来自数据流、状态流、产线图形、精确网格和 AI 结果动效" in spec


def test_reference_visual_audit_tracks_spec_routes_and_surface_boundaries() -> None:
    source = _read_repo_file(VISUAL_AUDIT_TOOL)

    assert "referenceChecklist" in source
    assert "targetReferenceImage" in source
    assert "referenceManifestPath" in source
    assert "targetReferenceImageDir" in source
    assert "referencePanelChecks" in source
    assert "targetImageMeta" in source
    assert "expectedPanelCount: expectedReferenceImages.length" in source
    assert "expectedReferenceImages = [" in source
    assert "docs', 'ui-reference', 'highres'" in source
    assert "REFERENCE_MANIFEST.md" in source
    assert "01-overview.png" in source
    assert "08-reports-delivery.png" in source
    assert "C:/Users/" not in source
    assert "D:/" not in source
    assert "Downloads" not in source
    assert "route: '/login'" in source
    assert "route: '/entry'" in source
    assert "route: '/review/factory'" in source
    assert "route: '/review/overview'" in source
    assert "route: '/review/tasks'" in source
    assert "route: '/review/cost-accounting'" in source
    assert "route: '/review/roadmap'" not in source
    assert "route: '/admin'" in source
    assert "route: '/admin/master'" in source
    assert "route: '/admin/ops'" in source
    assert "route: '/admin/users'" in source
    assert "moduleNumber: '02'" in source
    assert "moduleNumber: '04'" in source
    assert "moduleNumber: '05'" in source
    assert "moduleNumber: '15'" in source
    assert "captureEntryFlow" in source
    assert "04-entry-flow.png" in source
    assert "05-factory-board.png" in source
    assert "13-admin-users.png" in source
    assert "14-master-template.png" in source
    assert "surface boundary: fill-only nav isolation" in source
    assert "mobile preview module cancelled" in source
    assert "ensureTextAbsent" in source
    assert "ensureFactoryReferenceDensity" in source
    assert "factoryDensity: true" in source
    assert "ensureLayoutHook" in source
    assert "layoutHook: '.cmd-layout--mapping-center'" in source
    assert "layoutHook: '.cmd-layout--roadmap'" not in source


def test_visual_diff_gate_supports_per_module_threshold() -> None:
    script = _read_repo_file("frontend/tools/visual-audit/visual-diff.py")

    assert "REFERENCE_UI_TARGET_IMAGE" in script
    assert "C:/Users/" not in script
    assert "Downloads" not in script
    assert "DIFF_THRESHOLD_PERCENT" in script
    assert "TARGET_PANELS" in script
    assert "module_id" in script
    assert "threshold_percent" in script
    assert "FULL_REFERENCE_CANVAS" in script
    assert "generated-full-reference.png" in script
    assert "fit_generated_to_panel" in script
    assert "pixel_mismatch_percent" in script
    assert "full_canvas_diff_percent" in script
    assert "true_panel_diff_percent" in script
    assert "edge_diff_percent" in script
    assert "visual-diff-report.json" in script
    assert "VISUAL_DIFF_ENFORCE" in script
    assert "target-crops" in script


def test_visual_diff_runner_requires_target_env_or_arg(tmp_path: Path) -> None:
    script_path = _repo_file("frontend/tools/visual-audit/visual-diff.py")
    env = os.environ.copy()
    env.pop("REFERENCE_UI_TARGET_IMAGE", None)

    result = subprocess.run(
        [sys.executable, str(script_path), "--out", str(tmp_path / "report.json")],
        cwd=_resolve_repo_root(),
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode != 0
    assert "REFERENCE_UI_TARGET_IMAGE" in result.stderr


def test_visual_diff_custom_threshold_clears_passing_error(tmp_path: Path) -> None:
    from PIL import Image

    script_path = _repo_file("frontend/tools/visual-audit/visual-diff.py")
    target_path = tmp_path / "target.png"
    screenshot_dir = tmp_path / "screenshots"
    report_path = tmp_path / "visual-diff-report.json"
    screenshot_dir.mkdir()
    Image.new("RGB", (1672, 941), (244, 247, 251)).save(target_path)
    Image.new("RGB", (584, 275), (0, 0, 0)).save(screenshot_dir / "01-review-overview.png")
    env = os.environ.copy()
    env.pop("REFERENCE_UI_TARGET_IMAGE", None)

    result = subprocess.run(
        [
            sys.executable,
            str(script_path),
            "--module",
            "01",
            "--target",
            str(target_path),
            "--screenshots",
            str(screenshot_dir),
            "--out",
            str(report_path),
            "--threshold",
            "100",
        ],
        cwd=_resolve_repo_root(),
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0, result.stderr
    row = json.loads(report_path.read_text(encoding="utf-8"))["results"][0]
    assert row["status"] == "pass"
    assert row["error"] == ""
    assert row["threshold_percent"] == 100.0


def test_visual_diff_missing_screenshot_stays_failed_with_wide_threshold(tmp_path: Path) -> None:
    from PIL import Image

    script_path = _repo_file("frontend/tools/visual-audit/visual-diff.py")
    target_path = tmp_path / "target.png"
    screenshot_dir = tmp_path / "screenshots"
    report_path = tmp_path / "visual-diff-report.json"
    screenshot_dir.mkdir()
    Image.new("RGB", (1672, 941), (244, 247, 251)).save(target_path)
    env = os.environ.copy()
    env.pop("REFERENCE_UI_TARGET_IMAGE", None)

    result = subprocess.run(
        [
            sys.executable,
            str(script_path),
            "--module",
            "01",
            "--target",
            str(target_path),
            "--screenshots",
            str(screenshot_dir),
            "--out",
            str(report_path),
            "--threshold",
            "100",
        ],
        cwd=_resolve_repo_root(),
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0, result.stderr
    report = json.loads(report_path.read_text(encoding="utf-8"))
    row = report["results"][0]
    assert row["status"] == "fail"
    assert row["error"] == "missing screenshot"
    assert report["summary"]["failed"] == 1


def test_factory_board_module_05_is_table_first_like_reference_panel() -> None:
    source = _read_repo_file("frontend/src/views/dashboard/FactoryDirector.vue")

    assert "ReferencePageFrame" in source
    assert 'module-number="05"' in source
    assert "factoryBoardImage" not in source
    assert "cmd-factory-board__visual" not in source
    assert "cmd-factory-board__functional" not in source
    assert "reporting-status-table" in source
    for text in [
        "工厂作业看板",
        "今日上报状态",
        "车间",
        "产量(吨)",
        "状态",
        "今日关注",
        "近 7 日留存趋势",
    ]:
        assert text in source
    assert "提交生产数据" not in source
    assert "补录产量" not in source


def test_reference_modules_use_distinct_target_panel_layouts() -> None:
    modules = {
        "frontend/src/views/review/IngestionCenter.vue": ("module-number=\"06\"", "数据接入与字段映射中心"),
        "frontend/src/views/review/ReviewTaskCenter.vue": ("module-number=\"07\"", "审阅中心"),
        "frontend/src/views/reports/ReportList.vue": ("module-number=\"08\"", "日报与交付中心"),
        "frontend/src/views/quality/QualityCenter.vue": ("module-number=\"09\"", "质量与告警中心"),
        "frontend/src/views/review/CostAccountingCenter.vue": ("module-number=\"10\"", "成本核算与效益中心"),
        "frontend/src/views/reports/LiveDashboard.vue": ("module-number=\"12\"", "系统运维与观测"),
        "frontend/src/views/review/GovernanceCenter.vue": ("module-number=\"13\"", "权限与治理中心"),
        "frontend/src/views/master/WorkshopTemplateConfig.vue": ("module-number=\"14\"", "主数据与模板中心"),
    }
    for path, tokens in modules.items():
        source = _read_repo_file(path)
        assert "ReferencePageFrame" in source
        for token in tokens:
            assert token in source

    ai = _read_repo_file("frontend/src/views/ai/AiWorkstation.vue")
    assert "AI 工作台" in ai
    assert "cmd-module-page__visual" not in ai


def test_center_navigation_defines_first_round_business_centers_only() -> None:
    source = _read_repo_file("frontend/src/config/navigation.js")

    for expected in [
        "no: '01'",
        "no: '03'",
        "no: '05'",
        "no: '06'",
        "no: '07'",
        "no: '08'",
        "no: '09'",
        "no: '10'",
        "no: '11'",
        "no: '12'",
        "no: '13'",
        "no: '14'",
    ]:
        assert expected in source
    for expected in [
        "title: '独立填报端首页'",
        "title: '系统总览主视图'",
        "title: '工厂作业看板'",
        "title: '数据接入与字段映射中心'",
        "title: '审阅中心'",
        "title: '日报与交付中心'",
        "title: '质量与告警中心'",
        "title: '成本核算与效益中心'",
        "title: 'AI 总控中心'",
        "title: '系统运维与观测'",
        "title: '权限与治理中心'",
        "title: '主数据与模板中心'",
    ]:
        assert expected in source
    assert "no: '02'" not in source
    assert "no: '04'" not in source
    assert "no: '15'" not in source
    assert "no: '16'" not in source
    assert "description" not in source


def test_unified_shells_and_core_route_meta_follow_three_surface_blueprint() -> None:
    router = _read_repo_file("frontend/src/router/index.js")
    entry_shell = _read_repo_file("frontend/src/layout/EntryShell.vue")
    manage_shell = _read_repo_file("frontend/src/layout/ManageShell.vue")

    assert 'data-testid="entry-shell"' in entry_shell
    assert 'data-testid="manage-shell"' in manage_shell
    assert "数据中枢" in manage_shell
    assert "const entryMeta = { requiresAuth: true, zone: 'entry', access: 'entry' }" in router
    assert "const reviewMeta = { requiresAuth: true, zone: 'manage', access: 'review' }" in router
    assert "const adminMeta = { requiresAuth: true, zone: 'manage', access: 'admin' }" in router

    required_canonicals = [
        ("canonical: '/entry'", "'03'"),
        ("path: 'report/:businessDate/:shiftId'", "'04'"),
        ("path: 'advanced/:businessDate/:shiftId'", "'04'"),
        ("canonical: '/manage/overview'", "'01'"),
        ("canonical: '/manage/factory'", "'05'"),
        ("canonical: '/manage/workshop'", "'05'"),
        ("canonical: '/manage/entry-center'", "'07'"),
        ("canonical: '/manage/reports'", "'08'"),
        ("canonical: '/manage/quality'", "'09'"),
        ("canonical: '/manage/reconciliation'", "'09'"),
        ("canonical: '/manage/cost'", "'10'"),
        ("canonical: '/manage/ingestion'", "'06'"),
        ("canonical: '/manage/master'", "'14'"),
        ("canonical: '/manage/admin/templates'", "'14'"),
        ("canonical: '/manage/admin/users'", "'13'"),
        ("canonical: '/manage/admin/governance'", "'13'"),
        ("canonical: '/manage/admin/settings'", "'12'"),
    ]
    for anchor, center_no in required_canonicals:
        index = router.index(anchor)
        route_slice = router[max(0, index - 280): index + 360]
        assert "title:" in route_slice
        assert "meta:" in route_slice
        assert "canonical:" in route_slice
        assert f"centerNo: {center_no}" in route_slice


def test_router_exposes_reference_admin_ops_short_path() -> None:
    source = _read_repo_file("frontend/src/router/index.js")

    assert "path: 'admin/ops'" in source
    assert "redirect: { name: 'admin-ops-reliability' }" in source
    assert "{ path: '/ops/reliability', redirect: '/manage/admin/settings' }" in source


def test_router_exposes_reference_admin_short_paths() -> None:
    source = _read_repo_file("frontend/src/router/index.js")

    assert "path: 'master'," in source
    assert "path: 'admin/templates'," in source
    assert "path: 'admin/users'," in source
    assert "path: '/admin/ingestion', redirect: '/manage/ingestion'" in source
    assert "redirect: { name: 'admin-master-workshop' }" in source
    assert "path: '/admin/templates', redirect: '/manage/admin/templates'" in source
    assert "path: '/admin/users', redirect: '/manage/admin/users'" in source


def test_review_roadmap_is_legacy_redirect_not_formal_center() -> None:
    source = _read_repo_file("frontend/src/router/index.js")

    assert "{ path: '/review/roadmap', redirect: '/manage/overview' }" in source
    assert "name: 'review-roadmap-center'" not in source
    assert "moduleId: '16'" not in source


def test_review_roadmap_is_not_formal_review_navigation_item() -> None:
    source = _read_repo_file("frontend/src/config/navigation.js")

    assert "review-roadmap-center" not in source
    assert "admin-roadmap-center" not in source
    assert "路线图" not in source


def test_factory_board_uses_reference_frame_module_05() -> None:
    source = _read_repo_file("frontend/src/views/dashboard/FactoryDirector.vue")

    assert "ReferencePageFrame" in source
    assert 'module-number="05"' in source
    assert 'title="工厂作业看板"' in source
