"""
비동기 워커.
두 가지 루프를 실행한다:
  1. monitor_loop  — 활성 게시글을 주기적으로 폴링하여 새 댓글을 감지
  2. executor_loop — action_queue에서 실행 시각이 된 작업을 꺼내 실행
"""
import asyncio
import json
from datetime import datetime, timezone
from bot.config import config
from bot.database.db import get_connection
from bot.database import models
from bot.tiktok import monitor, reply as tiktok_reply, dm as tiktok_dm
from bot.tiktok.auth import ensure_logged_in
from bot.anti_bot.delays import poll_delay
from bot.queue.manager import schedule_reply_and_dm
from bot.telegram.notifier import notify
from bot.utils.logger import get_logger

logger = get_logger(__name__)

MAX_RETRIES = 3


async def monitor_loop() -> None:
    """활성 게시글을 순차적으로 폴링한다."""
    logger.info("Monitor loop started")
    page = await ensure_logged_in()

    while True:
        conn = get_connection()
        posts = models.get_active_posts(conn)
        conn.close()

        for post in posts:
            await _check_post(page, dict(post))
            # 게시글 간 짧은 휴식
            await asyncio.sleep(2)

        await poll_delay()


async def _check_post(page, post: dict) -> None:
    post_id = post["id"]
    video_url = post["url"]

    conn = get_connection()
    rules = [dict(r) for r in models.get_rules_for_post(conn, post_id)]
    conn.close()

    if not rules:
        return

    comments = await monitor.fetch_comments(page, video_url)

    for comment in comments:
        conn = get_connection()

        # 이미 처리한 댓글 건너뜀
        if models.comment_already_processed(conn, comment.comment_id):
            conn.close()
            continue

        # 24시간 내 같은 유저 중복 방지
        if models.user_in_cooldown(conn, comment.username):
            conn.close()
            logger.debug("User @%s in cooldown, skipping", comment.username)
            continue

        conn.close()

        # 키워드 매칭
        for rule in rules:
            keyword = rule["keyword"].lower()
            if keyword in comment.text.lower():
                logger.info(
                    "Keyword '%s' matched in comment by @%s: %s",
                    keyword, comment.username, comment.text[:50],
                )
                # 큐에 등록
                schedule_reply_and_dm(
                    post_id=post_id,
                    comment_id=comment.comment_id,
                    username=comment.username,
                    user_profile_url=comment.user_profile_url,
                    video_url=video_url,
                    reply_text=rule["reply_text"],
                    dm_text=rule.get("dm_text"),
                    matched_keyword=keyword,
                )
                # 처리됨으로 기록 (중복 방지)
                conn = get_connection()
                models.mark_comment_processed(
                    conn, comment.comment_id, post_id, comment.username, keyword
                )
                conn.close()
                break  # 첫 번째 매칭 규칙만 적용


async def executor_loop() -> None:
    """실행 시각이 된 action_queue 항목을 처리한다."""
    logger.info("Executor loop started")
    page = await ensure_logged_in()

    while True:
        conn = get_connection()
        due_actions = models.get_due_actions(conn)
        conn.close()

        for action in due_actions:
            action_id = action["id"]
            action_type = action["type"]
            payload = json.loads(action["payload"])
            retry_count = action["retry_count"]

            conn = get_connection()
            models.update_action_status(conn, action_id, "running")
            conn.close()

            success = False
            try:
                if action_type == "reply":
                    success = await tiktok_reply.post_reply(
                        page,
                        payload["video_url"],
                        payload["comment_id"],
                        payload["reply_text"],
                    )
                    if success:
                        conn = get_connection()
                        # reply_sent 업데이트
                        conn.execute(
                            "UPDATE processed_comments SET reply_sent=1 WHERE comment_id=?",
                            (payload["comment_id"],),
                        )
                        conn.commit()
                        conn.close()
                        await notify(f"✅ @{payload['username']} 댓글에 대댓글 완료")

                elif action_type == "dm":
                    success = await tiktok_dm.send_dm(
                        page,
                        payload["username"],
                        payload["user_profile_url"],
                        payload["dm_text"],
                    )
                    if success:
                        conn = get_connection()
                        conn.execute(
                            "UPDATE processed_comments SET dm_sent=1 WHERE comment_id=?",
                            (payload["comment_id"],),
                        )
                        conn.commit()
                        conn.close()
                        await notify(f"✅ @{payload['username']} 에게 DM 발송 완료")

            except Exception as exc:
                logger.exception("Action %d failed: %s", action_id, exc)

            conn = get_connection()
            if success:
                models.update_action_status(conn, action_id, "done")
            elif retry_count < MAX_RETRIES:
                models.update_action_status(conn, action_id, "pending", retry_count + 1)
                logger.warning("Action %d will retry (%d/%d)", action_id, retry_count + 1, MAX_RETRIES)
            else:
                models.update_action_status(conn, action_id, "failed")
                logger.error("Action %d failed after %d retries", action_id, MAX_RETRIES)
                await notify(f"❌ 액션 실패 (id={action_id}, type={action_type})")
            conn.close()

            # 액션 사이 짧은 휴식
            await asyncio.sleep(1)

        # 큐가 빌 때 0.5초 대기
        await asyncio.sleep(0.5)
