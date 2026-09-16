"""Process boundary. All env parsing and validation lives here."""

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    mistral_api_key: str = ""
    mistral_model: str = "ministral-8b-2512"
    openrouter_api_key: str = ""
    openrouter_model: str = "nvidia/nemotron-3-super-120b-a12b:free"
    inception_api_key: str = ""
    jina_api_key: str = ""
    inception_model: str = "mercury-2.5"
    groq_api_key: str = ""
    groq_model: str = "openai/gpt-oss-20b"
    cors_allowed_origins: str = "http://localhost:3000"
    llm_timeout_s: int = 60
    llm_max_retries: int = 1
    chat_rate_per_minute: int = 20
    default_timeout_seconds: int = 10
    dime_jev_enabled: bool = False
    typesafe_api_key: str = ""
    typesafe_model: str = "jev-1.13.0"
    typesafe_timeout_seconds: float = 2.0
    dime_jev_shadow_log: str = ""

    @property
    def cors_origins(self) -> list[str]:
        return [o.strip() for o in self.cors_allowed_origins.split(",") if o.strip()]


settings = Settings()
