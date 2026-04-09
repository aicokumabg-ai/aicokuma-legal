"""
TikTok login and session verification.
Uses saved cookies when available; falls back to username/password login.
"""
import asyncio
from playwright.async_api import Page
from bot.config import config
from bot.tiktok.browser import new_page
from bot.utils.logger import get_logger

logger = get_logger(__name__)

LOGIN_URL = "https://www.tiktok.com/login/phone-or-email/email"
PROFILE_URL = "https://www.tiktok.com/foryou"


async def is_logged_in(page: Page) -> bool:
    """쿠키 기반 세션 유효성 확인."""
    await page.goto(PROFILE_URL, wait_until="domcontentloaded")
    await asyncio.sleep(3)
    # 로그인된 상태면 프로필 아바타가 존재
    try:
        await page.wait_for_selector('[data-e2e="profile-icon"]', timeout=8000)
        return True
    except Exception:
        return False


async def login_with_credentials(page: Page) -> bool:
    """
    이메일/비밀번호로 로그인.
    성공 시 True, 실패 시 False.
    """
    logger.info("Attempting TikTok login for %s", config.tiktok_username)
    await page.goto(LOGIN_URL, wait_until="domcontentloaded")
    await asyncio.sleep(2)

    # 이메일 입력
    email_input = page.locator('input[name="username"]')
    await email_input.click()
    await _type_humanlike(page, 'input[name="username"]', config.tiktok_username)
    await asyncio.sleep(0.5)

    # 비밀번호 입력
    pass_input = page.locator('input[type="password"]')
    await pass_input.click()
    await _type_humanlike(page, 'input[type="password"]', config.tiktok_password)
    await asyncio.sleep(1)

    # 로그인 버튼 클릭
    await page.click('button[type="submit"]')
    await asyncio.sleep(5)

    logged_in = await is_logged_in(page)
    if logged_in:
        logger.info("Login successful")
    else:
        logger.error("Login failed — check credentials or solve CAPTCHA manually")
    return logged_in


async def ensure_logged_in() -> Page:
    """
    유효한 세션 페이지를 반환한다.
    쿠키 세션이 있으면 재사용, 없으면 로그인 시도.
    """
    page = await new_page()
    if await is_logged_in(page):
        logger.info("Reused existing TikTok session")
        return page

    success = await login_with_credentials(page)
    if not success:
        raise RuntimeError(
            "TikTok 로그인 실패. 수동으로 로그인하거나 환경변수를 확인하세요."
        )
    return page


async def _type_humanlike(page: Page, selector: str, text: str) -> None:
    """느리고 자연스러운 타이핑 (anti-bot/typer 모듈 로딩 전 부트스트랩용)."""
    import random
    for char in text:
        await page.type(selector, char, delay=random.randint(60, 180))
