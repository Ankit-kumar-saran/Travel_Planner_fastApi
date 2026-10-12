from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Reads every value from environment variables / the .env file and validates its type.

    A field named `db_user` is filled from the variable `DB_USER` (case-insensitive).
    Fields without a default value are REQUIRED: the app refuses to start without them.
    """

    # --- MySQL ---
    db_host: str = "localhost"
    db_port: int = 3306
    db_user: str
    db_password: str
    db_name: str = "wandersync"

    # --- JWT ---
    jwt_secret: str
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 60

    # --- External place data (optional) ---
    google_places_api_key: str = ""

    # --- Password reset email (optional) ---
    smtp_host: str = ""
    smtp_port: int = 587
    smtp_user: str = ""
    smtp_password: str = ""
    smtp_from: str = "noreply@wandersync.local"
    frontend_url: str = "http://localhost:5500"

    # --- CORS: comma separated list of allowed frontend origins ---
    cors_origins: str = "http://localhost:5500,http://127.0.0.1:5500"

    # Tell pydantic-settings to read ".env" and to ignore variables we did not declare
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")


settings = Settings()
