from __future__ import annotations

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


def _reference_command_files() -> list[Path]:
    root = _repo_file("frontend/src/reference-command")
    if not root.exists():
        return []
    return [path for path in root.rglob("*") if path.is_file()]


def test_reference_command_boundary_files_are_declared() -> None:
    expected = [
        "frontend/src/reference-command/assets/logo.js",
        "frontend/src/reference-command/assets/industry-graphics.js",
        "frontend/src/reference-command/data/moduleCatalog.js",
        "frontend/src/reference-command/data/moduleAdapters.js",
        "frontend/src/reference-command/components/CommandCanvas.vue",
        "frontend/src/reference-command/components/CommandPanel.vue",
        "frontend/src/reference-command/components/CommandPage.vue",
        "frontend/src/reference-command/components/CommandKpi.vue",
        "frontend/src/reference-command/components/CommandTable.vue",
        "frontend/src/reference-command/components/CommandTrend.vue",
        "frontend/src/reference-command/components/CommandFlowMap.vue",
        "frontend/src/reference-command/components/CommandActionBar.vue",
        "frontend/src/reference-command/components/CommandStatus.vue",
        "frontend/src/reference-command/shells/CommandEntryShell.vue",
        "frontend/src/reference-command/shells/CommandReviewShell.vue",
        "frontend/src/reference-command/shells/CommandAdminShell.vue",
        "frontend/src/reference-command/pages/CommandLogin.vue",
        "frontend/src/reference-command/pages/CommandOverview.vue",
        "frontend/src/reference-command/pages/CommandEntryHome.vue",
        "frontend/src/reference-command/pages/CommandEntryFlow.vue",
        "frontend/src/reference-command/pages/CommandModulePage.vue",
        "frontend/src/reference-command/styles/command-tokens.css",
        "frontend/src/reference-command/styles/command-layout.css",
        "frontend/src/reference-command/styles/command-motion.css",
    ]
    for path in expected:
        assert _repo_file(path).exists(), path


def test_reference_command_ui_uses_chinese_dense_copy_without_helper_fields() -> None:
    files = _reference_command_files()
    assert files, "frontend/src/reference-command must contain the rebuilt UI boundary"

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


def test_reference_command_catalog_declares_16_target_modules() -> None:
    catalog = _read_repo_file("frontend/src/reference-command/data/moduleCatalog.js")

    for module_id in [f"{index:02d}" for index in range(1, 17)]:
        assert f"moduleId: '{module_id}'" in catalog

    for title in [
        "系统总览主视图",
        "登录与角色入口",
        "独立填报终端首页",
        "填报流程页",
        "工厂作业看板",
        "数据接入与字段映射中心",
        "审阅中心",
        "日报与交付中心",
        "质量与告警中心",
        "成本核算与效益中心",
        "AI 总大脑中心",
        "系统运维与可观测",
        "权限治理中心",
        "主数据与模板中心",
        "响应式录入体验",
        "路线图与下一步",
    ]:
        assert title in catalog

    for surface in ["surface: 'entry'", "surface: 'review'", "surface: 'admin'", "surface: 'system'"]:
        assert surface in catalog


def test_reference_command_tokens_match_target_image_rules() -> None:
    tokens = _read_repo_file("frontend/src/reference-command/styles/command-tokens.css")

    assert "--cmd-bg: #f4f7fb" in tokens
    assert "--cmd-panel: #ffffff" in tokens
    assert "--cmd-border: #e5edf7" in tokens
    assert "--cmd-blue: #1f6fff" in tokens
    assert "DIN Alternate" in tokens
    assert "Microsoft YaHei" in tokens


def test_reference_command_components_expose_target_css_hooks() -> None:
    hooks = {
        "CommandPanel.vue": ["cmd-panel", "cmd-panel__number", "cmd-panel__title"],
        "CommandCanvas.vue": ["cmd-canvas", "cmd-canvas__grid"],
        "CommandPage.vue": ["cmd-module-page", "cmd-module-page__primary", "cmd-module-page__side"],
        "CommandKpi.vue": ["cmd-kpi", "cmd-kpi__value"],
        "CommandActionBar.vue": ["cmd-action-bar"],
    }
    for filename, expected_hooks in hooks.items():
        source = _read_repo_file(f"frontend/src/reference-command/components/{filename}")
        for hook in expected_hooks:
            assert hook in source


