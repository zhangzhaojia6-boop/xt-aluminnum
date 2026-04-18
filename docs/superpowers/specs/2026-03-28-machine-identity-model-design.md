# Machine Identity Model Design

**Date:** 2026-03-28

## Goal

Build a production-ready "one machine = one account" identity model so each machine can have its own login, QR code, shift configuration, operational status, and machine-specific consumable fields while preserving hard data isolation in the mobile reporting flow.

## Scope

- Extend the master-data model so `Equipment` becomes a true machine runtime entity instead of a simple lookup table.
- Add one-machine-one-account binding between `equipment` and `users`.
- Support per-machine shift assignment, on/off/maintenance state, QR code identity, and per-machine custom fields.
- Seed real workshop and equipment data for the revised factory structure.
- Add admin-only machine creation, PIN reset, status toggle, and field management APIs.
- Update mobile bootstrap and mobile entry behavior so machine-bound users only see their own machine.
- Add QR login for machine accounts.
- Add an equipment management UI and machine creation wizard in the frontend.

## Updated Product Decisions

- The revised workshop seed becomes:
  - `ZD` 铸锭车间
  - `ZR2` 铸二车间
  - `ZR3` 铸三车间
  - `RZ` 热轧车间
  - `LZ2050` 2050冷轧车间
  - `LZ1450` 1450冷轧车间
  - `LZ3` 冷轧三车间
  - `JZ` 精整车间
  - `JZ2` 二分厂精整车间
  - `JQ` 园区剪切车间
  - `CPK` 成品库
- QR flow now uses direct machine auto-login and no longer follows the earlier "prefill username, enter PIN" fallback.
- A machine account is still modeled as a normal `User`, but it is identified by an `Equipment.bound_user_id` binding rather than a special standalone auth subsystem.
- Machine custom fields are additive and merge into the existing workshop template rather than replacing it.

## Architecture

The implementation should stay aligned with the current repo shape:

- SQLAlchemy models stay under `backend/app/models/`
- routers stay thin under `backend/app/routers/`
- new machine-specific write logic lives in `backend/app/services/equipment_service.py`
- mobile scope resolution stays in the existing mobile service layer rather than adding a second bootstrap path
- master-data schemas stay in `backend/app/schemas/master.py`
- auth request and response models stay in `backend/app/schemas/auth.py`
- frontend master-data screens stay under `frontend/src/views/master/`
- machine-bound mobile behavior stays inside `frontend/src/views/mobile/`

The implementation introduces a new concept without replacing current role-based auth:

1. admin creates or seeds a machine
2. backend creates or updates the `Equipment` record
3. backend creates a bound `User` account and PIN
4. backend generates a machine QR code
5. mobile login resolves whether the current user is machine-bound
6. machine-bound users receive a single-machine scope
7. mobile form merges workshop template fields with machine custom fields
8. writes are rejected if the target machine does not match the bound machine

## Data Model

## Revised Workshop Seed

The real master-data seed must use the revised workshop list above and stop exposing any legacy sample workshops through the active master-data APIs.

## Equipment

Extend `backend/app/models/master.py` `Equipment` with:

- `operational_status: String(20)` default `stopped`
- `shift_mode: String(10)` default `three`
- `assigned_shift_ids: JSONB | null`
- `custom_fields: JSONB | null`, default list
- `qr_code: String(100) | null`, unique
- `bound_user_id: Integer | null`, FK to `users.id`
- `sort_order: Integer`, default `0`
- relationship `bound_user = relationship('User', foreign_keys=[bound_user_id])`

Existing fields such as `code`, `name`, `workshop_id`, `equipment_type`, `spec`, and `is_active` stay in place.

### Field Semantics

- `operational_status`
  - `running`: machine is live and can report
  - `stopped`: machine cannot log in or submit
  - `maintenance`: machine exists but cannot report production
- `shift_mode`
  - `two`
  - `three`
- `assigned_shift_ids`
  - explicit per-machine shift availability
  - when null, machine inherits all active shifts available to the workshop
