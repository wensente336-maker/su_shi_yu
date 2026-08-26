from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    database_url: str
    environment: str = "development"
    development_default_user: str = "admin"
    cors_origins: str = "http://localhost:3100"
    report_source_root: str = "/report-source"
    ai_provider: str = "disabled"
    ai_model: str = "gpt-4.1-mini"
    openai_api_key: str | None = None
    hermes_analysis_enabled: bool = False
    hermes_analysis_url: str = "http://host.docker.internal:8120"
    hermes_analysis_token: str | None = None
    wecom_push_enabled: bool = False
    wecom_webhook_url: str | None = None
    wecom_aibot_enabled: bool = False
    wecom_aibot_url: str = "http://wecom-aibot:8090"
    wecom_aibot_target_userid: str | None = None
    wecom_aibot_internal_token: str | None = None
    wecom_push_weekday: int = 4
    wecom_push_hour: int = 18
    wecom_push_minute: int = 0
    wecom_allow_preliminary_analysis: bool = True
    wecom_catchup_hours: int = 6

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")


settings = Settings()


def allowed_origins() -> list[str]:
    return [origin.strip() for origin in settings.cors_origins.split(",") if origin.strip()]
