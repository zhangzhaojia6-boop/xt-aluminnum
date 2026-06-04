from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict


class ConsumablePayload(BaseModel):
    """Field lock for ``daily_consumable_logs.payload`` jsonb.

    Defines the authoritative whitelist of keys allowed inside the consumable
    log payload. Any key not declared here is rejected by ``extra='forbid'``.
    Source: docs/truth-source-three-layer-schema.md sec. 3.2 G2.
    """

    model_config = ConfigDict(extra='forbid')

    electricity_daily: float | None = None
    electricity_monthly: float | None = None
    electricity_target: float | None = None
    electricity_compare: str | None = None

    gas_daily: float | None = None
    gas_monthly: float | None = None
    gas_target: float | None = None
    gas_compare: str | None = None

    liquefied_gas_per_ton: float | None = None
    titanium_wire_per_ton: float | None = None
    steel_strip_per_ton: float | None = None
    magnesium_per_ton: float | None = None
    manganese_per_ton: float | None = None
    iron_per_ton: float | None = None
    copper_per_ton: float | None = None

    hot_roll_emulsion_per_ton: float | None = None
    rolling_oil_per_ton: float | None = None
    filter_agent_per_ton: float | None = None
    diatomite_per_ton: float | None = None
    white_earth_per_ton: float | None = None
    filter_cloth_daily: float | None = None
    high_temp_tape_daily: float | None = None
    regen_oil_out: float | None = None
    regen_oil_in: float | None = None
    d40_per_ton: float | None = None
    steel_plate_per_ton: float | None = None
    steel_buckle_per_ton: float | None = None
    paint_per_ton: float | None = None
    packaging_inbound_output_tons: float | None = None

    hydraulic_oil_daily: float | None = None
    hydraulic_oil_monthly: float | None = None
    hydraulic_oil_target: float | None = None
    hydraulic_oil_compare: str | None = None

    gear_oil_daily: float | None = None
    gear_oil_monthly: float | None = None
    gear_oil_target: float | None = None
    gear_oil_compare: str | None = None


def validate_consumable_payload(raw: dict[str, Any]) -> dict[str, Any]:
    """Validate a raw payload dict against the field lock.

    Returns the cleaned dict (with ``None`` values stripped). Raises
    ``pydantic.ValidationError`` on unknown keys or wrong types.
    """

    model = ConsumablePayload.model_validate(raw)
    return model.model_dump(exclude_none=True)
