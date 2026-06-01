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


def test_readme_promotes_dingtalk_mobile_entry() -> None:
    readme = _read_repo_file("README.md")

    assert "钉钉" in readme
    assert "手机填报唯一入口" in readme or "单入口优先" in readme
    assert "企业微信单入口优先" not in readme


def test_mobile_entry_copy_uses_single_dingtalk_priority() -> None:
    source = _read_repo_file("frontend/src/views/mobile/MobileEntry.vue")

    assert "钉钉" in source
    assert "企业微信" not in source
    assert 'data-testid="mobile-go-report"' in source
    assert 'data-testid="mobile-go-ocr"' not in source


def test_mobile_entry_routes_to_current_fill_surfaces() -> None:
    source = _read_repo_file("frontend/src/router/index.js")

    assert "const ShiftReportForm = () => import('../views/mobile/ShiftReportForm.vue')" in source
    assert "const UnifiedEntryForm = () => import('../views/mobile/UnifiedEntryForm.vue')" in source
    assert "const CoilEntryWorkbench = () => import('../views/mobile/CoilEntryWorkbench.vue')" in source
    assert "const ShiftReportHistory = () => import('../views/mobile/ShiftReportHistory.vue')" in source

    for route in [
        "path: 'fill', name: 'mobile-unified-entry', component: UnifiedEntryForm",
        "path: 'report/:businessDate/:shiftId', name: 'mobile-report-form', component: ShiftReportForm",
        "path: 'advanced/:businessDate/:shiftId', name: 'mobile-report-form-advanced', redirect: { name: 'mobile-unified-entry' }",
        "path: 'coil/:businessDate/:shiftId', name: 'mobile-coil-entry', component: CoilEntryWorkbench",
        "path: 'history', name: 'mobile-report-history', component: ShiftReportHistory",
    ]:
        assert route in source

    assert "DynamicEntryForm" not in source


def test_mobile_legacy_deep_links_preserve_query_hash_and_params() -> None:
    source = _read_repo_file("frontend/src/router/index.js")

    expected_routes = [
        "{ path: '/mobile/report/:businessDate/:shiftId', redirect: (to) => ({ path: `/entry/report/${to.params.businessDate}/${to.params.shiftId}`, query: to.query, hash: to.hash }) }",
        "{ path: '/mobile/report-advanced/:businessDate/:shiftId', redirect: (to) => ({ path: `/entry/advanced/${to.params.businessDate}/${to.params.shiftId}`, query: to.query, hash: to.hash }) }",
        "{ path: '/mobile/history', redirect: (to) => ({ path: '/entry/history', query: to.query, hash: to.hash }) }",
        "{ path: '/worker', redirect: (to) => ({ name: 'mobile-entry', query: to.query, hash: to.hash }) }",
    ]
    for route in expected_routes:
        assert route in source


def test_unified_entry_form_keeps_endpoint_specific_payloads() -> None:
    source = _read_repo_file("frontend/src/views/mobile/UnifiedEntryForm.vue")

    assert "function buildCoilEntryPayload" in source
    assert "function buildMobileReportPayload" in source
    assert "data: { ...form }" not in source
    assert "await createCoilEntry(buildCoilEntryPayload(sc), { skipErrorToast: true })" in source
    assert "const payload = buildMobileReportPayload(sc)" in source
    assert "await submitMobileReport(payload)" in source


def test_mobile_error_parsers_handle_object_detail_payloads() -> None:
    for relative_path in [
        "frontend/src/views/mobile/MobileEntry.vue",
        "frontend/src/views/mobile/OCRCapture.vue",
        "frontend/src/views/mobile/AttendanceConfirm.vue",
        "frontend/src/views/mobile/ShiftReportHistory.vue",
        "frontend/src/utils/reportStatus.js",
    ]:
        source = _read_repo_file(relative_path)
        assert "detail.message || detail.msg || fallback" in source


def test_shift_report_form_uses_current_task_and_safe_submit_copy() -> None:
    source = _read_repo_file("frontend/src/views/mobile/ShiftReportForm.vue")

    assert "当前任务" in source
    assert "提交确认" in source
    assert "正式提交" in source
    assert "requestErrorMessage" in source
    assert "goDesktop" not in source


def test_history_page_reads_all_day_records_not_only_current_shift() -> None:
    source = _read_repo_file("frontend/src/views/mobile/ShiftReportHistory.vue")

    assert "fetchMobileHistory" in source
    assert "business_date" in source
    assert "shift_id" in source
    assert "roleBucket" in source
    assert "currentUserRoleBucket" in source


def test_mobile_photo_upload_lets_browser_set_multipart_boundary() -> None:
    source = _read_repo_file("frontend/src/api/mobile.js")

    upload_section = source.split("export async function uploadMobileReportPhoto", 1)[1]
    upload_section = upload_section.split("export async function fetchMobileHistory", 1)[0]

    assert "'Content-Type': 'multipart/form-data'" not in upload_section
    assert 'headers: { "Content-Type": "multipart/form-data" }' not in upload_section


def test_entry_shell_keeps_operator_navigation_small_and_current() -> None:
    source = _read_repo_file("frontend/src/layout/EntryShell.vue")

    for token in [
        "path: '/entry'",
        "path: '/entry/fill'",
        "path: '/entry/history'",
        "path: '/entry/drafts'",
        "label: '首页'",
        "label: '录入'",
        "label: '历史'",
        "label: '草稿'",
    ]:
        assert token in source
    assert "team-lead" not in source
