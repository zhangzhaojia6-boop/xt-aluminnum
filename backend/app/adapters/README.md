# MES Adapter Contract

This package defines the integration seam for a future MES vendor adapter. The current system uses `NullMesAdapter`, which performs no external calls and preserves today's manual workflow.

## Goal

Implement one concrete adapter class, for example `RestApiMesAdapter`, that satisfies the `MesAdapter` interface in [mes_adapter.py](/D:/zzj%20Claude%20code/aluminum-bypass/backend/app/adapters/mes_adapter.py). Once it exists, operations can switch from the null adapter by changing one configuration value: `MES_ADAPTER`.

## Interface

### `get_tracking_card_info(card_no: str) -> CardInfo | None`

Use this when a work order is first created from a tracking card number.

Input:
- `card_no`: MES tracking card number, already normalized to uppercase text.

Output:
- Return `CardInfo` when MES recognizes the card.
- Return `None` when MES has no data for the card or when the adapter chooses to degrade gracefully.

Required fields on `CardInfo`:
- `card_no: str`
- `process_route_code: str | None`
- `alloy_grade: str | None`
- `batch_no: str | None`
- `qr_code: str | None`

Behavior requirements:
- `process_route_code` should be the MES route code that the backend stores on `work_orders.process_route_code`.
- `alloy_grade` should be the alloy grade to prefill on the work order header.
- `batch_no` should carry the MES batch clue when available.
- `qr_code` should carry the MES card QR clue when available.
- Extra vendor fields may be placed in `metadata`.

### `list_coil_snapshots(cursor: str | None, updated_after: datetime | None, limit: int = 200) -> tuple[list[CoilSnapshot], str | None]`

Use this when the backend needs to mirror MES coil-level flow into a local read model.

Input:
- `cursor`: adapter-defined incremental cursor
- `updated_after`: fallback time window for replay-safe polling
- `limit`: max batch size for one poll

Output:
- Return a tuple of `(snapshots, next_cursor)`
- `snapshots` may be empty
- `next_cursor` may be the same as incoming cursor when the vendor API has no new cursor

Required `CoilSnapshot` fields:
- `coil_id: str`
- `tracking_card_no: str`
- `qr_code: str | None`
- `batch_no: str | None`
- `contract_no: str | None`
- `workshop_code: str | None`
- `process_code: str | None`
- `machine_code: str | None`
- `shift_code: str | None`
- `status: str | None`
- `event_time: datetime | None`
- `updated_at: datetime | None`

Behavior requirements:
- `coil_id` must be stable and unique for idempotent upserts
- `updated_at` should reflect the latest MES-side update time for the coil snapshot
- adapter must tolerate duplicate/overlapping windows so the sync service can replay safely

### `get_daily_schedule(business_date: date, workshop: str) -> list[ScheduleItem]`

Reserved for future scheduling integration.

Input:
- `business_date`: target production date.
- `workshop`: canonical workshop identifier or name.

Output:
- Return a list of `ScheduleItem`.
- Return an empty list when no schedule is available.

Recommended `ScheduleItem` fields:
- `tracking_card_no: str`
- `workshop: str`
- `machine: str | None`
- `shift: str | None`
- `planned_input_weight: float | None`
- `planned_output_weight: float | None`
- `metadata: dict[str, Any]`

### `push_completion(card_no: str, output_weight: float | None, yield_rate: float | None) -> bool`

Use this when the backend has marked a work order as fully completed.

Input:
- `card_no`: tracking card number.
- `output_weight`: final output weight for the completion event.
- `yield_rate`: computed yield percentage for the completion event.

Output:
- Return `True` when the MES accepted the completion push.
- Return `False` when the push was skipped, declined, or failed in a recoverable way.

## Error Handling Requirements

The adapter must not break core production entry flows.

Recommended rules:
- For recoverable read failures in `get_tracking_card_info`, log internally and return `None`.
- For recoverable read failures in `get_daily_schedule`, log internally and return `[]`.
- For recoverable write failures in `push_completion`, log internally and return `False`.
- Only raise exceptions for programmer errors or unrecoverable configuration mistakes, such as missing credentials at startup.

The backend treats MES access as optional. If MES is unavailable, users must still be able to create and complete work orders manually.

## Authentication Pattern

The concrete adapter may use either of these patterns:
- API key: recommended for simple server-to-server integration.
- OAuth2 client credentials: recommended when the MES vendor requires token-based authorization.

Implementation guidance:
- Read credentials from environment-backed settings, never hard-code them.
- Cache tokens if OAuth2 is used.
- Apply request timeouts and retries with conservative limits.
- Keep secrets out of logs and audit payloads.

## Configuration

Current setting:
- `MES_ADAPTER=null`

Future example:
- `MES_ADAPTER=rest_api`
- `MES_API_BASE=https://mes.example.com/api/v1`
- `MES_API_TRACKING_CARD_INFO_PATH=/tracking-cards/{card_no}`
- `MES_API_COIL_SNAPSHOTS_PATH=/coil-snapshots`

When a real adapter is added, update the factory in [main.py](/D:/zzj%20Claude%20code/aluminum-bypass/backend/app/main.py) to instantiate it for the new config value.
