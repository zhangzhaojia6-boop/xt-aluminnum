from __future__ import annotations

from datetime import date

from app.schemas.command import CommandModuleOut, CommandSurface, CommandSurfaceResponseOut


def _module(
    *,
    module_id: str,
    title: str,
    surface: CommandSurface,
    kpis: list[dict] | None = None,
    status_summary: list[str] | None = None,
    primary_rows: list[dict] | None = None,
    trend_series: list[dict] | None = None,
    actions: list[dict] | None = None,
    updated_at: date | str | None = None,
) -> CommandModuleOut:
    updated_at_value = updated_at.isoformat() if isinstance(updated_at, date) else updated_at
    return CommandModuleOut(
        module_id=module_id,
        title=title,
        surface=surface,
        kpis=kpis or [],
        status_summary=status_summary or [],
        primary_rows=primary_rows or [],
        trend_series=trend_series or [],
        actions=actions or [],
        updated_at=updated_at_value or date.today().isoformat(),
    )


def build_command_surface(*, surface: CommandSurface, target_date: date | None = None) -> CommandSurfaceResponseOut:
    builders = {
        'entry': _build_entry_modules,
        'review': _build_review_modules,
        'admin': _build_admin_modules,
    }
    return CommandSurfaceResponseOut(
        surface=surface,
        modules=builders[surface](target_date=target_date or date.today()),
    )


def build_admin_module_overview(*, module_id: str, target_date: date | None = None) -> CommandModuleOut:
    for module in _build_admin_modules(target_date=target_date or date.today()):
        if module.module_id == module_id:
            return module
    raise ValueError(f'Unknown admin module: {module_id}')


def _build_entry_modules(*, target_date: date) -> list[CommandModuleOut]:
    return [
        _module(
            module_id='03',
            title='独立填报端首页',
            surface='entry',
            kpis=[
                {'label': '待填任务', 'value': '12', 'unit': '项', 'trend': '今日', 'status': 'warning', 'icon_key': 'task'},
                {'label': '已提交', 'value': '18', 'unit': '项', 'trend': '已同步', 'status': 'success', 'icon_key': 'submitted'},
                {'label': '异常待补', 'value': '3', 'unit': '项', 'trend': '需处理', 'status': 'danger', 'icon_key': 'alert'},
            ],
            status_summary=[f'{target_date.isoformat()} 录入端只保留现场填报、历史与草稿。'],
            actions=[
                {'label': '今日任务', 'route_name': 'mobile-entry', 'access': 'fill_surface'},
                {'label': '草稿', 'route_name': 'entry-drafts', 'access': 'fill_surface'},
            ],
        ),
        _module(
            module_id='04',
            title='填报流程页',
            surface='entry',
            primary_rows=[
                {'step': '随行卡', 'status': '已接入'},
                {'step': '本卷', 'status': '已接入'},
                {'step': '提交', 'status': '已接入'},
            ],
        ),
        _module(
            module_id='15',
            title='响应式录入体验',
            surface='entry',
            status_summary=['移动端预览模块取消，真实录入端页面作为响应式验收对象。'],
        ),
    ]


def _build_review_modules(*, target_date: date) -> list[CommandModuleOut]:
    return [
        _module(
            module_id='01',
            title='系统总览主视图',
            surface='review',
            kpis=[
                {'label': '今日产量', 'value': '5824', 'unit': '吨', 'trend': '+8.6%', 'status': 'success', 'icon_key': 'output'},
                {'label': '订单达成率', 'value': '96.7', 'unit': '%', 'trend': '+2.1%', 'status': 'success', 'icon_key': 'order'},
                {'label': '综合成品率', 'value': '98.2', 'unit': '%', 'trend': '+1.3%', 'status': 'success', 'icon_key': 'yield'},
            ],
            trend_series=[
                {'label': '00:00', 'value': 680},
                {'label': '08:00', 'value': 1320},
                {'label': '16:00', 'value': 2180},
            ],
            actions=[
                {'label': '系统总览', 'route_name': 'review-overview-home', 'access': 'review_surface'},
                {'label': '审阅中心', 'route_name': 'review-task-center', 'access': 'review_surface'},
            ],
        ),
        _module(module_id='05', title='工厂作业看板', surface='review', actions=[{'label': '厂级看板', 'route_name': 'factory-dashboard', 'access': 'review_surface'}]),
        _module(module_id='07', title='审阅中心', surface='review', status_summary=['待审、已审、已驳回三类任务分离。']),
        _module(module_id='08', title='日报与交付中心', surface='review', status_summary=[f'{target_date.isoformat()} 日报交付状态可追踪。']),
        _module(module_id='09', title='质量与告警中心', surface='review', status_summary=['质量告警与差异核对保持联动。']),
        _module(module_id='10', title='成本核算与效益中心', surface='review', status_summary=['按策略引擎输出吨耗与校差记录。']),
        _module(module_id='11', title='AI 总控中心', surface='review', status_summary=['AI 建议为辅助建议，必须展示 mock/live 来源。']),
    ]


def _build_admin_modules(*, target_date: date) -> list[CommandModuleOut]:
    return [
        _module(module_id='06', title='数据接入与字段映射中心', surface='admin', status_summary=['导入、映射、错误解释统一管理。']),
        _module(module_id='12', title='系统运维与观测', surface='admin', status_summary=[f'{target_date.isoformat()} 探针与实时运营合并展示。']),
        _module(module_id='13', title='权限与治理中心', surface='admin', status_summary=['角色矩阵、数据范围和账号分布统一治理。']),
        _module(module_id='14', title='主数据与模板中心', surface='admin', status_summary=['字段模板、车间主数据、录入口径统一维护。']),
    ]
