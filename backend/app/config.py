from pydantic_settings import BaseSettings
from pydantic import Field


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

    jwt_secret_key: str = "change-this-secret-in-your-.env-file-please"
    jwt_algorithm: str = "HS256"
    jwt_expire_minutes: int = 60 * 12

    class Config:
        env_file = ".env"

    @property
    def database_url(self) -> str:
        return (
            f"mysql+pymysql://{self.db_user}:{self.db_password}"
            f"@{self.db_host}:{self.db_port}/{self.db_name}"
        )


settings = Settings()
