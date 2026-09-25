from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # Database
    DATABASE_URL: str = (
        "postgresql://mermra:mermra_secret@localhost:5432/mermra_exam"
    )

    # OpenAI / LLM
    OPENAI_API_KEY: str = ""
    OPENAI_BASE_URL: str | None = None
    LLM_MODEL: str = "gpt-4o-mini"
    
    # Voyage Embeddings
    VOYAGE_API_KEY: str = ""
    EMBEDDING_MODEL: str = "voyage-3"

    # ScholarXIV Papers API
    SCHOLARXIV_API_URL: str = "https://scholarxiv.com"
    SCHOLARXIV_API_KEY: str = ""

    # PDF storage: "local" or "s3"
    UPLOAD_BACKEND: str = "local"
    UPLOAD_DIR: str = "uploads"

    # S3 settings (used when UPLOAD_BACKEND=s3)
    S3_BUCKET: str = ""
    S3_PREFIX: str = "theses/"
    AWS_REGION: str = "us-east-1"

    # CORS — comma-separated origins (parsed in main.py)
    ALLOWED_ORIGINS: str = "http://localhost:5173,http://localhost:3000"

    # Voice service (Phase 2)
    # NOTE: Before deploying to EthioDeploy, lock the Voxide publishable key
    # to the production domain in the Voxide dashboard → Settings → Allowed Domains.
    VOXIDE_PUBLISHABLE_KEY: str = ""

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}


settings = Settings()
