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
    redis_url: str = "redis://127.0.0.1:6379/0"
    redis_socket_connect_timeout_seconds: float = 1
    redis_socket_timeout_seconds: float = 1
    cache_enabled: bool = True
    cache_fail_open: bool = True
    auction_cache_ttl_seconds: int = 30
    rate_limit_enabled: bool = True
    rate_limit_fail_open: bool = False
    auth_register_rate_limit_limit: int = 5
    auth_register_rate_limit_window_seconds: int = 60
    auth_login_ip_rate_limit_limit: int = 20
    auth_login_ip_rate_limit_window_seconds: int = 60
    auth_login_username_rate_limit_limit: int = 8
    auth_login_username_rate_limit_window_seconds: int = 300
    bid_user_rate_limit_limit: int = 30
    bid_user_rate_limit_window_seconds: int = 60
    bid_lot_rate_limit_limit: int = 120
    bid_lot_rate_limit_window_seconds: int = 60
    cors_allowed_origins: str = ""
    s3_endpoint_url: str | None = None
    s3_bucket: str = "lotus-media"
    s3_region: str = "us-east-1"
    s3_access_key_id: str | None = None
    s3_secret_access_key: str | None = None
    s3_force_path_style: bool = True
    s3_presigned_url_expire_seconds: int = 900
    item_images_max_count: int = 10
    item_image_max_size_bytes: int = 5 * 1024 * 1024
    item_image_allowed_content_types: str = "image/jpeg,image/png,image/webp"

    @property
    def allowed_item_image_content_types(self) -> set[str]:
        return {
            content_type.strip()
            for content_type in self.item_image_allowed_content_types.split(",")
            if content_type.strip()
        }

    @property
    def cors_origins(self) -> list[str]:
        return [
            origin.strip()
            for origin in self.cors_allowed_origins.split(",")
            if origin.strip()
        ]

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        env_nested_delimiter="__",
        extra="ignore",
    )


settings = Settings()  # type: ignore[call-arg]
