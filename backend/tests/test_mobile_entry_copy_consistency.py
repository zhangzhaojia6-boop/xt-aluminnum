from __future__ import annotations

import re
from pathlib import Path

from tests.path_helpers import REPO_ROOT


def _resolve_repo_root() -> Path:
    if (REPO_ROOT / "frontend").exists() and (REPO_ROOT / "README.md").exists():
        return REPO_ROOT
    return Path(__file__).resolve().parents[2]


def _read_repo_file(relative_path: str) -> str:
    return (_resolve_repo_root() / relative_path).read_text(encoding="utf-8-sig")


VISUAL_AUDIT_TOOL = "frontend/tools/visual-audit/command-center-audit.cjs"


def test_readme_promotes_dingtalk_mobile_entry() -> None:
    readme = _read_repo_file("README.md")

    assert "钉钉" in readme
    assert "手机填报唯一入口" in readme or "单入口优先" in readme
    assert "企业微信单入口优先" not in readme


def test_copy_consistency_reader_resolves_repo_root_without_env_override() -> None:
    repo_root = _resolve_repo_root()

    assert (repo_root / "README.md").exists()
    assert (repo_root / "frontend" / "src").exists()


def test_mobile_entry_copy_uses_single_dingtalk_priority() -> None:
    source = _read_repo_file("frontend/src/views/mobile/MobileEntry.vue")

    assert "钉钉" in source
    assert "企业微信" not in source
    assert 'data-testid="mobile-go-ocr"' not in source


def test_worker_redirect_preserves_query_for_wecom_and_qr_handoff() -> None:
    source = _read_repo_file("frontend/src/router/index.js")

    assert "path: '/worker'" in source
    assert "redirect: (to) => ({" in source
    assert "query: to.query" in source


def test_mobile_entry_handles_bootstrap_load_failure_as_error_state() -> None:
    source = _read_repo_file("frontend/src/views/mobile/MobileEntry.vue")

    assert "catch (error)" in source
    assert "加载当前班次失败，请稍后重试或改用账号登录。" in source


def test_mobile_report_route_defaults_to_shift_report_form() -> None:
    source = _read_repo_file("frontend/src/router/index.js")

    assert "const ShiftReportForm = () => import('../views/mobile/ShiftReportForm.vue')" in source
    assert re.search(
        r"path: 'report/:businessDate/:shiftId'.*?name: 'mobile-report-form'.*?component: ShiftReportForm",
        source,
        re.S,
    )
    assert re.search(
        r"path: 'advanced/:businessDate/:shiftId'.*?component: DynamicEntryForm",
        source,
        re.S,
    )
    assert re.search(
        r"path: '/mobile/report/:businessDate/:shiftId'.*?path: `/entry/report/",
        source,
        re.S,
    )


def test_mobile_entry_uses_current_task_first_copy() -> None:
    source = _read_repo_file("frontend/src/views/mobile/MobileEntry.vue")

    assert "03 独立填报端" in source
    assert "当前任务" in source
    assert "入口 ${entryMode}" in source
    assert "mobile-report-form-advanced" in source
    assert "transitionMapping.value.role_bucket" in source
    assert "'machine_operator'" in source
    assert "'weigher'" in source
    assert "'qc'" in source
    assert "'energy_stat'" in source
    assert "'inventory_keeper'" in source
    assert "'utility_manager'" in source


def test_shift_report_form_copy_matches_manual_phase() -> None:
    source = _read_repo_file("frontend/src/views/mobile/ShiftReportForm.vue")

    assert "提交确认" in source
    assert "正式提交" in source
    assert "04 填报流程页" in source
    assert "goDesktop" not in source
    assert "canAccessDesktop" not in source
    assert "function requestErrorMessage(error, fallback = '操作失败')" in source
    assert "Array.isArray(detail)" in source
    assert "detail.message || detail.msg || fallback" in source
    assert "ElMessage.error(requestErrorMessage(error, '暂存失败'))" in source
    assert "ElMessage.error(requestErrorMessage(error, '提交失败'))" in source
    assert "ElMessage.error(requestErrorMessage(error, '图片上传失败，请重试'))" in source
    assert "loadError.value = requestErrorMessage(error, '加载班次填报失败，请返回入口后重试。')" in source
    assert "catch (error)" in source
    assert "加载班次填报失败，请返回入口后重试。" in source


def test_attendance_confirm_surfaces_load_and_draft_errors() -> None:
    source = _read_repo_file("frontend/src/views/mobile/AttendanceConfirm.vue")

    assert "const pageError = ref('')" in source
    assert "v-if=\"pageError\"" in source
    assert "pageError.value = ''" in source
    assert "pageError.value = requestErrorMessage(error, '加载考勤确认页面失败，请刷新重试。')" in source
    assert "ElMessage.error(requestErrorMessage(error, '加载考勤草稿失败，请稍后重试'))" in source
    assert "detail.message || detail.msg || fallback" in source


