from datetime import date, datetime

from sqlalchemy import Boolean, Date, DateTime, ForeignKey, Index, Integer, Numeric, String, Text, func, text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin, json_object_type


class ImportBatch(Base, TimestampMixin):
    __tablename__ = 'import_batches'

    id: Mapped[int] = mapped_column(primary_key=True)
    batch_no: Mapped[str] = mapped_column(String(60), unique=True, index=True, nullable=False)
    import_type: Mapped[str] = mapped_column(String(32), index=True, nullable=False)
    template_code: Mapped[str | None] = mapped_column(String(64), nullable=True)
    mapping_template_code: Mapped[str | None] = mapped_column(String(64), nullable=True)
    source_type: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    file_name: Mapped[str] = mapped_column(String(255), nullable=False)
    file_size: Mapped[int | None] = mapped_column(Integer, nullable=True)
    file_path: Mapped[str | None] = mapped_column(String(512), nullable=True)
    total_rows: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    success_rows: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    failed_rows: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    skipped_rows: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    status: Mapped[str] = mapped_column(String(16), default='processing', nullable=False)
    quality_status: Mapped[str] = mapped_column(String(16), default='pending_check', nullable=False)
    parsed_successfully: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    error_summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    imported_by: Mapped[int | None] = mapped_column(ForeignKey('users.id'), nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    rows: Mapped[list['ImportRow']] = relationship(back_populates='batch', cascade='all, delete-orphan')
    creator = relationship('User')


class ImportRow(Base, TimestampMixin):
    __tablename__ = 'import_rows'

    id: Mapped[int] = mapped_column(primary_key=True)
    batch_id: Mapped[int] = mapped_column(ForeignKey('import_batches.id'), index=True, nullable=False)
    row_number: Mapped[int] = mapped_column(Integer, nullable=False)
    raw_data: Mapped[dict | None] = mapped_column(json_object_type, nullable=True)
    mapped_data: Mapped[dict | None] = mapped_column(json_object_type, nullable=True)
    status: Mapped[str] = mapped_column(String(16), default='pending', nullable=False)
    error_msg: Mapped[str | None] = mapped_column(Text, nullable=True)

    batch: Mapped['ImportBatch'] = relationship(back_populates='rows')


class ImportedDailyMetricFact(Base, TimestampMixin):
    __tablename__ = 'imported_daily_metric_facts'
    __table_args__ = (
        Index(
            'uq_imported_daily_metric_active_key',
            'business_date',
            'field_name',
            'source_kind',
            unique=True,
            postgresql_where=text("data_status = 'confirmed'"),
            sqlite_where=text("data_status = 'confirmed'"),
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    business_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    field_name: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    metric_value: Mapped[float] = mapped_column(Numeric(18, 6), nullable=False)
    unit: Mapped[str] = mapped_column(String(32), nullable=False)
    source_kind: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    import_batch_id: Mapped[int] = mapped_column(ForeignKey('import_batches.id'), nullable=False, index=True)
    import_row_id: Mapped[int] = mapped_column(ForeignKey('import_rows.id'), nullable=False, index=True)
    source_anchors: Mapped[list] = mapped_column(json_object_type, nullable=False, default=list)
    lineage_hash: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    metric_contract_version: Mapped[str] = mapped_column(String(32), nullable=False)
    data_status: Mapped[str] = mapped_column(String(16), nullable=False, default='confirmed', index=True)
    version_no: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    superseded_by_id: Mapped[int | None] = mapped_column(
        ForeignKey('imported_daily_metric_facts.id'), nullable=True, index=True
    )
    confirmed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    voided_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    voided_reason: Mapped[str | None] = mapped_column(Text, nullable=True)


class FieldMappingTemplate(Base, TimestampMixin):
    __tablename__ = 'field_mapping_templates'

    id: Mapped[int] = mapped_column(primary_key=True)
    template_code: Mapped[str] = mapped_column(String(64), unique=True, index=True, nullable=False)
    template_name: Mapped[str] = mapped_column(String(128), nullable=False)
    import_type: Mapped[str] = mapped_column(String(32), nullable=False)
    source_type: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    mappings: Mapped[dict] = mapped_column(json_object_type, nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
