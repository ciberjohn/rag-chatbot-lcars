from pydantic import SecretStr
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    anthropic_api_key: SecretStr
    chroma_host: str = "chroma"
    chroma_port: int = 8000
    chroma_auth_token: SecretStr = SecretStr("")
    docs_path: str = "/app/docs"
    data_path: str = "/app/data"
    collection_name: str = "tech_docs"
    sync_interval_minutes: int = 30
    max_search_results: int = 5
    log_level: str = "INFO"
    model: str = "claude-haiku-4-5-20251001"
    admin_token: SecretStr = SecretStr("")

    class Config:
        env_file = ".env"


settings = Settings()
