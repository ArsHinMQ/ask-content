from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=Path(__file__).parent / ".env",
        env_file_encoding="utf-8",
        extra="allow",
    )

    openrouter_api_key: str
    openrouter_base_url: str = "https://openrouter.ai/api/v1"
    # YouTube cookies: a live browser profile wins over a cookies file.
    yt_cookies_from_browser: str | None = None
    yt_cookies_file: str | None = None


def get_settings() -> Settings:
    return Settings()