def test_mobile_error_parsers_handle_object_detail_payloads() -> None:
    dynamic_source = _read_repo_file("frontend/src/views/mobile/DynamicEntryForm.vue")
    entry_source = _read_repo_file("frontend/src/views/mobile/MobileEntry.vue")
    ocr_source = _read_repo_file("frontend/src/views/mobile/OCRCapture.vue")

    assert "detail.message || detail.msg || fallback" in dynamic_source
    assert "detail.message || detail.msg || fallback" in entry_source
    assert "detail.message || detail.msg || fallback" in ocr_source


def test_dynamic_entry_form_switches_special_owners_to_owner_only_mode() -> None:
    source = _read_repo_file("frontend/src/views/mobile/DynamicEntryForm.vue")

    assert "const ownerOnlyRoleBuckets = ['contracts', 'inventory_keeper', 'utility_manager']" in source
    assert "const isOwnerOnlyMode = computed(() => ownerOnlyRoleBuckets.includes(transitionMapping.value.role_bucket))" in source
    assert "按班次补录，系统会自动归档。" in source
    assert "当前岗位按班次补录，不需要随行卡。系统会自动按日期、班次和岗位归档。" not in source
    assert "if (!isOwnerOnlyMode.value && !normalized)" in source
    assert "OWNER-" in source


def test_dynamic_entry_form_hides_work_order_scaffold_for_owner_only_mode() -> None:
    source = _read_repo_file("frontend/src/views/mobile/DynamicEntryForm.vue")

    assert "<template #work_order>" in source
    assert "v-if=\"!isOwnerOnlyMode\"" in source
    assert "isOwnerOnlyMode ? ownerModeConfig.title : '批次号填报'" in source
    assert "isOwnerOnlyMode.value ? 'core' : 'work_order'" in source


def test_dynamic_entry_form_owner_only_mode_skips_tracking_card_and_machine_summary() -> None:
    source = _read_repo_file("frontend/src/views/mobile/DynamicEntryForm.vue")

    assert "label: isOwnerOnlyMode.value ? '岗位归档' : '批次号'" in source
    assert "label: isOwnerOnlyMode.value ? '岗位' : (isMachineBound.value ? '机台' : '班组')" in source
    assert "if (equipmentOptions.value.length && !formState.machine_id && !isOwnerOnlyMode.value)" in source
    assert "if (isFastTempo.value && !isOwnerOnlyMode.value)" in source
    assert "currentStepKey.value = isOwnerOnlyMode.value ? 'core' : 'work_order'" in source


def test_dynamic_entry_form_uses_shift_fields_and_trims_review_copy() -> None:
    source = _read_repo_file("frontend/src/views/mobile/DynamicEntryForm.vue")

    assert "const shiftFields = computed(() => template.value?.shift_fields || [])" in source
    assert "if (hasShiftConfirmationFields.value) return '班末确认'" in source
    assert "<template #header>{{ supplementalCardTitle }}</template>" in source
    assert "<template #header>确认提交</template>" in source
    assert "<template #header>工具与记录</template>" in source
    assert "title=\"拍照记录\"" in source
    assert "title=\"批量粘贴\"" in source
    assert "label: '已填'" in source
    assert "label: '识别来源'" not in source


def test_dynamic_entry_form_trims_operator_surface_copy() -> None:
    source = _read_repo_file("frontend/src/views/mobile/DynamicEntryForm.vue")

    assert "04 填报流程页" in source
    assert "goDesktop" not in source
    assert "canAccessDesktop" not in source
    assert "<template #header>连续录入</template>" in source
    assert "批次号填报" in source
    assert "<label>当前卷</label>" in source
    assert "<template #header>本班交接</template>" in source
    assert "继续录入" in source
    assert "前序记录" in source
    assert "<label>工艺路线</label>" not in source
    assert "<label>工单状态</label>" not in source
    assert "<label>工单头信息</label>" not in source
    assert "快工序节奏" not in source
    assert "慢工序交接" not in source
    assert "前序班次已填数据" not in source
    assert "本班接续（下班继续）" not in source


def test_dynamic_entry_form_trims_redundant_helper_copy() -> None:
    source = _read_repo_file("frontend/src/views/mobile/DynamicEntryForm.vue")

    assert "当前账号暂时无法填报。" in source
    assert "队列 {{ batchQueue.length }} 卷" in source
    assert "制表符分列，每行一卷。" in source
    assert "{{ isOwnerOnlyMode ? ownerModeConfig.coreCardTitle : '填写' }}" in source
    assert "ownerModeConfig.title" in source
    assert "前序记录" in source
    assert "{{ isOwnerOnlyMode ? '岗位补录' : '按随行卡填报' }}" not in source
    assert "按随行卡逐卷录入，提交前请核对数据与现场一致。" not in source
    assert "随行卡号来自外部生产系统，本系统只做录入与流转，不直接连接外部生产系统。" not in source
    assert "机台账号已绑定到当前设备，无法切换其他机台。" not in source
    assert "当前车间尚未配置机台，先允许按班次录入。" not in source
    assert "当前随行卡在本车间还没有前序班次记录。" not in source
    assert "确认后正式提交。" not in source


