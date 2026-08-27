from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.api.v1.dependencies import require_roles
from app.core.config import settings
from app.db import get_db
from app.db.models import BusinessAnalysis, Employee, FormSubmission, ReportSnapshot, ReportingWeek
from app.services.analysis import build_analysis_prompt, generate_analysis
from app.services.hermes_jobs import enqueue_analysis_job
from app.services.report_reader import ReportReader

router = APIRouter(prefix="/api/v1")


class SnapshotRequest(BaseModel):
    reporting_week_id: int | None = None


class AnalysisRequest(BaseModel):
    reporting_week_id: int | None = None
    report_snapshot_id: int | None = None


class ReviewRequest(BaseModel):
    decision: str = Field(pattern="^(approved|rejected)$")
    comment: str = Field(min_length=1, max_length=2000)


def resolve_week(db: Session, week_id: int | None) -> ReportingWeek:
    week = db.get(ReportingWeek, week_id) if week_id else db.scalar(select(ReportingWeek).where(ReportingWeek.is_current.is_(True)))
    if week is None:
        raise HTTPException(status_code=404, detail="统计周不存在或未配置当前统计周")
    return week


def snapshot_view(item: ReportSnapshot) -> dict:
    return {"id": item.id, "reporting_week_id": item.reporting_week_id, "source_kind": item.source_kind, "source_paths": item.source_paths, "content_hash": item.content_hash, "metadata": item.source_metadata, "retrieved_at": item.retrieved_at}


def analysis_view(item: BusinessAnalysis) -> dict:
    return {"id": item.id, "reporting_week_id": item.reporting_week_id, "report_snapshot_id": item.report_snapshot_id, "structured_data": item.structured_data, "provider": item.provider, "model": item.model, "status": item.status, "output": item.output, "review_comment": item.review_comment, "reviewer": item.reviewer.name if item.reviewer else None, "generated_at": item.generated_at, "reviewed_at": item.reviewed_at}


@router.post("/report-snapshots", status_code=201)
def create_snapshot(payload: SnapshotRequest = SnapshotRequest(), db: Session = Depends(get_db), _: Employee = Depends(require_roles("admin", "department_manager"))) -> dict:
    if settings.hermes_agent_enabled:
        raise HTTPException(status_code=409, detail="云端部署由 macmini Hermes Agent 在分析任务中固化周报快照，请直接创建经营分析。")
    week = resolve_week(db, payload.reporting_week_id)
    try:
        result = ReportReader(settings.report_source_root).read_week(week.week_start, week.week_end)
    except (OSError, ValueError) as error:
        raise HTTPException(status_code=503, detail=f"周报来源不可读取：{error}") from error
    if not result.content:
        raise HTTPException(status_code=422, detail="该统计周未读取到日报或周报内容")
    item = ReportSnapshot(reporting_week_id=week.id, source_kind=result.source_kind, source_paths=result.source_paths, content_hash=result.content_hash, content=result.content, source_metadata=result.metadata)
    db.add(item)
    db.commit()
    db.refresh(item)
    return snapshot_view(item)


@router.get("/report-snapshots")
def list_snapshots(reporting_week_id: int | None = None, db: Session = Depends(get_db), _: Employee = Depends(require_roles("admin", "department_manager"))) -> list[dict]:
    statement = select(ReportSnapshot)
    if reporting_week_id:
        statement = statement.where(ReportSnapshot.reporting_week_id == reporting_week_id)
    return [snapshot_view(item) for item in db.scalars(statement.order_by(ReportSnapshot.retrieved_at.desc())).all()]


@router.post("/business-analyses", status_code=201)
def create_analysis(payload: AnalysisRequest = AnalysisRequest(), db: Session = Depends(get_db), _: Employee = Depends(require_roles("admin", "department_manager"))) -> dict:
    week = resolve_week(db, payload.reporting_week_id)
    if settings.hermes_agent_enabled:
        job = enqueue_analysis_job(db, week)
        return {"status": job.status, "job_id": job.id, "reporting_week_id": week.id, "message": "已交由 macmini Hermes Agent 处理；完成后会自动回传周报快照与分析结果。"}
    snapshot = db.get(ReportSnapshot, payload.report_snapshot_id) if payload.report_snapshot_id else db.scalar(select(ReportSnapshot).where(ReportSnapshot.reporting_week_id == week.id).order_by(ReportSnapshot.retrieved_at.desc()))
    if snapshot is None or snapshot.reporting_week_id != week.id:
        raise HTTPException(status_code=404, detail="请先生成该统计周的周报快照")
    submissions = db.scalars(select(FormSubmission).where(FormSubmission.reporting_week_id == week.id).options(selectinload(FormSubmission.schema), selectinload(FormSubmission.employee))).all()
    structured_data = {"week": {"start": week.week_start.isoformat(), "end": week.week_end.isoformat()}, "submissions": [{"form": item.schema.code, "employee": item.employee.name, "values": item.values} for item in submissions]}
    previous_snapshot = db.scalar(
        select(ReportSnapshot)
        .join(ReportingWeek, ReportingWeek.id == ReportSnapshot.reporting_week_id)
        .where(ReportingWeek.week_end < week.week_start)
        .order_by(ReportingWeek.week_end.desc(), ReportSnapshot.retrieved_at.desc())
    )
    prompt = build_analysis_prompt(structured_data, snapshot.content, previous_snapshot.content if previous_snapshot else None)
    status, model, output = generate_analysis(prompt)
    item = BusinessAnalysis(reporting_week_id=week.id, report_snapshot_id=snapshot.id, structured_data=structured_data, prompt=prompt, output=output, provider="hermes" if settings.hermes_analysis_enabled else settings.ai_provider, model=model, status=status)
    db.add(item)
    db.commit()
    db.refresh(item)
    return analysis_view(item)


@router.get("/business-analyses")
def list_analyses(reporting_week_id: int | None = None, db: Session = Depends(get_db), _: Employee = Depends(require_roles("admin", "department_manager"))) -> list[dict]:
    statement = select(BusinessAnalysis).options(selectinload(BusinessAnalysis.reviewer))
    if reporting_week_id:
        statement = statement.where(BusinessAnalysis.reporting_week_id == reporting_week_id)
    return [analysis_view(item) for item in db.scalars(statement.order_by(BusinessAnalysis.generated_at.desc())).all()]


@router.post("/business-analyses/{analysis_id}/review")
def review_analysis(analysis_id: int, payload: ReviewRequest, db: Session = Depends(get_db), reviewer: Employee = Depends(require_roles("admin", "department_manager"))) -> dict:
    item = db.get(BusinessAnalysis, analysis_id)
    if item is None:
        raise HTTPException(status_code=404, detail="分析记录不存在")
    if item.status != "generated":
        raise HTTPException(status_code=409, detail="仅可审核已由模型生成的分析结论")
    item.status = f"review_{payload.decision}"
    item.reviewer_id, item.review_comment, item.reviewed_at = reviewer.id, payload.comment, datetime.now(timezone.utc)
    db.commit()
    item = db.scalar(select(BusinessAnalysis).where(BusinessAnalysis.id == analysis_id).options(selectinload(BusinessAnalysis.reviewer)))
    return analysis_view(item)
