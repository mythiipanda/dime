"""Process boundary. All env parsing and validation lives here."""

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    mistral_api_key: str = ""
    mistral_model: str = "ministral-8b-2512"
    openrouter_api_key: str = ""
    openrouter_model: str = "nvidia/nemotron-3-super-120b-a12b:free"
    cors_allowed_origins: str = "http://localhost:3000"
    llm_timeout_s: int = 60
    llm_max_retries: int = 1
    chat_rate_per_minute: int = 20
    default_timeout_seconds: int = 10

    @property
    def cors_origins(self) -> list[str]:
        return [o.strip() for o in self.cors_allowed_origins.split(",") if o.strip()]


settings = Settings()
