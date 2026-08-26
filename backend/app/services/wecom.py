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
    conclusion = analysis.get("output") if analysis and analysis.get("status") == "review_approved" else "尚无经人工审核通过的 AI 分析。"
    return f"## 深圳盈进经营数据中心｜经营周报 {overview['week']['week_start']} 至 {overview['week']['week_end']}\n{metric_lines}\n> 已提交表单：{overview['submission_count']} 份\n\n### 审核后经营分析\n{conclusion}"


def deliver_weekly_summary(db: Session, trigger: str) -> WecomDelivery:
    week = db.scalar(select(ReportingWeek).where(ReportingWeek.is_current.is_(True)))
    if week is None:
        raise RuntimeError("未配置当前统计周")
    overview = build_overview(db, week)
    approved = overview.get("analysis") and overview["analysis"]["status"] == "review_approved"
    message = _message(overview)
    if not settings.wecom_push_enabled or not settings.wecom_webhook_url:
        item = WecomDelivery(reporting_week_id=week.id, business_analysis_id=overview["analysis"]["id"] if overview.get("analysis") else None, trigger=trigger, status="skipped", message="推送未启用或未配置 Webhook；未发送外部消息。")
    elif not overview["collection"]["complete"]:
        item = WecomDelivery(reporting_week_id=week.id, business_analysis_id=overview["analysis"]["id"] if overview.get("analysis") else None, trigger=trigger, status="skipped", message=f"尚未收齐经营数据：{', '.join(overview['collection']['missing_forms'])}；未发送驾驶舱。")
    elif not approved:
        item = WecomDelivery(reporting_week_id=week.id, business_analysis_id=overview["analysis"]["id"] if overview.get("analysis") else None, trigger=trigger, status="skipped", message="缺少人工审核通过的经营分析；未发送外部消息。")
    else:
        try:
            response = httpx.post(settings.wecom_webhook_url, json={"msgtype": "markdown", "markdown": {"content": message}}, timeout=15)
            response.raise_for_status()
            item = WecomDelivery(reporting_week_id=week.id, business_analysis_id=overview["analysis"]["id"], trigger=trigger, status="sent", message=message, response_code=response.status_code)
        except httpx.HTTPError as error:
            item = WecomDelivery(reporting_week_id=week.id, business_analysis_id=overview["analysis"]["id"], trigger=trigger, status="failed", message=str(error), response_code=None)
    db.add(item)
    db.commit()
    db.refresh(item)
    return item
