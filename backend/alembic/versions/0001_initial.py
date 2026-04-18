"""initial schema

Revision ID: 0001_initial
Revises:
Create Date: 2026-03-25
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "0001_initial"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "workshops",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("code", sa.String(length=32), nullable=False),
        sa.Column("name", sa.String(length=64), nullable=False),
        sa.Column("sort_order", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.UniqueConstraint("code"),
    )
    op.create_index("ix_workshops_code", "workshops", ["code"], unique=True)

    op.create_table(
        "teams",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("workshop_id", sa.Integer(), nullable=False),
        sa.Column("code", sa.String(length=32), nullable=False),
        sa.Column("name", sa.String(length=64), nullable=False),
        sa.Column("sort_order", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["workshop_id"], ["workshops.id"]),
        sa.UniqueConstraint("workshop_id", "code", name="uq_teams_workshop_code"),
    )
    op.create_index("ix_teams_code", "teams", ["code"], unique=False)
    op.create_index("ix_teams_workshop_id", "teams", ["workshop_id"], unique=False)

    op.create_table(
        "positions",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("code", sa.String(length=32), nullable=False),
        sa.Column("name", sa.String(length=64), nullable=False),
        sa.Column("workshop_id", sa.Integer(), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["workshop_id"], ["workshops.id"]),
        sa.UniqueConstraint("code"),
    )
    op.create_index("ix_positions_code", "positions", ["code"], unique=True)

    op.create_table(
        "equipment",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("code", sa.String(length=32), nullable=False),
        sa.Column("name", sa.String(length=64), nullable=False),
        sa.Column("workshop_id", sa.Integer(), nullable=False),
        sa.Column("equipment_type", sa.String(length=32), nullable=True),
        sa.Column("spec", sa.String(length=128), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["workshop_id"], ["workshops.id"]),
        sa.UniqueConstraint("code"),
    )
    op.create_index("ix_equipment_code", "equipment", ["code"], unique=True)

    op.create_table(
        "users",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("username", sa.String(length=64), nullable=False),
        sa.Column("password_hash", sa.String(length=255), nullable=False),
        sa.Column("name", sa.String(length=64), nullable=False),
        sa.Column("role", sa.String(length=32), nullable=False),
        sa.Column("workshop_id", sa.Integer(), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("last_login", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["workshop_id"], ["workshops.id"]),
        sa.UniqueConstraint("username"),
    )
    op.create_index("ix_users_username", "users", ["username"], unique=True)

    op.create_table(
        "employees",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("employee_no", sa.String(length=32), nullable=False),
        sa.Column("name", sa.String(length=64), nullable=False),
        sa.Column("workshop_id", sa.Integer(), nullable=False),
        sa.Column("team_id", sa.Integer(), nullable=True),
        sa.Column("position_id", sa.Integer(), nullable=True),
        sa.Column("phone", sa.String(length=32), nullable=True),
        sa.Column("dingtalk_user_id", sa.String(length=64), nullable=True),
        sa.Column("dingtalk_union_id", sa.String(length=64), nullable=True),
        sa.Column("hire_date", sa.Date(), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["workshop_id"], ["workshops.id"]),
        sa.ForeignKeyConstraint(["team_id"], ["teams.id"]),
        sa.ForeignKeyConstraint(["position_id"], ["positions.id"]),
        sa.UniqueConstraint("employee_no"),
    )
    op.create_index("ix_employees_employee_no", "employees", ["employee_no"], unique=True)
    op.create_index("ix_employees_workshop_id", "employees", ["workshop_id"], unique=False)
    op.create_index("ix_employees_team_id", "employees", ["team_id"], unique=False)
    op.create_index("ix_employees_dingtalk_user_id", "employees", ["dingtalk_user_id"], unique=False)

    op.create_table(
        "system_configs",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("config_key", sa.String(length=128), nullable=False),
        sa.Column("config_value", sa.Text(), nullable=True),
        sa.Column("config_type", sa.String(length=32), nullable=False, server_default=sa.text("'string'")),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("updated_by", sa.Integer(), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["updated_by"], ["users.id"]),
        sa.UniqueConstraint("config_key"),
    )
    op.create_index("ix_system_configs_config_key", "system_configs", ["config_key"], unique=True)

    op.create_table(
        "audit_logs",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), nullable=True),
        sa.Column("user_name", sa.String(length=64), nullable=False),
        sa.Column("action", sa.String(length=64), nullable=False),
        sa.Column("module", sa.String(length=64), nullable=False),
        sa.Column("table_name", sa.String(length=64), nullable=True),
        sa.Column("record_id", sa.Integer(), nullable=True),
        sa.Column("old_value", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("new_value", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("reason", sa.Text(), nullable=True),
        sa.Column("ip_address", sa.String(length=45), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
    )
    op.create_index("ix_audit_logs_user_id", "audit_logs", ["user_id"], unique=False)

    op.create_table(
        "shift_configs",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("code", sa.String(length=32), nullable=False),
        sa.Column("name", sa.String(length=64), nullable=False),
        sa.Column("shift_type", sa.String(length=32), nullable=False),
        sa.Column("start_time", sa.Time(), nullable=False),
        sa.Column("end_time", sa.Time(), nullable=False),
        sa.Column("is_cross_day", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("business_day_offset", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("late_tolerance_minutes", sa.Integer(), nullable=False, server_default=sa.text("30")),
        sa.Column("early_tolerance_minutes", sa.Integer(), nullable=False, server_default=sa.text("30")),
        sa.Column("sort_order", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("workshop_id", sa.Integer(), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["workshop_id"], ["workshops.id"]),
        sa.UniqueConstraint("code"),
    )
    op.create_index("ix_shift_configs_code", "shift_configs", ["code"], unique=True)

    op.create_table(
        "import_batches",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("batch_no", sa.String(length=60), nullable=False),
        sa.Column("import_type", sa.String(length=32), nullable=False),
        sa.Column("template_code", sa.String(length=64), nullable=True),
        sa.Column("file_name", sa.String(length=255), nullable=False),
        sa.Column("file_size", sa.Integer(), nullable=True),
        sa.Column("file_path", sa.String(length=512), nullable=True),
        sa.Column("total_rows", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("success_rows", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("failed_rows", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("skipped_rows", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("status", sa.String(length=16), nullable=False, server_default=sa.text("'processing'")),
        sa.Column("error_summary", sa.Text(), nullable=True),
        sa.Column("imported_by", sa.Integer(), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["imported_by"], ["users.id"]),
        sa.UniqueConstraint("batch_no"),
    )
    op.create_index("ix_import_batches_batch_no", "import_batches", ["batch_no"], unique=True)
    op.create_index("ix_import_batches_import_type", "import_batches", ["import_type"], unique=False)

    op.create_table(
        "import_rows",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("batch_id", sa.Integer(), nullable=False),
        sa.Column("row_number", sa.Integer(), nullable=False),
        sa.Column("raw_data", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("mapped_data", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("status", sa.String(length=16), nullable=False, server_default=sa.text("'pending'")),
        sa.Column("error_msg", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["batch_id"], ["import_batches.id"]),
    )
    op.create_index("ix_import_rows_batch_id", "import_rows", ["batch_id"], unique=False)

    op.create_table(
        "field_mapping_templates",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("template_code", sa.String(length=64), nullable=False),
        sa.Column("template_name", sa.String(length=128), nullable=False),
        sa.Column("import_type", sa.String(length=32), nullable=False),
        sa.Column("mappings", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.UniqueConstraint("template_code"),
    )
    op.create_index("ix_field_mapping_templates_template_code", "field_mapping_templates", ["template_code"], unique=True)

    op.create_table(
        "attendance_schedules",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("employee_id", sa.Integer(), nullable=False),
        sa.Column("business_date", sa.Date(), nullable=False),
        sa.Column("shift_id", sa.Integer(), nullable=True),
        sa.Column("team_id", sa.Integer(), nullable=True),
        sa.Column("is_rest_day", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("source", sa.String(length=16), nullable=False, server_default=sa.text("'manual'")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["employee_id"], ["employees.id"]),
        sa.ForeignKeyConstraint(["shift_id"], ["shift_configs.id"]),
        sa.ForeignKeyConstraint(["team_id"], ["teams.id"]),
        sa.UniqueConstraint("employee_id", "business_date", name="uq_schedule_emp_date"),
    )
    op.create_index("ix_attendance_schedules_employee_id", "attendance_schedules", ["employee_id"], unique=False)
    op.create_index("ix_attendance_schedules_business_date", "attendance_schedules", ["business_date"], unique=False)

    op.create_table(
        "clock_records",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("employee_id", sa.Integer(), nullable=False),
        sa.Column("clock_time", sa.DateTime(timezone=True), nullable=False),
        sa.Column("clock_type", sa.String(length=16), nullable=False),
        sa.Column("device_id", sa.String(length=64), nullable=True),
        sa.Column("source", sa.String(length=16), nullable=False, server_default=sa.text("'device'")),
        sa.Column("raw_data", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["employee_id"], ["employees.id"]),
    )
    op.create_index("ix_clock_records_employee_id", "clock_records", ["employee_id"], unique=False)
    op.create_index("ix_clock_records_clock_time", "clock_records", ["clock_time"], unique=False)

    op.create_table(
        "shift_swaps",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("employee_id", sa.Integer(), nullable=False),
        sa.Column("swap_date", sa.Date(), nullable=False),
        sa.Column("original_shift_id", sa.Integer(), nullable=True),
        sa.Column("new_shift_id", sa.Integer(), nullable=True),
        sa.Column("reason", sa.String(length=256), nullable=True),
        sa.Column("status", sa.String(length=16), nullable=False, server_default=sa.text("'pending'")),
        sa.Column("approved_by", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["employee_id"], ["employees.id"]),
        sa.ForeignKeyConstraint(["original_shift_id"], ["shift_configs.id"]),
        sa.ForeignKeyConstraint(["new_shift_id"], ["shift_configs.id"]),
        sa.ForeignKeyConstraint(["approved_by"], ["users.id"]),
    )
    op.create_index("ix_shift_swaps_employee_id", "shift_swaps", ["employee_id"], unique=False)
    op.create_index("ix_shift_swaps_swap_date", "shift_swaps", ["swap_date"], unique=False)

    op.create_table(
        "attendance_results",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("employee_id", sa.Integer(), nullable=False),
        sa.Column("business_date", sa.Date(), nullable=False),
        sa.Column("shift_id", sa.Integer(), nullable=True),
        sa.Column("attendance_status", sa.String(length=16), nullable=False),
        sa.Column("check_in_time", sa.DateTime(timezone=True), nullable=True),
        sa.Column("check_out_time", sa.DateTime(timezone=True), nullable=True),
        sa.Column("late_minutes", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("early_leave_minutes", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("overtime_minutes", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("work_hours", sa.Float(), nullable=True),
        sa.Column("exception_flag", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("remark", sa.String(length=256), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["employee_id"], ["employees.id"]),
        sa.ForeignKeyConstraint(["shift_id"], ["shift_configs.id"]),
        sa.UniqueConstraint("employee_id", "business_date", name="uq_attendance_emp_date"),
    )
    op.create_index("ix_attendance_results_employee_id", "attendance_results", ["employee_id"], unique=False)
    op.create_index("ix_attendance_results_business_date", "attendance_results", ["business_date"], unique=False)
    op.create_index("ix_attendance_results_status", "attendance_results", ["attendance_status"], unique=False)

    op.create_table(
        "attendance_exceptions",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("employee_id", sa.Integer(), nullable=False),
        sa.Column("business_date", sa.Date(), nullable=False),
        sa.Column("exception_type", sa.String(length=32), nullable=False),
        sa.Column("description", sa.String(length=256), nullable=True),
        sa.Column("status", sa.String(length=16), nullable=False, server_default=sa.text("'open'")),
        sa.Column("resolved_by", sa.Integer(), nullable=True),
        sa.Column("resolved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["employee_id"], ["employees.id"]),
        sa.ForeignKeyConstraint(["resolved_by"], ["users.id"]),
    )
    op.create_index("ix_attendance_exceptions_employee_id", "attendance_exceptions", ["employee_id"], unique=False)
    op.create_index("ix_attendance_exceptions_business_date", "attendance_exceptions", ["business_date"], unique=False)
    op.create_index("ix_attendance_exceptions_type", "attendance_exceptions", ["exception_type"], unique=False)

    op.create_table(
        "shift_production_data",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("workshop_id", sa.Integer(), nullable=False),
        sa.Column("equipment_id", sa.Integer(), nullable=True),
        sa.Column("team_id", sa.Integer(), nullable=True),
        sa.Column("business_date", sa.Date(), nullable=False),
        sa.Column("shift_id", sa.Integer(), nullable=True),
        sa.Column("product_code", sa.String(length=64), nullable=True),
        sa.Column("product_name", sa.String(length=128), nullable=True),
        sa.Column("planned_qty", sa.Numeric(12, 3), nullable=True),
        sa.Column("actual_qty", sa.Numeric(12, 3), nullable=True),
        sa.Column("scrap_qty", sa.Numeric(12, 3), nullable=True),
        sa.Column("unit", sa.String(length=16), nullable=True),
        sa.Column("raw_data", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("import_batch_id", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["workshop_id"], ["workshops.id"]),
        sa.ForeignKeyConstraint(["equipment_id"], ["equipment.id"]),
        sa.ForeignKeyConstraint(["team_id"], ["teams.id"]),
        sa.ForeignKeyConstraint(["shift_id"], ["shift_configs.id"]),
        sa.ForeignKeyConstraint(["import_batch_id"], ["import_batches.id"]),
        sa.UniqueConstraint(
            "workshop_id",
            "equipment_id",
            "business_date",
            "shift_id",
            name="uq_prod_equipment_date_shift",
        ),
    )

    op.create_table(
        "production_exceptions",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("workshop_id", sa.Integer(), nullable=False),
        sa.Column("equipment_id", sa.Integer(), nullable=True),
        sa.Column("business_date", sa.Date(), nullable=False),
        sa.Column("exception_type", sa.String(length=32), nullable=False),
        sa.Column("description", sa.String(length=256), nullable=True),
        sa.Column("duration_minutes", sa.Integer(), nullable=True),
        sa.Column("status", sa.String(length=16), nullable=False, server_default=sa.text("'open'")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["workshop_id"], ["workshops.id"]),
        sa.ForeignKeyConstraint(["equipment_id"], ["equipment.id"]),
    )
    op.create_index("ix_production_exceptions_type", "production_exceptions", ["exception_type"], unique=False)

    op.create_table(
        "daily_reports",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("report_date", sa.Date(), nullable=False),
        sa.Column("report_type", sa.String(length=32), nullable=False),
        sa.Column("workshop_id", sa.Integer(), nullable=True),
        sa.Column("report_data", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("status", sa.String(length=16), nullable=False, server_default=sa.text("'draft'")),
        sa.Column("generated_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("reviewed_by", sa.Integer(), nullable=True),
        sa.Column("reviewed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("published_by", sa.Integer(), nullable=True),
        sa.Column("published_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["workshop_id"], ["workshops.id"]),
        sa.ForeignKeyConstraint(["reviewed_by"], ["users.id"]),
        sa.ForeignKeyConstraint(["published_by"], ["users.id"]),
        sa.UniqueConstraint("report_date", "report_type", name="uq_report_date_type"),
    )
    op.create_index("ix_daily_reports_report_date", "daily_reports", ["report_date"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_daily_reports_report_date", table_name="daily_reports")
    op.drop_table("daily_reports")
    op.drop_index("ix_production_exceptions_type", table_name="production_exceptions")
    op.drop_table("production_exceptions")
    op.drop_table("shift_production_data")
    op.drop_index("ix_attendance_exceptions_type", table_name="attendance_exceptions")
    op.drop_index("ix_attendance_exceptions_business_date", table_name="attendance_exceptions")
    op.drop_index("ix_attendance_exceptions_employee_id", table_name="attendance_exceptions")
    op.drop_table("attendance_exceptions")
    op.drop_index("ix_attendance_results_status", table_name="attendance_results")
    op.drop_index("ix_attendance_results_business_date", table_name="attendance_results")
    op.drop_index("ix_attendance_results_employee_id", table_name="attendance_results")
    op.drop_table("attendance_results")
    op.drop_index("ix_shift_swaps_swap_date", table_name="shift_swaps")
    op.drop_index("ix_shift_swaps_employee_id", table_name="shift_swaps")
    op.drop_table("shift_swaps")
    op.drop_index("ix_clock_records_clock_time", table_name="clock_records")
    op.drop_index("ix_clock_records_employee_id", table_name="clock_records")
    op.drop_table("clock_records")
    op.drop_index("ix_attendance_schedules_business_date", table_name="attendance_schedules")
    op.drop_index("ix_attendance_schedules_employee_id", table_name="attendance_schedules")
    op.drop_table("attendance_schedules")
    op.drop_index("ix_field_mapping_templates_template_code", table_name="field_mapping_templates")
    op.drop_table("field_mapping_templates")
    op.drop_index("ix_import_rows_batch_id", table_name="import_rows")
    op.drop_table("import_rows")
    op.drop_index("ix_import_batches_import_type", table_name="import_batches")
    op.drop_index("ix_import_batches_batch_no", table_name="import_batches")
    op.drop_table("import_batches")
    op.drop_index("ix_shift_configs_code", table_name="shift_configs")
    op.drop_table("shift_configs")
    op.drop_index("ix_audit_logs_user_id", table_name="audit_logs")
    op.drop_table("audit_logs")
    op.drop_index("ix_system_configs_config_key", table_name="system_configs")
    op.drop_table("system_configs")
    op.drop_index("ix_employees_dingtalk_user_id", table_name="employees")
    op.drop_index("ix_employees_team_id", table_name="employees")
    op.drop_index("ix_employees_workshop_id", table_name="employees")
    op.drop_index("ix_employees_employee_no", table_name="employees")
    op.drop_table("employees")
    op.drop_index("ix_users_username", table_name="users")
    op.drop_table("users")
    op.drop_index("ix_equipment_code", table_name="equipment")
    op.drop_table("equipment")
    op.drop_index("ix_positions_code", table_name="positions")
    op.drop_table("positions")
    op.drop_index("ix_teams_workshop_id", table_name="teams")
    op.drop_index("ix_teams_code", table_name="teams")
    op.drop_table("teams")
    op.drop_index("ix_workshops_code", table_name="workshops")
    op.drop_table("workshops")
