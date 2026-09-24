from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    env: str = "dev"
    database_url: str = "sqlite:///./app.db"
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

    # GigaChat (модуль H8)
    giga_auth_key: str = ""
    giga_scope: str = "GIGACHAT_API_PERS"
    giga_ca_bundle: str = ""


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