- `custom_fields`
  - machine-specific consumables or extra inputs
  - stored as ordered JSON objects with `name`, `label`, `type`, `unit`
- `qr_code`
  - generated as `XT-{workshop_code}-{equipment_code}`
- `bound_user_id`
  - one machine maps to one account

## User

Extend `backend/app/models/system.py` `User` with:

- `pin_code: String(6) | null`

`pin_code` is admin-visible for machine accounts and is separate from `password_hash`.

Rules:

- `password_hash` remains the actual login secret
- `pin_code` stores the current clear PIN for display/reset workflows
- resetting a PIN updates both `pin_code` and `password_hash`

## Work Order / Entry Storage

Machine custom-field values need a persisted home when the mobile form is submitted. The clean path is to store them in a JSON field on the production entry/work-order entry model that already represents machine work.

Implementation target:

- add or reuse a JSON payload column such as `field_values` on the entry record
- standard template fields remain as first-class columns
- machine custom fields are stored in `field_values`

This keeps analytics on core metrics simple while still preserving flexible machine-specific payloads.

## Seed Data

## Equipment Seed Rules

The revised real master-data seed must:

- update the workshop list to the new 11-workshop set
- seed revised equipment defaults for `ZD`, `ZR2`, `ZR3`, `RZ`, `LZ2050`, `LZ1450`
- keep `JZ`, `JZ2`, and `JQ` seed data from the current real-machine seed unless superseded
- set operational status and shift mode during seeding
- set per-machine `assigned_shift_ids` where the machine is two-shift only
- set machine custom fields for:
  - all `ZR2` machines using the 辅助材料使用明细表 fields
  - `RZ-ZJ` or hot-roll machines using the specified trim/oil fields
- remain idempotent and safe to run repeatedly

## Machine Account Service

Create `backend/app/services/equipment_service.py`.

### `create_machine_with_account(...)`

Responsibilities:

1. validate workshop and machine code uniqueness
2. create `Equipment`
3. generate machine username
4. generate 6-digit cryptographically safe PIN
5. create bound `User`
6. link `Equipment.bound_user_id`
7. generate `Equipment.qr_code`
8. return account summary once

### Username Normalization

Base format:

- `{workshop.code}-{machine_code}`

Normalization requirements:

- lowercase or uppercase consistency must be deterministic across create, seed, reset, and QR flows
- strip spaces
- preserve hyphen separators
- remove unsupported punctuation

Recommendation:

- store usernames in uppercase to stay visually aligned with machine codes already used on the factory floor

### Status and Account Coupling

- `running` -> bound user `is_active = true`
- `stopped` -> bound user `is_active = false`
- `maintenance` -> bound user `is_active = false`

This is the hard gate that prevents stopped machines from logging in.

### Reset PIN

`POST /master/equipment/{id}/reset-pin`

Behavior:

- generate new 6-digit PIN
- update `users.pin_code`
- update `users.password_hash`
- return `username` and `new_pin`
- do not expose old PIN again

### Toggle Status

`POST /master/equipment/{id}/toggle-status`

Behavior:

- update `equipment.operational_status`
- synchronize `bound_user.is_active`
- return updated machine summary

## Auth and QR Flow

## QR Login Endpoint

Add `POST /auth/qr-login`.

Input:

```json
{ "qr_code": "XT-ZR2-1" }
```

Behavior:

- find machine by `qr_code`
- if machine not found -> `404 未找到该机台`
- if machine not `running` -> `403 该机台已停机`
- if no bound account -> `404 该机台未绑定账号，请联系管理员`
- if valid -> generate JWT for bound user and return:
  - `access_token`
  - `token_type`
  - `user`
  - `machine_info`

The token payload should also include machine context where feasible so downstream services can cheaply identify machine-bound sessions.

## Login Resolution

Normal username/password login still works for machine accounts. The QR path is additive.

Machine-bound users are identified by:

- `Equipment.bound_user_id == current_user.id`

## Mobile Scope Model

## Machine-Bound Bootstrap

Update the existing mobile bootstrap/current-shift service path so machine-bound users:

