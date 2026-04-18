# Photo-To-Form OCR Design

**Date:** 2026-03-28

## Goal

Add a photo-to-form OCR workflow for high-temperature workshops so a shift leader can photograph a paper form, review machine-extracted values, and then continue through the existing work-order entry and submit flow without introducing a second source of truth.

## Scope

- Add OCR runtime dependencies to the backend Python environment.
- Add OCR image preprocessing and field extraction service logic.
- Add persistent OCR submission records and image evidence storage.
- Add OCR extract and verify APIs for mobile users.
- Hand verified OCR values into the existing dynamic work-order entry form.
- Add a mobile OCR capture and review view for OCR-enabled workshops.

## Approved Product Decisions

- `POST /ocr/verify` does not create or submit a `work_order_entry`.
- The canonical create/update/submit path remains the existing work-order flow.
- `OCRCapture.vue` handles image upload, OCR review, and corrected-value confirmation.
- `DynamicEntryForm.vue` remains the final human verification and submission screen.
- Original photos are retained as audit evidence and linked back to the resulting work-order entry.

## Architecture

The implementation stays aligned with the current application shape:

- SQLAlchemy models remain in `backend/app/models/production.py`
- routers stay thin under `backend/app/routers/`
- OCR extraction and persistence logic lives in `backend/app/services/ocr_service.py`
- work-order linkage continues through `backend/app/services/work_order_service.py`
- request and response models live in `backend/app/schemas/`
- schema changes land in a new Alembic revision
- mobile UI changes stay under `frontend/src/views/mobile/`

The OCR flow becomes a preparation stage ahead of the existing entry workflow:

1. user captures a paper form photo
2. backend stores the image and runs OCR
3. OCR result is saved as an `ocr_submissions` record
4. user reviews and corrects extracted values
5. backend stores verified values
6. frontend opens `DynamicEntryForm.vue` with OCR-prefilled data
7. normal work-order APIs create, update, and submit the entry

## Data Model

### OCR Submissions

Add `ocr_submissions` with:

- `id`
- `image_path`
- `workshop_type`
- `extracted_json`
- `verified_json`
- `linked_entry_id`
- `status`
- `created_by`
- `created_at`

Status values:

- `pending_review`
- `verified`
- `rejected`

`extracted_json` stores raw OCR output and machine confidence. `verified_json` stores the corrected values that were accepted by the operator before handoff into the entry form.

### Work Order Entry Linkage

The existing `work_order_entries` create payload gains optional `ocr_submission_id`.

Rules:

- if present, the OCR record must exist
- only the creating user or an authorized global role may attach it
- once the entry is created, `ocr_submissions.linked_entry_id` is updated
- the image remains immutable evidence and is never overwritten

## Storage Design

Images are stored below the already-mounted uploads root:

- `uploads/ocr/<yyyy>/<mm>/<uuid>.<ext>`

This keeps OCR evidence inside the current `/uploads` static mount and follows the existing photo-storage pattern used by mobile reporting.

Allowed upload extensions should mirror the mobile photo flow:

- `.jpg`
- `.jpeg`
- `.png`
- `.webp`

The OCR service should reject oversized or unsupported files with clear 400 responses.

## OCR Service Design

`backend/app/services/ocr_service.py` exposes two main functions.

### `preprocess_image(image_bytes)`

Steps:

- decode bytes with OpenCV
- convert to grayscale
- apply adaptive thresholding for handwritten and low-contrast forms
- estimate dominant line angle
- deskew using the detected angle when the rotation is meaningful

The goal is not perfect document understanding. The goal is to produce a stable, high-contrast image that gives Tesseract the best chance on workshop paper forms photographed by phone.

### `extract_fields(image_bytes, workshop_template_type)`

Steps:

- load the workshop template so extraction only targets relevant fields
- preprocess the image
- run Tesseract with `chi_sim+eng`
- collect raw OCR text and word-level confidence data
- derive field candidates from template labels, field names, and numeric patterns
- apply regex cleanup for numeric fields such as weights, gas, temperatures, and speed
- return a normalized payload

Return shape:

```json
{
  "raw_text": "...",
  "fields": {
    "input_weight": { "value": "9430", "confidence": 0.85 },
    "output_weight": { "value": "9220", "confidence": 0.91 }
  },
  "image_id": "uuid"
}
```

