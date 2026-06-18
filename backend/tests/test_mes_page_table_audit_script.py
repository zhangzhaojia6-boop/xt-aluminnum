from importlib.util import module_from_spec, spec_from_file_location

from app.config import Settings
from tests.path_helpers import BACKEND_ROOT


SCRIPT_PATH = BACKEND_ROOT / 'scripts' / 'audit_mes_page_table_mapping.py'


def _load_script_module():
    spec = spec_from_file_location('audit_mes_page_table_mapping_script', SCRIPT_PATH)
    assert spec is not None and spec.loader is not None
    module = module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _build_settings(**overrides) -> Settings:
    values = {
        'APP_ENV': 'development',
        'DATABASE_URL': 'postgresql+psycopg2://user:pass@localhost:5432/test',
        'SECRET_KEY': 's' * 32,
        'INIT_ADMIN_PASSWORD': 'AdminPassword#2026',
        'MES_MVC_BASE_URL': 'https://mes.example.com',
        'MES_MVC_USERNAME': 'mes-user',
        'MES_MVC_PASSWORD': 'mes-secret-pass',
        'MES_SQLSERVER_HOST': 'sqlserver.example.com',
        'MES_SQLSERVER_DATABASE': 'XTAL',
        'MES_SQLSERVER_USERNAME': 'readonly',
        'MES_SQLSERVER_PASSWORD': 'sql-secret-pass',
    }
    values.update(overrides)
    return Settings(**values)


def _fake_query_runner():
    menu_rows = [
        {'id': 1, 'parent_id': 0, 'name': '销售管理', 'url': ''},
        {'id': 2, 'parent_id': 1, 'name': '生产通知单查询', 'url': '/ContractNotice/Index'},
        {'id': 3, 'parent_id': 0, 'name': '计划管理', 'url': ''},
        {'id': 4, 'parent_id': 3, 'name': '生产通知单管理', 'url': '/ContractNotice/Index'},
        {'id': 5, 'parent_id': 3, 'name': '投料管理', 'url': '/Feeding/Index'},
        {'id': 6, 'parent_id': 0, 'name': '包装管理', 'url': ''},
        {'id': 7, 'parent_id': 6, 'name': '包装录入', 'url': '/Pack/Index'},
        {'id': 8, 'parent_id': 0, 'name': '成品库', 'url': ''},
        {'id': 9, 'parent_id': 8, 'name': '库存查询', 'url': '/Stock/Index'},
    ]
    table_rows = [
        {'table_schema': 'dbo', 'table_name': 'MES_Product', 'table_type': 'BASE TABLE'},
        {'table_schema': 'dbo', 'table_name': 'MES_ProductProcessRecord', 'table_type': 'BASE TABLE'},
        {'table_schema': 'dbo', 'table_name': 'WMS_Stock', 'table_type': 'BASE TABLE'},
        {'table_schema': 'dbo', 'table_name': 'WMS_InStock', 'table_type': 'BASE TABLE'},
        {'table_schema': 'dbo', 'table_name': 'WMS_InStockDetail', 'table_type': 'BASE TABLE'},
        {'table_schema': 'dbo', 'table_name': 'MES_ContractNotice', 'table_type': 'BASE TABLE'},
        {'table_schema': 'dbo', 'table_name': 'MES_Right', 'table_type': 'BASE TABLE'},
    ]
    columns = []
    for table_name, column_names in {
        'MES_Product': ['Id', 'MaterialCode', 'FeedingWeight', 'CreateDate', 'CurrentWorkShop'],
        'MES_ProductProcessRecord': ['Id', 'Process', 'WorkShop', 'EndWeight', 'EndDatetime'],
        'WMS_Stock': ['Id', 'PID', 'NetWeight', 'InStockDate'],
        'WMS_InStock': ['Id', 'Code', 'TotalNetWeight', 'InStockDate'],
        'WMS_InStockDetail': ['Id', 'PID', 'NetWeight', 'CreateDate'],
        'MES_ContractNotice': ['Id', 'ContractCode', 'CreateDate'],
        'MES_Right': ['Id', 'Name', 'Url'],
    }.items():
        for index, column_name in enumerate(column_names, start=1):
            columns.append({
                'table_schema': 'dbo',
                'table_name': table_name,
                'column_name': column_name,
                'data_type': 'nvarchar',
                'ordinal_position': index,
            })

    def runner(query, params=()):
        assert params == ()
        if 'FROM MES_Right' in query:
            return menu_rows
        if 'INFORMATION_SCHEMA.TABLES' in query:
            return table_rows
        if 'INFORMATION_SCHEMA.COLUMNS' in query:
            return columns
        raise AssertionError(f'unexpected query: {query}')

    return runner


