# app/core/config.py
from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import Field


class Settings(BaseSettings):
    APP_NAME: str = "Tour App API"
    ENV: str = "dev"

    # DB
    DATABASE_URL: str = Field(default="")  # e.g. mysql+pymysql://...

    # Auth / security
    SECRET_KEY: str | None = None

    # JWT (you currently have duplicates, keeping both for compatibility)
    JWT_ALGO: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MIN: int = 30
    REFRESH_TOKEN_EXPIRE_MIN: int = 60 * 24 * 7  # 7 days

    JWT_SECRET: str = "Mavia@123"
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 15
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7

    # Email / OTP
    BREVO_API_KEY: str | None = None
    MAIL_FROM_EMAIL: str = "amavia03@gmail.com"
    MAIL_FROM_NAME: str = "Umrah Advisor"
    OTP_EXP_MINUTES: int = 10

    # Password reset / site
    PASSWORD_RESET_EXP_MINUTES: int = 60
    SITE_URL: str = "http://127.0.0.1:8000"  # set to production domain in prod
    ADMIN_NOTIFICATION_EMAIL: str = "amavia03@gmail.com"

    # ✅ Single config block (no duplicates)
    model_config = SettingsConfigDict(
        env_file=".env",
        case_sensitive=False,  # allow DATABASE_URL or database_url, etc.
        extra="ignore",
    )


settings = Settings()