def test_dynamic_entry_form_uses_field_facing_step_titles_and_trimmed_summary_strip() -> None:
    source = _read_repo_file("frontend/src/views/mobile/DynamicEntryForm.vue")

    assert "items.push({ key: 'work_order', title: '批次号' })" in source
    assert "items.push({ key: 'core', title: isOwnerOnlyMode.value ? ownerModeConfig.value.coreStepTitle : '本卷' })" in source
    assert "items.push({ key: 'supplemental', title: isOwnerOnlyMode.value ? ownerModeConfig.value.supplementalStepTitle : (hasShiftConfirmationFields.value ? '班末' : '补充') })" in source
    assert "items.push({ key: 'review', title: '提交' })" in source
    assert "const summaryFacts = computed(() => [" in source
    assert "formState.business_date || '-'" in source
    assert "currentShift.shift_name || currentShift.shift_code || '-'" in source
    assert "isOwnerOnlyMode.value ? '本班补录' : '本卷录入'" in source
    assert "entry-summary-strip__row" not in source
    assert "const summaryIdentity = computed(() => [" not in source
    assert "tempoLabel.value" not in source
    assert "currentShift.leader_name || auth.displayName" not in source
    assert "template.value?.supports_ocr ? '支持拍照识别' : '手动录入'" not in source
    assert "<el-button plain @click=\"goEntry\">返回入口</el-button>" not in source


def test_dynamic_entry_form_only_shows_fast_tempo_helper_when_it_is_useful() -> None:
    source = _read_repo_file("frontend/src/views/mobile/DynamicEntryForm.vue")

    assert "const showFastEntryHelper = computed(() => Boolean(" in source
    assert "!isOwnerOnlyMode.value" in source
    assert "isFastTempo.value" in source
    assert "submittedCount.value" in source
    assert "batchQueue.value.length" in source
    assert "canContinueNext.value" in source
    assert "v-if=\"template && showFastEntryHelper\"" in source
    assert "<el-card v-if=\"template && showFastEntryHelper\" class=\"panel mobile-card\">" in source


def test_dynamic_entry_form_uses_owner_specific_workbench_copy_and_group_titles() -> None:
    source = _read_repo_file("frontend/src/views/mobile/DynamicEntryForm.vue")

    assert "title: '成品库填报'" in source
    assert "description: '录今日入库、发货与结存。'" in source
    assert "title: '水电气填报'" in source
    assert "description: '录用电、天然气和用水原始值。'" in source
    assert "title: '计划科填报'" in source
    assert "description: '录合同、余量与投料口径。'" in source
    assert "title: '今日入库'" in source
    assert "title: '今日发货'" in source
    assert "title: '结存与备料'" in source
    assert "title: '用电'" in source
    assert "title: '天然气'" in source
    assert "title: '用水'" in source
    assert "title: '当日合同'" in source
    assert "title: '月累计与余合同'" in source
    assert "title: '投料与坯料'" in source
    assert "ownerModeConfig.title" in source
    assert "ownerCoreSections" in source
    assert "ownerSupplementalSections" in source


def test_mobile_transition_copy_matches_special_owner_scope() -> None:
    source = _read_repo_file("frontend/src/utils/mobileTransition.js")

    assert "title: '计划科补录'" in source
    assert "只录合同与投料口径。" in source
    assert "title: '成品库补录'" in source
    assert "只录入库、发货与结存。" in source
    assert "title: '水电气补录'" in source
    assert "只录全厂水、电、气。" in source


def test_mobile_bottom_nav_keeps_entry_surface_only() -> None:
    source = _read_repo_file("frontend/src/views/mobile/MobileBottomNav.vue")

    assert "const desktopNavItem = computed(() => {" not in source
    assert "factory-dashboard" not in source
    assert "master-workshop" not in source
    assert "后台" not in source


def test_entry_shell_owns_bottom_navigation_without_page_duplicates() -> None:
    shell = _read_repo_file("frontend/src/layout/EntryShell.vue")

    assert "xt-entry__tabbar" in shell
    for path in [
        "frontend/src/views/mobile/MobileEntry.vue",
        "frontend/src/views/mobile/AttendanceConfirm.vue",
        "frontend/src/views/mobile/DynamicEntryForm.vue",
        "frontend/src/views/mobile/OCRCapture.vue",
        "frontend/src/views/mobile/ShiftReportHistory.vue",
    ]:
        source = _read_repo_file(path)
        assert "<MobileBottomNav" not in source
        assert "import MobileBottomNav" not in source


def test_phase1_desktop_landing_skips_statistics_and_review_defaults() -> None:
    source = _read_repo_file("frontend/src/router/index.js")

    assert "if (authStore.canAccessStatisticsDashboard) return { name: 'statistics-dashboard' }" not in source
    assert "if (authStore.canAccessReviewDesk) return { name: 'shift-center' }" not in source
    assert "if (authStore.isAdmin || authStore.isManager) return { name: 'admin-overview' }" in source


def test_phase1_layout_hides_review_and_statistics_navigation() -> None:
    source = _read_repo_file("frontend/src/layout/ManageShell.vue")

    assert 'data-testid="manage-shell"' in source
    assert "数据中枢" in source
    assert "班次观察台" not in source
    assert "差异处置" not in source


