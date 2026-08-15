from __future__ import annotations

from pydantic import SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    openweather_api_key: SecretStr = SecretStr("")

    raw_dir: str = "data/raw"
    gold_dir: str = "data/gold"
    history_hours: int = 24

    cities_source: str = "file"
    cities_file: str = "config/cities.json"

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )


settings = Settings()