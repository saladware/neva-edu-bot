from functools import lru_cache

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    model_config = {
        "env_file": ".env",
        "env_file_encoding": "utf-8",
        "env_prefix": "NEVAEDU_"
    }

    bot_token: str
    chat_id: str


@lru_cache
def get_settings() -> Settings:
    return Settings()  # type: ignore