def test_reference_command_keeps_legacy_routes_and_route_names() -> None:
    router = _read_repo_file("frontend/src/router/index.js")

    for route_name in [
        "mobile-entry",
        "dynamic-entry-form",
        "review-overview-home",
        "factory-dashboard",
        "review-task-center",
        "report-list",
        "quality-center",
        "cost-accounting-center",
        "brain-center",
        "ops-reliability",
        "governance-center",
        "master-workshop",
        "workshop-template-config",
    ]:
        assert f"name: '{route_name}'" in router

    for legacy_path in ["/mobile", "/dashboard", "/master", "/ops/reliability"]:
        assert legacy_path in router


def test_command_login_replaces_old_login_route_with_three_roles() -> None:
    router = _read_repo_file("frontend/src/router/index.js")
    login = _read_repo_file("frontend/src/reference-command/pages/CommandLogin.vue")
    audit = _read_repo_file("frontend/tmp_visual_audit.cjs")

    assert "component: CommandLogin" in router
    for role in ["录入端", "审阅端", "管理端"]:
        assert role in login
    assert "cmd-login-reference" in login
    assert "loginRoleHandoffImage" in login
    assert "cmd-login__functional" in login
    assert "cmd-login-reference" in audit
    assert "(Login" not in login


def test_reference_command_shells_keep_three_surfaces_separate() -> None:
    entry = _read_repo_file("frontend/src/reference-command/shells/CommandEntryShell.vue")
    review = _read_repo_file("frontend/src/reference-command/shells/CommandReviewShell.vue")
    admin = _read_repo_file("frontend/src/reference-command/shells/CommandAdminShell.vue")

    assert "独立填报端" in entry
    assert "审阅中心" not in entry
    assert "主数据" not in entry
    assert "AI 总大脑" in review
    assert "管理控制台" in admin
    assert "现场填报" not in admin


def test_review_overview_uses_single_reference_module_01() -> None:
    overview = _read_repo_file("frontend/src/reference-command/pages/CommandOverview.vue")
    router = _read_repo_file("frontend/src/router/index.js")

    assert "cmd-overview-board" in overview
    assert "cmd-overview-kpis" in overview
    assert "overviewKpisImage" in overview
    assert "cmd-overview-kpis__visual" in overview
    assert "cmd-overview-shortcuts" in overview
    assert "cmd-overview-line" in overview
    assert "overviewFactoryLineImage" in overview
    assert "overviewShortcutsImage" in overview
    assert "cmd-overview-card__visual" in overview
    assert "cmd-overview-status__label" in overview
    assert "name: 'review-overview-home'" in router
    assert "component: CommandOverview" in router
    assert "moduleId: '01'" in router


def test_entry_surface_is_entry_only_and_matches_modules_03_04() -> None:
    home = _read_repo_file("frontend/src/reference-command/pages/CommandEntryHome.vue")
    flow = _read_repo_file("frontend/src/reference-command/pages/CommandEntryFlow.vue")
    router = _read_repo_file("frontend/src/router/index.js")
    audit = _read_repo_file("frontend/tmp_visual_audit.cjs")

    assert 'data-module="03"' in home
    assert 'data-module="04"' in flow
    assert "cmd-entry-terminal" in home
    assert "entryTerminalImage" in home
    assert "cmd-entry-terminal__functional" in home
    assert "cmd-entry-terminal" in audit
    assert "快速填报" in home
    assert "基础信息" in flow
    assert "name: 'mobile-entry'" in router
    assert "name: 'dynamic-entry-form'" in router
    for forbidden in ["权限治理", "主数据", "审阅任务"]:
        assert forbidden not in home
        assert forbidden not in flow


