from datetime import date, datetime, time

from sqlalchemy import Boolean, Date, DateTime, ForeignKey, Index, Integer, JSON, Numeric, String, Text, Time, UniqueConstraint, func, text
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base

AUTO_CONFIRMED_REPORT_STATUSES = {'approved', 'auto_confirmed'}


class ShiftProductionData(Base):
    __tablename__ = 'shift_production_data'
    __table_args__ = (
        Index(
            'uq_shift_production_active_key',
            'business_date',
            'shift_config_id',
            'workshop_id',
            'equipment_id',
            unique=True,
            postgresql_where=text("data_status <> 'voided'"),
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    business_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    shift_config_id: Mapped[int] = mapped_column(Integer, ForeignKey('shift_configs.id'), nullable=False, index=True)
    workshop_id: Mapped[int] = mapped_column(Integer, ForeignKey('workshops.id'), nullable=False, index=True)
    team_id: Mapped[int | None] = mapped_column(Integer, ForeignKey('teams.id'), nullable=True, index=True)
    equipment_id: Mapped[int | None] = mapped_column(Integer, ForeignKey('equipment.id'), nullable=True, index=True)

    input_weight: Mapped[float | None] = mapped_column(Numeric(14, 3), nullable=True)
    output_weight: Mapped[float | None] = mapped_column(Numeric(14, 3), nullable=True)
    qualified_weight: Mapped[float | None] = mapped_column(Numeric(14, 3), nullable=True)
    scrap_weight: Mapped[float | None] = mapped_column(Numeric(14, 3), nullable=True)

    planned_headcount: Mapped[int | None] = mapped_column(Integer, nullable=True)
    actual_headcount: Mapped[int | None] = mapped_column(Integer, nullable=True)

    downtime_minutes: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    downtime_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    issue_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    electricity_kwh: Mapped[float | None] = mapped_column(Numeric(14, 3), nullable=True)

    data_source: Mapped[str] = mapped_column(String(32), nullable=False, default='import')
    import_batch_id: Mapped[int | None] = mapped_column(Integer, ForeignKey('import_batches.id'), nullable=True)
    data_status: Mapped[str] = mapped_column(String(16), nullable=False, default='pending', index=True)
    version_no: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    superseded_by_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey('shift_production_data.id'), nullable=True, index=True
    )
    reviewed_by: Mapped[int | None] = mapped_column(Integer, ForeignKey('users.id'), nullable=True, index=True)
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    confirmed_by: Mapped[int | None] = mapped_column(Integer, ForeignKey('users.id'), nullable=True, index=True)
    confirmed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    rejected_by: Mapped[int | None] = mapped_column(Integer, ForeignKey('users.id'), nullable=True, index=True)
    rejected_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    rejected_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    voided_by: Mapped[int | None] = mapped_column(Integer, ForeignKey('users.id'), nullable=True, index=True)
    voided_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    voided_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    published_by: Mapped[int | None] = mapped_column(Integer, ForeignKey('users.id'), nullable=True, index=True)
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )


class ProductionException(Base):
    __tablename__ = 'production_exceptions'

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    production_data_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey('shift_production_data.id'), nullable=True, index=True
    )
    business_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    workshop_id: Mapped[int] = mapped_column(Integer, ForeignKey('workshops.id'), nullable=False, index=True)
    team_id: Mapped[int | None] = mapped_column(Integer, ForeignKey('teams.id'), nullable=True, index=True)
    equipment_id: Mapped[int | None] = mapped_column(Integer, ForeignKey('equipment.id'), nullable=True, index=True)
    shift_config_id: Mapped[int | None] = mapped_column(Integer, ForeignKey('shift_configs.id'), nullable=True, index=True)

    exception_type: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    exception_desc: Mapped[str] = mapped_column(Text, nullable=False)
    severity: Mapped[str] = mapped_column(String(16), nullable=False, default='warning')
    status: Mapped[str] = mapped_column(String(16), nullable=False, default='open', index=True)

    resolved_by: Mapped[int | None] = mapped_column(Integer, ForeignKey('users.id'), nullable=True)
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )


class MobileShiftReport(Base):
    __tablename__ = 'mobile_shift_reports'
    __table_args__ = (
        UniqueConstraint(
            'business_date',
            'shift_config_id',
            'workshop_id',
            'team_id',
            name='uq_mobile_shift_reports_key',
        ),
        Index('ix_mobile_shift_reports_status_date', 'report_status', 'business_date'),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    business_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    shift_config_id: Mapped[int] = mapped_column(Integer, ForeignKey('shift_configs.id'), nullable=False, index=True)
    workshop_id: Mapped[int] = mapped_column(Integer, ForeignKey('workshops.id'), nullable=False, index=True)
    team_id: Mapped[int | None] = mapped_column(Integer, ForeignKey('teams.id'), nullable=True, index=True)
    owner_user_id: Mapped[int | None] = mapped_column(Integer, ForeignKey('users.id'), nullable=True, index=True)
    leader_user_id: Mapped[int | None] = mapped_column(Integer, ForeignKey('users.id'), nullable=True, index=True)
    leader_name: Mapped[str | None] = mapped_column(String(64), nullable=True)
    dingtalk_user_id: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    dingtalk_union_id: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)

    attendance_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    input_weight: Mapped[float | None] = mapped_column(Numeric(14, 3), nullable=True)
    output_weight: Mapped[float | None] = mapped_column(Numeric(14, 3), nullable=True)
    scrap_weight: Mapped[float | None] = mapped_column(Numeric(14, 3), nullable=True)
    storage_prepared: Mapped[float | None] = mapped_column(Numeric(14, 3), nullable=True)
    storage_finished: Mapped[float | None] = mapped_column(Numeric(14, 3), nullable=True)
    shipment_weight: Mapped[float | None] = mapped_column(Numeric(14, 3), nullable=True)
    contract_received: Mapped[float | None] = mapped_column(Numeric(14, 3), nullable=True)
    electricity_daily: Mapped[float | None] = mapped_column(Numeric(14, 3), nullable=True)
    gas_daily: Mapped[float | None] = mapped_column(Numeric(14, 3), nullable=True)

    has_exception: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    exception_type: Mapped[str | None] = mapped_column(String(64), nullable=True)
    note: Mapped[str | None] = mapped_column(Text, nullable=True)
    optional_photo_url: Mapped[str | None] = mapped_column(String(512), nullable=True)

    report_status: Mapped[str] = mapped_column(String(16), nullable=False, default='draft', index=True)
    linked_production_data_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey('shift_production_data.id'), nullable=True, index=True
    )
    submitted_by_user_id: Mapped[int | None] = mapped_column(Integer, ForeignKey('users.id'), nullable=True, index=True)
    last_action_by_user_id: Mapped[int | None] = mapped_column(Integer, ForeignKey('users.id'), nullable=True, index=True)
    photo_file_path: Mapped[str | None] = mapped_column(String(512), nullable=True)
    photo_file_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    photo_uploaded_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    submitted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_saved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    returned_reason: Mapped[str | None] = mapped_column(Text, nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )

    @property
    def auto_confirmed(self) -> bool:
        return self.returned_reason is None and self.report_status in AUTO_CONFIRMED_REPORT_STATUSES

    @property
    def decision_status(self) -> str:
        if self.returned_reason:
            return 'returned'
        if self.auto_confirmed:
            return 'auto_confirmed'
        return self.report_status


class MobileReminderRecord(Base):
    __tablename__ = 'mobile_reminder_records'
    __table_args__ = (
        UniqueConstraint(
            'business_date',
            'shift_config_id',
            'workshop_id',
            'team_id',
            'leader_user_id',
            'reminder_type',
            name='uq_mobile_reminder_records_key',
        ),
        Index('ix_mobile_reminder_records_status_date', 'reminder_status', 'business_date'),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    business_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    shift_config_id: Mapped[int] = mapped_column(Integer, ForeignKey('shift_configs.id'), nullable=False, index=True)
    workshop_id: Mapped[int] = mapped_column(Integer, ForeignKey('workshops.id'), nullable=False, index=True)
    team_id: Mapped[int | None] = mapped_column(Integer, ForeignKey('teams.id'), nullable=True, index=True)
    leader_user_id: Mapped[int | None] = mapped_column(Integer, ForeignKey('users.id'), nullable=True, index=True)
    reminder_type: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    reminder_status: Mapped[str] = mapped_column(String(16), nullable=False, default='pending', index=True)
    reminder_channel: Mapped[str] = mapped_column(String(32), nullable=False, default='system')
    reminder_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    last_reminded_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    acknowledged_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    acknowledged_by: Mapped[int | None] = mapped_column(Integer, ForeignKey('users.id'), nullable=True)
    closed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    closed_by: Mapped[int | None] = mapped_column(Integer, ForeignKey('users.id'), nullable=True)
    note: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )


class WorkOrder(Base):
    __tablename__ = 'work_orders'

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    tracking_card_no: Mapped[str] = mapped_column(String(64), nullable=False, unique=True, index=True)
    process_route_code: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    alloy_grade: Mapped[str | None] = mapped_column(String(64), nullable=True)
    contract_no: Mapped[str | None] = mapped_column(String(64), nullable=True)
    customer_name: Mapped[str | None] = mapped_column(String(128), nullable=True)
    contract_weight: Mapped[float | None] = mapped_column(Numeric(14, 3), nullable=True)
    current_station: Mapped[str | None] = mapped_column(String(64), nullable=True)
    previous_stage_output: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    overall_status: Mapped[str] = mapped_column(String(16), nullable=False, default='created', index=True)
    created_by: Mapped[int | None] = mapped_column(Integer, ForeignKey('users.id'), nullable=True, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )


