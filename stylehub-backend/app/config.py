from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings, loaded from environment variables / .env file."""

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    app_name: str = "StyleHub API"

    # JWT
    secret_key: str  # required - no insecure default on purpose
    algorithm: str = "HS256"
    access_token_expire_minutes: int = 60

    # Database
    database_url: str = "sqlite:///./stylehub.db"

    # Stripe
    stripe_secret_key: str = ""
    stripe_publishable_key: str = ""
    stripe_webhook_secret: str = ""
    currency: str = "usd"

    # CORS
    cors_origins: str = "http://localhost:5173"

    seed_products: bool = True

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
