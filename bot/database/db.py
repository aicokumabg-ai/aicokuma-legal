"""
SQLite connection and table initialization.
"""
import sqlite3
import os
from bot.config import config
from bot.utils.logger import get_logger

logger = get_logger(__name__)


def get_connection() -> sqlite3.Connection:
    os.makedirs(os.path.dirname(config.db_path), exist_ok=True)
    conn = sqlite3.connect(config.db_path, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def init_db() -> None:
    conn = get_connection()
    with conn:
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS monitored_posts (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                url         TEXT UNIQUE NOT NULL,
                video_id    TEXT UNIQUE NOT NULL,
                active      INTEGER DEFAULT 1,
                created_at  DATETIME DEFAULT CURRENT_TIMESTAMP
            );

            CREATE TABLE IF NOT EXISTS keyword_rules (
                id            INTEGER PRIMARY KEY AUTOINCREMENT,
                post_id       INTEGER REFERENCES monitored_posts(id) ON DELETE CASCADE,
                keyword       TEXT NOT NULL,
                reply_text    TEXT NOT NULL,
                dm_text       TEXT,
                active        INTEGER DEFAULT 1,
                created_at    DATETIME DEFAULT CURRENT_TIMESTAMP
            );

            CREATE TABLE IF NOT EXISTS processed_comments (
                id              INTEGER PRIMARY KEY AUTOINCREMENT,
                comment_id      TEXT UNIQUE NOT NULL,
                post_id         INTEGER REFERENCES monitored_posts(id),
                username        TEXT,
                matched_keyword TEXT,
                reply_sent      INTEGER DEFAULT 0,
                dm_sent         INTEGER DEFAULT 0,
                processed_at    DATETIME DEFAULT CURRENT_TIMESTAMP
            );

            CREATE TABLE IF NOT EXISTS action_queue (
                id           INTEGER PRIMARY KEY AUTOINCREMENT,
                type         TEXT NOT NULL,
                payload      TEXT NOT NULL,
                status       TEXT DEFAULT 'pending',
                retry_count  INTEGER DEFAULT 0,
                scheduled_at DATETIME,
                created_at   DATETIME DEFAULT CURRENT_TIMESTAMP
            );
        """)
    conn.close()
    logger.info("Database initialized at %s", config.db_path)
