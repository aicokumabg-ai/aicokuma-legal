"""
Playwright browser session management.
- Opens a persistent context so cookies survive restarts.
- Headless=False recommended to avoid bot detection.
"""
import os
from playwright.async_api import (
    async_playwright,
    BrowserContext,
    Page,
    Playwright,
)
from bot.config import config
from bot.utils.logger import get_logger

logger = get_logger(__name__)

_playwright: Playwright | None = None
_context: BrowserContext | None = None


async def get_context() -> BrowserContext:
    global _playwright, _context
    if _context is not None:
        return _context

    os.makedirs(config.session_dir, exist_ok=True)
    _playwright = await async_playwright().start()
    _context = await _playwright.chromium.launch_persistent_context(
        user_data_dir=config.session_dir,
        headless=config.browser_headless,
        viewport={"width": 1366, "height": 768},
        locale="ko-KR",
        timezone_id="Asia/Seoul",
        user_agent=(
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/124.0.0.0 Safari/537.36"
        ),
        args=[
            "--disable-blink-features=AutomationControlled",
            "--no-first-run",
            "--no-sandbox",
        ],
    )
    # 자동화 탐지 스크립트 제거
    await _context.add_init_script(
        "Object.defineProperty(navigator, 'webdriver', {get: () => undefined})"
    )
    logger.info("Browser context started (headless=%s)", config.browser_headless)
    return _context


async def new_page() -> Page:
    ctx = await get_context()
    page = await ctx.new_page()
    return page


async def close_browser() -> None:
    global _playwright, _context
    if _context:
        await _context.close()
        _context = None
    if _playwright:
        await _playwright.stop()
        _playwright = None
    logger.info("Browser closed")
