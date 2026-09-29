from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict
import os
from typing import Literal

RuntimeV2Mode = Literal["off", "on", "shadow"]


def runtime_v2_mode() -> RuntimeV2Mode:
    mode = os.environ.get("DIME_RUNTIME_V2", "off").strip().lower()
    if mode == "on":
        return "on"
    if mode == "shadow":
        return "shadow"
    return "off"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    nvidia_nim_api_key: str = ""
    nvidia_nim_model: str = "z-ai/glm-5.3-flash"
    gemini_api_key: str = ""
    gemini_model: str = "gemini-3.5-flash-lite"
    mistral_api_key: str = ""
    mistral_model: str = "ministral-8b-2512"
    openrouter_api_key: str = ""
    openrouter_model: str = "nvidia/nemotron-3-super-120b-a12b:free"
    inception_api_key: str = ""
    dime_enable_inception: bool = False
    jina_api_key: str = ""
    inception_model: str = "mercury-2.5"
    groq_api_key: str = ""
    dime_enable_groq: bool = False
    groq_model: str = "openai/gpt-oss-20b"
    cors_allowed_origins: str = "http://localhost:3000,https://dime-fawn.vercel.app"
    llm_timeout_s: int = 60
    llm_max_retries: int = 1
    dime_v2_pre_tool_timeout_s: float = Field(default=45.0, gt=0)
    dime_v2_run_timeout_s: float = Field(default=360.0, gt=0)
    dime_first_token_timeout_s: float = Field(default=45.0, gt=0)
    chat_rate_per_minute: int = 20
    default_timeout_seconds: int = 10

    @property
    def cors_origins(self) -> list[str]:
        return [o.strip() for o in self.cors_allowed_origins.split(",") if o.strip()]


settings = Settings()
