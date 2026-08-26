from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    database_url: str
    environment: str = "development"
    development_default_user: str = "admin"
    report_source_root: str = "/report-source"
    ai_provider: str = "disabled"
    ai_model: str = "gpt-4.1-mini"
    openai_api_key: str | None = None
    wecom_push_enabled: bool = False
    wecom_webhook_url: str | None = None
    wecom_push_weekday: int = 4
    wecom_push_hour: int = 18

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")


settings = Settings()