def test_layout_trims_admin_navigation_to_phase1_minimum_controls() -> None:
    source = _read_repo_file("frontend/src/config/navigation.js")

    assert "const adminNavigation = [" in source
    assert "group: '管理总览'" in source
    assert "label: '数据接入'" in source
    assert "label: '权限治理'" in source
    assert "routeName: 'admin-master-workshop'" in source
    assert "routeName: 'admin-template-center'" in source
    assert "routeName: 'master-team'" not in source
    assert "routeName: 'master-employee'" not in source
    assert "routeName: 'master-alias'" not in source
    assert "routeName: 'admin-roadmap-center'" not in source


def test_layout_surfaces_phase1_agent_shell_badges() -> None:
    source = _read_repo_file("frontend/src/layout/AppShell.vue")

    assert "审阅指挥台" in source
    assert "录入端" in source
    assert "审阅端" in source
    assert "AI 助手" in source


def test_router_exposes_separate_review_surface() -> None:
    source = _read_repo_file("frontend/src/router/index.js")

    assert "const ManageShell = () => import('../layout/ManageShell.vue')" in source
    assert "path: '/manage'" in source
    assert "path: '/review'" in source
    assert "component: ManageShell" in source
    assert "zone: 'manage'" in source


def test_reference_ui_keeps_legacy_route_names_and_urls() -> None:
    source = _read_repo_file("frontend/src/router/index.js")

    assert "name: 'mobile-entry'" in source
    assert "name: 'review-overview-home'" in source
    assert "name: 'factory-dashboard'" in source
    assert "name: 'workshop-dashboard'" in source
    assert "name: 'master-workshop'" in source
    assert "path: '/mobile'" in source
    assert "redirect: (to) => ({ path: '/entry'" in source
    assert "path: '/dashboard/factory', redirect: '/manage/factory'" in source
    assert "path: '/master/workshop', name: 'master-workshop', redirect: '/manage/master'" in source


def test_reference_ui_declares_three_independent_surfaces() -> None:
    router_source = _read_repo_file("frontend/src/router/index.js")
    nav_source = _read_repo_file("frontend/src/config/navigation.js")
    auth_source = _read_repo_file("frontend/src/stores/auth.js")

    assert "path: '/entry'" in router_source
    assert "path: '/manage'" in router_source
    assert "path: '/review'" in router_source
    assert "path: '/admin'" in router_source
    assert "entrySurface()" in auth_source
    assert "reviewSurface()" in auth_source
    assert "adminSurface()" in auth_source
    assert "const entryNavigation" in nav_source
    assert "const reviewNavigation" in nav_source
    assert "const adminNavigation" in nav_source


def test_shells_do_not_leak_cross_surface_navigation() -> None:
    entry = _read_repo_file("frontend/src/layout/EntryShell.vue")
    app_shell = _read_repo_file("frontend/src/layout/AppShell.vue")
    manage = _read_repo_file("frontend/src/layout/ManageShell.vue")

    assert "现场填报" in entry
    assert "审阅任务" not in entry
    assert "主数据" not in entry
    assert "AI 助手" in app_shell
    assert "管理控制台" in app_shell
    assert 'data-testid="manage-shell"' in manage
    assert "现场填报" not in manage


def test_reference_ui_component_layer_exists() -> None:
    for path in [
        "frontend/src/components/reference/ReferencePageFrame.vue",
        "frontend/src/components/reference/ReferenceModuleCard.vue",
        "frontend/src/components/reference/ReferenceKpiTile.vue",
        "frontend/src/components/reference/ReferenceStatusTag.vue",
        "frontend/src/components/reference/ReferenceDataTable.vue",
        "frontend/src/components/reference/ReferenceFlowGraphic.vue",
        "frontend/src/components/xt/XtCard.vue",
        "frontend/src/components/xt/XtKpi.vue",
        "frontend/src/components/xt/XtTable.vue",
        "frontend/src/components/xt/XtStatus.vue",
    ]:
        assert (_resolve_repo_root() / path).exists()

    tokens = _read_repo_file("frontend/src/design/xt-tokens.css")
    base = _read_repo_file("frontend/src/design/xt-base.css")
    assert "--xt-bg-page" in tokens
    assert "--xt-primary" in tokens
    assert ".reference-page" in base


def test_reference_login_and_entry_use_cn_titles_and_no_english_subtitles() -> None:
    login = _read_repo_file("frontend/src/views/Login.vue")
    entry = _read_repo_file("frontend/src/views/mobile/MobileEntry.vue")
    dynamic = _read_repo_file("frontend/src/views/mobile/DynamicEntryForm.vue")
    shift = _read_repo_file("frontend/src/views/mobile/ShiftReportForm.vue")
    bottom_nav = _read_repo_file("frontend/src/views/mobile/MobileBottomNav.vue")

    assert "Login & Role Handoff" not in login
    assert "Independent Entry Terminal" not in entry
    assert "02 登录与角色入口" in login
    assert "03 独立填报端" in entry
    assert "04 填报流程页" in dynamic
    assert "04 填报流程页" in shift
    assert "打开审阅端" not in entry
    assert "goDesktop" not in entry
    assert "goDesktop" not in dynamic
    assert "goDesktop" not in shift
    assert "desktopNavItem" not in bottom_nav
    assert "后台" not in bottom_nav


