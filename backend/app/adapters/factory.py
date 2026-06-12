from __future__ import annotations

from app.adapters.mes_adapter import MesAdapter, NullMesAdapter
from app.config import Settings, settings


def create_mes_adapter(runtime_settings: Settings = settings) -> MesAdapter:
    adapter_name = (runtime_settings.MES_ADAPTER or 'null').strip().lower()
    if adapter_name == 'null':
        return NullMesAdapter()
    if adapter_name == 'rest_api':
        from app.adapters.rest_api_mes_adapter import RestApiMesAdapter

        return RestApiMesAdapter(
            base_url=str(runtime_settings.MES_API_BASE or '').strip(),
            api_key=runtime_settings.MES_API_KEY,
            timeout_seconds=runtime_settings.MES_API_TIMEOUT_SECONDS,
            tracking_card_info_path=runtime_settings.mes_api_tracking_card_info_path_normalized,
            coil_snapshots_path=runtime_settings.mes_api_coil_snapshots_path_normalized,
        )
    if adapter_name in {'xintai', 'xintai_api'}:
        from app.adapters.xintai_mes_adapter import XintaiMesAdapter

        return XintaiMesAdapter(
            base_url=str(runtime_settings.MES_API_BASE or '').strip(),
            api_key=str(runtime_settings.MES_API_KEY or '').strip(),
            timeout_seconds=runtime_settings.MES_API_TIMEOUT_SECONDS,
        )
    if adapter_name == 'mvc':
        from app.adapters.mvc_mes_adapter import MvcMesAdapter

        return MvcMesAdapter(
            base_url=str(runtime_settings.MES_MVC_BASE_URL or '').strip(),
            username=str(runtime_settings.MES_MVC_USERNAME or '').strip(),
            password=str(runtime_settings.MES_MVC_PASSWORD or ''),
            timeout_seconds=runtime_settings.MES_MVC_TIMEOUT_SECONDS,
        )
    if adapter_name == 'sqlserver':
        from app.adapters.sqlserver_mes_adapter import SqlServerMesAdapter

        return SqlServerMesAdapter(
            host=str(runtime_settings.MES_SQLSERVER_HOST or '').strip(),
            port=runtime_settings.MES_SQLSERVER_PORT,
            database=str(runtime_settings.MES_SQLSERVER_DATABASE or '').strip(),
            username=str(runtime_settings.MES_SQLSERVER_USERNAME or '').strip(),
            password=str(runtime_settings.MES_SQLSERVER_PASSWORD or ''),
            timeout_seconds=runtime_settings.MES_SQLSERVER_TIMEOUT_SECONDS,
            encrypt=runtime_settings.MES_SQLSERVER_ENCRYPT,
        )
    raise RuntimeError(f'Unsupported MES_ADAPTER: {runtime_settings.MES_ADAPTER}')