class OCRSubmission(Base):
    __tablename__ = 'ocr_submissions'

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    image_path: Mapped[str] = mapped_column(String(512), nullable=False)
    workshop_type: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    extracted_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    verified_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    linked_entry_id: Mapped[int | None] = mapped_column(Integer, ForeignKey('work_order_entries.id'), nullable=True, index=True)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default='pending_review', index=True)
    created_by: Mapped[int | None] = mapped_column(Integer, ForeignKey('users.id'), nullable=True, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )


class RealtimeEvent(Base):
    __tablename__ = 'realtime_events'
    __table_args__ = (
        Index('ix_realtime_events_created_at', 'created_at'),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    event_type: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    payload: Mapped[dict] = mapped_column(JSON, nullable=False)
    workshop_id: Mapped[int | None] = mapped_column(Integer, nullable=True, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())


class WorkOrderEntry(Base):
    __tablename__ = 'work_order_entries'
    __table_args__ = (
        Index('ix_work_order_entries_work_order_workshop_date', 'work_order_id', 'workshop_id', 'business_date'),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    work_order_id: Mapped[int] = mapped_column(Integer, ForeignKey('work_orders.id'), nullable=False, index=True)
    workshop_id: Mapped[int] = mapped_column(Integer, ForeignKey('workshops.id'), nullable=False, index=True)
    machine_id: Mapped[int | None] = mapped_column(Integer, ForeignKey('equipment.id'), nullable=True, index=True)
    shift_id: Mapped[int | None] = mapped_column(Integer, ForeignKey('shift_configs.id'), nullable=True, index=True)
    business_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)

    on_machine_time: Mapped[time | None] = mapped_column(Time(), nullable=True)
    off_machine_time: Mapped[time | None] = mapped_column(Time(), nullable=True)
    input_weight: Mapped[float | None] = mapped_column(Numeric(14, 3), nullable=True)
    output_weight: Mapped[float | None] = mapped_column(Numeric(14, 3), nullable=True)
    input_spec: Mapped[str | None] = mapped_column(String(64), nullable=True)
    output_spec: Mapped[str | None] = mapped_column(String(64), nullable=True)
    material_state: Mapped[str | None] = mapped_column(String(64), nullable=True)
    scrap_weight: Mapped[float | None] = mapped_column(Numeric(14, 3), nullable=True)
    spool_weight: Mapped[float | None] = mapped_column(Numeric(14, 3), nullable=True)
    operator_notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    verified_input_weight: Mapped[float | None] = mapped_column(Numeric(14, 3), nullable=True)
    verified_output_weight: Mapped[float | None] = mapped_column(Numeric(14, 3), nullable=True)
    weigher_user_id: Mapped[int | None] = mapped_column(Integer, ForeignKey('users.id'), nullable=True, index=True)
    weighed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    qc_grade: Mapped[str | None] = mapped_column(String(64), nullable=True)
    qc_notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    qc_user_id: Mapped[int | None] = mapped_column(Integer, ForeignKey('users.id'), nullable=True, index=True)
    qc_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    energy_kwh: Mapped[float | None] = mapped_column(Numeric(14, 3), nullable=True)
    gas_m3: Mapped[float | None] = mapped_column(Numeric(14, 3), nullable=True)
    extra_payload: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    qc_payload: Mapped[dict | None] = mapped_column(JSON, nullable=True)

    yield_rate: Mapped[float | None] = mapped_column(Numeric(8, 4), nullable=True)
    entry_type: Mapped[str] = mapped_column(String(16), nullable=False, default='in_progress')
    entry_status: Mapped[str] = mapped_column(String(16), nullable=False, default='draft', index=True)
    locked_fields: Mapped[list[str] | None] = mapped_column(JSON, nullable=True)
    submitted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    verified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    approved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_by: Mapped[int | None] = mapped_column(Integer, ForeignKey('users.id'), nullable=True, index=True)
    created_by_user_id: Mapped[int | None] = mapped_column(Integer, ForeignKey('users.id'), nullable=True, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )


class FieldAmendment(Base):
    __tablename__ = 'field_amendments'
    __table_args__ = (
        Index('ix_field_amendments_status_table', 'status', 'table_name'),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    table_name: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    record_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    field_name: Mapped[str] = mapped_column(String(64), nullable=False)
    old_value: Mapped[str | None] = mapped_column(Text, nullable=True)
    new_value: Mapped[str | None] = mapped_column(Text, nullable=True)
    reason: Mapped[str] = mapped_column(Text, nullable=False)
    requested_by: Mapped[int | None] = mapped_column(Integer, ForeignKey('users.id'), nullable=True, index=True)
    requested_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    approved_by: Mapped[int | None] = mapped_column(Integer, ForeignKey('users.id'), nullable=True, index=True)
    approved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    status: Mapped[str] = mapped_column(String(16), nullable=False, default='pending', index=True)