def test_review_modules_are_schema_driven_command_pages() -> None:
    router = _read_repo_file("frontend/src/router/index.js")
    review_start = router.index("path: '/review'")
    review_end = router.index("{ path: '/factory'", review_start)
    review_routes = router[review_start:review_end]
    expected = [
        ("name: 'factory-dashboard'", "moduleId: '05'"),
        ("name: 'review-task-center'", "moduleId: '07'"),
        ("name: 'review-report-center'", "moduleId: '08'"),
        ("name: 'review-quality-center'", "moduleId: '09'"),
        ("name: 'review-cost-accounting'", "moduleId: '10'"),
        ("name: 'review-brain-center'", "moduleId: '11'"),
        ("name: 'review-roadmap-center'", "moduleId: '16'"),
    ]
    for route_name, module_id in expected:
        route_index = review_routes.index(route_name)
        route_slice = review_routes[route_index: route_index + 360]
        assert "component: CommandModulePage" in route_slice
        assert module_id in route_slice


def test_admin_modules_are_schema_driven_command_pages() -> None:
    router = _read_repo_file("frontend/src/router/index.js")
    admin_start = router.index("path: '/admin'")
    admin_end = router.index("path: '/review'", admin_start)
    admin_routes = router[admin_start:admin_end]
    expected = [
        ("name: 'admin-ingestion-center'", "moduleId: '06'"),
        ("name: 'admin-ops-reliability'", "moduleId: '12'"),
        ("name: 'admin-governance-center'", "moduleId: '13'"),
        ("name: 'admin-users'", "moduleId: '13'"),
        ("name: 'admin-master-workshop'", "moduleId: '14'"),
        ("name: 'admin-template-center'", "moduleId: '14'"),
        ("name: 'admin-roadmap-center'", "moduleId: '16'"),
    ]
    for route_name, module_id in expected:
        route_index = admin_routes.index(route_name)
        route_slice = admin_routes[route_index: route_index + 360]
        assert "component: CommandModulePage" in route_slice
        assert module_id in route_slice


def test_ui_replica_spec_locks_reference_module_granularity() -> None:
    spec = _read_repo_file("docs/ui-replica-spec.md")

    assert "# UI 复刻规范（参考图级生产指挥中心执行规格）" in spec
    required_rows = [
        "| 01 | 系统总览主视图 | 审阅端 | `/review/overview` |",
        "| 02 | 登录与角色入口 | 公共入口 | `/login` |",
        "| 03 | 独立填报终端首页 | 录入端 | `/entry` |",
        "| 04 | 填报流程页 | 录入端 | `/entry/report/*`、`/entry/advanced/*` |",
        "| 05 | 工厂作业看板 | 审阅端 | `/review/factory` |",
        "| 06 | 数据接入与字段映射中心 | 管理端 | `/admin/ingestion` |",
        "| 07 | 审阅中心 | 审阅端 | `/review/tasks` |",
        "| 08 | 日报与交付中心 | 审阅端 | `/review/reports` |",
        "| 09 | 质量与告警中心 | 审阅端 | `/review/quality` |",
        "| 10 | 成本核算与效益中心 | 审阅端 | `/review/cost-accounting` |",
        "| 11 | AI 总大脑中心 | 审阅端 | `/review/brain` |",
        "| 12 | 系统运维与可观测 | 管理端 | `/admin/ops` |",
        "| 13 | 权限治理中心 | 管理端 | `/admin/governance` |",
        "| 14 | 主数据与模板中心 | 管理端 | `/admin/master`、`/admin/master/templates` |",
        "| 15 | 响应式录入体验 | 全局验收 | `/entry` 全链路 |",
        "| 16 | 路线图与下一步 | 双端 | `/review/roadmap`、`/admin/roadmap` |",
    ]
    for row in required_rows:
        assert row in spec

    assert "移动端预览模块取消" in spec
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
    source = _read_repo_file("frontend/tmp_visual_audit.cjs")

    assert "referenceChecklist" in source
    assert "targetReferenceImage" in source
    assert "referencePanelChecks" in source
    assert "targetImageMeta" in source
    assert "expectedPanelCount: 16" in source
    assert "cb3b60f0-1a5d-43e4-94bc-9d4cf4274aa5.png" in source
    assert "route: '/login'" in source
    assert "route: '/entry'" in source
    assert "route: '/review/factory'" in source
    assert "route: '/review/overview'" in source
    assert "route: '/review/tasks'" in source
    assert "route: '/review/cost-accounting'" in source
    assert "route: '/review/roadmap'" in source
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
    assert "14-admin-master.png" in source
    assert "16-review-roadmap.png" in source
    assert "surface boundary: fill-only nav isolation" in source
    assert "mobile preview module cancelled" in source
    assert "ensureTextAbsent" in source
    assert "ensureFactoryReferenceDensity" in source
    assert "factoryDensity: true" in source
    assert "ensureLayoutHook" in source
    assert "layoutHook: '.cmd-layout--mapping-center'" in source
    assert "layoutHook: '.cmd-layout--roadmap'" in source