def test_audit_script_rejects_non_select_sql() -> None:
    module = _load_script_module()

    module._ensure_read_only_select('SELECT * FROM MES_Product')

    try:
        module._ensure_read_only_select('DELETE FROM MES_Product')
    except ValueError as exc:
        assert 'read-only' in str(exc)
    else:
        raise AssertionError('DELETE query was not rejected')


def test_extract_page_surface_finds_fields_and_endpoints_without_passwords() -> None:
    module = _load_script_module()

    surface = module.extract_page_surface(
        '''
        <table><tr><th>随行卡</th><th>投料重量</th></tr></table>
        <label>客户</label>
        <input id="MaterialCode" name="MaterialCode" placeholder="卡号" />
        <input id="Password" name="Password" value="secret-pass" />
        <script>
          var table = $('#x').DataTable({ url: '/Product/QueryListByFeeding' });
          $.post('/Production/Save', {});
        </script>
        '''
    )

    assert surface['table_headers'] == ['随行卡', '投料重量']
    assert surface['labels'] == ['客户']
    assert {'tag': 'input', 'id': 'MaterialCode', 'name': 'MaterialCode', 'placeholder': '卡号'} in surface['fields']
    assert {'path': '/Product/QueryListByFeeding', 'kind': 'read_or_page_endpoint'} in surface['endpoints']
    assert {'path': '/Production/Save', 'kind': 'write_endpoint_seen_on_page'} in surface['endpoints']
    assert 'secret-pass' not in repr(surface)


def test_page_inventory_preserves_duplicate_urls_under_different_menus() -> None:
    module = _load_script_module()
    catalog = module.inspect_sqlserver_catalog(_fake_query_runner())
    menu = module.fetch_mes_menu(_fake_query_runner())

    pages = module.build_page_inventory(menu, catalog=catalog, surface_by_url={})

    notice_pages = [page for page in pages if page['url'] == '/ContractNotice/Index']
    assert len(notice_pages) == 2
    assert notice_pages[0]['menu_label'] == '销售管理 / 生产通知单查询'
    assert notice_pages[1]['menu_label'] == '计划管理 / 生产通知单管理'


def test_audit_payload_maps_core_pages_and_does_not_leak_secrets() -> None:
    module = _load_script_module()
    calls = []

    def page_fetcher(path):
        calls.append(path)
        return '<th>字段</th><script>var x = { url: "/Product/QueryListByFeeding" };</script>'

    payload = module.inspect_mes_page_table_mapping(
        runtime_settings=_build_settings(),
        query_runner=_fake_query_runner(),
        page_fetcher=page_fetcher,
    )

    by_url = {}
    for page in payload['pages']:
        by_url.setdefault(page['url'], []).append(page)

    feeding_tables = [item['name'] for item in by_url['/Feeding/Index'][0]['source_tables']]
    pack_tables = [item['name'] for item in by_url['/Pack/Index'][0]['source_tables']]
    stock_tables = [item['name'] for item in by_url['/Stock/Index'][0]['source_tables']]
    assert 'MES_Product' in feeding_tables
    assert 'MES_ProductProcessRecord' in pack_tables
    assert 'WMS_InStockDetail' in stock_tables
    assert payload['business_day']['start_time'] == '07:30'
    assert payload['mes_home']['verified_facts'][0]['source_table'] == 'MES_Product'
    assert calls.count('/ContractNotice/Index') == 1
    assert 'mes-secret-pass' not in repr(payload)
    assert 'sql-secret-pass' not in repr(payload)
