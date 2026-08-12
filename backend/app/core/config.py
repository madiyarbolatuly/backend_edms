import os
from dotenv import load_dotenv
from pydantic_settings import BaseSettings
from pathlib import Path   # ← make sure pathlib is imported

load_dotenv()


class GlobalConfig(BaseSettings):
    """
    Global Configuration for the FastAPI application.
    """

    title: str = os.environ.get("TITLE", "EDMS")
    version: str = "1.0.0"
    description: str = os.environ.get("DESCRIPTION", "Electronic Document Management System")
    host_url: str = "http://localhost:8000"
    docs_url: str = "/docs"
    redoc_url: str = "/redoc"
    openapi_url: str = "/openapi.json"
    api_prefix: str = "/v2"

    postgres_user: str = os.environ.get("POSTGRES_USER")
    postgres_password: str = os.environ.get("POSTGRES_PASSWORD")
    postgres_hostname: str = os.environ.get("DATABASE_HOSTNAME")
    postgres_port: int = int(os.environ.get("POSTGRES_PORT"))
    postgres_db: str = os.environ.get("POSTGRES_DB")
    
    debug: bool = str(os.environ.get("DEBUG", "False")).lower() == "true"
    db_echo_log: bool = str(os.environ.get("DEBUG", "False")).lower() == "true"

    # ─── user config ────────────────────────────────────────────────────────────
    local_storage_path: str = os.getenv("LOCAL_STORAGE_PATH", "./uploads")

    # Base address share links are built against. Must be reachable by the
    # recipient, so it is the public deployment URL — never localhost or a LAN
    # address, even when the app is opened from one.
    frontend_url: str = os.getenv("FRONTEND_URL", "http://77.245.107.136:8088").rstrip("/")

    # Browser origins allowed to call the API. Set CORS_ORIGINS (comma-separated)
    # to override wholesale — a deployment that moves to a new address needs an
    # env change, not a code change.
    cors_origins_env: str = os.getenv("CORS_ORIGINS", "")

    @property
    def cors_origins(self) -> list[str]:
        if self.cors_origins_env.strip():
            return [o.strip().rstrip("/") for o in self.cors_origins_env.split(",") if o.strip()]
        return [
            "http://localhost:5173",
            "http://localhost:3000",
            "http://localhost:8088",
            "http://localhost:8081",
            "http://127.0.0.1:8088",
            "http://127.0.0.1:8000",
            "http://77.245.107.136:8088",
            "http://89.218.93.198:8088",
            "http://192.168.8.121:8088",
            "http://192.168.2.94:8088",
        ]

    # ─── add this alias immediately below ───────────────────────────────────────
    @property
    def upload_dir(self) -> str:
        return self.local_storage_path
    
    @property
    def UPLOADS_DIR(self) -> str:
        return self.upload_dir

    # How long a share lasts when the sharer does not pick a date. One value for
    # both kinds of share — a per-recipient grant and a public link — so they
    # cannot drift apart. Public links used to have no expiry at all, and
    # recipient grants defaulted to a week.
    share_expiry_days: int = int(os.environ.get("SHARE_EXPIRY_DAYS", "3"))

    access_token_expire_min: int = os.environ.get("ACCESS_TOKEN_EXPIRE_MIN")
    refresh_token_expire_min: int = os.environ.get("REFRESH_TOKEN_EXPIRE_MIN")
    algorithm: str = os.environ.get("ALGORITHM")
    jwt_secret_key: str = os.environ.get("JWT_SECRET_KEY")
    jwt_refresh_secret_key: str = os.environ.get("JWT_REFRESH_SECRET_KEY")

    @property
    def secret_key(self) -> str:
        """Backward-compat alias for old code paths."""
        return self.jwt_secret_key

    # Email Service
    smtp_server: str = os.environ.get("SMTP_SERVER")
    smtp_port: int = os.environ.get("SMTP_PORT")
    email: str = os.environ.get("EMAIL")
    app_pw: str = os.environ.get("APP_PASSWORD")

    @property
    def sync_database_url(self) -> str:
        return (
            f"postgresql://{self.postgres_user}:{self.postgres_password}@"
            f"{self.postgres_hostname}:{self.postgres_port}/{self.postgres_db}"
        )

    @property
    def async_database_url(self) -> str:
        return (
            f"postgresql+asyncpg://{self.postgres_user}:{self.postgres_password}@"
            f"{self.postgres_hostname}:{self.postgres_port}/{self.postgres_db}"
        )


# ─── instantiate and ensure the upload dir exists ─────────────────────────────
settings = GlobalConfig()
# Create the directory (and parents) if it doesn’t already exist:
Path(settings.upload_dir).mkdir(parents=True, exist_ok=True)
