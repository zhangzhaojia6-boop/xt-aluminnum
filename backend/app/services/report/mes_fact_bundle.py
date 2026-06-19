from __future__ import annotations

from datetime import date
from typing import Any

from sqlalchemy.exc import OperationalError, ProgrammingError
from sqlalchemy.orm import Session

from app.models.mes import MesMaterialRecord
from app.core.business_time import production_business_window
from app.services import mes_extended_service, mes_sync_service
from app.services.report import mes_factory_production_fact, mes_workshop_machine_reconciliation


STATUS_VERIFIED = '已证实'
STATUS_CANDIDATE = '候选'
STATUS_NEEDS_CHECK = '待浏览器/SQL复核'
STATUS_UNAVAILABLE = '不可用'
READ_MODEL_MODE = 'sqlserver_adapter_to_local_mes_projection'


def _round2(value: Any) -> float | None:
    if value is None or value == '':
        return None
    try:
        return round(float(value), 2)
    except (TypeError, ValueError):
        return None


def _iso(value: Any) -> str | None:
    if value is None:
        return None
    return value.isoformat() if hasattr(value, 'isoformat') else str(value)


def _source(
    *,
    page: str,
    path: str | None,
    table: str | None,
    fields: list[str],
    projection_table: str | None,
    status: str,
    note: str | None = None,
) -> dict[str, Any]:
    return {
        'source_system': 'MES SQL Server',
        'source_page': page,
        'source_path': path,
        'source_table': table,
        'source_fields': fields,
        'projection_table': projection_table,
        'status': status,
        'note': note,
    }


def _fact(
    *,
    key: str,
    label: str,
    value: Any,
    unit: str | None,
    grain: str,
    business_date: date,
    source: dict[str, Any],
    api: str,
    frontend_pages: list[str],
    hermes_field: str,
    dimensions: dict[str, Any] | None = None,
    difference_categories: list[str] | None = None,
    updated_at: Any = None,
    sync_status: dict[str, Any] | None = None,
    missing_reason: str | None = None,
    difference_status: str = 'not_compared',
    difference_note: str | None = None,
) -> dict[str, Any]:
    categories = difference_categories or ['单位', '业务日', '车间别名', '数据源', '算法口径']
    return {
        'key': key,
        'label': label,
        'metric_name': label,
        'value': _round2(value),
        'unit': unit,
        'status': source.get('status'),
        'grain': grain,
        'business_date': business_date.isoformat(),
        'dimensions': dimensions or {},
        'updated_at': _iso(updated_at),
        'sync_status': sync_status or {},
        'missing_reason': missing_reason,
        'source': source,
        'api': api,
        'frontend_pages': frontend_pages,
        'hermes_field': hermes_field,
        'difference_status': difference_status,
        'difference_categories': categories,
        'difference_note': difference_note or f"如与 MES 页面不一致，按{', '.join(categories)}分类排查；不改写 MES 原库。",
    }


def _safe_factory_production_fact(db: Session, *, target_date: date) -> dict[str, Any]:
    try:
        return mes_factory_production_fact.build_factory_production_fact(db, target_date=target_date)
    except (OperationalError, ProgrammingError):
        return {
            'status': 'unavailable',
            'target_date': target_date.isoformat(),
            'missing_reason': 'factory_production_projection_unavailable',
        }


def _safe_workshop_machine_reconciliation(db: Session, *, target_date: date) -> dict[str, Any]:
    try:
        return mes_workshop_machine_reconciliation.build_mes_workshop_machine_reconciliation(
            db,
            target_date=target_date,
        )
    except (OperationalError, ProgrammingError):
        return {'status': 'unavailable', 'target_date': target_date.isoformat(), 'workshops': [], 'totals': {}}


def _safe_latest_sync_status(db: Session) -> dict[str, Any]:
    try:
        return mes_sync_service.latest_sync_status(db)
    except (OperationalError, ProgrammingError):
        return {
            'configured': True,
            'migration_ready': False,
            'status': 'unavailable',
            'source': 'mes_projection',
            'action_required': 'check_projection_tables',
        }


def _latest_fact_timestamp(*values: Any) -> Any:
    candidates = [value for value in values if value not in (None, '')]
    if not candidates:
        return None
    return max(candidates, key=lambda value: _iso(value) or '')


