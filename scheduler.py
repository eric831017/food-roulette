import asyncio
import logging

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

from config import TIMEZONE
from database import get_conn
from services.push import push_recommendation, push_weekly_digest_to

logger = logging.getLogger(__name__)


def _all_onboarded_users() -> list[str]:
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT line_user_id FROM users WHERE onboard_complete = 1 "
            "AND location_1_lat IS NOT NULL"
        ).fetchall()
    return [r["line_user_id"] for r in rows]


async def _push_to_all(meal_type: str) -> None:
    users = _all_onboarded_users()
    logger.info("scheduled %s push to %d users", meal_type, len(users))
    for uid in users:
        try:
            await push_recommendation(uid, meal_type)
        except Exception:
            logger.exception("push failed for %s", uid)


async def _weekly_digest_all() -> None:
    users = _all_onboarded_users()
    logger.info("weekly digest to %d users", len(users))
    for uid in users:
        try:
            push_weekly_digest_to(uid)
        except Exception:
            logger.exception("weekly digest failed for %s", uid)


def start_scheduler() -> AsyncIOScheduler:
    scheduler = AsyncIOScheduler(timezone=TIMEZONE)

    scheduler.add_job(
        _push_to_all, CronTrigger(hour=6, minute=30, timezone=TIMEZONE),
        args=["breakfast"], id="push_breakfast", replace_existing=True,
    )
    scheduler.add_job(
        _push_to_all, CronTrigger(hour=11, minute=30, timezone=TIMEZONE),
        args=["lunch"], id="push_lunch", replace_existing=True,
    )
    scheduler.add_job(
        _push_to_all, CronTrigger(hour=17, minute=30, timezone=TIMEZONE),
        args=["dinner"], id="push_dinner", replace_existing=True,
    )
    scheduler.add_job(
        _weekly_digest_all,
        CronTrigger(day_of_week="mon", hour=8, minute=0, timezone=TIMEZONE),
        id="weekly_digest", replace_existing=True,
    )

    scheduler.start()
    logger.info(
        "scheduler started (tz=%s): breakfast 06:30, lunch 11:30, dinner 17:30, "
        "weekly mon 08:00",
        TIMEZONE,
    )
    return scheduler
