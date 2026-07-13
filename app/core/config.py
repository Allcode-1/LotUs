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

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        env_nested_delimiter="__",
        extra="ignore",
    )


settings = Settings()  # type: ignore[call-arg]
