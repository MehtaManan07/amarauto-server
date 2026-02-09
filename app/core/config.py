from pydantic_settings import BaseSettings
from pydantic import Field


class Config(BaseSettings):
    # Turso Configuration (libSQL cloud database) - REQUIRED
    turso_database_url: str = Field(alias="TURSO_DATABASE_URL")
    turso_auth_token: str = Field(alias="TURSO_AUTH_TOKEN")

    # JWT Configuration
    jwt_secret: str = Field(default="", alias="JWT_SECRET")

    # GCP Configuration (for Cloud Storage)
    gcp_project_id: str = Field(default="", alias="GCP_PROJECT_ID")
    gcp_bucket_name: str = Field(default="", alias="GCP_BUCKET_NAME")
    gcp_invoice_prefix: str = Field(default="invoices/", alias="GCP_INVOICE_PREFIX")
    gcp_product_images_prefix: str = Field(
        default="product-images/", alias="GCP_PRODUCT_IMAGES_PREFIX"
    )

    secret_key: str = Field(default="", alias="SECRET_KEY")
    algorithm: str = Field(default="HS256", alias="ALGORITHM")
    # Token expiration: 7 days for development, override in .env for production
    access_token_expire_minutes: int = Field(
        default=10080, alias="ACCESS_TOKEN_EXPIRE_MINUTES"
    )
    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        extra = "allow"


# Instantiate the settings
config = Config()
