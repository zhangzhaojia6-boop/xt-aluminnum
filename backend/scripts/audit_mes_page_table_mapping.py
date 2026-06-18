"""Read-only MES page/table mapping audit.

This command joins three evidence sources:
- the MES menu stored in SQL Server `MES_Right`
- SQL Server table/column metadata
- the MES MVC page surface after login

It never writes SQL Server data and never prints credentials, cookies, tokens,
or raw HTML.
"""

from __future__ import annotations

import argparse
from datetime import date, datetime, time, timedelta, timezone
import json
import re
import sys
from html import unescape
from pathlib import Path
from typing import Any, Callable, Mapping

import httpx

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from app.adapters.sqlserver_mes_adapter import _ensure_read_only_query, _run_pymssql_query
from app.config import Settings, settings
from app.core.redaction import filter_sensitive_mapping, is_sensitive_key, redact_secret_text


QueryRunner = Callable[[str, tuple[Any, ...]], list[Mapping[str, Any]]]
PageFetcher = Callable[[str], str]


MENU_QUERY = (
    'SELECT Id AS id, ParentId AS parent_id, Name AS name, Url AS url, '
    'IsButton AS is_button, Sort AS sort, Status AS status '
    'FROM MES_Right WHERE ISNULL(IsButton, 0) = 0 AND ISNULL(Status, 0) = 0 '
    'ORDER BY ParentId, Sort, Id'
)

TABLE_QUERY = (
    'SELECT TABLE_SCHEMA AS table_schema, TABLE_NAME AS table_name, TABLE_TYPE AS table_type '
    "FROM INFORMATION_SCHEMA.TABLES WHERE TABLE_TYPE IN ('BASE TABLE', 'VIEW') "
    'ORDER BY TABLE_SCHEMA, TABLE_NAME'
)

COLUMN_QUERY = (
    'SELECT TABLE_SCHEMA AS table_schema, TABLE_NAME AS table_name, COLUMN_NAME AS column_name, '
    'DATA_TYPE AS data_type, ORDINAL_POSITION AS ordinal_position '
    'FROM INFORMATION_SCHEMA.COLUMNS ORDER BY TABLE_SCHEMA, TABLE_NAME, ORDINAL_POSITION'
)

WRITE_PATH_HINTS = (
    'Save',
    'Delete',
    'Deleted',
    'Remove',
    'Set',
    'Invalid',
    'Disabled',
    'Enabled',
    'Unbind',
    'Recovery',
    'Revoke',
    'Send',
    'Update',
    'Edit',
    'Add',
    'Upload',
    'Import',
)

IGNORED_ENDPOINT_PREFIXES = (
    '/Content/',
    '/Scripts/',
    '/fonts/',
    '/Images/',
    '/img/',
    '/css/',
    '/js/',
)

