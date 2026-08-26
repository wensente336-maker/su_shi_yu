from __future__ import annotations

from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.db.models import BusinessAnalysis, FormSchema, FormSubmission, ReportSnapshot, ReportingWeek


def build_overview(db: Session, week: ReportingWeek) -> dict[str, Any]:
    submissions = db.scalars(select(FormSubmission).where(FormSubmission.reporting_week_id == week.id).options(selectinload(FormSubmission.schema))).all()
    required_forms = db.scalars(select(FormSchema).where(FormSchema.is_active.is_(True))).all()
    submitted_form_codes = {item.schema.code for item in submissions}
    missing_forms = [item.name for item in required_forms if item.code not in submitted_form_codes]
    totals = {"sales_amount": 0.0, "new_leads": 0.0, "signed_customers": 0.0, "revenue": 0.0, "cash_inflow": 0.0}
    for submission in submissions:
        for key in totals:
            value = submission.values.get(key)
            if isinstance(value, (int, float)) and not isinstance(value, bool):
                totals[key] += float(value)
    approved = db.scalar(select(BusinessAnalysis).where(BusinessAnalysis.reporting_week_id == week.id, BusinessAnalysis.status == "review_approved").order_by(BusinessAnalysis.reviewed_at.desc()))
    latest = approved or db.scalar(select(BusinessAnalysis).where(BusinessAnalysis.reporting_week_id == week.id).order_by(BusinessAnalysis.generated_at.desc()))
    snapshot = db.scalar(select(ReportSnapshot).where(ReportSnapshot.reporting_week_id == week.id).order_by(ReportSnapshot.retrieved_at.desc()))
    return {
        "title": "深圳盈进经营数据中心",
        "week": {"id": week.id, "week_start": week.week_start, "week_end": week.week_end, "status": week.status},
        "metrics": [
            {"key": "sales_amount", "label": "销售额", "value": totals["sales_amount"], "unit": "元"},
            {"key": "new_leads", "label": "新增线索", "value": totals["new_leads"], "unit": "个"},
            {"key": "signed_customers", "label": "成交客户", "value": totals["signed_customers"], "unit": "个"},
            {"key": "revenue", "label": "营业收入", "value": totals["revenue"], "unit": "元"},
            {"key": "cash_inflow", "label": "回款", "value": totals["cash_inflow"], "unit": "元"},
        ],
        "submission_count": len(submissions),
        "collection": {"complete": not missing_forms, "required_form_count": len(required_forms), "submitted_form_count": len(submitted_form_codes), "missing_forms": missing_forms},
        "report_snapshot": {"id": snapshot.id, "source_kind": snapshot.source_kind, "retrieved_at": snapshot.retrieved_at} if snapshot else None,
        "analysis": {"id": latest.id, "status": latest.status, "output": latest.output, "review_comment": latest.review_comment} if latest else None,
    }
