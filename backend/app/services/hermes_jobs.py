"""Durable hand-off between the cloud API and the private Hermes agent."""

from __future__ import annotations

import hashlib
import secrets
from datetime import datetime, timedelta, timezone
from typing import Any

from sqlalchemy import select, update
from sqlalchemy.orm import Session, selectinload

from app.core.config import settings
from app.db.models import BusinessAnalysis, FormSubmission, HermesAnalysisJob, ReportSnapshot, ReportingWeek
from app.services.report_reader import clip_utf8


MAX_AGENT_OUTPUT_BYTES = 70_000
MAX_AGENT_REPORT_BYTES = 70_000


def structured_data_for_week(db: Session, week: ReportingWeek) -> dict[str, Any]:
    submissions = db.scalars(
        select(FormSubmission)
        .where(FormSubmission.reporting_week_id == week.id)
        .options(selectinload(FormSubmission.schema), selectinload(FormSubmission.employee))
    ).all()
    return {
        "week": {"start": week.week_start.isoformat(), "end": week.week_end.isoformat()},
        "submissions": [
            {"form": item.schema.code, "employee": item.employee.name, "values": item.values}
            for item in submissions
        ],
    }


def enqueue_analysis_job(db: Session, week: ReportingWeek) -> HermesAnalysisJob:
    """Create once per reporting week; failed leases are retried by the same job."""
    key = f"weekly-analysis:{week.id}"
    item = db.scalar(select(HermesAnalysisJob).where(HermesAnalysisJob.idempotency_key == key))
    if item is not None:
        return item
    previous_snapshot = db.scalar(
        select(ReportSnapshot)
        .join(ReportingWeek, ReportingWeek.id == ReportSnapshot.reporting_week_id)
        .where(ReportingWeek.week_end < week.week_start)
        .order_by(ReportingWeek.week_end.desc(), ReportSnapshot.retrieved_at.desc())
    )
    payload = {
        "job_type": "weekly_business_analysis",
        "week": {"id": week.id, "start": week.week_start.isoformat(), "end": week.week_end.isoformat()},
        "structured_data": structured_data_for_week(db, week),
        "previous_week_report": clip_utf8(previous_snapshot.content, 20_000) if previous_snapshot else None,
    }
    item = HermesAnalysisJob(
        reporting_week_id=week.id,
        idempotency_key=key,
        status="queued",
        payload=payload,
        max_attempts=settings.hermes_agent_max_attempts,
    )
    db.add(item)
    db.commit()
    db.refresh(item)
    return item


def claim_next_job(db: Session, agent_id: str) -> tuple[HermesAnalysisJob, str] | None:
    now = datetime.now(timezone.utc)
    db.execute(
        update(HermesAnalysisJob)
        .where(
            HermesAnalysisJob.status == "leased",
            HermesAnalysisJob.lease_expires_at.is_not(None),
            HermesAnalysisJob.lease_expires_at < now,
            HermesAnalysisJob.attempt_count >= HermesAnalysisJob.max_attempts,
        )
        .values(status="failed", error_message="Hermes Agent 租约多次超时", updated_at=now)
    )
    job = db.scalar(
        select(HermesAnalysisJob)
        .where(
            (HermesAnalysisJob.status == "queued")
            | ((HermesAnalysisJob.status == "leased") & (HermesAnalysisJob.lease_expires_at < now)),
            HermesAnalysisJob.attempt_count < HermesAnalysisJob.max_attempts,
        )
        .order_by(HermesAnalysisJob.created_at.asc())
        .with_for_update(skip_locked=True)
    )
    if job is None:
        db.commit()
        return None
    token = secrets.token_urlsafe(32)
    job.status = "leased"
    job.agent_id = agent_id
    job.lease_token_hash = hashlib.sha256(token.encode("utf-8")).hexdigest()
    job.lease_expires_at = now + timedelta(seconds=settings.hermes_agent_lease_seconds)
    job.attempt_count += 1
    job.updated_at = now
    db.commit()
    db.refresh(job)
    return job, token


