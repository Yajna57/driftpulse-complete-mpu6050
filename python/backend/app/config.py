from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "DriftPulse API"
    database_url: str = "postgresql+psycopg://driftpulse:driftpulse@localhost:5432/driftpulse"
    cors_origins: str = "http://localhost:5173,http://127.0.0.1:5173,http://localhost:3000"

    baseline_min_samples: int = 60
    ewma_alpha: float = 0.20
    cusum_k: float = 0.50
    cusum_h: float = 5.00

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    @property
    def cors_origin_list(self) -> list[str]:
        return [item.strip() for item in self.cors_origins.split(",") if item.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