def _fact_sync_status(sync_status: dict[str, Any]) -> dict[str, Any]:
    return {
        'status': sync_status.get('status'),
        'source': sync_status.get('source'),
        'last_synced_at': sync_status.get('last_synced_at'),
        'last_event_at': sync_status.get('last_event_at'),
        'lag_seconds': sync_status.get('lag_seconds'),
    }


def _factory_facts(factory: dict[str, Any], *, target_date: date, sync_status: dict[str, Any]) -> list[dict[str, Any]]:
    feeding_updated_at = (factory.get('feeding_fact') or {}).get('last_seen_from_mes_at')
    packaging_updated_at = (factory.get('packaging_fact') or {}).get('last_seen_from_mes_at')
    inbound_updated_at = (factory.get('finished_inbound_fact') or {}).get('last_seen_from_mes_at')
    fact_sync_status = _fact_sync_status(sync_status)
    projection_unavailable = factory.get('status') == 'unavailable'
    source_status = STATUS_UNAVAILABLE if projection_unavailable else STATUS_VERIFIED
    missing_reason = factory.get('missing_reason') if projection_unavailable else None
    difference_status = 'source_unavailable' if projection_unavailable else 'not_compared'
    return [
        _fact(
            key='factory_feeding_daily_input',
            label='全厂投料量',
            value=factory.get('factory_feeding_daily_input'),
            unit='吨',
            grain='全厂/日',
            business_date=target_date,
            source=_source(
                page='计划管理 / 投料管理；计划管理 / 随行卡管理',
                path='/Feeding/Index；/FollowCard/Index',
                table='MES_Product',
                fields=['FeedingWeight', 'CreateDate', 'CurrentWorkShop'],
                projection_table='mes_coil_snapshots',
                status=source_status,
                note='随行卡管理汇总区仍需真实页面复核，但当前投料事实与投料管理共用 MES_Product.FeedingWeight。',
            ),
            api='/api/v1/dashboard/mes-factory-production-reconciliation',
            frontend_pages=['/manage/live', '/manage/today', '/manage/workshop-dashboard'],
            hermes_field='factory_feeding_daily_input',
            difference_categories=['单位', '业务日', '车间别名'],
            updated_at=feeding_updated_at,
            sync_status=fact_sync_status,
            missing_reason=missing_reason,
            difference_status=difference_status,
        ),
        _fact(
            key='factory_packaging_daily_output',
            label='全厂包装量',
            value=factory.get('factory_packaging_daily_output'),
            unit='吨',
            grain='全厂/日',
            business_date=target_date,
            source=_source(
                page='包装管理 / 包装录入',
                path='/Pack/Index',
                table='MES_ProductProcessRecord',
                fields=['Process=包装', 'EndWeight', 'EndDatetime'],
                projection_table='mes_workshop_process_records',
                status=source_status,
            ),
            api='/api/v1/dashboard/mes-factory-production-reconciliation',
            frontend_pages=['/manage/live', '/manage/today', '/manage/workshop-dashboard'],
            hermes_field='factory_packaging_daily_output',
            updated_at=packaging_updated_at,
            sync_status=fact_sync_status,
            missing_reason=missing_reason,
            difference_status=difference_status,
        ),
        _fact(
            key='factory_finished_inbound_daily_output',
            label='成品入库量',
            value=factory.get('factory_finished_inbound_daily_output'),
            unit='吨',
            grain='全厂/日',
            business_date=target_date,
            source=_source(
                page='成品库 / 入库',
                path='/Stock/Index',
                table='WMS_InStock / WMS_InStockDetail',
                fields=['TotalNetWeight', 'NetWeight', 'InStockDate', 'CreateDate'],
                projection_table='mes_stock_records',
                status=source_status,
            ),
            api='/api/v1/dashboard/mes-factory-production-reconciliation',
            frontend_pages=['/manage/live', '/manage/today', '/manage/workshop-dashboard'],
            hermes_field='factory_finished_inbound_daily_output',
            updated_at=inbound_updated_at,
            sync_status=fact_sync_status,
            missing_reason=missing_reason,
            difference_status=difference_status,
        ),
        _fact(
            key='daily_yield_rate',
            label='全厂成品率',
            value=factory.get('daily_yield_rate'),
            unit='%',
            grain='全厂/日',
            business_date=target_date,
            source=_source(
                page='数据中枢事实口径',
                path=None,
                table='MES_Product + WMS_InStock / WMS_InStockDetail',
                fields=['factory_finished_inbound_daily_output / factory_feeding_daily_input * 100'],
                projection_table='mes_coil_snapshots + mes_stock_records',
                status=source_status,
                note='分母为 0 时返回 null，不显示为 0。',
            ),
            api='/api/v1/dashboard/mes-factory-production-reconciliation',
            frontend_pages=['/manage/live', '/manage/today', '/manage/workshop-dashboard'],
            hermes_field='daily_yield_rate',
            difference_categories=['分母', '业务日', '数据源', '算法口径'],
            updated_at=_latest_fact_timestamp(feeding_updated_at, packaging_updated_at, inbound_updated_at),
            sync_status=fact_sync_status,
            missing_reason=missing_reason,
            difference_status=difference_status,
        ),
    ]


