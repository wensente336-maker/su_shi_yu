from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.v1.dependencies import require_roles
from app.db import get_db
from app.db.models import Employee, ReportingWeek, WecomDelivery
from app.services.dashboard import build_overview
from app.services.wecom import deliver_weekly_summary

router = APIRouter(prefix="/api/v1")


def current_week(db: Session, week_id: int | None) -> ReportingWeek:
    week = db.get(ReportingWeek, week_id) if week_id else db.scalar(select(ReportingWeek).where(ReportingWeek.is_current.is_(True)))
    if week is None:
        raise HTTPException(status_code=404, detail="统计周不存在")
    return week


@router.get("/dashboard/overview")
def dashboard_overview(reporting_week_id: int | None = None, db: Session = Depends(get_db), _: Employee = Depends(require_roles("admin", "department_manager"))) -> dict:
    return build_overview(db, current_week(db, reporting_week_id))


@router.post("/wecom-deliveries/weekly", status_code=201)
def send_weekly_summary(db: Session = Depends(get_db), _: Employee = Depends(require_roles("admin"))) -> dict:
    item = deliver_weekly_summary(db, "manual")
    return {"id": item.id, "status": item.status, "message": item.message, "response_code": item.response_code, "created_at": item.created_at}


@router.get("/wecom-deliveries")
def list_deliveries(db: Session = Depends(get_db), _: Employee = Depends(require_roles("admin", "department_manager"))) -> list[dict]:
    items = db.scalars(select(WecomDelivery).order_by(WecomDelivery.created_at.desc())).all()
    return [{"id": item.id, "reporting_week_id": item.reporting_week_id, "trigger": item.trigger, "status": item.status, "message": item.message, "response_code": item.response_code, "created_at": item.created_at} for item in items]
