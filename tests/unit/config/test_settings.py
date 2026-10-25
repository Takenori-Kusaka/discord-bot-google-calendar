"""Settings のテスト"""

import pytest

from src.config.settings import DEFAULT_CLAUDE_MODEL, Settings

REQUIRED_ENV = {
    "DISCORD_BOT_TOKEN": "token",
    "DISCORD_GUILD_ID": "1",
    "DISCORD_OWNER_ID": "2",
    "GOOGLE_CALENDAR_ID": "cal@example.com",
    "ANTHROPIC_API_KEY": "key",
}


@pytest.fixture
def base_env(monkeypatch):
    for key, value in REQUIRED_ENV.items():
        monkeypatch.setenv(key, value)
    for key in ("CLAUDE_MODEL", "ENABLE_SCHEDULED_JOBS"):
        monkeypatch.delenv(key, raising=False)


def _settings() -> Settings:
    # .env ファイルの影響を受けないように無効化する
    return Settings(_env_file=None)


class TestSettings:
    def test_defaults(self, base_env):
        settings = _settings()
        assert settings.claude_model == DEFAULT_CLAUDE_MODEL
        assert settings.enable_scheduled_jobs is True

    def test_claude_model_override(self, base_env, monkeypatch):
        monkeypatch.setenv("CLAUDE_MODEL", "claude-opus-5-5")
        assert _settings().claude_model == "claude-opus-5-5"

    def test_scheduled_jobs_can_be_disabled(self, base_env, monkeypatch):
        monkeypatch.setenv("ENABLE_SCHEDULED_JOBS", "false")
        assert _settings().enable_scheduled_jobs is False
