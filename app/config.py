"""Environment-driven configuration for the lab.

Every value has a lab-friendly default so the service runs with zero setup. Override any
of them with environment variables (or a local .env file) of the same name.
"""

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    # llama.cpp OpenAI-compatible server.
    llama_base_url: str = "http://localhost:8080/v1"
    llama_model: str = "local-model"  # llama.cpp typically ignores/echoes this.
    llama_api_key: str = "sk-no-key"  # Sent as a Bearer token; llama.cpp ignores it.
    llama_timeout: float = 120.0

    jwt_secret: str = "dev-secret-change-me"
    jwt_alg: str = "HS256"
    jwt_issuer: str = "cybersci-lab"
    jwt_ttl_seconds: int = 3600

    # Tool loop.
    max_tool_iterations: int = 5

    # Server. Auto-reload is local-dev only; see main.py.
    app_reload: bool = False

    # Truncation caps so a huge page/file does not blow up the context window.
    max_fetch_chars: int = 20_000
    max_file_chars: int = 20_000
    max_http_tool_chars: int = 20_000

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")


@lru_cache
def get_settings() -> Settings:
    return Settings()
