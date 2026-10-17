from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=("../.env", ".env"), extra="ignore")

    app_name: str = "TraceMatrix"
    app_env: str = "development"
    secret_key: str = "dev-only-change-me"
    frontend_origin: str = "http://localhost:5173"
    api_host: str = "0.0.0.0"
    api_port: int = 8000
    log_level: str = "INFO"

    database_url: str = "postgresql+psycopg://tracematrix:tracematrix@localhost:5432/tracematrix"
    redis_url: str = ""

    bootstrap_admin_email: str = "analyst@example.com"
    bootstrap_admin_password: str = ""

    eth_rpc_url: str = ""
    etherscan_api_url: str = "https://api.etherscan.io/api"
    etherscan_api_key: str = ""

    github_token: str = ""
    github_api_base: str = "https://api.github.com"
    osint_feed_allowlist: str = ""

    max_ingest_transactions: int = 200
    max_graph_nodes: int = 250
    max_graph_depth: int = 3
    job_timeout_seconds: int = 180
    allow_fixture_provider: bool = False
    sync_jobs: bool = False

    access_token_minutes: int = 480
    login_max_attempts: int = 8
    login_window_seconds: int = 300

    @property
    def feed_allowlist(self) -> set[str]:
        return {item.strip().lower() for item in self.osint_feed_allowlist.split(",") if item.strip()}


@lru_cache
def get_settings() -> Settings:
    return Settings()
