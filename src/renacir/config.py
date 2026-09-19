from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

    environment: str = "development"
    log_level: str = "INFO"

    # Diagnoser (Phase 4C). Never hardcode a value for either of these —
    # both must come from the environment/.env, and `llm_model` in
    # particular must never gain a code-level default: the exact model
    # identifier is a per-experiment decision, not an invisible default.
    anthropic_api_key: str | None = None
    llm_model: str | None = None


settings = Settings()
