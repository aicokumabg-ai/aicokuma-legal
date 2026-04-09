"""
TikTok login and session verification.
Priority:
  1. Existing cookies (persistent context) → reuse
  2. Username + password (env) → auto login
  3. Manual login → open browser, wait up to 5 minutes for user
"""
import asyncio
from playwright.async_api import Page
from bot.config import config
from bot.tiktok.browser import new_page
from bot.telegram.notifier import notify
from bot.utils.logger import get_logger

logger = get_logger(__name__)

LOGIN_URL = "https://www.tiktok.com/login/phone-or-email/email"
PROFILE_URL = "https://www.tiktok.com/foryou"
MANUAL_LOGIN_TIMEOUT = 300  # 5분


async def is_logged_in(page: Page) -> bool:
    """쿠키 기반 세션 유효성 확인."""
    try:
        await page.goto(PROFILE_URL, wait_until="domcontentloaded", timeout=20000)
        await asyncio.sleep(3)
        await page.wait_for_selector('[data-e2e="profile-icon"]', timeout=8000)
        return True
    except Exception:
        return False


async def login_with_credentials(page: Page) -> bool:
    """이메일/비밀번호 자동 로그인."""
    logger.info("Attempting TikTok login for %s", config.tiktok_username)
    await page.goto(LOGIN_URL, wait_until="domcontentloaded")
    await asyncio.sleep(2)

    await _type_humanlike(page, 'input[name="username"]', config.tiktok_username)
    await asyncio.sleep(0.5)
    await _type_humanlike(page, 'input[type="password"]', config.tiktok_password)
    await asyncio.sleep(1)
    await page.click('button[type="submit"]')
    await asyncio.sleep(5)

    logged_in = await is_logged_in(page)
    if logged_in:
        logger.info("Auto login successful")
    else:
        logger.error("Auto login failed")
    return logged_in


async def wait_for_manual_login(page: Page) -> bool:
    """
    브라우저를 TikTok 로그인 페이지로 열고 사용자가 직접 로그인할 때까지 대기.
    텔레그램으로 안내 메시지 발송.
    """
    logger.info("Opening TikTok login page for manual login...")
    await page.goto(LOGIN_URL, wait_until="domcontentloaded")

    await notify(
        "🔐 TikTok 로그인 필요\n\n"
        "서버에서 TikTok 브라우저가 열렸습니다.\n"
        "직접 로그인해주세요 (5분 내).\n"
        "로그인 완료 후 봇이 자동으로 시작됩니다."
    )
    logger.info("Waiting up to %ds for manual TikTok login...", MANUAL_LOGIN_TIMEOUT)

    deadline = asyncio.get_event_loop().time() + MANUAL_LOGIN_TIMEOUT
    while asyncio.get_event_loop().time() < deadline:
        try:
            await page.wait_for_selector('[data-e2e="profile-icon"]', timeout=5000)
            logger.info("Manual login detected!")
            await notify("✅ TikTok 로그인 완료! 봇이 시작됩니다.")
            return True
        except Exception:
            await asyncio.sleep(3)

    logger.error("Manual login timed out after %ds", MANUAL_LOGIN_TIMEOUT)
    await notify("❌ TikTok 로그인 시간 초과. /login 명령으로 다시 시도해주세요.")
    return False


async def ensure_logged_in() -> Page:
    """
    유효한 TikTok 세션 페이지를 반환한다.
    """
    page = await new_page()

    # 1) 기존 세션 쿠키 재사용
    if await is_logged_in(page):
        logger.info("Reused existing TikTok session")
        return page

    # 2) 자격증명 자동 로그인
    if config.tiktok_username and config.tiktok_password:
        if await login_with_credentials(page):
            return page

    # 3) 수동 로그인 대기
    success = await wait_for_manual_login(page)
    if not success:
        raise RuntimeError("TikTok 로그인 실패 (수동 로그인 시간 초과)")
    return page


async def _type_humanlike(page: Page, selector: str, text: str) -> None:
    import random
    for char in text:
        await page.type(selector, char, delay=random.randint(60, 180))
