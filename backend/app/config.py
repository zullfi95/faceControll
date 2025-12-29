"""
Централизованная конфигурация приложения с валидацией через Pydantic Settings.
"""
from pydantic_settings import BaseSettings
from pydantic import field_validator
from typing import Optional
import os


class Settings(BaseSettings):
    """Настройки приложения."""

    # Database
    database_url: str = "sqlite+aiosqlite:///./test.db"
    postgres_user: Optional[str] = None
    postgres_password: Optional[str] = None
    postgres_db: Optional[str] = None

    # JWT
    jwt_secret_key: str = "test-secret-key-change-in-production"
    jwt_algorithm: str = "HS256"
    jwt_access_token_expire_minutes: int = 30 * 24 * 60  # 30 дней

    # Encryption
    encryption_key: str

    # Webhook
    webhook_api_key: str = ""

    # Server
    http_port: int = 8000  # Backend работает на порту 8000
    server_ip: str = "46.62.223.55"

    # Telegram Bot
    telegram_bot_token: Optional[str] = None
    telegram_chat_id: Optional[str] = None

    # Environment
    environment: str = "development"

    class Config:
        env_file = ".env"
        case_sensitive = False

    @field_validator("jwt_secret_key", "encryption_key", "webhook_api_key")
    @classmethod
    def validate_required_fields(cls, v, info):
        """Валидация обязательных полей в production окружении."""
        if info.field_name in ["jwt_secret_key", "encryption_key"] and not v:
            raise ValueError(f"{info.field_name} is required and cannot be empty")
        return v

    @field_validator("database_url")
    @classmethod
    def assemble_database_url(cls, v, info):
        """Сборка DATABASE_URL из отдельных компонентов если используется PostgreSQL."""
        values = info.data
        if values.get("postgres_user") and values.get("postgres_password") and values.get("postgres_db"):
            return f"postgresql+asyncpg://{values['postgres_user']}:{values['postgres_password']}@db:5432/{values['postgres_db']}"
        return v

    def is_production(self) -> bool:
        """Проверка на production окружение."""
        return self.environment.lower() == "production"

    def is_development(self) -> bool:
        """Проверка на development окружение."""
        return self.environment.lower() == "development"


# Создание глобального экземпляра настроек
settings = Settings()
