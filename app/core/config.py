from pathlib import Path

from pydantic import BaseModel, Field
from pydantic_settings import BaseSettings, SettingsConfigDict


BASE_DIR = Path(__file__).resolve().parents[2]


class AuthJWTSettings(BaseModel):
    public_key_path: Path = BASE_DIR / "certs" / "public.pem"
    private_key_path: Path = BASE_DIR / "certs" / "private.pem"
    algorithm: str = "RS256"
    access_token_expire_minutes: int = 15
    refresh_token_expire_days: int = 30


class Settings(BaseSettings):
    database_url: str
    auth_jwt: AuthJWTSettings = Field(default_factory=AuthJWTSettings)

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        env_nested_delimiter="__",
        extra="ignore",
    )


settings = Settings()  # type: ignore[call-arg]
