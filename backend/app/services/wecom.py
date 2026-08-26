from __future__ import annotations

import httpx
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.db.models import BusinessAnalysis, ReportingWeek, WecomDelivery
from app.services.dashboard import build_overview


def _message(overview: dict) -> str:
    metric_lines = "\n".join(f"> {item['label']}：**{item['value']:,.0f}{item['unit']}**" for item in overview["metrics"])
    analysis = overview.get("analysis")
    approved = analysis and analysis.get("status") == "review_approved"
    review_state = "人工审核：已通过" if approved else "人工审核：待审核（AI 初步分析）"
    conclusion = analysis.get("output") if analysis else "尚未生成 AI 分析。"
    return f"## 深圳盈进经营数据中心｜经营周报 {overview['week']['week_start']} 至 {overview['week']['week_end']}\n{metric_lines}\n> 已提交表单：{overview['submission_count']} 份\n> {review_state}\n\n### AI 经营分析\n{conclusion}"


def _already_sent(db: Session, week_id: int, trigger: str) -> WecomDelivery | None:
    return db.scalar(
        select(WecomDelivery)
        .where(
            WecomDelivery.reporting_week_id == week_id,
            WecomDelivery.trigger == trigger,
            WecomDelivery.status == "sent",
        )
        .order_by(WecomDelivery.created_at.desc())
    )


def _post_or_record(db: Session, week: ReportingWeek, trigger: str, message: str, analysis_id: int | None = None) -> WecomDelivery:
    if not settings.wecom_push_enabled:
        item = WecomDelivery(reporting_week_id=week.id, business_analysis_id=analysis_id, trigger=trigger, status="skipped", message="推送未启用；未发送外部消息。")
    else:
        try:
            if settings.wecom_aibot_enabled and settings.wecom_aibot_target_userid and settings.wecom_aibot_internal_token:
                response = httpx.post(
                    f"{settings.wecom_aibot_url.rstrip('/')}/send",
                    headers={"Authorization": f"Bearer {settings.wecom_aibot_internal_token}"},
                    json={"target_userid": settings.wecom_aibot_target_userid, "content": message},
                    timeout=20,
                )
            elif settings.wecom_webhook_url:
                response = httpx.post(settings.wecom_webhook_url, json={"msgtype": "markdown", "markdown": {"content": message}}, timeout=15)
            else:
                raise RuntimeError("未配置智能机器人或群 Webhook 推送通道")
            response.raise_for_status()
            item = WecomDelivery(reporting_week_id=week.id, business_analysis_id=analysis_id, trigger=trigger, status="sent", message=message, response_code=response.status_code)
        except (httpx.HTTPError, RuntimeError) as error:
            item = WecomDelivery(reporting_week_id=week.id, business_analysis_id=analysis_id, trigger=trigger, status="failed", message=str(error), response_code=None)
    db.add(item)
    db.commit()
    db.refresh(item)
    return item


def deliver_exception(db: Session, week: ReportingWeek, trigger: str, reason: str) -> WecomDelivery:
    existing = _already_sent(db, week.id, f"{trigger}_exception")
    if existing:
        return existing
    message = f"## 深圳盈进经营数据中心｜异常提醒\n> 统计周期：{week.week_start} 至 {week.week_end}\n> {reason}\n\n本周未发送正式经营驾驶舱，请补齐数据或检查周报链路。"
    return _post_or_record(db, week, f"{trigger}_exception", message)


def deliver_weekly_summary(db: Session, trigger: str) -> WecomDelivery:
    week = db.scalar(select(ReportingWeek).where(ReportingWeek.is_current.is_(True)))
    if week is None:
        raise RuntimeError("未配置当前统计周")
    existing = _already_sent(db, week.id, trigger)
    if existing:
        return existing
    overview = build_overview(db, week)
    analysis = overview.get("analysis")
    approved = analysis and analysis["status"] == "review_approved"
    preliminary = analysis and analysis["status"] == "generated" and settings.wecom_allow_preliminary_analysis
    message = _message(overview)
    if not settings.wecom_push_enabled:
        return _post_or_record(db, week, trigger, message, analysis["id"] if analysis else None)
    elif not overview["collection"]["complete"]:
        return deliver_exception(db, week, trigger, f"尚未收齐经营数据：{', '.join(overview['collection']['missing_forms'])}")
    elif not approved and not preliminary:
        return deliver_exception(db, week, trigger, "AI 分析尚未生成或未通过人工审核")
    return _post_or_record(db, week, trigger, message, analysis["id"] if analysis else None)
