"""スケジュールジョブ"""

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

from ..utils.logger import get_logger

logger = get_logger(__name__)


def create_scheduler(timezone: str = "Asia/Tokyo") -> AsyncIOScheduler:
    """スケジューラを作成（ジョブなし）

    Args:
        timezone: タイムゾーン

    Returns:
        AsyncIOScheduler: スケジューラ
    """
    return AsyncIOScheduler(timezone=timezone)


def setup_scheduler(
    morning_job,
    morning_hour: int = 6,
    morning_minute: int = 0,
    weekly_job=None,
    weekly_day: str = "fri",
    weekly_hour: int = 18,
    life_info_job=None,
    life_info_day: str = "mon",
    life_info_hour: int = 9,
    coaching_job=None,
    coaching_hour: int = 7,
    coaching_minute: int = 0,
    timezone: str = "Asia/Tokyo",
    scheduler: AsyncIOScheduler | None = None,
) -> AsyncIOScheduler:
    """スケジューラをセットアップ

    Args:
        morning_job: 朝の通知ジョブ
        morning_hour: 朝の通知時刻（時）
        morning_minute: 朝の通知時刻（分）
        weekly_job: 週次イベント通知ジョブ（Phase 2）
        weekly_day: 週次イベント通知曜日
        weekly_hour: 週次イベント通知時刻（時）
        life_info_job: 生活影響情報通知ジョブ（Phase 4）
        life_info_day: 生活影響情報通知曜日
        life_info_hour: 生活影響情報通知時刻（時）
        timezone: タイムゾーン
        scheduler: 既存のスケジューラ（指定しない場合は新規作成）

    Returns:
        AsyncIOScheduler: スケジューラ
    """
    if scheduler is None:
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
        misfire_grace_time=300,  # 5分以内の遅延実行を許可
        coalesce=True,  # 複数回分をまとめて1回だけ実行
        max_instances=1,  # 同時に1インスタンスのみ実行
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
            misfire_grace_time=300,  # 5分以内の遅延実行を許可
            coalesce=True,  # 複数回分をまとめて1回だけ実行
            max_instances=1,  # 同時に1インスタンスのみ実行
        )
        logger.info(
            "Weekly events job scheduled",
            day=weekly_day,
            hour=weekly_hour,
        )

    # 週次生活影響情報通知（Phase 4）- 毎週月曜朝9時
    if life_info_job:
        scheduler.add_job(
            life_info_job,
            CronTrigger(
                day_of_week=life_info_day,
                hour=life_info_hour,
                minute=0,
                timezone=timezone,
            ),
            id="weekly_life_info",
            name="週次生活影響情報通知",
            replace_existing=True,
            misfire_grace_time=300,  # 5分以内の遅延実行を許可
            coalesce=True,  # 複数回分をまとめて1回だけ実行
            max_instances=1,  # 同時に1インスタンスのみ実行
        )
        logger.info(
            "Weekly life info job scheduled",
            day=life_info_day,
            hour=life_info_hour,
        )

    # デイリーコーチング通知（毎日）
    if coaching_job:
        scheduler.add_job(
            coaching_job,
            CronTrigger(
                hour=coaching_hour,
                minute=coaching_minute,
                timezone=timezone,
            ),
            id="daily_coaching",
            name="デイリーコーチング通知",
            replace_existing=True,
            misfire_grace_time=300,
            coalesce=True,
            max_instances=1,
        )
        logger.info(
            "Daily coaching job scheduled",
            hour=coaching_hour,
            minute=coaching_minute,
        )

    return scheduler
