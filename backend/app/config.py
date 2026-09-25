from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

BACKEND_DIR = Path(__file__).resolve().parent.parent
PROJECT_DIR = BACKEND_DIR.parent


class Settings(BaseSettings):
    # Один .env на весь проект — в корне (рядом с docker-compose.yml).
    # В Docker переменные приходят из compose, файл внутри контейнера не нужен.
    model_config = SettingsConfigDict(env_file=(PROJECT_DIR / ".env", ".env"), extra="ignore")

    env: str = "dev"
    database_url: str = f"sqlite:///{(BACKEND_DIR / 'app.db').as_posix()}"
    jwt_secret: str = "dev-secret-change-me"
    jwt_ttl_days: int = 7
    admin_token: str = ""

    # MAX
    max_bot_token: str = ""
    max_bot_name: str = ""
    max_api_base: str = "https://platform-api2.max.ru"
    max_ca_bundle: str = ""
    # polling — для разработки и хакатона; webhook — для прода (нужен HTTPS на 443)
    max_mode: str = "polling"
    max_webhook_secret: str = ""
    max_polling_enabled: bool = True
    max_drop_webhooks: bool = True
    max_auth_ttl_seconds: int = 3600
    public_url: str = "http://localhost:8000"
    frontend_origin: str = "http://localhost:5173"
    dev_fake_auth: bool = False
    # при старте загрузить data/events.yaml, если в базе ещё нет мероприятий (первый запуск в Docker)
    seed_if_empty: bool = True
    # собранный фронт (в общем Docker-образе лежит здесь); если папки нет — бэкенд отдаёт только API
    static_dir: str = "/app/static"

    # LLM для конвейера наполнения (модуль H8): OpenRouter, OpenAI-совместимый API
    llm_api_base: str = "https://openrouter.ai/api/v1"
    llm_api_key: str = ""
    llm_model: str = "deepseek/deepseek-v4.1-flash"
    llm_timeout: float = 90.0


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