def test_reference_review_modules_use_numbered_cn_titles() -> None:
    modules = {
        "frontend/src/views/review/OverviewCenter.vue": ("01", "系统总览主视图"),
        "frontend/src/views/review/ReviewTaskCenter.vue": ("07", "审阅中心"),
        "frontend/src/views/reports/ReportList.vue": ("08", "日报与交付中心"),
        "frontend/src/views/quality/QualityCenter.vue": ("09", "质量与告警中心"),
        "frontend/src/views/review/CostAccountingCenter.vue": ("10", "成本核算与效益中心"),
        "frontend/src/views/assistant/BrainCenter.vue": ("11", "AI 总控中心"),
    }
    for path, (number, title) in modules.items():
        source = _read_repo_file(path)
        assert f'module-number="{number}"' in source
        assert title in source
        assert "ReferencePageFrame" in source


def test_reference_admin_modules_use_numbered_cn_titles() -> None:
    router_source = _read_repo_file("frontend/src/router/index.js")
    assert "const ManageShell = () => import('../layout/ManageShell.vue')" in router_source
    assert "name: 'admin-overview'" in router_source
    assert "component: page('管理控制台', '14')" in router_source
    assert "centerNo: '14'" in router_source

    modules = {
        "frontend/src/views/review/IngestionCenter.vue": ("06", "数据接入与字段映射中心"),
        "frontend/src/views/reports/LiveDashboard.vue": ("12", "系统运维与观测"),
        "frontend/src/views/review/GovernanceCenter.vue": ("13", "权限与治理中心"),
        "frontend/src/views/master/WorkshopTemplateConfig.vue": ("14", "主数据与模板中心"),
    }
    for path, (number, title) in modules.items():
        source = _read_repo_file(path)
        assert f'module-number="{number}"' in source
        assert title in source
        assert "ReferencePageFrame" in source

    assert not (_resolve_repo_root() / "frontend/src/views/review/RoadmapCenter.vue").exists()


def test_review_router_closes_core_centers_for_target_granularity() -> None:
    source = _read_repo_file("frontend/src/router/index.js")

    assert "name: 'review-ingestion-center'" in source
    assert "name: 'review-report-center'" in source
    assert "name: 'review-quality-center'" in source
    assert "name: 'review-reconciliation-center'" in source
    assert "name: 'review-ops-reliability'" in source
    assert "name: 'review-cost-accounting'" in source
    assert "name: 'review-governance-center'" in source
    assert "name: 'review-template-center'" in source
    assert "name: 'admin-ingestion-center'" in source
    assert "name: 'admin-ops-reliability'" in source
    assert "name: 'admin-governance-center'" in source
    assert "name: 'admin-template-center'" in source
    assert "name: 'review-roadmap-center'" not in source
    assert "name: 'admin-roadmap-center'" not in source
    assert "path: 'ai'," in source
    assert "name: 'review-brain-center'" in source
    assert "centerNo: '11'" in source
    assert "path: '/ops/reliability', redirect: '/manage/admin/settings'" in source
    assert "path: '/cost/accounting', redirect: '/manage/cost'" in source
    assert "path: '/roadmap/next', redirect: '/manage/overview'" in source
    assert "path: '/master/workshop-templates'" in source
    assert "redirect: '/manage/admin/templates'" in source


def test_review_layout_exposes_multi_center_navigation_groups() -> None:
    source = _read_repo_file("frontend/src/config/navigation.js")

    assert "label: '总览中心'" in source
    assert "label: '审阅处置'" in source
    assert "label: '经营与智能'" in source
    assert "label: '录入端'" in source
    assert "label: '管理端'" in source
    assert "label: '数据接入'" in source
    assert "label: '权限治理'" in source
    assert "routeName: 'admin-ops-reliability'" in source
    assert "routeName: 'review-cost-accounting'" in source
    assert "routeName: 'admin-governance-center'" in source
    assert "routeName: 'admin-roadmap-center'" not in source
    assert "routeName: 'mobile-entry'" not in re.search(
        r"const reviewNavigation = \[(.*?)\]\n\nconst adminNavigation",
        source,
        re.S,
    ).group(1)


def test_review_overview_surfaces_ai_runtime_summary_cards() -> None:
    source = _read_repo_file("frontend/src/views/review/OverviewCenter.vue")

    assert "AI 今日摘要" in source
    assert "AI 风险摘要" in source
    assert "const aiTodaySummary = computed(() => {" in source
    assert "const aiRiskSummary = computed(() => {" in source


def test_ingestion_center_surfaces_ai_mapping_and_error_cards() -> None:
    source = _read_repo_file("frontend/src/views/review/IngestionCenter.vue")

    assert "AI 字段映射建议" in source
    assert "AI 错误解释" in source
    assert "const mappingSuggestions = computed(() => {" in source
    assert "const errorExplanations = computed(() => {" in source


