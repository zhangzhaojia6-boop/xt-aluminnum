"""G2 — `daily_consumable_logs.payload` field-name lock (truth-source §3.2).

Real ground-truth columns from 底层/2026-5-24 班长统计耗材.xls. The shift
leader owner-agent must emit exactly these keys; anything else stays in
the `extra` dict but does not get fed into reconciliation / report
templates.

Why pydantic and not a plain set: we want `model_validate()` at the
agent boundary so a schema drift surfaces as a 422 rather than silently
landing as a typo'd jsonb key.
"""

from __future__ import annotations

from typing import Optional

from pydantic import BaseModel, ConfigDict, Field


class _CompareGroup(BaseModel):
    """daily / monthly / target / compare(arrow text or delta)."""

    model_config = ConfigDict(extra='forbid')

    daily: Optional[float] = None
    monthly: Optional[float] = None
    target: Optional[float] = None
    compare: Optional[str] = None


class CastingPerTonGroup(BaseModel):
    """Casting workshop per-ton consumables (铸轧 — 真值底 #12)."""

    model_config = ConfigDict(extra='forbid')

    liquefied_gas_per_ton: Optional[float] = None
    titanium_wire_per_ton: Optional[float] = None
    steel_strip_per_ton: Optional[float] = None
    magnesium_per_ton: Optional[float] = None
    manganese_per_ton: Optional[float] = None
    iron_per_ton: Optional[float] = None
    copper_per_ton: Optional[float] = None


class ConsumablePayload(BaseModel):
    """Locked schema for `daily_consumable_logs.payload`.

    Energy + gas use `_CompareGroup` (4-tuple per metric) so the
    daily-report renderer can quote 当日/月累计/指标/对比 in one shot.
    Hydraulic / gear oil follow the same shape per 真值底 #12 列头.
    """

    model_config = ConfigDict(extra='forbid')

    electricity: _CompareGroup = Field(default_factory=_CompareGroup)
    gas: _CompareGroup = Field(default_factory=_CompareGroup)

    casting_per_ton: Optional[CastingPerTonGroup] = None

    hydraulic_oil: _CompareGroup = Field(default_factory=_CompareGroup)
    gear_oil: _CompareGroup = Field(default_factory=_CompareGroup)


CONSUMABLE_PAYLOAD_FIELDS_FLAT: tuple[str, ...] = (
    'electricity_daily',
    'electricity_monthly',
    'electricity_target',
    'electricity_compare',
    'gas_daily',
    'gas_monthly',
    'gas_target',
    'gas_compare',
    'liquefied_gas_per_ton',
    'titanium_wire_per_ton',
    'steel_strip_per_ton',
    'magnesium_per_ton',
    'manganese_per_ton',
    'iron_per_ton',
    'copper_per_ton',
    'hydraulic_oil_daily',
    'hydraulic_oil_monthly',
    'hydraulic_oil_target',
    'hydraulic_oil_compare',
    'gear_oil_daily',
    'gear_oil_monthly',
    'gear_oil_target',
    'gear_oil_compare',
)


def flatten_payload(payload: ConsumablePayload) -> dict:
    """Flatten nested groups to the single-level field names listed in
    CONSUMABLE_PAYLOAD_FIELDS_FLAT, matching how 真值底 #12 renders.

    Nested per-ton fields stay flat (one row per metric).
    """

    out: dict = {}
    for prefix, group in (
        ('electricity', payload.electricity),
        ('gas', payload.gas),
        ('hydraulic_oil', payload.hydraulic_oil),
        ('gear_oil', payload.gear_oil),
    ):
        for key in ('daily', 'monthly', 'target', 'compare'):
            value = getattr(group, key)
            if value is not None:
                out[f'{prefix}_{key}'] = value

    if payload.casting_per_ton is not None:
        for field in CastingPerTonGroup.model_fields:
            value = getattr(payload.casting_per_ton, field)
            if value is not None:
                out[field] = value
    return out


def parse_payload(raw: dict | None) -> ConsumablePayload:
    """Inverse of flatten_payload — accepts either nested or the flat form
    used in DB jsonb storage."""

    raw = raw or {}
    if any(k in raw for k in ('electricity', 'gas', 'hydraulic_oil', 'gear_oil', 'casting_per_ton')):
        return ConsumablePayload.model_validate(raw)

    grouped: dict = {
        'electricity': {},
        'gas': {},
        'hydraulic_oil': {},
        'gear_oil': {},
    }
    casting: dict = {}
    for key, value in raw.items():
        matched_group = False
        for prefix in ('electricity', 'gas', 'hydraulic_oil', 'gear_oil'):
            for suffix in ('_daily', '_monthly', '_target', '_compare'):
                if key == f'{prefix}{suffix}':
                    grouped[prefix][suffix.lstrip('_')] = value
                    matched_group = True
                    break
            if matched_group:
                break
        if matched_group:
            continue
        if key in CastingPerTonGroup.model_fields:
            casting[key] = value
    payload_dict: dict = {k: v for k, v in grouped.items() if v}
    if casting:
        payload_dict['casting_per_ton'] = casting
    return ConsumablePayload.model_validate(payload_dict)
