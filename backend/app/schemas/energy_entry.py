from __future__ import annotations

from datetime import date

from pydantic import BaseModel, Field


class ShiftEnergyEntryIn(BaseModel):
    business_date: date
    workshop_code: str = Field(min_length=1, max_length=64)
    shift_code: str = Field(min_length=1, max_length=64)
    electricity_value: float | None = Field(default=None, ge=0)
    gas_value: float | None = Field(default=None, ge=0)
    water_value: float | None = Field(default=None, ge=0)
    note: str | None = Field(default=None, max_length=1000)


class ShiftEnergyEntryOut(ShiftEnergyEntryIn):
    total_energy: float | None = None
    energy_per_ton: float | None = None

