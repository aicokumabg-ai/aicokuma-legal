"""
작업 큐 관리자.
댓글 감지 시 대댓글/DM 액션을 스케줄링하여 action_queue에 등록한다.
"""
import json
from datetime import datetime, timedelta, timezone
from bot.config import config
from bot.anti_bot.delays import _beta_sample
from bot.database.db import get_connection
from bot.database import models
from bot.utils.logger import get_logger

logger = get_logger(__name__)


def schedule_reply_and_dm(
    post_id: int,
    comment_id: str,
    username: str,
    user_profile_url: str,
    video_url: str,
    reply_text: str,
    dm_text: str | None,
    matched_keyword: str,
) -> None:
    """
    대댓글과 DM 액션을 큐에 등록한다.
    대댓글은 reply_delay 후, DM은 그 이후 dm_delay 후 실행된다.
    """
    conn = get_connection()
    try:
        now = datetime.now(timezone.utc).replace(tzinfo=None)

        # 대댓글 스케줄
        reply_secs = _beta_sample(config.reply_delay_min, config.reply_delay_max)
        reply_at = now + timedelta(seconds=reply_secs)
        reply_payload = {
            "post_id": post_id,
            "comment_id": comment_id,
            "video_url": video_url,
            "reply_text": reply_text,
            "username": username,
            "matched_keyword": matched_keyword,
        }
        models.enqueue_action(conn, "reply", reply_payload, reply_at)
        logger.info(
            "Scheduled reply for comment %s in %.0fs (at %s)",
            comment_id, reply_secs, reply_at.strftime("%H:%M:%S"),
        )

        # DM 스케줄 (대댓글 이후)
        if dm_text:
            dm_secs = reply_secs + _beta_sample(config.dm_delay_min, config.dm_delay_max)
            dm_at = now + timedelta(seconds=dm_secs)
            dm_payload = {
                "post_id": post_id,
                "comment_id": comment_id,
                "username": username,
                "user_profile_url": user_profile_url,
                "dm_text": dm_text,
                "matched_keyword": matched_keyword,
            }
            models.enqueue_action(conn, "dm", dm_payload, dm_at)
            logger.info(
                "Scheduled DM for @%s in %.0fs (at %s)",
                username, dm_secs, dm_at.strftime("%H:%M:%S"),
            )
    finally:
        conn.close()
