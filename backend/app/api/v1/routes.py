from datetime import date
from numbers import Real
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.api.v1.dependencies import get_current_employee, require_roles
from app.db import get_db
from app.db.models import Department, Employee, FormField, FormSchema, FormSubmission, ReportingWeek

router = APIRouter(prefix="/api/v1")


class WeekCreate(BaseModel):
    week_start: date
    week_end: date


class SubmissionCreate(BaseModel):
    reporting_week_id: int
    values: dict[str, Any]


@router.get("/me")
def current_user(employee: Employee = Depends(get_current_employee)) -> dict:
    return {"employee_code": employee.employee_code, "name": employee.name, "role": employee.role, "department": employee.department.code if employee.department else None}


@router.get("/departments")
def list_departments(db: Session = Depends(get_db)) -> list[dict]:
    departments = db.scalars(select(Department).where(Department.is_active.is_(True)).order_by(Department.id)).all()
    return [{"code": item.code, "name": item.name} for item in departments]


@router.get("/reporting-weeks/current")
def current_week(db: Session = Depends(get_db)) -> dict:
    week = db.scalar(select(ReportingWeek).where(ReportingWeek.is_current.is_(True)))
    if week is None:
        raise HTTPException(status_code=404, detail="未配置当前统计周")
    return {"id": week.id, "week_start": week.week_start, "week_end": week.week_end, "status": week.status}


@router.get("/reporting-weeks")
def list_weeks(db: Session = Depends(get_db)) -> list[dict]:
    weeks = db.scalars(select(ReportingWeek).order_by(ReportingWeek.week_start.desc())).all()
    return [{"id": week.id, "week_start": week.week_start, "week_end": week.week_end, "status": week.status, "is_current": week.is_current} for week in weeks]


@router.post("/reporting-weeks", status_code=201)
def create_week(payload: WeekCreate, db: Session = Depends(get_db), _: Employee = Depends(require_roles("admin"))) -> dict:
    if payload.week_end < payload.week_start:
        raise HTTPException(status_code=422, detail="周结束日期不能早于开始日期")
    db.query(ReportingWeek).update({ReportingWeek.is_current: False})
    week = ReportingWeek(week_start=payload.week_start, week_end=payload.week_end, is_current=True)
    db.add(week)
    db.commit()
    db.refresh(week)
    return {"id": week.id, "week_start": week.week_start, "week_end": week.week_end, "status": week.status}


@router.get("/form-schemas")
def list_form_schemas(db: Session = Depends(get_db), employee: Employee = Depends(get_current_employee)) -> list[dict]:
    statement = select(FormSchema).where(FormSchema.is_active.is_(True)).options(selectinload(FormSchema.department))
    if employee.role not in {"admin"} and employee.department_id:
        statement = statement.where(FormSchema.department_id == employee.department_id)
    schemas = db.scalars(statement.order_by(FormSchema.id)).all()
    return [{"code": item.code, "name": item.name, "description": item.description, "version": item.version, "department": item.department.code if item.department else None} for item in schemas]


@router.get("/form-schemas/{schema_code}")
def get_form_schema(schema_code: str, db: Session = Depends(get_db), employee: Employee = Depends(get_current_employee)) -> dict:
    schema = db.scalar(select(FormSchema).where(FormSchema.code == schema_code, FormSchema.is_active.is_(True)).options(selectinload(FormSchema.department), selectinload(FormSchema.fields)))
    if schema is None:
        raise HTTPException(status_code=404, detail="表单配置不存在")
    if employee.role != "admin" and schema.department_id != employee.department_id:
        raise HTTPException(status_code=403, detail="当前身份无权读取该部门表单")
    return {"code": schema.code, "name": schema.name, "description": schema.description, "version": schema.version, "department": schema.department.code if schema.department else None, "fields": [{"key": field.key, "label": field.label, "type": field.field_type, "required": field.required, "config": field.config} for field in sorted(schema.fields, key=lambda field: field.position)]}


def _get_accessible_schema(schema_code: str, db: Session, employee: Employee) -> FormSchema:
    schema = db.scalar(select(FormSchema).where(FormSchema.code == schema_code, FormSchema.is_active.is_(True)).options(selectinload(FormSchema.fields)))
    if schema is None:
        raise HTTPException(status_code=404, detail="表单配置不存在")
    if employee.role != "admin" and schema.department_id != employee.department_id:
        raise HTTPException(status_code=403, detail="当前身份无权操作该部门表单")
    return schema


