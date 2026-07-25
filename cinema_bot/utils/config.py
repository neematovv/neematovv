import time
from typing import List
from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    BOT_TOKEN: str
    ADMIN_IDS: str
    CHANNEL_ID: int
    CHANNEL_USERNAME: str
    CHANNEL_INVITE_LINK: str
    BOT_USERNAME: str
    DATABASE_NAME: str = "cinema.db"
    
    START_TIME: float = time.time()
    VERSION: str = "3.0.0"
    BUILD_VERSION: str = "2026.07.22"

    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", extra="ignore"
    )

    @property
    def admin_list(self) -> List[int]:
        try:
            return [int(x.strip()) for x in self.ADMIN_IDS.split(",") if x.strip()]
        except ValueError:
            return []

config = Settings()
