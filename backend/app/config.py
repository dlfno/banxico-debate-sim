from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    PROVIDER: Literal["anthropic", "openrouter"] = "anthropic"
    MODEL: str = "claude-sonnet-4-6"
    ANTHROPIC_API_KEY: str = ""
    OPENROUTER_API_KEY: str = ""
    TAVILY_API_KEY: str = ""
    BANXICO_TOKEN: str = ""
    DATABASE_URL: str = "sqlite:///./banxico.db"
    CORS_ORIGINS: str = "http://localhost:5173"
    JWT_SECRET: str = "dev-only-change-me"
    JWT_EXPIRES_HOURS: int = 720
    ALLOW_REGISTRATION: bool = True
    # Modo demo público: la Simulación de Junta reproduce debates pre-generados
    # (app/data/demo_meetings/) SIN llamar al LLM, y el chat 1-a-1 se deshabilita.
    # Permite un deploy público funcional con costo $0 y sin API keys.
    DEMO_MODE: bool = False

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    @property
    def cors_origins_list(self) -> list[str]:
        return [o.strip() for o in self.CORS_ORIGINS.split(",") if o.strip()]


settings = Settings()
