from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # Database
    DATABASE_URL: str = (
        "postgresql://mermra:mermra_secret@localhost:5432/mermra_exam"
    )

    # External service keys (populated later)
    SCHOLARXIV_API_KEY: str = ""
    VOXIDE_PUBLISHABLE_KEY: str = ""

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}


settings = Settings()