def _workshop_machine_facts(
    reconciliation: dict[str, Any], *, target_date: date, sync_status: dict[str, Any]
) -> list[dict[str, Any]]:
    payload: list[dict[str, Any]] = []
    fact_sync_status = _fact_sync_status(sync_status)
    for workshop in reconciliation.get('workshops') or []:
        workshop_name = str(workshop.get('workshop_name') or '')
        dimensions = {'workshop': workshop_name, 'workshop_id': workshop.get('workshop_id')}
        payload.append(
            _fact(
                key='workshop_feeding_input',
                label='车间投料量',
                value=workshop.get('workshop_feeding_input'),
                unit='吨',
                grain='车间/日',
                business_date=target_date,
                dimensions=dimensions,
                source=_source(
                    page='车间生产管理 / 车间报表',
                    path='/Report/ProductionWorkshopReport',
                    table='MES_ProductProcessRecord',
                    fields=['WorkShop', 'DeviceName', 'BeginWeight', 'EndDatetime'],
                    projection_table='mes_workshop_process_records',
                    status=STATUS_VERIFIED,
                ),
                api='/api/v1/dashboard/mes-workshop-machine-reconciliation',
                frontend_pages=['/manage/workshop-dashboard', '/manage/live'],
                hermes_field='workshop_feeding_input',
                sync_status=fact_sync_status,
            )
        )
        payload.append(
            _fact(
                key='workshop_down_machine_output',
                label='车间下机量',
                value=workshop.get('workshop_down_machine_output'),
                unit='吨',
                grain='车间/日',
                business_date=target_date,
                dimensions=dimensions,
                source=_source(
                    page='车间生产管理 / 车间报表',
                    path='/Report/ProductionWorkshopReport',
                    table='MES_ProductProcessRecord',
                    fields=['WorkShop', 'DeviceName', 'EndWeight', 'EndDatetime'],
                    projection_table='mes_workshop_process_records',
                    status=STATUS_VERIFIED,
                ),
                api='/api/v1/dashboard/mes-workshop-machine-reconciliation',
                frontend_pages=['/manage/workshop-dashboard', '/manage/live'],
                hermes_field='workshop_down_machine_output',
                sync_status=fact_sync_status,
            )
        )
        for machine in workshop.get('machines') or []:
            machine_dimensions = {
                **dimensions,
                'machine': machine.get('machine_name'),
                'machine_id': machine.get('machine_id'),
                'machine_binding_status': machine.get('machine_binding_status'),
            }
            payload.append(
                _fact(
                    key='machine_input_weight',
                    label='机台上机量',
                    value=machine.get('machine_input_weight'),
                    unit='吨',
                    grain='机台/日',
                    business_date=target_date,
                    dimensions=machine_dimensions,
                    source=_source(
                        page='车间生产管理 / 车间报表',
                        path='/Report/ProductionWorkshopReport',
                        table='MES_ProductProcessRecord',
                        fields=['DeviceName', 'BeginWeight', 'EndDatetime'],
                        projection_table='mes_workshop_process_records',
                        status=STATUS_VERIFIED,
                        note='本地未绑定机台保留为 MES未匹配机台，不猜归属。',
                    ),
                    api='/api/v1/dashboard/mes-workshop-machine-reconciliation',
                    frontend_pages=['/manage/workshop-dashboard', '/manage/live'],
                    hermes_field='machine_input_weight',
                    sync_status=fact_sync_status,
                )
            )
            payload.append(
                _fact(
                    key='machine_down_machine_output',
                    label='机台下机量',
                    value=machine.get('machine_down_machine_output'),
                    unit='吨',
                    grain='机台/日',
                    business_date=target_date,
                    dimensions=machine_dimensions,
                    source=_source(
                        page='车间生产管理 / 车间报表',
                        path='/Report/ProductionWorkshopReport',
                        table='MES_ProductProcessRecord',
                        fields=['DeviceName', 'EndWeight', 'EndDatetime'],
                        projection_table='mes_workshop_process_records',
                        status=STATUS_VERIFIED,
                        note='本地未绑定机台保留为 MES未匹配机台，不猜归属。',
                    ),
                    api='/api/v1/dashboard/mes-workshop-machine-reconciliation',
                    frontend_pages=['/manage/workshop-dashboard', '/manage/live'],
                    hermes_field='machine_down_machine_output',
                    sync_status=fact_sync_status,
                )
            )
    return payload


