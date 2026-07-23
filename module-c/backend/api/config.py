"""Module C Gateway configuration — reads from environment variables."""

import os


class Settings:
    """Gateway settings loaded from environment."""

    # Module A — Monitor Engine (RUL + Anomaly)
    monitor_url: str = os.getenv("MONITOR_URL", "http://127.0.0.1:18000")

    # Gateway own host/port
    host: str = os.getenv("HOST", "0.0.0.0")
    port: int = int(os.getenv("PORT", "8003"))

    # Request timeout (seconds)
    http_timeout: float = float(os.getenv("HTTP_TIMEOUT", "30.0"))

    # API token for simple auth (empty = disabled)
    api_token: str = os.getenv("API_TOKEN", "")

    # CORS allowed origins
    cors_origins: list[str] = os.getenv(
        "CORS_ORIGINS",
        "http://localhost:5173,http://localhost:3000",
    ).split(",")

    # Path prefixes that skip auth middleware
    auth_skip_prefixes: list[str] = ["/ws/"]

    # Development mode — when True, test endpoints are enabled
    dev_mode: bool = os.getenv("DEV_MODE", "true").lower() in ("1", "true", "yes")

    # Diagnosis history persistence file
    history_file: str = os.getenv("HISTORY_FILE", "./data/diagnosis_history.json")


settings = Settings()
