from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "real_estate_voice_agent"
    app_env: str = "development"
    vapi_api_key: str = ""
    vapi_assistant_id: str = ""
    vapi_public_key: str = ""
    deepgram_api_key: str = ""
    openai_api_key: str = ""
    openrouter_api_key: str = ""
    openrouter_base_url: str = "https://openrouter.ai/api/v1"
    openrouter_model: str = "openai/gpt-4o-mini"
    database_url: str = ""
    google_service_account_file: str = ""
    google_calendar_id: str = "primary"
    smtp_host: str = ""
    smtp_port: int = 587
    smtp_user: str = ""
    smtp_password: str = ""
    smtp_from: str = ""
    log_level: str = "INFO"
    ml_model_bundle_path: str = "backend/data/week8/models/model_bundle.joblib"
    ml_require_artifact: bool = False
    ml_max_batch_rows: int = 1000

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")


settings = Settings()