def _wip_facts(db: Session, *, target_date: date, sync_status: dict[str, Any]) -> list[dict[str, Any]]:
    rows = mes_extended_service.list_wip_total_snapshots(db, business_date=target_date, limit=500)
    fact_sync_status = _fact_sync_status(sync_status)
    return [
        _fact(
            key='wip_doing_weight',
            label='在制料重量',
            value=row.get('doing_weight_tons'),
            unit='吨',
            grain='车间工艺/最新快照',
            business_date=target_date,
            dimensions={'workshop': row.get('workshop_name'), 'process': row.get('process_name')},
            source=_source(
                page='调度管理 / 车间实时查询 / 在制料统计',
                path='/Dispatch/Index',
                table=row.get('source_table') or 'MES_Product',
                fields=[
                    row.get('source_workshop_field') or 'CurrentWorkShop',
                    row.get('source_process_field') or 'CurrentProcess',
                    row.get('source_weight_field') or 'FeedingWeight',
                ],
                projection_table='mes_wip_total_snapshots',
                status=STATUS_VERIFIED,
                note='对齐车间实时查询右上角在制料统计；本地投影可能由 /Dispatch/DoingReportTotal 同步得到，页面入口以 /Dispatch/Index 为准。',
            ),
            api='/api/v1/mes/extended/wip-total-snapshots',
            frontend_pages=['/manage/today', '/manage/workshop-dashboard'],
            hermes_field='wip_doing_weight',
            difference_categories=['快照时间', '单位', '车间别名', '工艺别名'],
            updated_at=row.get('snapshot_at'),
            sync_status=fact_sync_status,
        )
        for row in rows
    ]


def _to_float(value: Any) -> float:
    try:
        return float(value or 0)
    except (TypeError, ValueError):
        return 0.0


def _material_weight_tons(row: MesMaterialRecord) -> float:
    direct = _to_float(row.weight_tons)
    if direct > 0:
        return direct
    return _to_float(row.weight_kg) / 1000


def _material_status_counts(row: MesMaterialRecord) -> bool:
    payload = row.source_payload if isinstance(row.source_payload, dict) else {}
    status_text = str(row.status_name or payload.get('StatusName') or payload.get('Status') or '').strip()
    return '已使用' in status_text or '未使用' in status_text


def _billet_workshop_name(workshop_name: Any) -> str | None:
    text = str(workshop_name or '').strip()
    if not text:
        return None
    if '铸二' in text:
        return text
    if '铸三' in text:
        return text
    if '热轧' in text:
        return text
    return None


