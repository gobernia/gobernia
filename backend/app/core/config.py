from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    # App
    APP_ENV: str = "development"
    SECRET_KEY: str = "change-me-in-production"

    # Database (Supabase)
    # DATABASE_URL   → asyncpg, usado por FastAPI (pooler puerto 6543 en prod)
    # DATABASE_URL_SYNC → psycopg2, usado solo por Alembic (conexión directa puerto 5432)
    DATABASE_URL: str = ""
    DATABASE_URL_SYNC: str = ""
    USE_POOLER: bool = False  # True cuando DATABASE_URL apunta al pooler pgBouncer (puerto 6543)

    # Auth (Supabase)
    SUPABASE_URL: str = ""
    SUPABASE_ANON_KEY: str = ""
    SUPABASE_JWT_SECRET: str = ""

    # AI
    ANTHROPIC_API_KEY: str = ""
    AI_MODEL: str = "claude-sonnet-4-6"
    DIAGNOSTICO_AI_MODEL: str = "claude-opus-4-8"

    # Storage (S3-compatible: AWS S3 o Supabase Storage)
    AWS_ACCESS_KEY_ID: str = ""
    AWS_SECRET_ACCESS_KEY: str = ""
    AWS_REGION: str = "us-east-1"
    S3_BUCKET_DOCUMENTS: str = "gobernia-documents"
    # Vacío → AWS S3. Para Supabase Storage: https://<project-ref>.supabase.co/storage/v1/s3
    S3_ENDPOINT_URL: str = ""

    # Redis / Celery
    REDIS_URL: str = "redis://localhost:6379/0"

    # CORS
    ALLOWED_ORIGINS: list[str] = ["http://localhost:3000"]

    @property
    def is_production(self) -> bool:
        return self.APP_ENV == "production"


settings = Settings()
