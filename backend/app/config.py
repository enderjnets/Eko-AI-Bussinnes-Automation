from functools import lru_cache
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # App
    APP_NAME: str = "Eko AI Business Automation"
    APP_VERSION: str = "0.3.0"
    ENVIRONMENT: str = "development"
    DEBUG: bool = True
    SECRET_KEY: str = "change-this-in-production"
    LOG_LEVEL: str = "INFO"

    # Database
    DATABASE_URL: str = "postgresql+asyncpg://eko:eko_dev_pass@localhost:5432/eko_ai"

    # Redis
    REDIS_URL: str = "redis://localhost:6379/0"

    # API Keys
    OPENAI_API_KEY: str = ""
    OPENAI_MODEL: str = "gpt-4o"
    OPENAI_EMBEDDING_MODEL: str = "text-embedding-3-small"

    RESEND_API_KEY: str = ""
    RESEND_FROM_EMAIL: str = "Eko AI <eko@ekoai.com>"

    OUTSCRAPER_API_KEY: str = ""
    APIFY_API_KEY: str = ""
    YELP_API_KEY: str = ""
    SERPAPI_API_KEY: str = ""

    # Phase 3: Voice
    RETELL_API_KEY: str = ""
    VAPI_API_KEY: str = ""

    # Phase 2: Calendar
    CAL_COM_API_KEY: str = ""

    # Compliance
    DNC_SYNC_CRON: str = "0 2 1 * *"
    MAX_CONTACT_ATTEMPTS: int = 5
    COOLDOWN_HOURS_BETWEEN_CONTACTS: int = 72

    # CORS
    CORS_ORIGINS: str = "http://localhost:3000,http://localhost:8000"

    # Paperclip — AI Company Control Plane
    PAPERCLIP_API_URL: str = "http://100.88.47.99:3100"
    PAPERCLIP_COMPANY_ID: str = "a5151f95-51cd-4d2d-a35b-7d7cb4f4102e"
    PAPERCLIP_API_KEY: str = ""

    @property
    def is_development(self) -> bool:
        return self.ENVIRONMENT == "development"

    @property
    def is_production(self) -> bool:
        return self.ENVIRONMENT == "production"


@lru_cache
def get_settings() -> Settings:
    return Settings()
