"""
Central configuration, loaded from environment variables / .env file.
"""
from pydantic_settings import BaseSettings
from pydantic import Field


class Settings(BaseSettings):
    db_host: str = "localhost"
    db_port: int = 3306
    db_user: str = "root"
    db_password: str = ""
    db_name: str = "kush_medical"

    google_application_credentials: str = "./gcp-vision-key.json"

    # "auto" = try Google first, fall back to Tesseract automatically
    # "google" = Google only (no fallback)
    # "tesseract" = Tesseract only (fully free/offline, skips Google entirely)
    ocr_engine: str = "auto"

    upload_dir: str = "./uploads"
    fuzzy_match_threshold: int = Field(default=85, description="0-100, RapidFuzz score")

    class Config:
        env_file = ".env"

    @property
    def database_url(self) -> str:
        return (
            f"mysql+pymysql://{self.db_user}:{self.db_password}"
            f"@{self.db_host}:{self.db_port}/{self.db_name}"
        )


settings = Settings()