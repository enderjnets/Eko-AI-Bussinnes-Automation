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
    APP_VERSION: str = "0.5.1"
    APP_URL: str = "http://localhost:8000"
    ENVIRONMENT: str = "development"
    DEBUG: bool = True
    SECRET_KEY: str = "change-this-in-production"
    LOG_LEVEL: str = "INFO"

    # Database
    DATABASE_URL: str = "postgresql+asyncpg://eko:eko_dev_pass@localhost:5432/eko_ai"

    # Redis
    REDIS_URL: str = "redis://localhost:6379/0"

    # API Keys
    # AI Provider (openai, kimi, or ollama)
    AI_PROVIDER: str = "kimi"

    # OpenAI settings
    OPENAI_API_KEY: str = ""
    OPENAI_BASE_URL: str = "https://api.openai.com/v1"
    OPENAI_MODEL: str = "gpt-4o"
    OPENAI_EMBEDDING_MODEL: str = "text-embedding-3-small"

    # Kimi (Kimi Code API) settings
    KIMI_API_KEY: str = ""
    KIMI_BASE_URL: str = "https://api.kimi.com/coding/v1"
    KIMI_MODEL: str = "kimi-for-coding"
    KIMI_EMBEDDING_MODEL: str = "moonshot-v1-embedding-1024"

    # Ollama (local) settings
    OLLAMA_BASE_URL: str = "http://host.docker.internal:11434/v1"
    OLLAMA_MODEL: str = "qwen2.5-coder:14b"
    OLLAMA_EMBEDDING_MODEL: str = "nomic-embed-text"

    # MiniMax settings
    MINIMAX_API_KEY: str = ""
    MINIMAX_BASE_URL: str = "https://api.minimax.io/v1"
    MINIMAX_MODEL: str = "MiniMax-M2.7"
    MINIMAX_EMBEDDING_MODEL: str = "embedding-001"

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
    CAL_COM_USERNAME: str = "eko-ai"

    # Compliance
    DNC_SYNC_CRON: str = "0 2 1 * *"
    MAX_CONTACT_ATTEMPTS: int = 5
    COOLDOWN_HOURS_BETWEEN_CONTACTS: int = 72

    # Frontend URL for proposal links
    FRONTEND_URL: str = "http://localhost:3001"

    # CORS
    CORS_ORIGINS: str = "http://localhost:3000,http://localhost:3001,http://localhost:8000"

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