def test_cost_engine_exposes_backend_table_model_contracts() -> None:
    price_source = _read_repo_file("frontend/src/services/costing/priceResolver.ts")
    engine_source = _read_repo_file("frontend/src/services/costing/engine.ts")
    center_source = _read_repo_file("frontend/src/views/review/CostAccountingCenter.vue")

    assert "export type PriceMasterRow" in price_source
    assert "export const COST_PRICE_MASTER_TABLE = 'cost_price_master'" in price_source
    assert "export const DEFAULT_PRICE_MASTER_ROWS: PriceMasterRow[]" in price_source
    assert "item_code: 'ELECTRICITY'" in price_source
    assert "effective_from: '2026-04-01'" in price_source
    assert "workshop_scope: 'ALL'" in price_source
    assert "source_note: '大推进.md 默认单价'" in price_source

    assert "PRICE_MASTER: COST_PRICE_MASTER_TABLE" in engine_source
    assert "WORKSHOP_STRATEGY: 'cost_workshop_strategy'" in engine_source
    assert "DAILY_RESULT: 'cost_daily_result'" in engine_source
    assert "MONTHLY_ROLLUP: 'cost_monthly_rollup'" in engine_source
    assert "VARIANCE_RECORD: 'cost_variance_record'" in engine_source
    assert "function buildDailyResultRecord" in engine_source
    assert "function buildMonthlyRollupRecord" in engine_source
    assert "function buildVarianceRecords" in engine_source
    assert "tableModels: {" in engine_source

    assert "后端表模型快照" in center_source
    assert "校差记录" in center_source
    assert "const tableSnapshotRows = computed(() =>" in center_source


def test_backend_main_mounts_dingtalk_without_wecom_entry() -> None:
    source = _read_repo_file("backend/app/main.py")

    assert "app.include_router(dingtalk.router, prefix=f'{settings.API_V1_PREFIX}/dingtalk')" in source
    assert "app.include_router(wecom.router" not in source


def test_visual_audit_script_uses_admin_reference_routes() -> None:
    source = _read_repo_file(VISUAL_AUDIT_TOOL)

    assert "route: '/admin/master/templates'" in source
    assert "/master/workshop-templates" not in source
    assert "audit-report.json" in source
    assert "01 system overview visible" in source
    assert "12 ops center visible" in source
    assert "overview quick entries" in source
    assert "REFERENCE_MANIFEST.md" in source
    assert "08-reports-delivery.png" in source
    assert "C:/Users/" not in source
    assert "process.exitCode = 1" in source


def test_factory_dashboard_defaults_to_expanded_detail_on_desktop() -> None:
    source = _read_repo_file("frontend/src/views/dashboard/FactoryDirector.vue")

    assert "function prefersExpandedDetail()" in source
    assert "window.matchMedia('(min-width: 1080px)').matches" in source
    assert "const detailExpanded = ref(prefersExpandedDetail())" in source


def test_workshop_dashboard_opens_all_lane_panels_by_default() -> None:
    source = _read_repo_file("frontend/src/views/dashboard/WorkshopDirector.vue")

    assert "<el-collapse v-model=\"activePanels\">" in source
    assert "const activePanels = ref(['production', 'energy', 'inventory', 'exception'])" in source
    assert "accordion" not in source


def test_auth_store_separates_review_access_from_fill_surface() -> None:
    source = _read_repo_file("frontend/src/stores/auth.js")

    assert "canAccessReviewSurface()" in source
    assert "canAccessFillSurface()" in source
    assert "canAccessDesktopConfig()" in source


def test_mobile_entry_trims_agent_explainer_copy_from_fill_surface() -> None:
    source = _read_repo_file("frontend/src/views/mobile/MobileEntry.vue")

    assert "当前任务" in source
    assert "03 独立填报端" in source
    assert "系统自动归档处理。" not in source
    assert "采集清洗小队" not in source
    assert "分析决策小队" not in source
    assert "审核工作台" not in source


def test_factory_dashboard_mentions_agent_pipeline_and_retention_view() -> None:
    source = _read_repo_file("frontend/src/views/dashboard/FactoryDirector.vue")

    assert "鑫泰铝业 数据中枢" in source
    assert "月累计" in source
    assert "数据留存" in source


def test_factory_dashboard_highlights_two_agent_squads_and_direct_pipeline() -> None:
    source = _read_repo_file("frontend/src/views/dashboard/FactoryDirector.vue")

    assert "今日上报状态" in source
    assert "今日关注" in source
    assert "近 7 日留存趋势" in source
    assert "核心指标" in source
    assert "流程状态" not in source


def test_factory_dashboard_trims_review_home_copy_to_action_language() -> None:
    source = _read_repo_file("frontend/src/views/dashboard/FactoryDirector.vue")

    assert "最近更新：{{ lastRefreshLabel }}" in source
    assert "缺口：{{ formatDeliveryMissingSteps(delivery.missing_steps).join('；') }}" in source
    assert "hint: '主线指标。'" in source
    assert "hint: '先补原始值。'" in source
    assert "hint: '先清异常。'" in source
    assert "hint: '盯住波动。'" in source
    assert "hint: `月累计 ${formatNumber(monthToDateOutput.value)} 吨。`" in source
    assert "岗位直录进入采集清洗小队，分析决策小队自动收口，结果直接领导直达。" not in source
    assert "更新 {{ lastRefreshLabel }}" not in source


