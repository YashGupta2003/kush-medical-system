"""
Application configuration via pydantic-settings.

Security note on jwt_secret_key:
  The key MUST be changed from the default in any non-test environment.
  This is enforced in model_post_init() below — startup will raise ValueError
  if you forgot to set it. The test environment detection uses the same
  "pytest" in sys.modules check already used by cache.py, ensuring the test
  suite keeps working without a real .env file.

  Detection strategy: `"pytest" in sys.modules` is True during any pytest
  run (pytest imports itself before any test code runs). `TESTING=true` is
  an additional escape hatch for CI environments that run tests differently.
  Both checks are needed: `sys.modules` only covers in-process test runs,
  while `TESTING=true` covers scenarios where the settings object might be
  constructed from a subprocess or a non-pytest test runner.
"""
import sys
import os

from pydantic_settings import BaseSettings
from pydantic import Field, model_validator


class Settings(BaseSettings):
    db_host: str = "localhost"
    db_port: int = 3306
    db_user: str = "root"
    db_password: str = ""
    db_name: str = "kush_medical"

    google_application_credentials: str = "./gcp-vision-key.json"
    ocr_engine: str = "auto"

    upload_dir: str = "./uploads"
    fuzzy_match_threshold: int = Field(default=85, description="0-100, RapidFuzz score")

    redis_url: str = "redis://localhost:6379/0"
    ocr_confidence_threshold: float = 55.0

    # SECURITY: This MUST be set to a long random string in production.
    # Generate one with: python -c "import secrets; print(secrets.token_hex(32))"
    # The startup guard below enforces this — see model_post_init.
    jwt_secret_key: str = "change-this-secret-in-your-.env-file-please"
    jwt_algorithm: str = "HS256"
    jwt_expire_minutes: int = 60 * 12
    # Refresh tokens live for 30 days (long-lived, but revocable via RefreshToken table)
    refresh_token_expire_days: int = 30

    groq_api_key: str = ""
    # BUG FIX: "openai/gpt-oss-120b" is not a valid Groq model name.
    # Valid Groq models use IDs like "llama-3.1-70b-versatile", "llama3-8b-8192", etc.
    # Override via GROQ_MODEL environment variable to match your Groq tier.
    groq_model: str = "llama-3.3-70b-versatile"

    default_lead_time_days: int = 3
    reorder_safety_z_score: float = 1.65

    # Priority 1: Twilio WhatsApp integration.
    # Leave empty to disable WhatsApp delivery — the system works fully for
    # in-app notifications without these. See whatsapp_service.py.
    twilio_account_sid: str = ""
    twilio_auth_token: str = ""
    twilio_whatsapp_number: str = ""   # e.g. "whatsapp:+14155238886" (sandbox)

    # Priority 2e: Observability.
    # Leave empty to disable Sentry — same graceful no-op pattern as Groq/Twilio.
    sentry_dsn: str = ""

    # CORS: comma-separated list of allowed frontend origins.
    # In production, set ALLOWED_ORIGINS=https://yourdomain.com
    # Leave empty to allow localhost (development) origins only.
    allowed_origins: str = ""

    class Config:
        env_file = ".env"

    @model_validator(mode="after")
    def _validate_jwt_secret(self) -> "Settings":
        """
        Raises at startup if jwt_secret_key is still the insecure default
        in any non-test environment.

        Test environment detection (consistent with cache.py):
          1. "pytest" in sys.modules — True whenever pytest is running in-process.
          2. TESTING env var == "true" — escape hatch for CI/subprocess scenarios.

        This validator runs AFTER all fields are set, so it can safely read
        self.jwt_secret_key without the object being in a half-constructed state.
        """
        _is_testing = "pytest" in sys.modules or os.environ.get("TESTING", "").lower() == "true"
        _insecure_default = "change-this-secret-in-your-.env-file-please"

        if not _is_testing and self.jwt_secret_key == _insecure_default:
            raise ValueError(
                "jwt_secret_key is still set to the insecure default. "
                "Generate a strong key with: python -c \"import secrets; print(secrets.token_hex(32))\" "
                "and set it as JWT_SECRET_KEY in your .env file before starting the server."
            )
        return self

    @property
    def database_url(self) -> str:
        return (
            f"mysql+pymysql://{self.db_user}:{self.db_password}"
            f"@{self.db_host}:{self.db_port}/{self.db_name}"
        )


settings = Settings()