def test_visual_diff_gate_supports_per_module_threshold() -> None:
    script = _read_repo_file("frontend/tmp_visual_diff.py")

    assert "REFERENCE_UI_TARGET_IMAGE" in script
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


def test_factory_board_module_05_is_table_first_like_reference_panel() -> None:
    source = _read_repo_file("frontend/src/reference-command/components/CommandPage.vue")
    start = source.index('v-if="showFactoryCompat"')
    end = source.index("<template v-else>", start)
    factory_section = source[start:end]

    assert "cmd-factory-board__stats" not in factory_section
    assert "data-testid=\"review-command-deck\"" in factory_section
    assert "cmd-factory-table" in factory_section
    assert "合计/平均" in factory_section


def test_reference_modules_use_distinct_target_panel_layouts() -> None:
    source = _read_repo_file("frontend/src/reference-command/components/CommandPage.vue")

    required_hooks = [
        "cmd-layout--mapping-center",
        "cmd-layout--review-center",
        "cmd-layout--report-delivery",
        "cmd-layout--quality-alerts",
        "cmd-layout--cost-stack",
        "cmd-layout--ai-brain",
        "cmd-layout--ops-observability",
        "cmd-layout--governance-matrix",
        "cmd-layout--master-templates",
        "cmd-layout--roadmap",
    ]
    for hook in required_hooks:
        assert hook in source


def test_router_exposes_reference_admin_ops_short_path() -> None:
    source = _read_repo_file("frontend/src/router/index.js")

    assert "path: 'ops'," in source
    assert "redirect: { name: 'admin-ops-reliability' }" in source
    assert "{ path: '/ops/reliability', redirect: '/admin/ops' }" in source


def test_router_exposes_reference_admin_short_paths() -> None:
    source = _read_repo_file("frontend/src/router/index.js")

    assert "path: 'field-mapping'," in source
    assert "path: 'master'," in source
    assert "path: 'templates'," in source
    assert "path: 'users'," in source
    assert "redirect: { name: 'admin-ingestion-center' }" in source
    assert "redirect: { name: 'admin-master-workshop' }" in source
    assert "redirect: { name: 'admin-template-center' }" in source
    assert "redirect: { name: 'admin-users' }" in source


def test_review_roadmap_remains_in_review_surface() -> None:
    source = _read_repo_file("frontend/src/router/index.js")
    start = source.index("path: '/review'")
    end = source.index("{ path: '/factory'", start)
    review_routes = source[start:end]

    assert "path: 'roadmap'," in review_routes
    assert "name: 'review-roadmap-center'" in review_routes
    assert "component: CommandModulePage" in review_routes
    assert "moduleId: '16'" in review_routes
    assert "redirect: { name: 'admin-roadmap-center' }" not in review_routes


def test_review_roadmap_is_formal_review_navigation_item() -> None:
    source = _read_repo_file("frontend/src/config/navigation.js")

    assert "'review-roadmap-center': { center: 'roadmap', group: '经营与智能'" in source
    assert "'review-roadmap-center': { center: 'roadmap', group: '兼容入口'" not in source
    assert "{ routeName: 'review-roadmap-center', label: '路线图', access: 'review_surface' }" in source


def test_factory_board_uses_reference_frame_module_05() -> None:
    source = _read_repo_file("frontend/src/views/dashboard/FactoryDirector.vue")

    assert "ReferencePageFrame" in source
    assert 'module-number="05"' in source
    assert 'title="工厂作业看板"' in source
