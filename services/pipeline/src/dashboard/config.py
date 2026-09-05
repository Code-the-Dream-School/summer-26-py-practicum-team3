"""Runtime configuration for the dashboard service."""

from __future__ import annotations

from pydantic import SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class DashboardSettings(BaseSettings):
    """Dashboard runtime settings loaded from environment."""

    database_url: SecretStr = SecretStr("")

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )


settings = DashboardSettings()
