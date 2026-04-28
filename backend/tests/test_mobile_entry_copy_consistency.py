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


def test_readme_promotes_wecom_mobile_entry() -> None:
    readme = _read_repo_file("README.md")

    assert "企业微信" in readme
    assert "手机填报唯一入口" in readme or "单入口优先" in readme
    assert "钉钉工作台 H5 入口优先" not in readme


def test_copy_consistency_reader_resolves_repo_root_without_env_override() -> None:
    repo_root = _resolve_repo_root()

    assert (repo_root / "README.md").exists()
    assert (repo_root / "frontend" / "src").exists()


def test_mobile_entry_copy_uses_single_wecom_priority() -> None:
    source = _read_repo_file("frontend/src/views/mobile/MobileEntry.vue")

    assert "企业微信" in source or "WeCom" in source
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
        r"path: '/mobile/report/:businessDate/:shiftId'.*?name: 'mobile-report-form'.*?component: ShiftReportForm",
        source,
        re.S,
    )
    assert re.search(
        r"path: '/mobile/report-advanced/:businessDate/:shiftId'.*?component: DynamicEntryForm",
        source,
        re.S,
    )


def test_mobile_entry_mentions_manual_leader_entry_phase_notice() -> None:
    source = _read_repo_file("frontend/src/views/mobile/MobileEntry.vue")

    assert "当前阶段先由主操手工录入" in source
    assert "bootstrap.phase_notice" in source
    assert "录入方式" in source
    assert "主操手工直录" in source
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

    assert "当前阶段先由主操手工录入原始值，系统自动校验、汇总和催报" in source
    assert "catch (error)" in source
    assert "加载班次填报失败，请返回入口后重试。" in source


def test_dynamic_entry_form_switches_special_owners_to_owner_only_mode() -> None:
    source = _read_repo_file("frontend/src/views/mobile/DynamicEntryForm.vue")

    assert "const ownerOnlyRoleBuckets = ['contracts', 'inventory_keeper', 'utility_manager']" in source
    assert "const isOwnerOnlyMode = computed(() => ownerOnlyRoleBuckets.includes(transitionMapping.value.role_bucket))" in source
    assert "当前岗位按班次补录，不需要随行卡。系统会自动按日期、班次和岗位归档。" in source
    assert "if (!isOwnerOnlyMode.value && !normalized)" in source
    assert "OWNER-" in source


def test_dynamic_entry_form_hides_work_order_scaffold_for_owner_only_mode() -> None:
    source = _read_repo_file("frontend/src/views/mobile/DynamicEntryForm.vue")

    assert "v-if=\"template && !isOwnerOnlyMode\"" in source
    assert "isOwnerOnlyMode ? '岗位补录' : '按随行卡填报'" in source
    assert "isOwnerOnlyMode.value ? 'core' : 'work_order'" in source


def test_dynamic_entry_form_owner_only_mode_skips_tracking_card_and_machine_summary() -> None:
    source = _read_repo_file("frontend/src/views/mobile/DynamicEntryForm.vue")

    assert "label: isOwnerOnlyMode.value ? '岗位归档' : '随行卡号'" in source
    assert "label: isOwnerOnlyMode.value ? '岗位' : (isMachineBound.value ? '机台' : '班组')" in source
    assert "if (equipmentOptions.value.length && !formState.machine_id && !isOwnerOnlyMode.value)" in source
    assert "if (isFastTempo.value && !isOwnerOnlyMode.value)" in source
    assert "currentStepKey.value = isOwnerOnlyMode.value ? 'core' : 'work_order'" in source


def test_mobile_transition_copy_matches_special_owner_scope() -> None:
    source = _read_repo_file("frontend/src/utils/mobileTransition.js")

    assert "title: '计划科补录'" in source
    assert "只补录合同进度、余合同和投料口径。" in source
    assert "title: '成品库补录'" in source
    assert "只补录入库、发货、寄存和库存结存。" in source
    assert "title: '水电气补录'" in source
    assert "只补录全厂水、电、气原始值。" in source


