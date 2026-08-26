from datetime import date

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.api.v1.dependencies import get_current_employee, require_roles
from app.db import get_db
from app.db.models import Department, Employee, FormSchema, ReportingWeek

router = APIRouter(prefix="/api/v1")


class WeekCreate(BaseModel):
    week_start: date
    week_end: date


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