def complete_job(db: Session, job_id: int, agent_id: str, lease_token: str, result: dict[str, Any]) -> tuple[HermesAnalysisJob, BusinessAnalysis | None]:
    job = db.scalar(select(HermesAnalysisJob).where(HermesAnalysisJob.id == job_id).with_for_update())
    if job is None:
        raise LookupError("任务不存在")
    if job.status == "completed" and job.agent_id == agent_id:
        analysis = db.scalar(
            select(BusinessAnalysis)
            .where(BusinessAnalysis.reporting_week_id == job.reporting_week_id)
            .order_by(BusinessAnalysis.generated_at.desc())
        )
        db.commit()
        return job, analysis
    token_hash = hashlib.sha256(lease_token.encode("utf-8")).hexdigest()
    now = datetime.now(timezone.utc)
    if job.status != "leased" or job.agent_id != agent_id or not job.lease_expires_at or job.lease_expires_at < now or not secrets.compare_digest(job.lease_token_hash or "", token_hash):
        db.rollback()
        raise PermissionError("任务租约无效或已过期")

    content = clip_utf8(str(result["report_content"]), MAX_AGENT_REPORT_BYTES)
    if not content:
        db.rollback()
        raise ValueError("周报快照不能为空")
    content_hash = hashlib.sha256(content.encode("utf-8")).hexdigest()
    snapshot = db.scalar(
        select(ReportSnapshot)
        .where(ReportSnapshot.reporting_week_id == job.reporting_week_id, ReportSnapshot.content_hash == content_hash)
        .order_by(ReportSnapshot.retrieved_at.desc())
    )
    if snapshot is None:
        snapshot = ReportSnapshot(
            reporting_week_id=job.reporting_week_id,
            source_kind=str(result.get("source_kind") or "markdown")[:30],
            source_paths=[str(path)[:500] for path in result.get("source_paths", [])[:20]],
            content_hash=content_hash,
            content=content,
            source_metadata=result.get("source_metadata") if isinstance(result.get("source_metadata"), dict) else {},
        )
        db.add(snapshot)
        db.flush()
    output = clip_utf8(str(result["output"]), MAX_AGENT_OUTPUT_BYTES)
    analysis = BusinessAnalysis(
        reporting_week_id=job.reporting_week_id,
        report_snapshot_id=snapshot.id,
        structured_data=job.payload["structured_data"],
        prompt=str(result.get("prompt") or "")[:180_000],
        output=output,
        provider="hermes_agent",
        model=str(result.get("model") or "hermes")[:100],
        status="generated",
    )
    db.add(analysis)
    job.status = "completed"
    job.lease_token_hash = None
    job.lease_expires_at = None
    job.completed_at = now
    job.updated_at = now
    job.error_message = None
    db.commit()
    db.refresh(job)
    db.refresh(analysis)
    return job, analysis


def fail_job(db: Session, job_id: int, agent_id: str, lease_token: str, error_message: str) -> HermesAnalysisJob:
    job = db.scalar(select(HermesAnalysisJob).where(HermesAnalysisJob.id == job_id).with_for_update())
    if job is None:
        raise LookupError("任务不存在")
    token_hash = hashlib.sha256(lease_token.encode("utf-8")).hexdigest()
    now = datetime.now(timezone.utc)
    if job.status != "leased" or job.agent_id != agent_id or not secrets.compare_digest(job.lease_token_hash or "", token_hash):
        db.rollback()
        raise PermissionError("任务租约无效")
    job.error_message = error_message[:2_000]
    job.lease_token_hash = None
    job.lease_expires_at = None
    job.updated_at = now
    job.status = "failed" if job.attempt_count >= job.max_attempts else "queued"
    db.commit()
    db.refresh(job)
    return job
