"""
TikTok 게시글 댓글 폴링 모듈.
주어진 video URL의 최신 댓글을 스크래핑하여 반환한다.
"""
import asyncio
import re
from dataclasses import dataclass
from playwright.async_api import Page
from bot.utils.logger import get_logger

logger = get_logger(__name__)


@dataclass
class Comment:
    comment_id: str
    username: str
    text: str
    user_profile_url: str


async def fetch_comments(page: Page, video_url: str, max_scroll: int = 5) -> list[Comment]:
    """
    video_url의 댓글을 최대 max_scroll번 스크롤하며 수집한다.
    """
    logger.info("Fetching comments from %s", video_url)
    await page.goto(video_url, wait_until="domcontentloaded")
    await asyncio.sleep(3)

    # 댓글 섹션이 로드될 때까지 대기
    try:
        await page.wait_for_selector('[data-e2e="comment-list"]', timeout=15000)
    except Exception:
        logger.warning("Comment section not found at %s", video_url)
        return []

    comments: list[Comment] = []
    seen_ids: set[str] = set()

    for scroll_idx in range(max_scroll):
        comment_items = await page.query_selector_all('[data-e2e="comment-item"]')

        for item in comment_items:
            # 댓글 ID (data 속성 또는 고유 텍스트 해시)
            cid = await item.get_attribute("data-comment-id") or ""
            if not cid:
                # fallback: 유저명 + 댓글 내용 해시
                username_el = await item.query_selector('[data-e2e="comment-username"]')
                text_el = await item.query_selector('[data-e2e="comment-text"]')
                uname = (await username_el.inner_text()).strip() if username_el else ""
                ctext = (await text_el.inner_text()).strip() if text_el else ""
                cid = f"{uname}::{ctext[:50]}"

            if cid in seen_ids:
                continue
            seen_ids.add(cid)

            username_el = await item.query_selector('[data-e2e="comment-username"]')
            text_el = await item.query_selector('[data-e2e="comment-text"]')
            link_el = await item.query_selector('a[href*="/@"]')

            username = (await username_el.inner_text()).strip() if username_el else ""
            text = (await text_el.inner_text()).strip() if text_el else ""
            profile_href = await link_el.get_attribute("href") if link_el else ""
            profile_url = f"https://www.tiktok.com{profile_href}" if profile_href.startswith("/@") else profile_href

            if username and text:
                comments.append(Comment(
                    comment_id=cid,
                    username=username,
                    text=text,
                    user_profile_url=profile_url,
                ))

        # 더 많은 댓글을 위해 스크롤
        if scroll_idx < max_scroll - 1:
            await page.evaluate(
                "document.querySelector('[data-e2e=\"comment-list\"]')"
                ".scrollBy(0, 800)"
            )
            await asyncio.sleep(2)

    logger.info("Fetched %d comments from %s", len(comments), video_url)
    return comments


def extract_video_id(url: str) -> str:
    """TikTok URL에서 video ID 추출."""
    match = re.search(r"/video/(\d+)", url)
    return match.group(1) if match else ""
