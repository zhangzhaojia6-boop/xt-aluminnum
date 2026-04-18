from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal

from fastapi import UploadFile
from sqlalchemy.orm import Session

from app.models.imports import ImportRow
from app.models.mes import MesImportRecord
from app.models.system import User
from app.services import import_service
from app.services import master_service
from app.services.audit_service import record_audit
from app.utils.date_utils import parse_date


@dataclass(slots=True)
class MesImportResult:
    batch_id: int
    batch_no: str
    import_type: str
    summary: dict


def _to_float(value) -> float | None:
    if value is None:
        return None
    if isinstance(value, Decimal):
        return float(value)
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _normalize_mapped_data(mapped: dict) -> dict:
    return {str(key): import_service._normalize_value(value) for key, value in (mapped or {}).items()}


def import_mes_export(
    db: Session,
    *,
    upload_file: UploadFile,
    current_user: User,
) -> MesImportResult:
    stored_path, content, stored_filename = import_service._save_upload_file(upload_file)
    resolved_template_code, mappings = import_service._resolve_template_mapping(
        db, 'mes_export', None, source_type='mes_export'
    )
    batch = import_service._create_batch(
        db,
        import_type='mes_export',
        file_name=upload_file.filename or stored_filename,
        file_size=len(content),
        file_path=str(stored_path),
        imported_by=current_user.id,
        template_code=resolved_template_code,
        mapping_template_code=resolved_template_code,
        source_type='mes_export',
    )

    df = import_service._read_dataframe(stored_path)
    raw_rows = df.to_dict(orient='records')
    success = 0
    failed = 0
    canonical_fields = {
        'business_date',
        'workshop_code',
        'shift_code',
        'metric_code',
        'metric_name',
        'metric_value',
        'unit',
        'source_row_no',
    }

    for index, raw in enumerate(raw_rows, start=1):
        cleaned = {str(key): import_service._normalize_value(value) for key, value in raw.items()}
        mapped, missing_required = import_service._map_row(
            cleaned, mappings, canonical_fields, return_missing=True
        )
        mapped_data = _normalize_mapped_data(mapped)
        row = ImportRow(
            batch_id=batch.id,
            row_number=index,
            raw_data=cleaned,
            mapped_data=mapped_data,
            status='pending',
        )
        db.add(row)
        try:
            if missing_required:
                raise ValueError(f'missing required fields: {", ".join(missing_required)}')

            business_date = parse_date(mapped.get('business_date'))
            metric_code = (mapped.get('metric_code') or '').strip()
            if not metric_code:
                raise ValueError('metric_code is required')

            workshop_code = master_service.resolve_canonical_code(
                db,
                entity_type='workshop',
                value=mapped.get('workshop_code'),
                source_type='mes_export',
            )
            if not workshop_code:
                raise ValueError('workshop_code not found')
            shift_code = master_service.resolve_canonical_code(
                db,
                entity_type='shift',
                value=mapped.get('shift_code'),
                source_type='mes_export',
            )
            if not shift_code:
                raise ValueError('shift_code not found')

            record = MesImportRecord(
                import_batch_id=batch.id,
                source_type='mes_export',
                business_date=business_date,
                workshop_code=workshop_code,
                shift_code=shift_code,
                metric_code=metric_code,
                metric_name=(mapped.get('metric_name') or '').strip() or None,
                metric_value=_to_float(mapped.get('metric_value')),
                unit=(mapped.get('unit') or '').strip() or None,
                source_row_no=mapped.get('source_row_no') or index,
                raw_payload=cleaned,
            )
            db.add(record)
            row.status = 'success'
            row.error_msg = None
            success += 1
        except Exception as exc:  # noqa: BLE001
            row.status = 'failed'
            row.error_msg = str(exc)
            failed += 1

    import_service._finalize_batch(
        db,
        batch=batch,
        total_rows=len(raw_rows),
        success_rows=success,
        failed_rows=failed,
        skipped_rows=0,
        error_summary=None if failed == 0 else f'failed_rows={failed}',
    )
    db.commit()
    db.refresh(batch)

    record_audit(
        db,
        user=current_user,
        action='import_mes_export',
        module='mes',
        entity_type='import_batches',
        entity_id=batch.id,
        detail={'batch_no': batch.batch_no, 'success': success, 'failed': failed},
    )

    return MesImportResult(
        batch_id=batch.id,
        batch_no=batch.batch_no,
        import_type=batch.import_type,
        summary={
            'batch_no': batch.batch_no,
            'total_rows': len(raw_rows),
            'success_rows': success,
            'failed_rows': failed,
            'columns': list(df.columns),
        },
    )