PAGE_RULES: list[dict[str, Any]] = [
    {
        'prefix': '/ContractNotice/',
        'business_meaning': '生产通知单',
        'tables': ['MES_ContractNotice', 'MES_ContractNoticeDetail', 'MES_Contract', 'MES_ContractDetail'],
        'source_fields': ['ContractCode', 'Customer', 'Alloy', 'Specification', 'Weight', 'CreateDate'],
        'confidence': 'controller_catalog_match',
    },
    {
        'prefix': '/Contract/',
        'business_meaning': '销售合同',
        'tables': ['MES_Contract', 'MES_ContractDetail'],
        'source_fields': ['ContractCode', 'Customer', 'Alloy', 'Specification', 'Weight', 'DeliveryDate'],
        'confidence': 'controller_catalog_match',
    },
    {
        'prefix': '/Delivery/',
        'business_meaning': '发货通知',
        'tables': ['MES_Delivery', 'MES_DeliveryDetail', 'WMS_OutStock', 'WMS_OutStockDetail'],
        'source_fields': ['DeliveryCode', 'ContractCode', 'NetWeight', 'GrossWeight', 'OperateDate'],
        'confidence': 'controller_catalog_match',
    },
    {
        'prefix': '/Customer/',
        'business_meaning': '客户主数据',
        'tables': ['MES_Customer'],
        'source_fields': ['Name', 'SimpleName', 'Code'],
        'confidence': 'controller_catalog_match',
    },
    {
        'prefix': '/Saler/',
        'business_meaning': '业务员主数据',
        'tables': ['MES_Saler'],
        'source_fields': ['Name', 'Code'],
        'confidence': 'controller_catalog_match',
    },
    {
        'prefix': '/Company/',
        'business_meaning': '乙方公司主数据',
        'tables': ['MES_Company'],
        'source_fields': ['Name', 'Code'],
        'confidence': 'controller_catalog_match',
    },
    {
        'prefix': '/Feeding/',
        'business_meaning': '投料管理',
        'tables': ['MES_Product'],
        'source_fields': ['FeedingWeight', 'CreateDate', 'CurrentWorkShop', 'MaterialCode'],
        'confidence': 'verified_core_fact',
    },
    {
        'prefix': '/Production/',
        'business_meaning': '生产信息补录',
        'tables': ['MES_Product', 'MES_ProductProcessRecord'],
        'source_fields': ['CurrentWorkShop', 'CurrentProcess', 'BeginWeight', 'EndWeight', 'EndDatetime'],
        'confidence': 'controller_catalog_match',
    },
    {
        'prefix': '/FollowCard/',
        'business_meaning': '随行卡',
        'tables': ['MES_Product', 'MES_ProductProcessRecord'],
        'source_fields': ['MaterialCode', 'BatchNumber', 'ProcessRoute', 'CurrentProcess', 'CurrentWorkShop'],
        'confidence': 'controller_catalog_match',
    },
    {
        'prefix': '/ProductHistory/',
        'business_meaning': '工艺修改历史',
        'tables': ['MES_ProductHistory', 'MES_Product'],
        'source_fields': ['ProductId', 'ProcessRoute', 'OperateDate', 'CreateDate'],
        'confidence': 'controller_catalog_match',
    },
    {
        'prefix': '/Dispatch/',
        'business_meaning': '生产车间实时查询',
        'tables': ['MES_Product', 'MES_ProductProcessRecord'],
        'source_fields': ['CurrentWorkShop', 'CurrentProcess', 'NextWorkShop', 'NextProcess', 'EndDatetime'],
        'confidence': 'controller_catalog_match',
    },
    {
        'prefix': '/ProductProblem/',
        'business_meaning': '问题卷',
        'tables': ['MES_ProductProblem', 'MES_Product', 'MES_ProductProcessRecord'],
        'source_fields': ['ProductId', 'MaterialCode', 'Problem', 'OperateDate'],
        'confidence': 'controller_catalog_match',
    },
    {
        'prefix': '/Inspection/',
        'business_meaning': '质检报表',
        'tables': ['MES_Product', 'MES_ProductProcessRecord'],
        'source_fields': ['MaterialCode', 'Process', 'EndWeight', 'OperateDate'],
        'confidence': 'controller_catalog_match',
    },
    {
        'prefix': '/Workshop/',
        'business_meaning': '车间随行卡和过站记录',
        'tables': ['MES_Product', 'MES_ProductProcessRecord'],
        'source_fields': ['WorkShop', 'Process', 'BeginWeight', 'EndWeight', 'EndDatetime'],
        'confidence': 'controller_catalog_match',
    },
    {
        'prefix': '/Anneal/',
        'business_meaning': '退火管理',
        'tables': ['MES_Product', 'MES_ProductProcessRecord'],
        'source_fields': ['Process', 'WorkShop', 'BeginDatetime', 'EndDatetime', 'EndWeight'],
        'confidence': 'controller_catalog_match',
    },
    {
        'prefix': '/Pack/',
        'business_meaning': '包装录入',
        'tables': ['MES_ProductProcessRecord', 'MES_Product'],
        'source_fields': ['Process', 'WorkShop', 'EndWeight', 'EndDatetime', 'DeviceName'],
        'confidence': 'verified_core_fact',
    },
    {
        'prefix': '/Allocation/',
        'business_meaning': '成品调拨',
        'tables': ['WMS_Stock', 'WMS_InStockDetail', 'WMS_OutStockDetail'],
        'source_fields': ['PID', 'FromDepartment', 'ToDepartment', 'NetWeight', 'OperateDate'],
        'confidence': 'controller_catalog_match',
    },
    {
        'prefix': '/Material/',
        'business_meaning': '坯料和铸轧机列',
        'tables': ['MES_Material'],
        'source_fields': ['MaterialCode', 'PWorkShop', 'PCraft', 'Weight', 'ProductionDate'],
        'confidence': 'controller_catalog_match',
    },
    {
        'prefix': '/Notices/',
        'business_meaning': '公告',
        'tables': ['MES_Notices'],
        'source_fields': ['Title', 'Content', 'CreateDate'],
        'confidence': 'controller_catalog_match',
    },
    {
        'prefix': '/Stock/',
        'business_meaning': '成品库存',
        'tables': ['WMS_Stock', 'WMS_InStock', 'WMS_InStockDetail'],
        'source_fields': ['PID', 'BatchNumber', 'NetWeight', 'GrossWeight', 'InStockDate'],
        'confidence': 'verified_core_fact',
    },
    {
        'prefix': '/Right/',
        'business_meaning': '权限菜单',
        'tables': ['MES_Right'],
        'source_fields': ['Name', 'Url', 'ParentId', 'IsButton'],
        'confidence': 'verified_menu_source',
    },
    {
        'prefix': '/Role/',
        'business_meaning': '角色权限',
        'tables': ['MES_Role', 'MES_Right'],
        'source_fields': ['Name', 'RightIds', 'CreateDate'],
        'confidence': 'controller_catalog_match',
    },
    {
        'prefix': '/Department/',
        'business_meaning': '部门主数据',
        'tables': ['MES_Department'],
        'source_fields': ['Name', 'ParentId', 'CreateDate'],
        'confidence': 'controller_catalog_match',
    },
    {
        'prefix': '/Member/',
        'business_meaning': '员工主数据',
        'tables': ['MES_Member', 'MES_Department', 'MES_Role'],
        'source_fields': ['Name', 'Account', 'DepartmentId', 'RoleId'],
        'confidence': 'controller_catalog_match',
    },
    {
        'prefix': '/Dict/',
        'business_meaning': '数据字典',
        'tables': ['MES_Dict'],
        'source_fields': ['Name', 'Code', 'ParentId'],
        'confidence': 'controller_catalog_match',
    },
    {
        'prefix': '/Craft/',
        'business_meaning': '生产工艺',
        'tables': ['MES_Craft'],
        'source_fields': ['Name', 'Code', 'Sort'],
        'confidence': 'controller_catalog_match',
    },
    {
        'prefix': '/Device/',
        'business_meaning': '设备机器',
        'tables': ['MES_Device'],
        'source_fields': ['Name', 'MAC', 'IP', 'WorkShop', 'Craft', 'Status'],
        'confidence': 'verified_catalog_fact',
    },
    {
        'prefix': '/Log/',
        'business_meaning': '登录日志',
        'tables': ['MES_Log'],
        'source_fields': ['Account', 'OperateDate', 'CreateDate'],
        'confidence': 'controller_catalog_match',
    },
    {
        'prefix': '/Archives/',
        'business_meaning': '前世今生卷级追溯',
        'tables': ['MES_Product', 'MES_ProductProcessRecord', 'WMS_InStockDetail', 'WMS_Stock'],
        'source_fields': ['MaterialCode', 'BatchNumber', 'ProcessRoute', 'EndDatetime', 'InStockDate'],
        'confidence': 'controller_catalog_match',
    },
]

