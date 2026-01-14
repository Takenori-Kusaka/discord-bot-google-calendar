"""スケジュールジョブ"""

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

from ..utils.logger import get_logger

logger = get_logger(__name__)


def setup_scheduler(
    morning_job,
    morning_hour: int = 6,
    morning_minute: int = 0,
    weekly_job=None,
    weekly_day: str = "fri",
    weekly_hour: int = 18,
    timezone: str = "Asia/Tokyo",
) -> AsyncIOScheduler:
    """スケジューラをセットアップ

    Args:
        morning_job: 朝の通知ジョブ
        morning_hour: 朝の通知時刻（時）
        morning_minute: 朝の通知時刻（分）
        weekly_job: 週次通知ジョブ（Phase 2）
        weekly_day: 週次通知曜日
        weekly_hour: 週次通知時刻（時）
        timezone: タイムゾーン

    Returns:
        AsyncIOScheduler: スケジューラ
    """
    scheduler = AsyncIOScheduler(timezone=timezone)

    # 朝の予定通知（毎日）
    scheduler.add_job(
        morning_job,
        CronTrigger(
            hour=morning_hour,
            minute=morning_minute,
            timezone=timezone,
        ),
        id="morning_notification",
        name="朝の予定通知",
        replace_existing=True,
    )
    logger.info(
        "Morning notification job scheduled",
        hour=morning_hour,
        minute=morning_minute,
    )

    # 週次イベント通知（Phase 2）
    if weekly_job:
        scheduler.add_job(
            weekly_job,
            CronTrigger(
                day_of_week=weekly_day,
                hour=weekly_hour,
                minute=0,
                timezone=timezone,
            ),
            id="weekly_events",
            name="週次イベント通知",
            replace_existing=True,
        )
        logger.info(
            "Weekly events job scheduled",
            day=weekly_day,
            hour=weekly_hour,
        )

    return scheduler
