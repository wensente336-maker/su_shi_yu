from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.db.models import Employee, FormSchema, FormSubmission, ReportingWeek, SalesPerson


def collection_status(db: Session, week: ReportingWeek) -> dict:
    """Require every active member of a form's department to submit once."""
    forms = db.scalars(
        select(FormSchema)
        .where(FormSchema.is_active.is_(True))
        .options(selectinload(FormSchema.department))
    ).all()
    submissions = db.scalars(
        select(FormSubmission)
        .where(FormSubmission.reporting_week_id == week.id)
        .options(selectinload(FormSubmission.employee))
    ).all()
    submitted_by_schema: dict[int, set[int]] = {}
    for item in submissions:
        submitted_by_schema.setdefault(item.schema_id, set()).add(item.employee_id)

    items, missing = [], []
    for form in forms:
        if form.code == "sales-weekly-v1":
            expected = db.scalars(select(SalesPerson).where(SalesPerson.is_active.is_(True)).order_by(SalesPerson.name)).all()
            received_names = {
                " ".join(str(item.values.get("sales_person") or "").strip().split())
                for item in submissions
                if item.schema_id == form.id
            }
            pending = [person.name for person in expected if person.name not in received_names]
            expected_count, submitted_count = len(expected), len(received_names)
        else:
            expected = db.scalars(
                select(Employee)
                .where(Employee.department_id == form.department_id, Employee.is_active.is_(True))
                .order_by(Employee.id)
            ).all()
            received = submitted_by_schema.get(form.id, set())
            pending = [employee.name for employee in expected if employee.id not in received]
            expected_count, submitted_count = len(expected), len(received)
        complete = bool(expected) and not pending
        item = {
            "code": form.code,
            "name": form.name,
            "expected_count": expected_count,
            "submitted_count": submitted_count,
            "complete": complete,
            "pending_people": pending,
        }
        items.append(item)
        if not complete:
            suffix = f"（待提交：{'、'.join(pending)}）" if pending else "（未配置应填人员）"
            missing.append(f"{form.name}{suffix}")
    return {
        "complete": not missing,
        "required_form_count": len(forms),
        "submitted_form_count": sum(1 for item in items if item["complete"]),
        "missing_forms": missing,
        "forms": items,
    }