REPORT_RULES: dict[str, dict[str, Any]] = {
    '/Report/ContractStructReport': {
        'business_meaning': '合同结构一览表',
        'tables': ['MES_Contract', 'MES_ContractDetail', 'MES_ContractNotice', 'MES_Product'],
        'source_fields': ['ContractCode', 'MaterialCode', 'Weight', 'CurrentWorkShop'],
        'confidence': 'controller_catalog_match',
    },
    '/Report/ThreeReport': {
        'business_meaning': '三合一报表',
        'tables': ['MES_Product', 'MES_ProductProcessRecord', 'WMS_InStockDetail'],
        'source_fields': ['FeedingWeight', 'EndWeight', 'NetWeight', 'CreateDate', 'EndDatetime'],
        'confidence': 'controller_catalog_match',
    },
    '/Report/YieldReport': {
        'business_meaning': 'MES 成品率报表',
        'tables': ['MES_Product', 'MES_ProductProcessRecord'],
        'source_fields': ['FeedingWeight', 'EndWeight', 'Process', 'EndDatetime'],
        'confidence': 'controller_catalog_match',
    },
    '/Report/YieldWarningReport': {
        'business_meaning': '成品率预警',
        'tables': ['MES_Product', 'MES_ProductProcessRecord'],
        'source_fields': ['FeedingWeight', 'EndWeight', 'Process', 'EndDatetime'],
        'confidence': 'controller_catalog_match',
    },
    '/Report/ProductionWorkshopReport': {
        'business_meaning': '车间报表',
        'tables': ['MES_ProductProcessRecord'],
        'source_fields': ['WorkShop', 'Process', 'BeginWeight', 'EndWeight', 'EndDatetime'],
        'confidence': 'verified_core_fact',
    },
    '/ContractNotice/Report': {
        'business_meaning': '生产通知单报表',
        'tables': ['MES_ContractNotice', 'MES_ContractNoticeDetail', 'MES_Product'],
        'source_fields': ['ContractCode', 'MaterialCode', 'Weight', 'CreateDate'],
        'confidence': 'controller_catalog_match',
    },
}


