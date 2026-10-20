"""Konfigurasi aplikasi dari environment variable (pydantic-settings)."""
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # Database & cache
    DATABASE_URL: str = "postgresql+psycopg2://wa:wa@localhost:5432/wablast"
    REDIS_URL: str = "redis://localhost:6379/0"

    # Auth: nonaktifkan login (auto-login sebagai admin) — untuk mode single-user lokal.
    # Aktifkan lagi dengan AUTH_DISABLED=false bila butuh proteksi login.
    AUTH_DISABLED: bool = False

    # Auth JWT
    JWT_SECRET: str = "change-me-min-32-chars"
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7

    # Seed admin pertama saat startup
    ADMIN_USERNAME: str = "admin"
    ADMIN_PASSWORD: str = "admin123"

    # Gemini AI (opsional)
    GEMINI_API_KEY: str = ""
    GEMINI_MODEL: str = "gemini-2.0-flash"

    # WhatsApp resmi: Meta Cloud API (opsional)
    WA_PHONE_NUMBER_ID: str = ""
    WA_ACCESS_TOKEN: str = ""

    # WhatsApp non-resmi: Baileys sidecar self-hosted (opsional).
    # Kosongkan BAILEYS_API_URL untuk mode dry-run (tidak kirim sungguhan).
    BAILEYS_API_URL: str = ""
    BAILEYS_API_KEY: str = ""

    # CORS frontend
    FRONTEND_ORIGINS: str = "*"


settings = Settings()
