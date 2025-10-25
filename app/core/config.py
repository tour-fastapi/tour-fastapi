# app/core/config.py
from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    APP_NAME: str = "Tour App API"
    ENV: str = "dev"
    DATABASE_URL: str  # e.g. postgresql+psycopg2://user:pass@localhost:5432/tour_app

    # placeholders for later days
    SECRET_KEY: str | None = None
    JWT_ALGO: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MIN: int = 30
    REFRESH_TOKEN_EXPIRE_MIN: int = 60 * 24 * 7  # 7 days
    
    BREVO_API_KEY: str | None = None
    MAIL_FROM_EMAIL: str = "no-reply@example.com"
    MAIL_FROM_NAME: str = "Tour App"
    OTP_EXP_MINUTES: int = 10
    
    # ✅ Pydantic v2 config (no inner class)
    model_config = SettingsConfigDict(
        env_file=".env",
        case_sensitive=False  # lets you use DATABASE_URL or database_url
    )
    
    # NEW (JWT)
    JWT_SECRET: str = "Mavia@123"
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 15
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")
    PASSWORD_RESET_EXP_MINUTES: int = 60  # or 30
    SITE_URL: str = "http://127.0.0.1:8000"  # set to production domain in prod
    # app/core/config.py (example)
    ADMIN_NOTIFICATION_EMAIL: str = "amavia03@gmail.com"



settings = Settings()