- do not select a machine
- receive:
  - `machine_id`
  - `machine_name`
  - `machine_code`
  - `workshop_id`
  - `workshop_name`
  - `is_machine_bound`
- only resolve shifts from:
  - `equipment.assigned_shift_ids` when present
  - otherwise all workshop shifts

Current shift resolution should use:

- Asia/Shanghai server time
- existing `ShiftConfig` windows
- machine-specific shift filtering

## Hard Isolation Rule

Add `assert_machine_scope(current_user, target_machine_id)`.

Rules:

- admin bypass allowed
- non-machine users continue using existing workshop/team/shift scope logic
- machine-bound user may only act on the bound machine
- any write for another machine returns `403 无权操作此机台`

This check must be enforced in all mobile endpoints that save, submit, upload photos, or otherwise mutate production data.

## Frontend Design

## Equipment Management

Create or expand `frontend/src/views/master/Equipment.vue` with:

- columns:
  - 编码
  - 名称
  - 车间
  - 机器类型
  - 班制
  - 运行状态
  - 绑定账号
  - 二维码
  - 操作
- actions:
  - 编辑
  - 自定义字段
  - 生成二维码
  - 启停
  - 重置密码

Status badges should visually distinguish:

- `running`
- `stopped`
- `maintenance`

## Machine Wizard

Create `frontend/src/views/master/MachineWizard.vue`.

Steps:

1. 基本信息
2. 班次配置
3. 耗材字段配置
4. 账号生成
5. 完成

Important rule:

- any PIN preview before save is only a draft preview
- final credential values shown on the success card must come from backend response

## QR Code Display

Admin QR dialog should render a printable machine card containing:

- 鑫泰铝业
- 车间
- 机台名
- QR image
- 账号
- 密码

## Mobile Entry

For machine-bound users:

- hide machine selector
- show prominent header like `铸二车间 · 3#机 · 白班`
- only keep the direct reporting flow
- load workshop template and merge machine `custom_fields`

Field merge order:

1. workshop template fields
2. workshop extra fields
3. machine custom fields in a separate `机台耗材` section

## Dashboard Behavior

For two-shift machines:

- only machine-applicable shifts count as available
- non-applicable shift cells should be greyed out or omitted according to the existing dashboard grid structure

The statistics view must not imply that a stopped or two-shift machine is missing a third shift report when that shift is not assigned.

## API Surface

New or changed backend endpoints:

- `POST /master/equipment/create-with-account`
- `POST /master/equipment/{id}/reset-pin`
- `POST /master/equipment/{id}/toggle-status`
- `PATCH /master/equipment/{id}` for custom field and shift updates if not already present
- `GET /master/equipment/{id}` with machine runtime fields
- `POST /auth/qr-login`

## Error Handling

- duplicate machine code -> `400` with clear machine-code conflict message
- duplicate username or QR code -> `400`
- stopped or maintenance machine login -> `403`
- machine-bound user targeting a different machine -> `403`
- invalid shift selections for `two` mode -> `400`
- missing bound user on machine actions that require account lifecycle changes -> `400`

## Testing

Backend tests should cover:

- migration columns exist
- create machine with account
- reset PIN invalidates old password
- toggle stopped/maintenance disables login
- QR login success/failure cases
- machine-bound bootstrap returns single-machine scope
- mobile write endpoints reject cross-machine access
- machine custom fields merge into mobile response shape
- two-shift filtering affects bootstrap and aggregation behavior

Frontend tests or verification should cover:

- machine wizard happy path
- QR auto-login query flow
- machine-bound mobile entry hides selectors
- equipment screen actions call the new APIs correctly

## Risks and Constraints

- auto-login QR is intentionally less strict than PIN entry; physical QR possession becomes the credential
- storing `pin_code` in plaintext is an explicit product tradeoff and should be limited to admin-visible surfaces
- machine-specific custom fields will increase form variability, so backend validation should keep unknown payloads boxed into JSON rather than exploding the schema
- current repo has no dedicated equipment management page yet, so this work will create a new primary admin surface rather than just extend an existing one