def _validate_values(fields: list[FormField], values: dict[str, Any]) -> dict[str, Any]:
    known_keys = {field.key for field in fields}
    unknown_keys = set(values) - known_keys
    if unknown_keys:
        raise HTTPException(status_code=422, detail=f"存在未定义字段：{', '.join(sorted(unknown_keys))}")

    cleaned: dict[str, Any] = {}
    for field in fields:
        value = values.get(field.key)
        if value is None or value == "":
            if field.required:
                raise HTTPException(status_code=422, detail=f"{field.label}为必填项")
            continue
        if field.field_type in {"currency", "number"}:
            if not isinstance(value, Real) or isinstance(value, bool):
                raise HTTPException(status_code=422, detail=f"{field.label}必须为数字")
            numeric_value = float(value)
            if "min" in field.config and numeric_value < field.config["min"]:
                raise HTTPException(status_code=422, detail=f"{field.label}不能小于{field.config['min']}")
            cleaned[field.key] = numeric_value
        elif field.field_type == "textarea":
            if not isinstance(value, str):
                raise HTTPException(status_code=422, detail=f"{field.label}必须为文本")
            max_length = field.config.get("max_length")
            if max_length and len(value) > max_length:
                raise HTTPException(status_code=422, detail=f"{field.label}不能超过{max_length}个字符")
            cleaned[field.key] = value.strip()
        elif field.field_type == "text":
            if not isinstance(value, str):
                raise HTTPException(status_code=422, detail=f"{field.label}必须为文本")
            text_value = value.strip()
            if not text_value:
                raise HTTPException(status_code=422, detail=f"{field.label}不能为空")
            if field.config.get("max_length") and len(text_value) > field.config["max_length"]:
                raise HTTPException(status_code=422, detail=f"{field.label}不能超过{field.config['max_length']}个字符")
            cleaned[field.key] = text_value
        elif field.field_type == "select":
            options = field.config.get("options", [])
            if not isinstance(value, str) or value not in options:
                raise HTTPException(status_code=422, detail=f"{field.label}必须从预设选项中选择")
            cleaned[field.key] = value
        else:
            cleaned[field.key] = value
    return cleaned


def _submission_response(submission: FormSubmission) -> dict:
    return {"id": submission.id, "schema_code": submission.schema.code, "reporting_week": {"id": submission.reporting_week.id, "week_start": submission.reporting_week.week_start, "week_end": submission.reporting_week.week_end}, "employee": {"employee_code": submission.employee.employee_code, "name": submission.employee.name}, "values": submission.values, "status": submission.status, "submitted_at": submission.submitted_at}


@router.post("/form-schemas/{schema_code}/submissions", status_code=201)
def create_or_update_submission(schema_code: str, payload: SubmissionCreate, db: Session = Depends(get_db), employee: Employee = Depends(get_current_employee)) -> dict:
    schema = _get_accessible_schema(schema_code, db, employee)
    week = db.get(ReportingWeek, payload.reporting_week_id)
    if week is None:
        raise HTTPException(status_code=404, detail="统计周不存在")
    if week.status != "open":
        raise HTTPException(status_code=409, detail="当前统计周已关闭，不能录入")
    cleaned_values = _validate_values(schema.fields, payload.values)
    submission = db.scalar(select(FormSubmission).where(FormSubmission.schema_id == schema.id, FormSubmission.reporting_week_id == week.id, FormSubmission.employee_id == employee.id))
    if submission is None:
        submission = FormSubmission(schema_id=schema.id, reporting_week_id=week.id, employee_id=employee.id, values=cleaned_values)
        db.add(submission)
    else:
        submission.values = cleaned_values
    db.commit()
    db.refresh(submission)
    submission = db.scalar(select(FormSubmission).where(FormSubmission.id == submission.id).options(selectinload(FormSubmission.schema), selectinload(FormSubmission.reporting_week), selectinload(FormSubmission.employee)))
    return _submission_response(submission)


@router.get("/form-schemas/{schema_code}/submissions")
def list_submissions(schema_code: str, reporting_week_id: int | None = None, db: Session = Depends(get_db), employee: Employee = Depends(get_current_employee)) -> list[dict]:
    schema = _get_accessible_schema(schema_code, db, employee)
    statement = select(FormSubmission).where(FormSubmission.schema_id == schema.id).options(selectinload(FormSubmission.schema), selectinload(FormSubmission.reporting_week), selectinload(FormSubmission.employee))
    if reporting_week_id is not None:
        statement = statement.where(FormSubmission.reporting_week_id == reporting_week_id)
    if employee.role == "member":
        statement = statement.where(FormSubmission.employee_id == employee.id)
    submissions = db.scalars(statement.order_by(FormSubmission.submitted_at.desc())).all()
    return [_submission_response(item) for item in submissions]
