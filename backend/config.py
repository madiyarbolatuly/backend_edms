from pathlib import Path
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    app_name: str
    database_url: str
    secret_key: str
    access_token_expire_minutes: int
    refresh_token_expire_days: int
    jwt_algorithm: str
    permit_api_key: str
    permit_pdp: str
    env: str

    # ─── Local uploads ───────────────────────────────────────────────────────────
    # Directory where uploaded files are stored on disk
    upload_dir: str = "./storage

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


# Instantiate once and ensure the directory exists
settings = Settings()
Path(settings.upload_dir).mkdir(parents=True, exist_ok=True)
