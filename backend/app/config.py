from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "AccessAble API"
    api_prefix: str = "/api/v1"
    database_url: str = "sqlite:///./accessable.db"
    cors_origins: str = "http://localhost:5173"
    cors_allow_credentials: bool = False
    ring_client_id: str = ""
    ring_client_secret: str = ""
    ring_hmac_signing_key: str = ""
    ring_api_base_url: str = "https://api.amazonvision.com"
    ring_environment: str = "staging"

    model_config = SettingsConfigDict(
        env_file=".env",
        extra="ignore",
    )


settings = Settings()
