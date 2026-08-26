from __future__ import annotations

from datetime import date, datetime
from typing import Any

from sqlalchemy import Boolean, Date, DateTime, ForeignKey, Integer, JSON, String, Text, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base


class Department(Base):
    __tablename__ = "departments"

    id: Mapped[int] = mapped_column(primary_key=True)
    code: Mapped[str] = mapped_column(String(50), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(100))
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    employees: Mapped[list[Employee]] = relationship(back_populates="department")


class Employee(Base):
    __tablename__ = "employees"

    id: Mapped[int] = mapped_column(primary_key=True)
    employee_code: Mapped[str] = mapped_column(String(50), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(100))
    department_id: Mapped[int | None] = mapped_column(ForeignKey("departments.id"))
    role: Mapped[str] = mapped_column(String(30), default="member")
    wecom_userid: Mapped[str | None] = mapped_column(String(100), unique=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    department: Mapped[Department | None] = relationship(back_populates="employees")


class ReportingWeek(Base):
    __tablename__ = "reporting_weeks"
    __table_args__ = (UniqueConstraint("week_start", "week_end", name="uq_reporting_week_dates"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    week_start: Mapped[date] = mapped_column(Date, index=True)
    week_end: Mapped[date] = mapped_column(Date)
    status: Mapped[str] = mapped_column(String(20), default="open")
    is_current: Mapped[bool] = mapped_column(Boolean, default=False)


class FormSchema(Base):
    __tablename__ = "form_schemas"

    id: Mapped[int] = mapped_column(primary_key=True)
    code: Mapped[str] = mapped_column(String(100), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(200))
    department_id: Mapped[int | None] = mapped_column(ForeignKey("departments.id"))
    description: Mapped[str | None] = mapped_column(Text)
    version: Mapped[int] = mapped_column(Integer, default=1)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    department: Mapped[Department | None] = relationship()
    fields: Mapped[list[FormField]] = relationship(back_populates="schema", cascade="all, delete-orphan")


class FormField(Base):
    __tablename__ = "form_fields"
    __table_args__ = (UniqueConstraint("schema_id", "key", name="uq_schema_field_key"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    schema_id: Mapped[int] = mapped_column(ForeignKey("form_schemas.id"))
    key: Mapped[str] = mapped_column(String(100))
    label: Mapped[str] = mapped_column(String(200))
    field_type: Mapped[str] = mapped_column(String(30))
    required: Mapped[bool] = mapped_column(Boolean, default=False)
    position: Mapped[int] = mapped_column(Integer)
    config: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    schema: Mapped[FormSchema] = relationship(back_populates="fields")


class FormSubmission(Base):
    __tablename__ = "form_submissions"
    __table_args__ = (
        UniqueConstraint("schema_id", "reporting_week_id", "employee_id", name="uq_submission_scope"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    schema_id: Mapped[int] = mapped_column(ForeignKey("form_schemas.id"), index=True)
    reporting_week_id: Mapped[int] = mapped_column(ForeignKey("reporting_weeks.id"), index=True)
    employee_id: Mapped[int] = mapped_column(ForeignKey("employees.id"), index=True)
    values: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    status: Mapped[str] = mapped_column(String(20), default="submitted")
    submitted_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    schema: Mapped[FormSchema] = relationship()
    reporting_week: Mapped[ReportingWeek] = relationship()
    employee: Mapped[Employee] = relationship()


class ReportSnapshot(Base):
    __tablename__ = "report_snapshots"
    id: Mapped[int] = mapped_column(primary_key=True)
    reporting_week_id: Mapped[int] = mapped_column(ForeignKey("reporting_weeks.id"), index=True)
    source_kind: Mapped[str] = mapped_column(String(30))
    source_paths: Mapped[list[str]] = mapped_column(JSON, default=list)
    content_hash: Mapped[str] = mapped_column(String(64), index=True)
    content: Mapped[str] = mapped_column(Text)
    source_metadata: Mapped[dict[str, Any]] = mapped_column("metadata", JSON, default=dict)
    retrieved_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    reporting_week: Mapped[ReportingWeek] = relationship()


class BusinessAnalysis(Base):
    __tablename__ = "business_analyses"
    id: Mapped[int] = mapped_column(primary_key=True)
    reporting_week_id: Mapped[int] = mapped_column(ForeignKey("reporting_weeks.id"), index=True)
    report_snapshot_id: Mapped[int] = mapped_column(ForeignKey("report_snapshots.id"))
    structured_data: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    prompt: Mapped[str] = mapped_column(Text)
    output: Mapped[str | None] = mapped_column(Text)
    provider: Mapped[str] = mapped_column(String(50))
    model: Mapped[str | None] = mapped_column(String(100))
    status: Mapped[str] = mapped_column(String(40), default="pending_model_configuration")
    reviewer_id: Mapped[int | None] = mapped_column(ForeignKey("employees.id"))
    review_comment: Mapped[str | None] = mapped_column(Text)
    generated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    reporting_week: Mapped[ReportingWeek] = relationship(foreign_keys=[reporting_week_id])
    report_snapshot: Mapped[ReportSnapshot] = relationship()
    reviewer: Mapped[Employee | None] = relationship(foreign_keys=[reviewer_id])


class WecomDelivery(Base):
    __tablename__ = "wecom_deliveries"
    id: Mapped[int] = mapped_column(primary_key=True)
    reporting_week_id: Mapped[int] = mapped_column(ForeignKey("reporting_weeks.id"), index=True)
    business_analysis_id: Mapped[int | None] = mapped_column(ForeignKey("business_analyses.id"))
    trigger: Mapped[str] = mapped_column(String(30))
    status: Mapped[str] = mapped_column(String(30))
    message: Mapped[str] = mapped_column(Text)
    response_code: Mapped[int | None] = mapped_column(Integer)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    reporting_week: Mapped[ReportingWeek] = relationship()
    business_analysis: Mapped[BusinessAnalysis | None] = relationship()
