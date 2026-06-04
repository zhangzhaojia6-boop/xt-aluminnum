"""Test G2 — `daily_consumable_logs.payload` field-name lock contract."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from app.core.templates.consumable_payload import (
    CONSUMABLE_PAYLOAD_FIELDS_FLAT,
    ConsumablePayload,
    flatten_payload,
    parse_payload,
)


def test_flat_fields_match_truth_source_5_24():
    assert 'electricity_daily' in CONSUMABLE_PAYLOAD_FIELDS_FLAT
    assert 'gas_compare' in CONSUMABLE_PAYLOAD_FIELDS_FLAT
    assert 'liquefied_gas_per_ton' in CONSUMABLE_PAYLOAD_FIELDS_FLAT
    assert 'hydraulic_oil_target' in CONSUMABLE_PAYLOAD_FIELDS_FLAT
    assert 'gear_oil_monthly' in CONSUMABLE_PAYLOAD_FIELDS_FLAT
    assert 'packaging_inbound_output_tons' in CONSUMABLE_PAYLOAD_FIELDS_FLAT
    assert len(CONSUMABLE_PAYLOAD_FIELDS_FLAT) == 37


def test_unknown_field_rejected():
    with pytest.raises(ValidationError):
        ConsumablePayload.model_validate({'electricity': {'daily_typo': 1.0}})


def test_round_trip_flat_parse_then_flatten():
    raw = {
        'electricity_daily': 12345.6,
        'electricity_target': 13000,
        'gas_daily': 800,
        'gas_compare': '↓',
        'liquefied_gas_per_ton': 12.3,
        'd40_per_ton': 0.2,
        'packaging_inbound_output_tons': 18.5,
        'hydraulic_oil_target': 1.0,
        'gear_oil_monthly': 30.0,
    }
    payload = parse_payload(raw)
    assert payload.electricity.daily == 12345.6
    assert payload.gas.compare == '↓'
    assert payload.casting_per_ton is not None
    assert payload.casting_per_ton.liquefied_gas_per_ton == 12.3

    flat = flatten_payload(payload)
    assert flat['electricity_daily'] == 12345.6
    assert flat['gas_compare'] == '↓'
    assert flat['liquefied_gas_per_ton'] == 12.3
    assert flat['d40_per_ton'] == 0.2
    assert flat['packaging_inbound_output_tons'] == 18.5
    assert flat['hydraulic_oil_target'] == 1.0
    assert flat['gear_oil_monthly'] == 30.0


def test_empty_payload_round_trip():
    payload = parse_payload(None)
    assert flatten_payload(payload) == {}


def test_quality_issue_fields_not_in_entry_fields():
    """G11 — quality-issue fields are handled by the frontend interactive
    module, NOT duplicated in template entry_fields."""
    from app.core.templates import DEFAULT_WORKSHOP_TEMPLATES

    quality_keys = {
        'quality_note',
        'quality_issue_type',
        'quality_issue_card_no',
        'quality_issue_desc',
        'quality_issue_photo_path',
    }
    for workshop_type in ('cold_roll', 'hot_roll', 'casting', 'finishing', 'shearing', 'straightening'):
        template = DEFAULT_WORKSHOP_TEMPLATES[workshop_type]
        names = {field['name'] for field in template['entry_fields']}
        overlap = quality_keys & names
        assert not overlap, f'{workshop_type} should not have quality fields in entry_fields: {overlap}'
