from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    bot_token: str = Field(alias="BOT_TOKEN")
    backend_base_url: str = Field(default="http://localhost:8000", alias="BACKEND_BASE_URL")
    users_base_url: str = Field(default="http://localhost:8001", alias="USERS_BASE_URL")
    offer_url: str = Field(default="https://example.com/offer.pdf", alias="OFFER_URL")
    generation_poll_interval_seconds: float = Field(default=3.0, alias="GENERATION_POLL_INTERVAL_SECONDS")
    generation_poll_attempts: int = Field(default=80, alias="GENERATION_POLL_ATTEMPTS")
    nomina_base_agent: str = Field(default="natalai-geoservice/v1", alias="NOMINA_BASE_AGENT")
    nomina_url: str = Field(default="https://nominatim.openstreetmap.org/search", alias="NOMINA_URL")
    locationiq_token: str = Field(alias="LOCATIONIQ_ACCESS_TOKEN")
    locationiq_url: str = Field(default="https://us1.locationiq.com/v1/search", alias="LOCATIONIQ_URL")
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")
