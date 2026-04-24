from __future__ import annotations

from typing import Literal

from pydantic import BaseModel


CommandSurface = Literal['entry', 'review', 'admin']
CommandStatus = Literal['success', 'warning', 'danger', 'pending', 'normal']


class CommandKpiOut(BaseModel):
    label: str
    value: str
    unit: str = ''
    trend: str = ''
    status: CommandStatus = 'normal'
    icon_key: str = ''


class CommandActionOut(BaseModel):
    label: str
    route_name: str
    access: str


class CommandTrendPointOut(BaseModel):
    label: str
    value: float


class CommandModuleOut(BaseModel):
    module_id: str
    title: str
    surface: CommandSurface
    kpis: list[CommandKpiOut] = []
    status_summary: list[str] = []
    primary_rows: list[dict] = []
    trend_series: list[CommandTrendPointOut] = []
    actions: list[CommandActionOut] = []
    updated_at: str = ''


class CommandSurfaceResponseOut(BaseModel):
    surface: CommandSurface
    modules: list[CommandModuleOut]
