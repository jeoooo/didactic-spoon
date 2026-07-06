from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    opencode_api_key: str = ""
    opencode_base_url: str = "https://opencode.ai/api/v1"
    model_id: str = "opencode-go/kimi-k2.7-code"

    database_url: str = "postgresql+psycopg://postgres:postgres@localhost:5432/resume_screener"

    max_resume_chars: int = 20000
    max_jd_chars: int = 10000


settings = Settings()
