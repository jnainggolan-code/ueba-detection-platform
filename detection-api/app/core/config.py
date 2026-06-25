"""Application configuration via environment variables."""

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Settings loaded from environment variables / .env file."""

    app_name: str = "UEBA Detection API"
    app_version: str = "1.0.0"
    debug: bool = False

    database_url: str = "postgresql+asyncpg://ueba_admin:changeme@detection-db:5432/ueba_detection"
    database_url_sync: str = "postgresql://ueba_admin:changeme@detection-db:5432/ueba_detection"
    redis_url: str = "redis://detection-redis:6379/0"

    syslog_api_keys: str = ""
    raw_api_keys: str = ""
    wazuh_api_keys: str = ""
    delinea_api_keys: str = ""
    admin_api_keys: str = ""

    cors_origins: str = "*"
    rate_limit_per_minute: int = 60
    log_level: str = "INFO"
    reload: bool = True

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}


settings = Settings()
