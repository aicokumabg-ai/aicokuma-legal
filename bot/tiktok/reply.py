"""
TikTok 대댓글(comment reply) 작성 모듈.
"""
import asyncio
from playwright.async_api import Page
from bot.anti_bot.typer import type_text
from bot.anti_bot.human_mouse import move_to_element
from bot.utils.logger import get_logger

logger = get_logger(__name__)


async def post_reply(
    page: Page,
    video_url: str,
    comment_id: str,
    reply_text: str,
) -> bool:
    """
    특정 댓글에 대댓글을 단다.
    Returns True on success.
    """
    logger.info("Posting reply to comment %s on %s", comment_id, video_url)
    await page.goto(video_url, wait_until="domcontentloaded")
    await asyncio.sleep(3)

    # 댓글 섹션 대기
    try:
        await page.wait_for_selector('[data-e2e="comment-list"]', timeout=15000)
    except Exception:
        logger.error("Comment list not found; cannot post reply")
        return False

    # comment_id로 해당 댓글 항목 찾기
    comment_item = await _find_comment_item(page, comment_id)
    if not comment_item:
        logger.warning("Comment %s not found on page", comment_id)
        return False

    # 댓글 위에 마우스를 올려 Reply 버튼 표시
    await move_to_element(page, comment_item)
    await asyncio.sleep(0.8)

    # Reply 버튼 클릭
    reply_btn = await comment_item.query_selector('[data-e2e="comment-reply-btn"]')
    if not reply_btn:
        # 일부 버전: "Reply" 텍스트 링크
        reply_btn = await comment_item.query_selector('span:has-text("Reply")')
    if not reply_btn:
        logger.warning("Reply button not found for comment %s", comment_id)
        return False

    await move_to_element(page, reply_btn)
    await asyncio.sleep(0.4)
    await reply_btn.click()
    await asyncio.sleep(1.5)

    # 입력창 찾기
    input_box = page.locator('[data-e2e="comment-input"]').last
    try:
        await input_box.wait_for(timeout=5000)
    except Exception:
        logger.error("Reply input box not found")
        return False

    await input_box.click()
    await asyncio.sleep(0.5)
    await type_text(page, '[data-e2e="comment-input"]', reply_text)
    await asyncio.sleep(1)

    # 전송 버튼 클릭
    submit_btn = page.locator('[data-e2e="comment-post-btn"]').last
    await move_to_element(page, submit_btn)
    await asyncio.sleep(0.5)
    await submit_btn.click()
    await asyncio.sleep(2)

    logger.info("Reply posted successfully to comment %s", comment_id)
    return True


async def _find_comment_item(page, comment_id: str):
    """data-comment-id 또는 fallback 방식으로 댓글 요소를 찾는다."""
    # 1) data-comment-id 속성으로 찾기
    el = await page.query_selector(f'[data-comment-id="{comment_id}"]')
    if el:
        return el

    # 2) comment_id가 "username::text" 형식인 경우 username으로 찾기
    if "::" in comment_id:
        username, text_prefix = comment_id.split("::", 1)
        items = await page.query_selector_all('[data-e2e="comment-item"]')
        for item in items:
            uname_el = await item.query_selector('[data-e2e="comment-username"]')
            text_el = await item.query_selector('[data-e2e="comment-text"]')
            uname = (await uname_el.inner_text()).strip() if uname_el else ""
            ctext = (await text_el.inner_text()).strip() if text_el else ""
            if uname == username and ctext.startswith(text_prefix[:30]):
                return item
    return None
