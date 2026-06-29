"""
Centralized application configuration.

Why this exists:
Instead of scattering `os.getenv("SOME_VAR")` calls across 30 files (which makes
typos invisible and gives you zero type safety), every setting is declared ONCE
here as a typed field. Pydantic's BaseSettings automatically:
  1. Reads values from the .env file / real environment variables
  2. Validates and coerces types (e.g. "8000" -> int 8000)
  3. Raises a clear error at startup if something required is missing,
     instead of failing deep inside business logic later.

Usage elsewhere in the codebase:
    from backend.utils.config import settings
    settings.groq_api_key
"""

from functools import lru_cache
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    # ---- LLM Provider (Groq) ----
    groq_api_key: str = "your_groq_api_key_here"
    llm_model: str = "llama-3.3-70b-versatile"
    llm_temperature: float = 0.2

    # ---- RAG / Embeddings ----
    embedding_model: str = "all-MiniLM-L6-v2"
    chroma_persist_dir: str = "./chroma_store"
    knowledge_base_dir: str = "./knowledge_base"
    rag_top_k: int = 4

    # ---- Confidence thresholds (used by the agent graph) ----
    clarify_threshold: float = 0.60
    escalate_threshold: float = 0.30

    # ---- Database ----
    database_url: str = "sqlite:///./support_agent.db"

    # ---- API server ----
    api_host: str = "0.0.0.0"
    api_port: int = 8000

    # ---- App ----
    app_env: str = "development"
    log_level: str = "INFO"

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )


@lru_cache
def get_settings() -> Settings:
    """
    Returns a cached singleton Settings instance.

    @lru_cache means the .env file is parsed only ONCE per process,
    no matter how many modules call get_settings(). This avoids repeatedly
    re-reading and re-validating the file, and guarantees every part of
    the app sees the exact same configuration object.
    """
    return Settings()


# Convenience singleton — most modules will just do `from .config import settings`
settings = get_settings()