def test_review_assistant_dock_uses_short_status_copy() -> None:
    source = _read_repo_file("frontend/src/components/review/ReviewAssistantDock.vue")

    assert "AI 助手" in source
    assert "问、搜、看、推都从这里开。" not in source
    assert "首页先放常用入口，深一步进工作台。" not in source
    assert "title: '已接数据'" in source
    assert "detail: '分析 / 执行 / 出图'" in source
    assert "detail: '首页 / 流程 / 交付'" in source
    assert "detail: '分析决策 + 执行交付'" in source
    assert "title: '已接上下文'" not in source
    assert "detail: '问答 / 搜索 / 图像生成'" not in source
    assert "detail: '审阅首页 / 留存 / 流程追踪'" not in source


def test_factory_dashboard_shortcuts_seed_real_queries_for_assistant() -> None:
    source = _read_repo_file("frontend/src/views/dashboard/FactoryDirector.vue")

    assert ":quick-actions=\"assistantQuickActions\"" in source
    assert "const assistantQuickActions = computed(() => assistantCapabilities.value.quick_actions || buildAssistantFallback().quick_actions)" in source
    assert "const assistantShortcutActions = [" not in source
    assert "assistantShortcutSequence += 1" in source
    assert "assistantShortcutSeed.value = {" in source
    assert "assistantSeedQuery.value = ''" in source
    assert "assistantShortcutSeed.value = null" in source
    assert "const query = action?.query || action?.label || ''" in source
    assert "key: action?.key || `assistant-shortcut-${assistantShortcutSequence}`" in source
    assert "mode: action?.mode || 'answer'" in source
    assert "token: `assistant-shortcut-${assistantShortcutSequence}`" in source


def test_review_layout_and_workbench_share_short_copy_language() -> None:
    layout = _read_repo_file("frontend/src/layout/AppShell.vue")
    workbench = _read_repo_file("frontend/src/components/review/ReviewAssistantWorkbench.vue")

    assert "审阅指挥台" in layout
    assert "鑫泰铝业 数据中枢" in layout
    assert "智能生产数据系统" not in layout
    assert "AI 审阅工作台" in workbench
    assert "问答 · 取数 · 图卡 · 动作" in workbench
    assert "已接生产上下文，可直接用于审阅与交付。" in workbench
    assert "已接数据源" in workbench
    assert "图卡" in workbench
    assert "出说明图" not in workbench
    assert "已挂接上下文" not in workbench


def test_review_assistant_workbench_wires_mock_actions_and_result_panel() -> None:
    source = _read_repo_file("frontend/src/components/review/ReviewAssistantWorkbench.vue")
    api_source = _read_repo_file("frontend/src/api/assistant.js")

    assert "await queryAssistant({" in source
    assert "await generateAssistantImage({" in source
    assert "@click=\"runAssistantQuery('retrieve')\"" in source
    assert "@click=\"runAssistantImage\"" in source
    assert "@click=\"runAssistantQuery('answer')\"" in source
    assert "const assistantActionDefaults = {" in source
    assert "answer: '今天先处理哪个阻塞项最有效？'" in source
    assert "search: '帮我查这卷现在到哪了？'" in source
    assert "retrieve: '当前交付链路还缺什么步骤？'" in source
    assert "automation: '现在适合触发哪条自动化？'" in source
    assert "generate_image: '生成今日产量和异常简报图。'" in source
    assert "search: '搜索结果'" in source
    assert "automation: '动作建议'" in source
    assert "shortcutSeed: {" in source
    assert "const lastHandledShortcutToken = ref('')" in source
    assert "shortcutSeed?.token" in source
    assert "shortcutSeed.mode === 'generate_image'" in source
    assert "runAssistantQuery(shortcutSeed.mode || 'answer')" in source
    assert "if (normalized === 'analysis' || normalized === 'execution')" in source
    assert "ready = capabilities.has('query')" in source
    assert "surface: 'review_home'" in source
    assert "image_type: 'daily_briefing_card'" in source
    assert "<span>结果</span>" in source
    assert "暂无结果" in source
    assert "quick_actions: [" in api_source
    assert "key: 'priority-blocker'" in api_source
    assert "mode: 'answer'" in api_source
    assert "query: '今天先处理哪个阻塞项最有效？'" in api_source
    assert "key: 'delivery-readiness'" in api_source
    assert "mode: 'retrieve'" in api_source
    assert "query: '当前交付链路还缺什么步骤？'" in api_source
    assert "detail: '分析 / 执行 / 出图'" in api_source
    assert "title: '已接数据'" in api_source
    assert "detail: '首页 / 流程 / 交付'" in api_source
    assert "detail: '分析决策 + 执行交付'" in api_source
    assert "title: '已接上下文'" not in api_source
    assert "detail: '审阅首页 / 留存 / 流程追踪'" not in api_source
    assert "detail: '预留催报 / 推送 / 摘要'" not in api_source


def test_factory_dashboard_exposes_inventory_owner_metrics() -> None:
    source = _read_repo_file("frontend/src/views/dashboard/FactoryDirector.vue")

    assert "今日发货" in source
    assert "入库面积" in source
    assert "item.shipment_weight" in source
    assert "item.storage_inbound_area" in source


