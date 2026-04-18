# Work Orders Core Design

**Date:** 2026-03-27

## Goal

Create the foundational work-order model around MES tracking card numbers so all downstream modules can share one consistent source of truth for cross-role data entry, workshop isolation, field ownership, field locking, and audited amendments.

## Scope

- Add `work_orders`, `work_order_entries`, and `field_amendments`.
- Add role-based field ownership for work-order headers and entry fields.
- Add field-level locking once a role submits an entry.
- Add workshop-scoped visibility for operational roles.
- Add computed `previous_stage_output` on the work-order header.
- Add routers for work orders and amendments.

## Approved Visibility Rules

- `shift_leader`, `weigher`, and `qc` can read only `work_order_entries` from their own workshop.
- These operational roles can still read the work-order header for a card they can access.
- `contracts` can write contract header fields across all workshops, but cannot read or write `work_order_entries`.
- `admin`, `statistician`, and manager roles keep cross-workshop visibility.
- `previous_stage_output` is readable by all roles, writable by no role, and is computed from the latest completed entry in the immediately preceding workshop stage.

## Architecture

The implementation stays aligned with the current backend shape:

- SQLAlchemy models in `backend/app/models/production.py`
- permission and scope helpers in `backend/app/core/`
- thin routers in `backend/app/routers/`
- business logic in a new `backend/app/services/work_order_service.py`
- Pydantic request/response models in `backend/app/schemas/work_orders.py`
- schema changes in a new Alembic revision

`work_orders` stores the card-level header and system-computed rollup fields. `work_order_entries` stores workshop or shift-segment activity, including role-owned columns and status transitions. `field_amendments` records requested edits to locked fields and applies them only after approval.

## Data Model Decisions

### Work Orders

- One row per `tracking_card_no`
- `process_route_code` is parsed from the tracking card prefix and stored explicitly
- `current_station` reflects the latest active workshop/station handling the card
- `previous_stage_output` stores a small JSON snapshot of the prior completed workshop output
- `overall_status` is tracked on the header to support filtering and later orchestration

### Work Order Entries

- Each row belongs to one work order and one workshop/machine/shift/date segment
- Slow-process continuation is represented by multiple entries using `entry_type=in_progress` until a later row completes the coil
- `yield_rate` is server-computed from verified output when available, otherwise leader-entered output
- Submission is role-aware: only fields owned by the acting role become locked

### Field Amendments

- Stores old value, requested value, reason, requester, approver, and status
- Approval updates the target record, logs the change to `audit_logs`, and preserves the amendment trail

## Permission Model

Field permissions are defined centrally in `FIELD_OWNERSHIP`.

- `write` controls whether a role may send a field in create/update payloads
- `read` controls whether a field is included in serialized responses
- `*` in `read` means visible to all authorized viewers of that record
- sensitive header fields are null-filtered at serialization time if the role lacks read permission

For `work_orders`, the base readable header for operational roles includes:

- `tracking_card_no`
- `process_route_code`
- `alloy_grade`
- `overall_status`
- `current_station`
- `previous_stage_output`

Contract-sensitive fields remain hidden unless the role is explicitly allowed.

## Scope Rules

Scope enforcement is applied in service-layer query builders and uses `build_scope_summary()` from `backend/app/core/scope.py`.

- operational roles: filter entry queries to `entry.workshop_id == current_user.workshop_id`
- `contracts`: allow header queries globally, deny entry list/detail access
- `admin`, `statistician`, and manager roles: no workshop filter

Header access follows reachable-data logic:

- operational users can fetch a work order if at least one visible entry exists in their workshop, or if they are creating the first entry in their workshop
- global roles can fetch any work order

## Previous Stage Output

When an entry transitions to `entry_type=completed`, the service recomputes the parent `work_order.previous_stage_output`.

Rules:

- derive the previous stage from the ordered route implied by `process_route_code`
- find the latest completed entry from the previous workshop stage
- copy only `workshop`, `output_weight`, `output_spec`, and completion timestamp
- if no previous completed stage exists, store `null`

This gives the next workshop receiving context without exposing internal details like energy, scrap, or notes.

## Locking and Amendments

- Updating an entry checks whether any incoming field is already locked for the acting role
- `POST /work-orders/entries/{id}/submit` marks the acting role's owned fields as locked
- later edits to those fields are rejected unless applied through an approved amendment
- amendment approval writes the actual field change and logs both the approval and the underlying entity update

## Testing Strategy

- permission helper unit tests
- scope helper unit tests for workshop-local vs global visibility
- service tests for lock checks, previous-stage snapshot updates, and amendment approval
- router tests for field masking, entry visibility, and submit/amend flows using the repo's existing dependency-override pattern

## Risks To Control

- role name drift between existing users and new field-ownership mapping
- SQLite-in-tests differences for PostgreSQL JSON/enum behavior
- accidental exposure of hidden fields through direct model serialization
- over-broad work-order lookup that leaks cross-workshop entries