def test_phase1_desktop_landing_skips_statistics_and_review_defaults() -> None:
    source = _read_repo_file("frontend/src/router/index.js")

    assert "if (authStore.canAccessStatisticsDashboard) return { name: 'statistics-dashboard' }" not in source
    assert "if (authStore.canAccessReviewDesk) return { name: 'shift-center' }" not in source
    assert "if (authStore.isAdmin || authStore.isManager) return { name: 'master-workshop' }" in source


def test_phase1_layout_hides_review_and_statistics_navigation() -> None:
    source = _read_repo_file("frontend/src/views/Layout.vue")

    assert "统计观察看板" not in source
    assert "班次观察台" not in source
    assert "差异处置" not in source
    assert "智能生产数据系统" in source


def test_layout_trims_admin_navigation_to_phase1_minimum_controls() -> None:
    source = _read_repo_file("frontend/src/views/Layout.vue")

    assert "员工管理" not in source
    assert "班组管理" not in source
    assert "别名映射" not in source
    assert "成品率口径收敛图" not in source
    assert "机台管理" in source
    assert "班次配置" in source
    assert "车间模板" in source


def test_layout_surfaces_phase1_agent_shell_badges() -> None:
    source = _read_repo_file("frontend/src/views/Layout.vue")

    assert "Phase 1" in source
    assert "企业微信主入口" in source
    assert "智能体自动汇总" in source
    assert "直录优先" in source
    assert "自动校验" in source
    assert "自动汇总" in source


def test_mobile_entry_highlights_agent_squads_without_old_review_language() -> None:
    source = _read_repo_file("frontend/src/views/mobile/MobileEntry.vue")

    assert "采集清洗小队" in source
    assert "分析决策小队" in source
    assert "岗位直录" in source
    assert "审核工作台" not in source


def test_factory_dashboard_uses_compact_white_card_surface() -> None:
    source = _read_repo_file("frontend/src/views/dashboard/FactoryDirector.vue")

    assert "工厂作业看板" in source
    assert "月累计" in source
    assert "background: #ffffff" in source
    assert "border: 1px solid #e5e7eb" in source


def test_factory_dashboard_removes_redundant_agent_copy() -> None:
    source = _read_repo_file("frontend/src/views/dashboard/FactoryDirector.vue")

    assert "智能体联动" not in source
    assert "采集清洗小队" not in source
    assert "分析决策小队" not in source
    assert "领导直达" not in source
    assert "交付与闭环" not in source


def test_factory_dashboard_exposes_inventory_owner_metrics() -> None:
    source = _read_repo_file("frontend/src/views/dashboard/FactoryDirector.vue")

    assert "今日发货" in source
    assert "入库面积" in source
    assert "item.shipment_weight" in source
    assert "item.storage_inbound_area" in source


def test_factory_dashboard_maps_auto_confirmed_and_returned_statuses() -> None:
    source = _read_repo_file("frontend/src/views/dashboard/FactoryDirector.vue")

    assert "auto_confirmed: '自动确认'" in source
    assert "returned: '已退回'" in source
    assert "auto_confirmed: 'success'" in source
    assert "returned: 'danger'" in source


def test_workshop_dashboard_exposes_owner_metrics_and_energy_water() -> None:
    source = _read_repo_file("frontend/src/views/dashboard/WorkshopDirector.vue")

    assert "今日发货" in source
    assert "入库面积" in source
    assert "实际库存" in source
    assert "用水" in source
    assert "row.storage_inbound_area" in source
    assert "row.actual_inventory_weight" in source
    assert "row.water_value" in source


def test_workshop_dashboard_surfaces_direct_entry_runtime_panel() -> None:
    source = _read_repo_file("frontend/src/views/dashboard/WorkshopDirector.vue")

    assert "本车间运行层" in source
    assert "不再等统计汇总" in source
    assert "本车间直录" in source
    assert "专项 owner 补录" in source
    assert "自动催报" in source


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
