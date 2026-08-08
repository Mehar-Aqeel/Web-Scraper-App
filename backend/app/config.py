from pydantic_settings import BaseSettings
from typing import List


class Settings(BaseSettings):
    APP_ENV: str = "development"
    BACKEND_URL: str = "http://localhost:8000"
    FRONTEND_URL: str = "http://localhost:5173"

    REQUEST_TIMEOUT: int = 15
    CONNECT_TIMEOUT: int = 5
    MAX_RESPONSE_SIZE: int = 10485760
    MAX_REDIRECTS: int = 3
    MAX_RESULT_ROWS: int = 2000
    SCRAPER_USER_AGENT: str = "UniversalWebDataExtractor/1.0 (+https://github.com/<your-username>/universal-web-data-extractor)"
    ROBOTS_CACHE_TTL_SECONDS: int = 3600
    RATE_LIMIT_PER_IP_PER_MINUTE: int = 20
    PER_DOMAIN_REQUEST_DELAY_MS: int = 500
    ALLOWED_ORIGINS: str = "http://localhost:5173"
    LOG_LEVEL: str = "INFO"
    MAX_RETRIES: int = 1
    GLOBAL_CONCURRENCY_LIMIT: int = 20
    CACHE_TTL_SECONDS: int = 300

    def allowed_origins_list(self) -> List[str]:
        return [o.strip() for o in self.ALLOWED_ORIGINS.split(",")]

    class Config:
        env_file = ".env"


settings = Settings()