def _billet_material_facts(db: Session, *, target_date: date, sync_status: dict[str, Any]) -> list[dict[str, Any]]:
    fact_sync_status = _fact_sync_status(sync_status)
    try:
        rows = (
            db.query(MesMaterialRecord)
            .filter(MesMaterialRecord.business_date == target_date)
            .order_by(MesMaterialRecord.id.asc())
            .all()
        )
    except (OperationalError, ProgrammingError):
        return []

    grouped: dict[str, dict[str, Any]] = {}
    for row in rows:
        workshop_name = _billet_workshop_name(row.workshop_name)
        if workshop_name is None or not _material_status_counts(row):
            continue
        weight = _material_weight_tons(row)
        if weight <= 0:
            continue
        item = grouped.setdefault(
            workshop_name,
            {'value': 0.0, 'row_count': 0, 'updated_at': None},
        )
        item['value'] += weight
        item['row_count'] += 1
        item['updated_at'] = _latest_fact_timestamp(item['updated_at'], row.last_seen_from_mes_at, row.production_date)

    facts: list[dict[str, Any]] = []
    for workshop_name, item in grouped.items():
        facts.append(
            _fact(
                key='billet_material_output',
                label='坯料明细产量',
                value=item['value'],
                unit='吨',
                grain='铸二/铸三/热轧/日',
                business_date=target_date,
                dimensions={'workshop': workshop_name, 'row_count': item['row_count']},
                source=_source(
                    page='坯料管理 / 坯料明细',
                    path='/Material/Index',
                    table='MES_Material',
                    fields=['Weight', 'ProductionDate', 'WorkShop', 'StatusName=已使用/未使用'],
                    projection_table='mes_material_records',
                    status=STATUS_VERIFIED,
                    note='铸二、铸三、热轧车间产量按坯料明细 Weight 求和，状态只计已使用和未使用。',
                ),
                api='/api/v1/mes/extended/material-records',
                frontend_pages=['/manage/today', '/manage/workshop-dashboard'],
                hermes_field='billet_material_output',
                updated_at=item['updated_at'],
                sync_status=fact_sync_status,
                difference_categories=['业务日', '状态过滤', '单位', '车间别名'],
            )
        )
    return facts


def _rule_and_gap_facts(*, target_date: date, sync_status: dict[str, Any]) -> list[dict[str, Any]]:
    fact_sync_status = _fact_sync_status(sync_status)
    return [
        _fact(
            key='billet_material_output_rule',
            label='坯料明细产量规则',
            value=None,
            unit='吨',
            grain='铸二/铸三/热轧/日',
            business_date=target_date,
            source=_source(
                page='坯料管理 / 坯料明细',
                path='/Material/Index',
                table='MES_Material',
                fields=['Weight', 'ProductionDate', 'WorkShop', 'StatusName=已使用/未使用'],
                projection_table='mes_material_records',
                status=STATUS_VERIFIED,
                note='铸二、铸三、热轧车间产量按坯料明细 Weight 求和，状态包含已使用和未使用，业务时间 10:00-10:00。',
            ),
            api='/api/v1/mes/extended/material-records',
            frontend_pages=['/manage/today', '/manage/workshop-dashboard'],
            hermes_field='billet_material_output_rule',
            missing_reason='rule_only',
            sync_status=fact_sync_status,
            difference_categories=['业务日', '状态过滤', '单位', '车间别名'],
        ),
        _fact(
            key='follow_card_page_total_feeding',
            label='随行卡页面总投料量',
            value=None,
            unit='吨',
            grain='页面汇总/日',
            business_date=target_date,
            source=_source(
                page='计划管理 / 随行卡管理',
                path='/FollowCard/Index',
                table='MES_Product / MES_ProductProcessRecord',
                fields=['FeedingWeight', 'BeginWeight'],
                projection_table='mes_coil_snapshots / mes_workshop_process_records',
                status=STATUS_NEEDS_CHECK,
                note='当前数据中枢总投料按 MES_Product.FeedingWeight；随行卡页面汇总区仍需浏览器和 SQL 复核。',
            ),
            api='/api/v1/dashboard/mes-factory-production-reconciliation',
            frontend_pages=['/manage/live', '/manage/today'],
            hermes_field='follow_card_page_total_feeding',
            missing_reason='requires_browser_sql_check',
            sync_status=fact_sync_status,
        ),
        _fact(
            key='finished_stock_outbound_delivery',
            label='成品库出库量',
            value=None,
            unit='吨',
            grain='成品库/日',
            business_date=target_date,
            source=_source(
                page='成品库 / 出库',
                path='/Stock/Index',
                table='WMS_OutStockDetail',
                fields=['NetWeight', 'CreateDate', 'OperateDate'],
                projection_table='mes_stock_records',
                status=STATUS_NEEDS_CHECK,
                note='SQL Server adapter 已有 delivery_stock_records 只读同步；页面筛选条件仍需真实页面复核。',
            ),
            api='/api/v1/mes/extended/stock-records',
            frontend_pages=['/manage/coils', '/manage/today'],
            hermes_field='finished_stock_outbound_delivery',
            missing_reason='requires_browser_sql_check',
            sync_status=fact_sync_status,
        ),
        _fact(
            key='allocation_packaging_reference',
            label='成品调拨包装参考量',
            value=None,
            unit='吨',
            grain='调拨单/日',
            business_date=target_date,
            source=_source(
                page='包装管理 / 成品调拨单',
                path='/Allocation/Index',
                table='WMS_Stock / WMS_InStockDetail / WMS_OutStockDetail',
                fields=['FromDepartment', 'ToDepartment', 'NetWeight', 'CreateDate'],
                projection_table='mes_stock_records',
                status=STATUS_CANDIDATE,
                note='用于园区精整、精整、拉矫包装产量对照；不替代包装录入主口径。',
            ),
            api='/api/v1/dashboard/mes-factory-production-reconciliation',
            frontend_pages=['/manage/today', '/manage/workshop-dashboard'],
            hermes_field='allocation_packaging_reference',
            missing_reason='candidate_reference_only',
            sync_status=fact_sync_status,
        ),
        _fact(
            key='coil_full_lifecycle_trace',
            label='前世今生全链路',
            value=None,
            unit=None,
            grain='批号/卷',
            business_date=target_date,
            source=_source(
                page='前世今生',
                path='/Archives/Index',
                table='MES_Product + MES_ProductProcessRecord + WMS_InStockDetail + WMS_OutStockDetail',
                fields=['BatchNo', 'ContractNo', 'BeginWeight', 'EndWeight', 'NetWeight', 'CurrentProcess'],
                projection_table='mes_coil_snapshots + mes_workshop_process_records + mes_stock_records',
                status=STATUS_NEEDS_CHECK,
                note='当前卷级线索页已有当前快照和最新工序；完整工序历史、包装、入库、出库还需补齐和复核。',
            ),
            api='/api/v1/factory-command/coils/{coil_key}/flow',
            frontend_pages=['/manage/coils'],
            hermes_field='coil_full_lifecycle_trace',
            missing_reason='requires_full_lifecycle_trace_completion',
            sync_status=fact_sync_status,
        ),
    ]


