"""
Central configuration management.
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
        default_factory=lambda: os.getenv("DB_PATH", "./data/bot.db")
    )

    # ─── Chrome 연결 방식 ────────────────────────────────────────────────────
    # 방법 1: 기존 Chrome에 CDP로 연결 (가장 권장)
    #   Chrome을 --remote-debugging-port=9222 로 실행해야 함
    chrome_debug_port: int = field(
        default_factory=lambda: int(os.getenv("CHROME_DEBUG_PORT", "9222"))
    )
    # 방법 2: 기존 Chrome 프로필 경로 사용 (Chrome이 꺼져 있어야 함)
    #   Windows: C:\Users\{사용자}\AppData\Local\Google\Chrome\User Data
    #   Mac:     /Users/{사용자}/Library/Application Support/Google/Chrome
    #   Linux:   /home/{사용자}/.config/google-chrome
    chrome_user_data_dir: str = field(
        default_factory=lambda: os.getenv("CHROME_USER_DATA_DIR", "")
    )
    # 사용할 Chrome 프로필 이름 (기본: Default)
    chrome_profile: str = field(
        default_factory=lambda: os.getenv("CHROME_PROFILE", "Default")
    )
    # 방법 3: 새 브라우저 (fallback — 세션 별도 관리)
    browser_headless: bool = field(
        default_factory=lambda: os.getenv("BROWSER_HEADLESS", "false").lower() == "true"
    )
    session_dir: str = field(
        default_factory=lambda: os.getenv("SESSION_DIR", "./data/tiktok_session")
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
    same_user_cooldown: int = field(
        default_factory=lambda: int(os.getenv("SAME_USER_COOLDOWN", "86400"))
    )


config = Config()