def test_factory_dashboard_maps_auto_confirmed_and_returned_statuses() -> None:
    source = _read_repo_file("frontend/src/views/dashboard/FactoryDirector.vue")

    assert "auto_confirmed: '已入汇总'" in source
    assert "returned: '退回补录'" in source
    assert "auto_confirmed: 'success'" in source
    assert "returned: 'danger'" in source


def test_machine_qr_urls_use_login_machine_entrypoint() -> None:
    equipment = _read_repo_file("frontend/src/views/master/Equipment.vue")
    wizard = _read_repo_file("frontend/src/views/master/MachineWizard.vue")

    assert "/login?machine=" in equipment
    assert "/login?machine=" in wizard
    assert "/mobile?machine=" not in equipment
    assert "/mobile?machine=" not in wizard


def test_login_review_surface_uses_manage_canonical_landing() -> None:
    login = _read_repo_file("frontend/src/views/Login.vue")
    command_login = _read_repo_file("frontend/src/reference-command/pages/CommandLogin.vue")

    assert "return '/manage/overview'" in login
    assert "return '/manage/overview'" in command_login
    assert "return '/review/overview'" not in login
    assert "return '/review/overview'" not in command_login


def test_review_dashboards_parse_structured_load_errors() -> None:
    factory_source = _read_repo_file("frontend/src/views/dashboard/FactoryDirector.vue")
    workshop_source = _read_repo_file("frontend/src/views/dashboard/WorkshopDirector.vue")

    assert "function requestErrorMessage(error, fallback = '数据加载失败，请稍后重试')" in factory_source
    assert "detail.message || detail.msg || fallback" in factory_source
    assert "const lastLoadErrorMessage = ref('')" in factory_source
    assert "lastLoadErrorMessage.value = ''" in factory_source
    assert "if (message !== lastLoadErrorMessage.value)" in factory_source
    assert "ElMessage.error(message)" in factory_source
    assert "function requestErrorMessage(error, fallback = '加载失败')" in workshop_source
    assert "detail.message || detail.msg || fallback" in workshop_source
    assert "const lastLoadErrorMessage = ref('')" in workshop_source
    assert "lastLoadErrorMessage.value = ''" in workshop_source
    assert "if (message !== lastLoadErrorMessage.value)" in workshop_source
    assert "ElMessage.error(message)" in workshop_source


def test_factory_dashboard_trims_reporting_status_hints_to_dashboard_language() -> None:
    source = _read_repo_file("frontend/src/views/dashboard/FactoryDirector.vue")

    assert "submitted: '主操已报'" in source
    assert "reviewed: '系统处理中'" in source
    assert "auto_confirmed: '已入汇总'" in source
    assert "returned: '退回补录'" in source
    assert "draft: '填报中'" in source
    assert "unreported: '待上报'" in source
    assert "late: '迟报'" in source
    assert "return map[status] || '同步中'" in source
    assert "主操已提交，等待系统自动收口" not in source
    assert "系统已接住本班数据，正在进入汇总" not in source


def test_workshop_dashboard_exposes_owner_metrics_and_energy_water() -> None:
    source = _read_repo_file("frontend/src/views/dashboard/WorkshopDirector.vue")

    assert "今日发货" in source
    assert "入库面积" in source
    assert "实际库存" in source
    assert "用水" in source
    assert "row.storage_inbound_area" in source
    assert "row.actual_inventory_weight" in source
    assert 'prop="water_value"' in source


def test_workshop_dashboard_surfaces_direct_entry_runtime_panel() -> None:
    source = _read_repo_file("frontend/src/views/dashboard/WorkshopDirector.vue")

    assert "数据流转" in source
    assert "先看来源，再看结果" in source
    assert "今日数据流转" in source
    assert "先跟进未闭环项" in source


def test_review_dashboards_use_runtime_trace_component() -> None:
    factory = _read_repo_file("frontend/src/views/dashboard/FactoryDirector.vue")
    workshop = _read_repo_file("frontend/src/views/dashboard/WorkshopDirector.vue")

    assert "AgentRuntimeFlow" in factory
    assert "AgentRuntimeFlow" in workshop
    assert "title=\"\"" in factory
    assert "先看来源，再看结果" in workshop


def test_readme_describes_phase1_manual_first_scope() -> None:
    readme = _read_repo_file("README.md")

    assert "先由主操手工录入" in readme
    assert "扫码补数" in readme
    assert "MES 接口保留为后续阶段能力" in readme


def test_readme_lists_github_and_cloud_packaging_prereqs() -> None:
    readme = _read_repo_file("README.md")

    assert "GitHub / 上云前封装准备" in readme
    assert ".env.example" in readme
    assert ".github/workflows/ci.yml" in readme
    assert "初始化或接回 Git 仓库" in readme
    assert "生产 `.env`" in readme


def test_pilot_checklist_does_not_require_mes_for_phase1_go_live() -> None:
    checklist = _read_repo_file("docs/pilot-readiness-checklist.md")

    assert "Phase 1 不以 MES 联调为上线前提" in checklist
    assert "主操手工直录可独立跑通" in checklist