## Template-Aware Extraction Rules

The OCR service should reuse workshop template metadata instead of hardcoding one global paper form.

Rules:

- only OCR-enabled workshop types can call the OCR endpoints
- extraction targets both `entry_fields` and `extra_fields`
- unsupported fields are ignored even if OCR text happens to contain matching words
- numeric cleanup is only applied to fields that are structurally numeric
- missing or low-confidence values remain editable and are not treated as valid submission data by themselves

This keeps the OCR flow aligned with the same workshop-specific template logic already used by the manual mobile form.

## API Design

### `POST /ocr/extract`

Auth:

- mobile user auth, same as current mobile routes

Input:

- multipart `file`
- form `workshop_type`

Behavior:

- validate workshop type and that it supports OCR
- store image under `uploads/ocr/...`
- run OCR extraction
- insert `ocr_submissions` with `pending_review`
- return `ocr_submission_id`, `image_url`, `raw_text`, and extracted fields

### `POST /ocr/verify`

Auth:

- mobile user auth

Input:

- `ocr_submission_id`
- corrected field map
- optional rejected flag when the operator decides the OCR result is unusable

Behavior:

- validate record ownership and status
- persist corrected values to `verified_json`
- mark status `verified` or `rejected`
- when verified, return a normalized handoff payload that `DynamicEntryForm.vue` can use directly

The normalized handoff payload should map into the same structure the form already expects:

- work-order header values like `alloy_grade`
- standard entry values
- `extra_payload`
- `qc_payload`
- `ocr_submission_id`

## Frontend Flow

### Mobile Entry Landing

For OCR-enabled workshop types such as `casting` and `hot_rolling`, `MobileEntry.vue` shows:

- `手动填写`
- `拍照识别`

Other workshops keep the standard manual flow only.

### OCR Capture View

`OCRCapture.vue` handles:

- camera or file capture
- photo preview
- OCR extract request
- confidence-tagged field review
- correction before handoff

Field confidence display:

- green: `>= 85%`
- yellow: `60% - 84%`
- red: `< 60%`

Yellow and red values stay visually highlighted so the operator is nudged to review them.

### Dynamic Entry Handoff

After verification, the app routes into `DynamicEntryForm.vue` with OCR-prefill state.

Requirements:

- final form layout still comes from the workshop template
- OCR-prefilled values appear as normal editable values
- the form should visually note that a value came from OCR and show confidence where practical
- final save and submit buttons continue using the existing work-order APIs

This preserves one consistent final step regardless of whether the operator typed values manually or started from OCR.

## Permissions And Audit

- OCR routes use mobile-user auth and workshop scope
- only OCR-enabled workshop types may use OCR
- `ocr_submissions` are user-owned by default within operational scope
- the photo path and verified JSON are preserved for evidence
- linking an OCR record to a work-order entry is recorded through the existing audit flow when the entry is created or updated

No OCR result bypasses field ownership, locking, or amendment rules because only the normal work-order flow creates the final operational record.

## Failure Handling

- if Tesseract or language packs are unavailable, return a clear 503 or 500-style business error rather than crashing the request
- if OCR extraction produces no meaningful values, still store the image and raw result so the operator can retry or reject
- if verification is rejected, keep the OCR record with `status=rejected` for traceability
- if handoff data is incomplete, `DynamicEntryForm.vue` remains responsible for validating required fields before submit

## Runtime Dependencies

Python packages:

- `pytesseract`
- `opencv-python-headless`

Host runtime dependency:

- Tesseract executable with `chi_sim` and `eng` language data installed on the server

The application should degrade gracefully when the host OCR runtime is missing.

## Testing Strategy

- unit tests for field extraction helpers with monkeypatched Tesseract output
- router tests for `/ocr/extract` and `/ocr/verify`
- service tests for OCR record persistence and entry linkage
- route tests for OCR route registration
- work-order service test for attaching `ocr_submission_id` to a created entry
- frontend build verification after mobile routing and API changes

## Risks To Control

- OCR runtime may be missing from deployment hosts even if Python dependencies are installed
- handwritten paper forms can produce noisy numeric results, so low-confidence review UX is critical
- a second submit path would bypass field locking, which is why OCR must hand off into the existing form flow
- oversized images can cause slow requests unless upload validation is enforced