def _text(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _row_value(row: Mapping[str, Any], *keys: str) -> Any:
    for key in keys:
        if key in row:
            return row[key]
    lower_map = {str(key).lower(): value for key, value in row.items()}
    for key in keys:
        value = lower_map.get(key.lower())
        if value is not None:
            return value
    return None


def _is_blank(value: str | None) -> bool:
    return value is None or not str(value).strip()


def _boolish(value: Any) -> bool:
    return str(value).strip().lower() in {'1', 'true', 'yes'}


def _dedupe(items: list[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for item in items:
        text = item.strip()
        if not text or text in seen:
            continue
        seen.add(text)
        result.append(text)
    return result


def _strip_html(value: str) -> str:
    text = re.sub(r'<script\b.*?</script>', ' ', value, flags=re.IGNORECASE | re.DOTALL)
    text = re.sub(r'<style\b.*?</style>', ' ', text, flags=re.IGNORECASE | re.DOTALL)
    text = re.sub(r'<[^>]+>', ' ', text)
    return re.sub(r'\s+', ' ', unescape(text)).strip()


def _attrs(tag: str) -> dict[str, str]:
    attrs: dict[str, str] = {}
    for key, quoted, bare in re.findall(r'([:\w-]+)\s*=\s*(?:"([^"]*)"|\'([^\']*)\')', tag):
        value = quoted or bare
        if key and not is_sensitive_key(key) and not is_sensitive_key(value):
            attrs[key] = unescape(value).strip()
    return attrs


def _safe_path(path: str) -> str | None:
    text = path.strip()
    if not text or text.startswith(('http://', 'https://', 'javascript:', '#')):
        return None
    if '?' in text:
        text = text.split('?', 1)[0]
    if not text.startswith('/'):
        return None
    if '..' in text:
        return None
    if any(text.startswith(prefix) for prefix in IGNORED_ENDPOINT_PREFIXES):
        return None
    return text.rstrip('/') or '/'


def _endpoint_kind(path: str) -> str:
    tail = path.rsplit('/', 1)[-1]
    if any(hint in tail for hint in WRITE_PATH_HINTS):
        return 'write_endpoint_seen_on_page'
    return 'read_or_page_endpoint'


def _ensure_read_only_select(query: str) -> None:
    _ensure_read_only_query(query)


def _ensure_read_only_page_path(path: str) -> None:
    safe = _safe_path(path)
    if not safe:
        raise ValueError('MES MVC page path is not a local path')
    tail = safe.rsplit('/', 1)[-1]
    if any(hint in tail for hint in WRITE_PATH_HINTS):
        raise ValueError(f'MES MVC page path is not read-only: {safe}')


def extract_page_surface(html: str) -> dict[str, Any]:
    headers = [
        _strip_html(match)
        for match in re.findall(r'<th\b[^>]*>(.*?)</th>', html, flags=re.IGNORECASE | re.DOTALL)
    ]
    labels = [
        _strip_html(match)
        for match in re.findall(r'<label\b[^>]*>(.*?)</label>', html, flags=re.IGNORECASE | re.DOTALL)
    ]
    buttons = [
        _strip_html(match)
        for match in re.findall(r'<button\b[^>]*>(.*?)</button>', html, flags=re.IGNORECASE | re.DOTALL)
    ]
    fields: list[dict[str, str]] = []
    for tag_match in re.finditer(r'<(input|select|textarea)\b([^>]*)>', html, flags=re.IGNORECASE | re.DOTALL):
        tag_name = tag_match.group(1).lower()
        attrs = _attrs(tag_match.group(2))
        item = {
            'tag': tag_name,
            'id': attrs.get('id', ''),
            'name': attrs.get('name', ''),
            'placeholder': attrs.get('placeholder', ''),
        }
        if any(item.values()):
            fields.append({key: value for key, value in item.items() if value})

    endpoint_candidates: list[str] = []
    endpoint_patterns = (
        r'\burl\s*:\s*["\']([^"\']+)["\']',
        r'\bsAjaxSource\s*:\s*["\']([^"\']+)["\']',
        r'\$\.(?:post|get)\(\s*["\']([^"\']+)["\']',
        r'\b(?:href|action)\s*=\s*["\'](/[^"\']+)["\']',
    )
    for pattern in endpoint_patterns:
        endpoint_candidates.extend(
            match.group(1)
            for match in re.finditer(pattern, html, flags=re.IGNORECASE)
        )
    endpoints = [
        path
        for path in (_safe_path(candidate) for candidate in endpoint_candidates)
        if path
    ]
    endpoints = _dedupe(endpoints)
    return {
        'table_headers': _dedupe([item for item in headers if item])[:80],
        'labels': _dedupe([item for item in labels if item])[:80],
        'buttons': _dedupe([item for item in buttons if item])[:80],
        'fields': fields[:120],
        'endpoints': [
            {'path': path, 'kind': _endpoint_kind(path)}
            for path in endpoints[:120]
        ],
        'has_datatable': 'dataTable' in html or 'DataTable' in html or 'sAjaxSource' in html,
    }


def _missing_sqlserver_env(runtime: Settings) -> list[str]:
    missing: list[str] = []
    for name in ('MES_SQLSERVER_HOST', 'MES_SQLSERVER_DATABASE', 'MES_SQLSERVER_USERNAME', 'MES_SQLSERVER_PASSWORD'):
        if _is_blank(getattr(runtime, name)):
            missing.append(name)
    return missing


def _missing_mvc_env(runtime: Settings) -> list[str]:
    missing: list[str] = []
    for name in ('MES_MVC_BASE_URL', 'MES_MVC_USERNAME', 'MES_MVC_PASSWORD'):
        if _is_blank(getattr(runtime, name)):
            missing.append(name)
    return missing


def _real_query_runner(runtime: Settings) -> QueryRunner:
    def runner(query: str, params: tuple[Any, ...] = ()) -> list[Mapping[str, Any]]:
        _ensure_read_only_select(query)
        return _run_pymssql_query(
            host=str(runtime.MES_SQLSERVER_HOST or '').strip(),
            port=int(runtime.MES_SQLSERVER_PORT),
            database=str(runtime.MES_SQLSERVER_DATABASE or '').strip(),
            username=str(runtime.MES_SQLSERVER_USERNAME or '').strip(),
            password=str(runtime.MES_SQLSERVER_PASSWORD or ''),
            timeout_seconds=runtime.MES_SQLSERVER_TIMEOUT_SECONDS,
            encrypt=runtime.MES_SQLSERVER_ENCRYPT,
            query=query,
            params=params,
        )

    return runner


class MesMvcPageFetcher:
    def __init__(self, runtime: Settings) -> None:
        self._base_url = str(runtime.MES_MVC_BASE_URL or '').rstrip('/')
        self._username = str(runtime.MES_MVC_USERNAME or '')
        self._password = str(runtime.MES_MVC_PASSWORD or '')
        self._client = httpx.Client(follow_redirects=True, timeout=runtime.MES_MVC_TIMEOUT_SECONDS)
        self._token: str | None = None
        self._logged_in = False

    def close(self) -> None:
        self._client.close()

    def __call__(self, path: str) -> str:
        _ensure_read_only_page_path(path)
        if not self._logged_in:
            self._login()
        response = self._client.post(
            f'{self._base_url}{path}',
            data={
                'IsMenu': 'true',
                '__RequestVerificationToken': self._token or '',
            },
            headers=self._headers(path),
        )
        response.raise_for_status()
        if self._looks_like_login_page(response.text):
            self._logged_in = False
            self._token = None
            self._login()
            response = self._client.post(
                f'{self._base_url}{path}',
                data={
                    'IsMenu': 'true',
                    '__RequestVerificationToken': self._token or '',
                },
                headers=self._headers(path),
            )
            response.raise_for_status()
        return response.text

    def _login(self) -> None:
        login_page = self._client.get(f'{self._base_url}/Login/Index', headers=self._headers('/Login/Index'))
        login_page.raise_for_status()
        token_match = re.search(
            r'name=["\']__RequestVerificationToken["\'][^>]*value=["\']([^"\']+)["\']',
            login_page.text,
        )
        if not token_match:
            raise RuntimeError('MES MVC login failed: missing request verification token')
        self._token = token_match.group(1)
        for path, data in (
            (
                '/Login/CheckLogin',
                {
                    '__RequestVerificationToken': self._token,
                    'Account': self._username,
                    'Password': self._password,
                    'MAC': '',
                    'ktsn': '',
                },
            ),
            (
                '/Login/QueryLogin',
                {
                    '__RequestVerificationToken': self._token,
                    'Account': self._username,
                    'Password': self._password,
                },
            ),
        ):
            response = self._client.post(f'{self._base_url}{path}', data=data, headers=self._headers(path))
            response.raise_for_status()
            payload = self._payload(response)
            if not self._success_payload(payload):
                raise RuntimeError('MES MVC login failed')
        self._client.post(
            f'{self._base_url}/Right/GetUserRightList',
            data={'__RequestVerificationToken': self._token},
            headers=self._headers('/Right/GetUserRightList'),
        )
        self._logged_in = True

    def _headers(self, path: str) -> dict[str, str]:
        return {
            'X-Requested-With': 'XMLHttpRequest',
            'Referer': f'{self._base_url}/Login/Index' if path.startswith('/Login') else f'{self._base_url}/',
        }

    @staticmethod
    def _payload(response: httpx.Response) -> Mapping[str, Any]:
        try:
            payload = response.json()
        except ValueError:
            return {}
        return payload if isinstance(payload, Mapping) else {}

    @staticmethod
    def _success_payload(payload: Mapping[str, Any]) -> bool:
        for key in ('status', 'Status', 'success', 'Success'):
            if key in payload:
                return payload.get(key) is True
        return False

    @staticmethod
    def _looks_like_login_page(text: str) -> bool:
        lowered = text.lower()
        return '__requestverificationtoken' in lowered and '/login/checklogin' in lowered


def _safe_columns(rows: list[Mapping[str, Any]], table_name: str, schema: str) -> list[dict[str, Any]]:
    columns: list[dict[str, Any]] = []
    for row in rows:
        row_schema = _text(_row_value(row, 'table_schema', 'TABLE_SCHEMA')) or ''
        row_table = _text(_row_value(row, 'table_name', 'TABLE_NAME')) or ''
        if row_schema != schema or row_table != table_name:
            continue
        column_name = _text(_row_value(row, 'column_name', 'COLUMN_NAME')) or ''
        if not column_name or is_sensitive_key(column_name):
            continue
        columns.append({
            'name': column_name,
            'data_type': _text(_row_value(row, 'data_type', 'DATA_TYPE')),
        })
    return columns


def inspect_sqlserver_catalog(query_runner: QueryRunner) -> dict[str, Any]:
    for query in (TABLE_QUERY, COLUMN_QUERY):
        _ensure_read_only_select(query)
    table_rows = list(query_runner(TABLE_QUERY, ()))
    column_rows = list(query_runner(COLUMN_QUERY, ()))
    tables: list[dict[str, Any]] = []
    for row in table_rows:
        schema = _text(_row_value(row, 'table_schema', 'TABLE_SCHEMA')) or 'dbo'
        name = _text(_row_value(row, 'table_name', 'TABLE_NAME')) or ''
        if not name:
            continue
        tables.append({
            'schema': schema,
            'name': name,
            'type': _text(_row_value(row, 'table_type', 'TABLE_TYPE')),
            'columns': _safe_columns(column_rows, name, schema),
        })
    return {
        'status': 'success',
        'table_count': len(tables),
        'tables': tables,
    }


def fetch_mes_menu(query_runner: QueryRunner) -> list[dict[str, Any]]:
    _ensure_read_only_select(MENU_QUERY)
    rows = list(query_runner(MENU_QUERY, ()))
    items: list[dict[str, Any]] = []
    for row in rows:
        name = _text(_row_value(row, 'name', 'Name'))
        if not name:
            continue
        url = _text(_row_value(row, 'url', 'Url'))
        items.append({
            'id': _text(_row_value(row, 'id', 'Id')),
            'parent_id': _text(_row_value(row, 'parent_id', 'ParentId')),
            'name': name,
            'url': url,
            'is_button': _boolish(_row_value(row, 'is_button', 'IsButton')),
            'sort': _row_value(row, 'sort', 'Sort'),
            'status': _row_value(row, 'status', 'Status'),
        })
    return items


def _menu_path(item: Mapping[str, Any], by_id: dict[str, Mapping[str, Any]]) -> list[str]:
    path: list[str] = []
    current: Mapping[str, Any] | None = item
    visited: set[str] = set()
    while current:
        item_id = _text(current.get('id')) or ''
        if item_id in visited:
            break
        visited.add(item_id)
        name = _text(current.get('name'))
        if name:
            path.append(name)
        parent_id = _text(current.get('parent_id'))
        current = by_id.get(parent_id or '')
    return list(reversed(path))


def _catalog_index(catalog: Mapping[str, Any]) -> dict[str, dict[str, Any]]:
    index: dict[str, dict[str, Any]] = {}
    for table in catalog.get('tables') or []:
        if not isinstance(table, Mapping):
            continue
        name = _text(table.get('name'))
        if name:
            index[name.lower()] = dict(table)
    return index


def _rule_for_page(url: str) -> dict[str, Any]:
    if url in REPORT_RULES:
        return REPORT_RULES[url]
    for rule in PAGE_RULES:
        if url.startswith(str(rule['prefix'])):
            return rule
    return {
        'business_meaning': '未归类页面',
        'tables': [],
        'source_fields': [],
        'confidence': 'needs_manual_mapping',
    }


def _resolve_tables(candidate_tables: list[str], catalog: Mapping[str, Any]) -> list[dict[str, Any]]:
    table_index = _catalog_index(catalog)
    resolved: list[dict[str, Any]] = []
    for candidate in candidate_tables:
        table = table_index.get(candidate.lower())
        if table:
            resolved.append({
                'name': table.get('name'),
                'schema': table.get('schema'),
                'status': 'catalog_match',
                'columns': [
                    column.get('name')
                    for column in table.get('columns', [])[:40]
                    if isinstance(column, Mapping) and column.get('name')
                ],
            })
        else:
            resolved.append({
                'name': candidate,
                'schema': None,
                'status': 'candidate_not_seen_in_catalog',
                'columns': [],
            })
    return resolved


def build_page_inventory(
    menu_items: list[Mapping[str, Any]],
    *,
    catalog: Mapping[str, Any],
    surface_by_url: Mapping[str, Mapping[str, Any]] | None = None,
) -> list[dict[str, Any]]:
    by_id = {str(item.get('id') or ''): item for item in menu_items if item.get('id') is not None}
    pages: list[dict[str, Any]] = []
    for item in menu_items:
        url = _safe_path(str(item.get('url') or ''))
        if not url:
            continue
        path = _menu_path(item, by_id)
        rule = _rule_for_page(url)
        surface = dict(surface_by_url.get(url, {})) if surface_by_url else {}
        endpoints = [
            endpoint.get('path')
            for endpoint in surface.get('endpoints', [])
            if isinstance(endpoint, Mapping) and endpoint.get('path')
        ]
        pages.append({
            'menu_path': path,
            'menu_label': ' / '.join(path),
            'url': url,
            'business_meaning': rule['business_meaning'],
            'mapping_confidence': rule['confidence'],
            'source_tables': _resolve_tables(list(rule['tables']), catalog),
            'source_fields': list(rule['source_fields']),
            'page_surface': surface or {'status': 'not_fetched'},
            'ajax_or_form_endpoints': endpoints,
        })
    return pages


def build_mes_home_mapping() -> dict[str, Any]:
    return {
        'page': 'MES 首页',
        'url': '/',
        'business_day': '07:30 至次日 07:30',
        'verified_facts': [
            {
                'metric': '当日投料量',
                'source_table': 'MES_Product',
                'weight_field': 'FeedingWeight',
                'time_field': 'CreateDate',
                'filter': 'CreateDate 落在业务日窗口内，CurrentWorkShop 非空',
                'known_2026_06_18': '427.0t',
            },
            {
                'metric': '首页当日包装总量',
                'source_table': 'MES_ProductProcessRecord',
                'weight_field': 'EndWeight',
                'time_field': 'EndDatetime',
                'filter': 'Process=包装 且 WorkShop=精整',
                'known_2026_06_18': '66.1t',
            },
            {
                'metric': '全厂包装量',
                'source_table': 'MES_ProductProcessRecord',
                'weight_field': 'EndWeight',
                'time_field': 'EndDatetime',
                'filter': 'Process=包装，WorkShop 不只限精整，还应包含园区精整、拉矫车间等包装工序',
                'known_2026_06_18': '需要按全厂车间拆分继续对账',
            },
            {
                'metric': '成品入库量',
                'source_table': 'WMS_InStock / WMS_InStockDetail',
                'weight_field': 'TotalNetWeight / NetWeight',
                'time_field': 'InStockDate',
                'filter': '成品入库事实，不与包装工序产量混用',
                'known_2026_06_18': '由数据中枢对账接口输出',
            },
        ],
    }


def build_business_day_payload(target: date | None = None) -> dict[str, Any]:
    target_date = target or date(2026, 6, 18)
    start = datetime.combine(target_date, time(7, 30))
    end = start + timedelta(days=1)
    month_start = datetime.combine(target_date.replace(day=1), time(7, 30))
    return {
        'timezone': 'Asia/Shanghai',
        'start_time': '07:30',
        'end_exclusive': 'next_day_07:30',
        'daily_window_example': {
            'business_date': target_date.isoformat(),
            'start': start.isoformat(),
            'end_exclusive': end.isoformat(),
        },
        'month_to_date_window_example': {
            'business_month': target_date.strftime('%Y-%m'),
            'start': month_start.isoformat(),
            'end_exclusive': end.isoformat(),
        },
    }


def build_xtmijd_alignment() -> list[dict[str, Any]]:
    return [
        {
            'xtmijd_route': '/manage/live',
            'shared_business_meaning': '全厂实时生产驾驶舱',
            'must_show_metrics': [
                {
                    'name': '投料量',
                    'source_tag': 'MES投料',
                    'source_table': 'MES_Product',
                    'source_field': 'FeedingWeight',
                    'time_field': 'CreateDate',
                },
                {
                    'name': '全厂包装',
                    'source_tag': '包装工序',
                    'source_table': 'MES_ProductProcessRecord',
                    'source_field': 'EndWeight',
                    'time_field': 'EndDatetime',
                    'filter': 'Process=包装',
                },
                {
                    'name': '成品入库',
                    'source_tag': '成品入库',
                    'source_table': 'WMS_InStock / WMS_InStockDetail',
                    'source_field': 'TotalNetWeight / NetWeight',
                    'time_field': 'InStockDate',
                },
                {
                    'name': '全厂成品率',
                    'source_tag': '投料到入库',
                    'formula': '成品入库量 / 投料量 * 100',
                    'zero_denominator': 'null，前端显示 --',
                },
            ],
            'local_projection_rule': '前端只读后端 API；后端读取本地 mes_* 投影表，不在页面请求时直连外部 SQL Server。',
        },
        {
            'xtmijd_route': '/manage/today',
            'shared_business_meaning': '日经营日报',
            'must_show_metrics': ['日投料', '日包装', '日成品入库', '日成品率', '月累计投料', '月累计入库', '月累计成品率'],
            'local_projection_rule': '日累计和月累计使用同一个业务日窗口定义。',
        },
        {
            'xtmijd_route': '/manage/workshop-dashboard',
            'shared_business_meaning': '车间看板',
            'must_show_metrics': ['车间在制', '车间包装', '车间能耗', '全厂头部投料/入库/成品率'],
            'local_projection_rule': '车间明细可按车间过滤；全厂头部数字必须复用统一全厂事实。',
        },
        {
            'xtmijd_route': '/manage/production',
            'shared_business_meaning': '生产分析',
            'must_show_metrics': ['产量趋势', '成品率参考', '在制', '能耗'],
            'local_projection_rule': 'yield_matrix_lane 只作为质检/历史参考，不覆盖全厂主成品率。',
        },
        {
            'xtmijd_route': '/manage/coils',
            'shared_business_meaning': '卷级线索',
            'must_show_metrics': ['随行卡', '客户', '合金', '规格', '当前车间', '当前工序'],
            'local_projection_rule': '卷级字段来自 MES_Product 投影；工序历史来自 MES_ProductProcessRecord 投影。',
        },
        {
            'xtmijd_route': '/manage/fill-details',
            'shared_business_meaning': '人工填报明细',
            'must_show_metrics': ['人工填报产量', '缺报', '补录'],
            'local_projection_rule': '人工填报不能混称为 MES 投料、包装或入库事实。',
        },
        {
            'xtmijd_route': '/manage/energy',
            'shared_business_meaning': '能耗中心',
            'must_show_metrics': ['电耗', '气耗', '吨耗'],
            'local_projection_rule': '吨耗分母若使用包装量，来源标签必须写包装工序。',
        },
    ]


def _safe_error(exc: Exception) -> dict[str, str]:
    return {
        'error': exc.__class__.__name__,
        'message': redact_secret_text(str(exc))[:300],
    }


def inspect_mes_page_table_mapping(
    *,
    runtime_settings: Settings | None = None,
    query_runner: QueryRunner | None = None,
    page_fetcher: PageFetcher | None = None,
    skip_mes_http: bool = False,
    skip_sqlserver: bool = False,
    page_limit: int | None = None,
) -> dict[str, Any]:
    runtime = runtime_settings or settings
    payload: dict[str, Any] = {
        'generated_at': datetime.now(timezone.utc).isoformat(),
        'mode': 'read_only',
        'business_day': build_business_day_payload(),
        'mes_home': build_mes_home_mapping(),
        'sqlserver': {
            'status': 'skipped',
            'missing_env': [],
            'table_count': 0,
            'tables': [],
        },
        'mes_menu': {
            'status': 'skipped',
            'page_count': 0,
            'menu_count': 0,
        },
        'pages': [],
        'xtmijd_alignment': build_xtmijd_alignment(),
    }

    catalog: dict[str, Any] = {'tables': []}
    menu_items: list[dict[str, Any]] = []
    if not skip_sqlserver:
        missing_sql = [] if query_runner else _missing_sqlserver_env(runtime)
        payload['sqlserver']['missing_env'] = missing_sql
        if missing_sql:
            payload['sqlserver']['reason'] = 'missing_config'
            payload['mes_menu']['reason'] = 'sqlserver_skipped'
            return payload
        runner = query_runner or _real_query_runner(runtime)
        try:
            catalog = inspect_sqlserver_catalog(runner)
            menu_items = fetch_mes_menu(runner)
            payload['sqlserver'] = {
                'status': 'success',
                'missing_env': [],
                'table_count': catalog['table_count'],
                'tables': catalog['tables'],
            }
            payload['mes_menu'] = {
                'status': 'success',
                'menu_count': len(menu_items),
                'page_count': len([item for item in menu_items if _safe_path(str(item.get('url') or ''))]),
            }
        except Exception as exc:  # noqa: BLE001 - diagnostic command reports class only
            payload['sqlserver']['status'] = 'failed'
            payload['sqlserver'].update(_safe_error(exc))
            payload['mes_menu']['reason'] = 'sqlserver_failed'
            return payload

    fetcher = page_fetcher
    real_fetcher: MesMvcPageFetcher | None = None
    surface_by_url: dict[str, dict[str, Any]] = {}
    if menu_items and not skip_mes_http:
        missing_mvc = [] if page_fetcher else _missing_mvc_env(runtime)
        if missing_mvc:
            surface_by_url = {}
        else:
            if fetcher is None:
                real_fetcher = MesMvcPageFetcher(runtime)
                fetcher = real_fetcher
            urls = _dedupe([
                _safe_path(str(item.get('url') or '')) or ''
                for item in menu_items
                if _safe_path(str(item.get('url') or ''))
            ])
            if page_limit is not None:
                urls = urls[: max(0, int(page_limit))]
            try:
                for url in urls:
                    try:
                        html = fetcher(url)
                        surface_by_url[url] = {
                            'status': 'success',
                            **extract_page_surface(html),
                        }
                    except Exception as exc:  # noqa: BLE001 - page-level diagnostic
                        surface_by_url[url] = {
                            'status': 'failed',
                            **_safe_error(exc),
                        }
            finally:
                if real_fetcher is not None:
                    real_fetcher.close()

    if menu_items and (skip_mes_http or not surface_by_url):
        for item in menu_items:
            url = _safe_path(str(item.get('url') or ''))
            if url and url not in surface_by_url:
                surface_by_url[url] = {'status': 'skipped'}

    payload['pages'] = build_page_inventory(menu_items, catalog=catalog, surface_by_url=surface_by_url)
    return filter_sensitive_mapping(payload)


def _print_text(payload: Mapping[str, Any]) -> None:
    print('MES page/table mapping audit')
    print(f"Mode: {payload.get('mode')}")
    business_day = payload.get('business_day') or {}
    print(f"Business day: {business_day.get('start_time')} to {business_day.get('end_exclusive')}")
    sqlserver = payload.get('sqlserver') or {}
    print(f"SQL Server: {sqlserver.get('status')}, tables={sqlserver.get('table_count')}")
    menu = payload.get('mes_menu') or {}
    print(f"MES menu: {menu.get('status')}, pages={menu.get('page_count')}, menu_items={menu.get('menu_count')}")
    print(f"Mapped pages: {len(payload.get('pages') or [])}")
    for page in list(payload.get('pages') or [])[:10]:
        tables = ', '.join(
            str(table.get('name'))
            for table in page.get('source_tables', [])
            if isinstance(table, Mapping)
        )
        print(f"- {page.get('menu_label')}: {page.get('url')} -> {tables or 'needs manual mapping'}")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description='Audit MES page/table mapping without writing SQL Server data.')
    parser.add_argument('--json', action='store_true', help='Print machine-readable JSON.')
    parser.add_argument('--output', type=Path, help='Optional path for JSON output.')
    parser.add_argument('--skip-mes-http', action='store_true', help='Skip MES page login/fetching.')
    parser.add_argument('--skip-sqlserver', action='store_true', help='Skip SQL Server menu/table metadata.')
    parser.add_argument('--page-limit', type=int, help='Limit the number of unique MES page URLs fetched.')
    args = parser.parse_args(argv)

    payload = inspect_mes_page_table_mapping(
        skip_mes_http=args.skip_mes_http,
        skip_sqlserver=args.skip_sqlserver,
        page_limit=args.page_limit,
    )
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding='utf-8')
    if args.json:
        print(json.dumps(payload, ensure_ascii=False, indent=2))
    else:
        _print_text(payload)
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
