"""
Central configuration management.
Loads all settings from environment variables with sensible defaults.
"""
import os
from dataclasses import dataclass, field
from dotenv import load_dotenv

load_dotenv()


@dataclass
class Config:
    # --- Telegram ---
    telegram_bot_token: str = field(default_factory=lambda: os.getenv("TELEGRAM_BOT_TOKEN", ""))
    telegram_allowed_users: list[int] = field(
        default_factory=lambda: [
            int(x.strip())
            for x in os.getenv("TELEGRAM_ALLOWED_USERS", "").split(",")
            if x.strip()
        ]
    )

    # --- TikTok ---
    tiktok_username: str = field(default_factory=lambda: os.getenv("TIKTOK_USERNAME", ""))
    tiktok_password: str = field(default_factory=lambda: os.getenv("TIKTOK_PASSWORD", ""))
    tiktok_base_url: str = "https://www.tiktok.com"

    # --- LLM (Ollama) ---
    ollama_base_url: str = field(
        default_factory=lambda: os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
    )
    ollama_model: str = field(
        default_factory=lambda: os.getenv("OLLAMA_MODEL", "llama3.1")
    )

    # --- Database ---
    db_path: str = field(
        default_factory=lambda: os.getenv("DB_PATH", "/app/data/bot.db")
    )

    # --- Browser ---
    browser_headless: bool = field(
        default_factory=lambda: os.getenv("BROWSER_HEADLESS", "false").lower() == "true"
    )
    session_dir: str = field(
        default_factory=lambda: os.getenv("SESSION_DIR", "/app/data/tiktok_session")
    )

    # --- Anti-bot delays (seconds) ---
    reply_delay_min: int = field(
        default_factory=lambda: int(os.getenv("REPLY_DELAY_MIN", "30"))
    )
    reply_delay_max: int = field(
        default_factory=lambda: int(os.getenv("REPLY_DELAY_MAX", "300"))
    )
    dm_delay_min: int = field(
        default_factory=lambda: int(os.getenv("DM_DELAY_MIN", "60"))
    )
    dm_delay_max: int = field(
        default_factory=lambda: int(os.getenv("DM_DELAY_MAX", "180"))
    )
    poll_interval_min: int = field(
        default_factory=lambda: int(os.getenv("POLL_INTERVAL_MIN", "300"))
    )
    poll_interval_max: int = field(
        default_factory=lambda: int(os.getenv("POLL_INTERVAL_MAX", "900"))
    )

    # --- Rate limiting ---
    # 동일 유저에게 재발송 금지 기간 (초)
    same_user_cooldown: int = field(
        default_factory=lambda: int(os.getenv("SAME_USER_COOLDOWN", "86400"))  # 24h
    )


config = Config()
