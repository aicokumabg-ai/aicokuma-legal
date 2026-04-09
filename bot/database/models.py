"""
DB helper functions (CRUD) for each table.
All functions accept an open sqlite3.Connection.
"""
import json
import sqlite3
from datetime import datetime, timezone
from typing import Optional
from bot.config import config


# ── monitored_posts ──────────────────────────────────────────────────────────

def add_post(conn: sqlite3.Connection, url: str, video_id: str) -> int:
    cur = conn.execute(
        "INSERT OR IGNORE INTO monitored_posts (url, video_id) VALUES (?, ?)",
        (url, video_id),
    )
    conn.commit()
    return cur.lastrowid or _get_post_id(conn, video_id)


def _get_post_id(conn: sqlite3.Connection, video_id: str) -> int:
    row = conn.execute(
        "SELECT id FROM monitored_posts WHERE video_id = ?", (video_id,)
    ).fetchone()
    return row["id"] if row else -1


def get_active_posts(conn: sqlite3.Connection) -> list[sqlite3.Row]:
    return conn.execute(
        "SELECT * FROM monitored_posts WHERE active = 1"
    ).fetchall()


def set_post_active(conn: sqlite3.Connection, post_id: int, active: bool) -> None:
    conn.execute(
        "UPDATE monitored_posts SET active = ? WHERE id = ?",
        (1 if active else 0, post_id),
    )
    conn.commit()


# ── keyword_rules ─────────────────────────────────────────────────────────────

def add_rule(
    conn: sqlite3.Connection,
    post_id: int,
    keyword: str,
    reply_text: str,
    dm_text: Optional[str] = None,
) -> int:
    cur = conn.execute(
        "INSERT INTO keyword_rules (post_id, keyword, reply_text, dm_text) VALUES (?,?,?,?)",
        (post_id, keyword, reply_text, dm_text),
    )
    conn.commit()
    return cur.lastrowid


def get_rules_for_post(conn: sqlite3.Connection, post_id: int) -> list[sqlite3.Row]:
    return conn.execute(
        "SELECT * FROM keyword_rules WHERE post_id = ? AND active = 1",
        (post_id,),
    ).fetchall()


# ── processed_comments ────────────────────────────────────────────────────────

def comment_already_processed(conn: sqlite3.Connection, comment_id: str) -> bool:
    row = conn.execute(
        "SELECT id FROM processed_comments WHERE comment_id = ?", (comment_id,)
    ).fetchone()
    return row is not None


def user_in_cooldown(conn: sqlite3.Connection, username: str) -> bool:
    row = conn.execute(
        """
        SELECT processed_at FROM processed_comments
        WHERE username = ? AND (reply_sent = 1 OR dm_sent = 1)
        ORDER BY processed_at DESC LIMIT 1
        """,
        (username,),
    ).fetchone()
    if not row:
        return False
    last = datetime.fromisoformat(row["processed_at"])
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    return (now - last).total_seconds() < config.same_user_cooldown


def mark_comment_processed(
    conn: sqlite3.Connection,
    comment_id: str,
    post_id: int,
    username: str,
    matched_keyword: str,
    reply_sent: bool = False,
    dm_sent: bool = False,
) -> None:
    conn.execute(
        """
        INSERT OR REPLACE INTO processed_comments
          (comment_id, post_id, username, matched_keyword, reply_sent, dm_sent)
        VALUES (?,?,?,?,?,?)
        """,
        (comment_id, post_id, username, matched_keyword, int(reply_sent), int(dm_sent)),
    )
    conn.commit()


# ── action_queue ──────────────────────────────────────────────────────────────

def enqueue_action(
    conn: sqlite3.Connection,
    action_type: str,
    payload: dict,
    scheduled_at: datetime,
) -> int:
    cur = conn.execute(
        """
        INSERT INTO action_queue (type, payload, scheduled_at)
        VALUES (?, ?, ?)
        """,
        (action_type, json.dumps(payload, ensure_ascii=False), scheduled_at.isoformat()),
    )
    conn.commit()
    return cur.lastrowid


def get_due_actions(conn: sqlite3.Connection) -> list[sqlite3.Row]:
    now = datetime.now(timezone.utc).replace(tzinfo=None).isoformat()
    return conn.execute(
        """
        SELECT * FROM action_queue
        WHERE status = 'pending' AND scheduled_at <= ?
        ORDER BY scheduled_at ASC
        """,
        (now,),
    ).fetchall()


def update_action_status(
    conn: sqlite3.Connection,
    action_id: int,
    status: str,
    retry_count: Optional[int] = None,
) -> None:
    if retry_count is not None:
        conn.execute(
            "UPDATE action_queue SET status = ?, retry_count = ? WHERE id = ?",
            (status, retry_count, action_id),
        )
    else:
        conn.execute(
            "UPDATE action_queue SET status = ? WHERE id = ?",
            (status, action_id),
        )
    conn.commit()
