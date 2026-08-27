from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.core.config import settings
from app.db.models import BusinessAnalysis, FormSubmission, ReportSnapshot, ReportingWeek, WecomDelivery
from app.services.analysis import build_analysis_prompt, generate_analysis
from app.services.completion import collection_status
from app.services.hermes_jobs import enqueue_analysis_job
from app.services.report_reader import ReportReader
from app.services.wecom import deliver_exception, deliver_weekly_summary


def _snapshot_week(db: Session, week: ReportingWeek) -> ReportSnapshot:
    result = ReportReader(settings.report_source_root).read_week(week.week_start, week.week_end)
    if not result.content:
        raise RuntimeError("未读取到本周周报文件")
    latest = db.scalar(
        select(ReportSnapshot)
        .where(ReportSnapshot.reporting_week_id == week.id)
        .order_by(ReportSnapshot.retrieved_at.desc())
    )
    if latest and latest.content_hash == result.content_hash:
        return latest
    item = ReportSnapshot(
        reporting_week_id=week.id,
        source_kind=result.source_kind,
        source_paths=result.source_paths,
        content_hash=result.content_hash,
        content=result.content,
        source_metadata=result.metadata,
    )
    db.add(item)
    db.commit()
    db.refresh(item)
    return item


def _generate_analysis(db: Session, week: ReportingWeek, snapshot: ReportSnapshot) -> BusinessAnalysis:
    submissions = db.scalars(
        select(FormSubmission)
        .where(FormSubmission.reporting_week_id == week.id)
        .options(selectinload(FormSubmission.schema), selectinload(FormSubmission.employee))
    ).all()
    structured_data = {
        "week": {"start": week.week_start.isoformat(), "end": week.week_end.isoformat()},
        "submissions": [
            {"form": item.schema.code, "employee": item.employee.name, "values": item.values}
            for item in submissions
        ],
    }
    previous_snapshot = db.scalar(
        select(ReportSnapshot)
        .join(ReportingWeek, ReportingWeek.id == ReportSnapshot.reporting_week_id)
        .where(ReportingWeek.week_end < week.week_start)
        .order_by(ReportingWeek.week_end.desc(), ReportSnapshot.retrieved_at.desc())
    )
    prompt = build_analysis_prompt(structured_data, snapshot.content, previous_snapshot.content if previous_snapshot else None)
    status, model, output = generate_analysis(prompt)
    item = BusinessAnalysis(
        reporting_week_id=week.id,
        report_snapshot_id=snapshot.id,
        structured_data=structured_data,
        prompt=prompt,
        output=output,
        provider="hermes" if settings.hermes_analysis_enabled else settings.ai_provider,
        model=model,
        status=status,
    )
    db.add(item)
    db.commit()
    db.refresh(item)
    return item


def run_scheduled_weekly_cycle(db: Session) -> None:
    week = db.scalar(select(ReportingWeek).where(ReportingWeek.is_current.is_(True)))
    if week is None:
        return
    if week.status == "simulation":
        return
    already_sent = db.scalar(
        select(WecomDelivery.id).where(
            WecomDelivery.reporting_week_id == week.id,
            WecomDelivery.trigger == "scheduled",
            WecomDelivery.status == "sent",
        )
    )
    if already_sent:
        return
    status = collection_status(db, week)
    if not status["complete"]:
        deliver_weekly_summary(db, "scheduled")
        return
    try:
        if settings.hermes_agent_enabled:
            analysis = db.scalar(
                select(BusinessAnalysis)
                .where(BusinessAnalysis.reporting_week_id == week.id)
                .order_by(BusinessAnalysis.generated_at.desc())
            )
            if analysis is None or analysis.status == "hermes_analysis_failed":
                enqueue_analysis_job(db, week)
                return
            delivery = deliver_weekly_summary(db, "scheduled")
            if delivery.status == "sent":
                week.status = "closed"
                db.commit()
            return
        snapshot = _snapshot_week(db, week)
        analysis = db.scalar(
            select(BusinessAnalysis)
            .where(BusinessAnalysis.reporting_week_id == week.id, BusinessAnalysis.report_snapshot_id == snapshot.id)
            .order_by(BusinessAnalysis.generated_at.desc())
        )
        if analysis is None or analysis.status in {"hermes_analysis_failed", "pending_model_configuration"}:
            _generate_analysis(db, week, snapshot)
        delivery = deliver_weekly_summary(db, "scheduled")
        if delivery.status == "sent":
            week.status = "closed"
            db.commit()
    except Exception as error:
        deliver_exception(db, week, "scheduled", f"自动汇总失败：{error}")
