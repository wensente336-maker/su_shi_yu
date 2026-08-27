from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from apscheduler.schedulers.blocking import BlockingScheduler
from apscheduler.triggers.interval import IntervalTrigger

from app.core.config import settings
from app.db import Base, SessionLocal, engine
from app.db.migrations import run_migrations
from app.db.seed import seed_reference_data
from app.services.weekly_run import run_scheduled_weekly_cycle


def scheduled_cycle() -> None:
    if not settings.wecom_push_enabled:
        return
    now = datetime.now(ZoneInfo("Asia/Shanghai"))
    starts = now.replace(hour=settings.wecom_push_hour, minute=settings.wecom_push_minute, second=0, microsecond=0)
    ends = starts + timedelta(hours=settings.wecom_catchup_hours)
    if now.weekday() != settings.wecom_push_weekday or not starts <= now <= ends:
        return
    with SessionLocal() as db:
        run_scheduled_weekly_cycle(db)


def main() -> None:
    Base.metadata.create_all(bind=engine)
    with SessionLocal() as db:
        run_migrations(db)
        seed_reference_data(db)
    scheduler = BlockingScheduler(timezone="Asia/Shanghai")
    scheduler.add_job(scheduled_cycle, IntervalTrigger(minutes=settings.wecom_push_retry_minutes), id="weekly-delivery-retry", replace_existing=True, max_instances=1, coalesce=True)
    scheduled_cycle()
    scheduler.start()


if __name__ == "__main__":
    main()
