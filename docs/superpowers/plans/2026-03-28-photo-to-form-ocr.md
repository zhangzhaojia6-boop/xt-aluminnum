# Photo-To-Form OCR Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a photo-to-form OCR workflow for OCR-enabled workshops that stores the original paper-form photo, extracts template-aware field values, lets the operator correct them, and then hands the verified payload into the existing dynamic work-order entry form and submit flow.

**Architecture:** Add OCR persistence and extraction on the backend, expose mobile OCR extract and verify endpoints, extend work-order entry creation with optional OCR evidence linkage, and add a dedicated mobile OCR capture/review screen that hands verified values into `DynamicEntryForm.vue`.

**Tech Stack:** FastAPI, SQLAlchemy 2.0, Alembic, Pydantic 2, Vue 3, Vite, Element Plus, Pinia, Axios, pytesseract, OpenCV

---

### Task 1: Red Tests For OCR Surface And Linkage

**Files:**
- Create: `backend/tests/test_ocr_routes.py`
- Create: `backend/tests/test_ocr_service.py`
- Modify: `backend/tests/test_work_order_routes.py`
- Modify: `backend/tests/test_work_order_service.py`

- [ ] Add failing route tests for `/api/v1/ocr/extract` and `/api/v1/ocr/verify`.
- [ ] Add failing service tests for OCR extraction normalization, verified payload persistence, and entry linkage through `ocr_submission_id`.
- [ ] Extend work-order tests to cover OCR evidence linkage on entry creation.
- [ ] Run focused pytest and confirm failures are caused by the missing OCR implementation.

### Task 2: Backend Schema And Dependency Changes

**Files:**
- Modify: `backend/requirements.txt`
- Modify: `backend/app/models/production.py`
- Create: `backend/alembic/versions/0014_photo_to_form_ocr.py`

- [ ] Add `pytesseract` and `opencv-python-headless` to the backend requirements.
- [ ] Add `ocr_submissions` ORM model with extracted, verified, status, and linkage columns.
- [ ] Add optional `ocr_submission_id` linkage support to the work-order entry flow if a dedicated column or service-side lookup is needed.
- [ ] Create the Alembic migration for the OCR submission table and any supporting indexes or foreign keys.

### Task 3: OCR Service And Router

**Files:**
- Create: `backend/app/services/ocr_service.py`
- Create: `backend/app/schemas/ocr.py`
- Create: `backend/app/routers/ocr.py`
- Modify: `backend/app/main.py`

- [ ] Implement upload validation, image preprocessing, deskew, OCR invocation, and template-aware field extraction.
- [ ] Persist OCR submissions and uploaded images under `uploads/ocr/...`.
- [ ] Add `POST /ocr/extract` for upload and extraction.
- [ ] Add `POST /ocr/verify` for corrected-value persistence and normalized form handoff.
- [ ] Handle missing Tesseract runtime gracefully with explicit API errors instead of uncaught failures.

### Task 4: Work-Order Flow Integration

**Files:**
- Modify: `backend/app/schemas/work_orders.py`
- Modify: `backend/app/services/work_order_service.py`
- Modify: `backend/app/core/field_permissions.py` if needed for OCR-only metadata handling

- [ ] Extend work-order entry create/update payload handling to accept optional `ocr_submission_id`.
- [ ] Link a verified OCR submission to the created entry without bypassing the existing field permission and locking logic.
- [ ] Ensure serialized entry or audit data can expose OCR evidence references only where appropriate.

### Task 5: Mobile OCR Capture And Handoff

**Files:**
- Create: `frontend/src/views/mobile/OCRCapture.vue`
- Modify: `frontend/src/views/mobile/MobileEntry.vue`
- Modify: `frontend/src/views/mobile/DynamicEntryForm.vue`
- Modify: `frontend/src/api/mobile.js`
- Modify: `frontend/src/router/index.js`
- Modify: `frontend/src/styles.css`

- [ ] Add OCR API helpers for extract and verify.
- [ ] Add a dedicated OCR capture/review screen with image preview and confidence badges.
- [ ] Show `手动填写` and `拍照识别` only for OCR-enabled workshops.
- [ ] Route verified OCR values into `DynamicEntryForm.vue` as prefilled, editable values with OCR evidence context.
- [ ] Keep the final create/update/submit logic in the existing dynamic form.

### Task 6: Verification

**Files:**
- Verify only

- [ ] Run focused OCR backend tests.
- [ ] Run the full backend suite.
- [ ] Run `npm run build` in `frontend`.
- [ ] Fix regressions until all checks pass.
