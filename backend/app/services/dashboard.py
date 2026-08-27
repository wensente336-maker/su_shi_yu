from __future__ import annotations

from datetime import date
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.db.models import BusinessAnalysis, FormSchema, FormSubmission, PersonalMonthlyTarget, ReportSnapshot, ReportingWeek
from app.services.completion import collection_status


def month_bounds(target_month: date) -> tuple[date, date]:
    """Return the inclusive calendar-month start and exclusive next-month start."""
    month_start = date(target_month.year, target_month.month, 1)
    return month_start, date(month_start.year + (month_start.month == 12), (month_start.month % 12) + 1, 1)


def build_overview(db: Session, week: ReportingWeek, target_month: date | None = None) -> dict[str, Any]:
    submissions = db.scalars(select(FormSubmission).where(FormSubmission.reporting_week_id == week.id).options(selectinload(FormSubmission.schema))).all()
    required_forms = db.scalars(select(FormSchema).where(FormSchema.is_active.is_(True))).all()
    submitted_form_codes = {item.schema.code for item in submissions}
    collection = collection_status(db, week)
    collection_by_code = {item["code"]: item for item in collection["forms"]}
    totals = {"sales_amount": 0.0, "new_leads": 0.0, "signed_customers": 0.0, "revenue": 0.0, "cash_inflow": 0.0}
    for submission in submissions:
        for key in totals:
            value = submission.values.get(key)
            if isinstance(value, (int, float)) and not isinstance(value, bool):
                totals[key] += float(value)
    approved = db.scalar(select(BusinessAnalysis).where(BusinessAnalysis.reporting_week_id == week.id, BusinessAnalysis.status == "review_approved").order_by(BusinessAnalysis.reviewed_at.desc()))
    latest = approved or db.scalar(select(BusinessAnalysis).where(BusinessAnalysis.reporting_week_id == week.id).order_by(BusinessAnalysis.generated_at.desc()))
    snapshot = db.scalar(select(ReportSnapshot).where(ReportSnapshot.reporting_week_id == week.id).order_by(ReportSnapshot.retrieved_at.desc()))
    previous_snapshot = db.scalar(
        select(ReportSnapshot)
        .join(ReportingWeek, ReportingWeek.id == ReportSnapshot.reporting_week_id)
        .where(ReportingWeek.week_end < week.week_start)
        .order_by(ReportingWeek.week_end.desc(), ReportSnapshot.retrieved_at.desc())
    )
    teams: dict[str, dict[str, float]] = {}
    people: dict[str, dict[str, float | str]] = {}
    for submission in submissions:
        values = submission.values
        if submission.schema.code != "sales-weekly-v1":
            continue
        team = str(values.get("sales_team") or "未分组")
        person = str(values.get("sales_person") or submission.employee.name)
        amount = float(values.get("sales_amount") or 0)
        customers = float(values.get("signed_customers") or 0)
        teams.setdefault(team, {"sales_amount": 0.0, "signed_customers": 0.0})
        teams[team]["sales_amount"] += amount
        teams[team]["signed_customers"] += customers
        people.setdefault(person, {"name": person, "sales_team": team, "sales_amount": 0.0, "signed_customers": 0.0})
        people[person]["sales_amount"] = float(people[person]["sales_amount"]) + amount
        people[person]["signed_customers"] = float(people[person]["signed_customers"]) + customers
    team_performance = [{"name": name, **values} for name, values in teams.items()]
    team_performance.sort(key=lambda item: item["sales_amount"], reverse=True)
    target_month = target_month or date(week.week_end.year, week.week_end.month, 1)
    target_month, next_month = month_bounds(target_month)
    simulation_week_exists = db.scalar(
        select(ReportingWeek.id).where(
            ReportingWeek.week_end >= target_month,
            ReportingWeek.week_end < next_month,
            ReportingWeek.status == "simulation",
        )
    ) is not None
    monthly_submissions = db.scalars(
        select(FormSubmission)
        .join(FormSchema)
        .join(ReportingWeek)
        .where(
            FormSchema.code == "sales-weekly-v1",
            ReportingWeek.week_end >= target_month,
            ReportingWeek.week_end < next_month,
            ReportingWeek.status != "simulation",
            FormSubmission.status == "submitted",
        )
        .options(selectinload(FormSubmission.reporting_week))
    ).all()
    monthly_people: dict[str, dict[str, float | str]] = {}
    for submission in monthly_submissions:
        values = submission.values
        person = str(values.get("sales_person") or submission.employee.name)
        monthly_people.setdefault(person, {"name": person, "sales_team": "未分组", "sales_amount": 0.0, "signed_customers": 0.0})
        monthly_people[person]["sales_team"] = str(values.get("sales_team") or "未分组")
        monthly_people[person]["sales_amount"] = float(monthly_people[person]["sales_amount"]) + float(values.get("sales_amount") or 0)
        monthly_people[person]["signed_customers"] = float(monthly_people[person]["signed_customers"]) + float(values.get("signed_customers") or 0)
    monthly_targets = db.scalars(
        select(PersonalMonthlyTarget)
        .where(PersonalMonthlyTarget.target_month == target_month)
        .order_by(PersonalMonthlyTarget.sales_person)
    ).all()
    target_items = []
    for target in monthly_targets:
        actual = monthly_people.get(target.sales_person, {"sales_team": "未分组", "sales_amount": 0.0, "signed_customers": 0.0})
        sales_target = float(target.sales_amount_target)
        customer_target = float(target.signed_customers_target) if target.signed_customers_target is not None else None
        target_items.append({
            "name": target.sales_person,
            "sales_team": actual["sales_team"],
            "sales_amount": actual["sales_amount"],
            "signed_customers": actual["signed_customers"],
            "sales_amount_target": sales_target,
            "signed_customers_target": customer_target,
            "sales_completion": actual["sales_amount"] / sales_target if sales_target else None,
            "signed_customers_completion": actual["signed_customers"] / customer_target if customer_target else None,
        })
    target_items.sort(key=lambda item: (item["sales_completion"] is None, -(item["sales_completion"] or 0)))
    sales_ranking = list(people.values())
    sales_ranking.sort(key=lambda item: float(item["sales_amount"]), reverse=True)

    recent_weeks = list(reversed(db.scalars(select(ReportingWeek).order_by(ReportingWeek.week_start.desc()).limit(8)).all()))
    recent_ids = [item.id for item in recent_weeks]
    recent_submissions = db.scalars(select(FormSubmission).where(FormSubmission.reporting_week_id.in_(recent_ids))).all() if recent_ids else []
    by_week: dict[int, dict[str, float]] = {item.id: {"sales_amount": 0.0, "cash_inflow": 0.0} for item in recent_weeks}
    for submission in recent_submissions:
        by_week[submission.reporting_week_id]["sales_amount"] += float(submission.values.get("sales_amount") or 0)
        by_week[submission.reporting_week_id]["cash_inflow"] += float(submission.values.get("cash_inflow") or 0)
    trend = [{"label": item.week_start.strftime("%m/%d"), **by_week[item.id]} for item in recent_weeks]
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
        "collection": collection,
        "source_status": [
            {
                "name": form.name,
                "kind": "form",
                "complete": collection_by_code[form.code]["complete"],
                "pending_people": collection_by_code[form.code]["pending_people"],
            }
            for form in required_forms
        ] + [
            {"name": "本周周报快照", "kind": "report", "complete": snapshot is not None},
            {"name": "上周真实周报背景", "kind": "report", "complete": previous_snapshot is not None},
        ],
        "team_performance": team_performance,
        "sales_ranking": sales_ranking,
        "trend": trend,
        "personal_goals": {
            "target_month": target_month.strftime("%Y-%m"),
            "configured": bool(target_items),
            "message": "尚未配置个人月度目标" if not target_items else "已按个人月度目标计算当月累计完成率",
            "source_note": "模拟统计周已自动排除，未计入月度完成率。" if simulation_week_exists else "按统计周结束日所属月份累计，仅计入有效销售填报。",
            "items": target_items,
        },
        "report_snapshot": {"id": snapshot.id, "source_kind": snapshot.source_kind, "retrieved_at": snapshot.retrieved_at} if snapshot else None,
        "previous_week_report": {
            "week_start": previous_snapshot.reporting_week.week_start,
            "week_end": previous_snapshot.reporting_week.week_end,
            "source_kind": previous_snapshot.source_kind,
            "retrieved_at": previous_snapshot.retrieved_at,
        } if previous_snapshot else None,
        "analysis": {"id": latest.id, "status": latest.status, "output": latest.output, "review_comment": latest.review_comment} if latest else None,
    }
