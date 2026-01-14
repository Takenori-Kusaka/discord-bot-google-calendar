"""設定管理"""

from functools import lru_cache
from pathlib import Path
from typing import Optional

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """アプリケーション設定"""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # Discord設定
    discord_bot_token: str = Field(..., description="Discord Botトークン")
    discord_guild_id: int = Field(..., description="DiscordサーバーID")
    discord_owner_id: int = Field(..., description="オーナーのユーザーID")
    discord_channel_schedule: str = Field(
        default="予定", description="予定通知チャンネル名"
    )
    discord_channel_region: str = Field(
        default="地域のこと", description="地域情報チャンネル名"
    )

    # Google Calendar設定
    google_calendar_id: str = Field(..., description="GoogleカレンダーID")
    google_credentials_path: Path = Field(
        default=Path("credentials/google.json"),
        description="Google認証情報ファイルパス",
    )

    # Claude API設定
    anthropic_api_key: str = Field(..., description="Anthropic APIキー")
    claude_model: str = Field(
        default="claude-sonnet-4-20250514", description="Claudeモデル名"
    )

    # スケジュール設定
    morning_notification_hour: int = Field(
        default=6, description="朝の通知時刻（時）"
    )
    morning_notification_minute: int = Field(
        default=0, description="朝の通知時刻（分）"
    )
    weekly_event_day: str = Field(
        default="fri", description="週次イベント通知曜日"
    )
    weekly_event_hour: int = Field(
        default=18, description="週次イベント通知時刻（時）"
    )
    timezone: str = Field(default="Asia/Tokyo", description="タイムゾーン")

    # ログ設定
    log_level: str = Field(default="INFO", description="ログレベル")
    log_dir: Optional[Path] = Field(default=Path("logs"), description="ログディレクトリ")

    # 執事設定
    butler_name: str = Field(default="黒田", description="執事の名前")


@lru_cache
def get_settings() -> Settings:
    """設定を取得する（キャッシュ付き）

    Returns:
        Settings: アプリケーション設定
    """
    return Settings()
