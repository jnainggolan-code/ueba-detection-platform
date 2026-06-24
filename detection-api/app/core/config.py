"""Application configuration via environment variables."""

from pydantic_settings import BaseSettings
from typing import Optional


class Settings(BaseSettings):
    """Settings loaded from environment variables / .env file."""

    # Application
    app_name: str = "UEBA Detection API"
    app_version: str = "1.0.0"
    debug: bool = False

    # Database
    db_host: str = "detection-db"
    db_port: int = 5433
    db_user: str = "fraud"
    db_password: str = "fraud_password"
    db_name: str = "fraud_detection"

    @property
    def database_url(self) -> str:
        return (
            f"postgresql+asyncpg://{self.db_user}:{self.db_password}"
            f"@{self.db_host}:{self.db_port}/{self.db_name}"
        )

    @property
    def database_url_sync(self) -> str:
        return (
            f"postgresql://{self.db_user}:{self.db_password}"
            f"@{self.db_host}:{self.db_port}/{self.db_name}"
        )

    # API Keys (comma-separated for multiple keys per scope)
    syslog_api_keys: str = ""
    raw_api_keys: str = ""
    wazuh_api_keys: str = ""
    delinea_api_keys: str = ""
    admin_api_keys: str = ""

    # CORS
    cors_origins: str = "*"

    # Rate limiting
    rate_limit_per_minute: int = 60

    # Logging
    log_level: str = "INFO"

    # Dev reload
    reload: bool = True

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}


settings = Settings()