def build_mes_fact_bundle(db: Session, *, target_date: date, include_debug: bool = True) -> dict[str, Any]:
    window_start, window_end = production_business_window(target_date)
    sync_status = _safe_latest_sync_status(db)
    factory = _safe_factory_production_fact(db, target_date=target_date)
    reconciliation = _safe_workshop_machine_reconciliation(db, target_date=target_date)
    facts = [
        *_factory_facts(factory, target_date=target_date, sync_status=sync_status),
        *_workshop_machine_facts(reconciliation, target_date=target_date, sync_status=sync_status),
        *_wip_facts(db, target_date=target_date, sync_status=sync_status),
        *_billet_material_facts(db, target_date=target_date, sync_status=sync_status),
    ]
    audit_gaps = _rule_and_gap_facts(target_date=target_date, sync_status=sync_status)
    payload = {
        'target_date': target_date.isoformat(),
        'business_day': {
            'start': _iso(window_start),
            'end': _iso(window_end),
            'policy': {
                'default': '07:50-07:50',
                '铸二': '10:00-10:00',
                '铸三': '10:00-10:00',
                '热轧': '10:00-10:00',
                'owner_daily': '09:30',
            },
        },
        'read_model': {
            'mode': READ_MODEL_MODE,
            'decision': '页面和 Hermes 读取本地 mes_* 投影；MES SQL Server 只用于 adapter、sync、audit、shadow reconciliation。',
            'projection_tables': [
                'mes_coil_snapshots',
                'mes_workshop_process_records',
                'mes_stock_records',
                'mes_material_records',
                'mes_wip_total_snapshots',
            ],
        },
        'mes_sync_status': sync_status,
        'fact_count': len(facts),
        'facts': facts,
        'audit_gap_count': len(audit_gaps),
        'audit_gaps': audit_gaps,
    }
    if include_debug:
        payload['debug'] = {
            'factory_production_fact': factory,
            'workshop_machine_reconciliation': {
                'target_date': reconciliation.get('target_date'),
                'business_day': reconciliation.get('business_day'),
                'source_mapping': reconciliation.get('source_mapping'),
                'totals': reconciliation.get('totals') or {},
            },
        }
    return payload
