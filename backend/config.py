"""
Application configuration — loads from environment variables.
All external API keys are stored per-user in the database (encrypted).
These env vars are for the backend service itself.
"""

import os
from dotenv import load_dotenv

load_dotenv()


class Settings:
    # Database
    DATABASE_URL: str = os.getenv("DATABASE_URL", "postgresql://localhost:5432/email_optimizer")

    # Encryption key for user API keys (AES-256)
    ENCRYPTION_KEY: str = os.getenv("ENCRYPTION_KEY", "")

    # Server
    HOST: str = os.getenv("HOST", "0.0.0.0")
    PORT: int = int(os.getenv("PORT", "8000"))
    DEBUG: bool = os.getenv("DEBUG", "false").lower() == "true"

    # Scheduler
    PIPELINE_CRON_HOUR: int = int(os.getenv("PIPELINE_CRON_HOUR", "8"))  # UTC
    PIPELINE_CRON_MINUTE: int = int(os.getenv("PIPELINE_CRON_MINUTE", "0"))


settings = Settings()
