"""Authenticated pull API used only by the outbound macmini Hermes agent."""

from __future__ import annotations

import hashlib
import hmac
import secrets
import time
from datetime import datetime, timedelta, timezone
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field
from sqlalchemy import delete
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.config import settings
from app.db import get_db
from app.db.models import HermesAgentNonce
from app.services.hermes_jobs import claim_next_job, complete_job, fail_job


router = APIRouter(prefix="/api/v1/internal/hermes", tags=["private-hermes-agent"])


class AgentResult(BaseModel):
    lease_token: str = Field(min_length=32, max_length=256)
    output: str = Field(min_length=1, max_length=70_000)
    model: str | None = Field(default=None, max_length=100)
    prompt: str | None = Field(default=None, max_length=180_000)
    report_content: str = Field(min_length=1, max_length=70_000)
    source_kind: str | None = Field(default="markdown", max_length=30)
    source_paths: list[str] = Field(default_factory=list, max_length=20)
    source_metadata: dict[str, Any] = Field(default_factory=dict)


class AgentFailure(BaseModel):
    lease_token: str = Field(min_length=32, max_length=256)
    error_message: str = Field(min_length=1, max_length=2_000)


async def require_signed_agent(request: Request, db: Session = Depends(get_db)) -> str:
    if not settings.hermes_agent_enabled or not settings.hermes_agent_shared_secret:
        raise HTTPException(status_code=404, detail="Hermes Agent 通道未启用")
    agent_id = request.headers.get("X-Hermes-Agent-Id", "")
    timestamp = request.headers.get("X-Hermes-Timestamp", "")
    nonce = request.headers.get("X-Hermes-Nonce", "")
    signature = request.headers.get("X-Hermes-Signature", "")
    if not all((agent_id, timestamp, nonce, signature)) or agent_id != settings.hermes_agent_id:
        raise HTTPException(status_code=401, detail="Hermes Agent 身份无效")
    try:
        timestamp_int = int(timestamp)
    except ValueError as error:
        raise HTTPException(status_code=401, detail="Hermes Agent 时间戳无效") from error
    if abs(int(time.time()) - timestamp_int) > settings.hermes_agent_clock_skew_seconds:
        raise HTTPException(status_code=401, detail="Hermes Agent 时间戳超出允许范围")
    body = await request.body()
    body_hash = hashlib.sha256(body).hexdigest()
    canonical = f"{request.method}\n{request.url.path}\n{timestamp}\n{nonce}\n{body_hash}".encode("utf-8")
    expected = hmac.new(settings.hermes_agent_shared_secret.encode("utf-8"), canonical, hashlib.sha256).hexdigest()
    if not hmac.compare_digest(signature, expected):
        raise HTTPException(status_code=401, detail="Hermes Agent 签名无效")
    now = datetime.now(timezone.utc)
    db.execute(delete(HermesAgentNonce).where(HermesAgentNonce.expires_at < now))
    db.add(HermesAgentNonce(agent_id=agent_id, nonce=nonce[:100], expires_at=now + timedelta(seconds=settings.hermes_agent_clock_skew_seconds)))
    try:
        db.commit()
    except IntegrityError as error:
        db.rollback()
        raise HTTPException(status_code=409, detail="Hermes Agent 请求已处理") from error
    return agent_id


@router.post("/jobs/claim")
def claim_job(agent_id: str = Depends(require_signed_agent), db: Session = Depends(get_db)) -> dict:
    claimed = claim_next_job(db, agent_id)
    if claimed is None:
        return {"job": None}
    job, token = claimed
    return {
        "job": {
            "id": job.id,
            "lease_token": token,
            "lease_expires_at": job.lease_expires_at,
            "payload": job.payload,
        }
    }


@router.post("/jobs/{job_id}/complete")
def complete_claimed_job(job_id: int, payload: AgentResult, agent_id: str = Depends(require_signed_agent), db: Session = Depends(get_db)) -> dict:
    try:
        job, analysis = complete_job(db, job_id, agent_id, payload.lease_token, payload.model_dump())
    except LookupError as error:
        raise HTTPException(status_code=404, detail=str(error)) from error
    except PermissionError as error:
        raise HTTPException(status_code=409, detail=str(error)) from error
    except ValueError as error:
        raise HTTPException(status_code=422, detail=str(error)) from error
    return {"job_id": job.id, "status": job.status, "analysis_id": analysis.id if analysis else None}


@router.post("/jobs/{job_id}/fail")
def fail_claimed_job(job_id: int, payload: AgentFailure, agent_id: str = Depends(require_signed_agent), db: Session = Depends(get_db)) -> dict:
    try:
        job = fail_job(db, job_id, agent_id, payload.lease_token, payload.error_message)
    except LookupError as error:
        raise HTTPException(status_code=404, detail=str(error)) from error
    except PermissionError as error:
        raise HTTPException(status_code=409, detail=str(error)) from error
    return {"job_id": job.id, "status": job.status, "attempt_count": job.attempt_count}
