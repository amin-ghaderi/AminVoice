"""Application configuration loaded from environment variables."""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

PROJECT_ROOT = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=PROJECT_ROOT / ".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    app_name: str = Field(default="Audiobook Generator", alias="APP_NAME")
    app_env: str = Field(default="development", alias="APP_ENV")
    debug: bool = Field(default=True, alias="DEBUG")
    host: str = Field(default="127.0.0.1", alias="HOST")
    port: int = Field(default=8000, alias="PORT")

    database_url: str = Field(
        default=f"sqlite:///{(PROJECT_ROOT / 'storage' / 'audiobook.db').as_posix()}",
        alias="DATABASE_URL",
    )
    storage_root: Path = Field(
        default=PROJECT_ROOT / "storage",
        alias="STORAGE_ROOT",
    )
    frontend_dir: Path = Field(
        default=PROJECT_ROOT / "frontend",
        alias="FRONTEND_DIR",
    )

    log_level: str = Field(default="INFO", alias="LOG_LEVEL")
    log_file: Path = Field(
        default=PROJECT_ROOT / "storage" / "logs" / "app.log",
        alias="LOG_FILE",
    )

    @property
    def frontend_static_dir(self) -> Path:
        return self.frontend_dir / "static"

    @property
    def frontend_templates_dir(self) -> Path:
        return self.frontend_dir / "templates"

    @property
    def jobs_dir(self) -> Path:
        return self.storage_root / "jobs"

    @property
    def chunks_dir(self) -> Path:
        return self.storage_root / "chunks"

    @property
    def outputs_dir(self) -> Path:
        return self.storage_root / "outputs"

    @property
    def temp_dir(self) -> Path:
        return self.storage_root / "temp"

    def ensure_storage_dirs(self) -> None:
        for path in (
            self.storage_root,
            self.jobs_dir,
            self.chunks_dir,
            self.outputs_dir,
            self.temp_dir,
            self.log_file.parent,
            self.frontend_static_dir / "uploads",
        ):
            path.mkdir(parents=True, exist_ok=True)


@lru_cache
def get_settings() -> Settings:
    settings = Settings()
    settings.ensure_storage_dirs()
    return settings
