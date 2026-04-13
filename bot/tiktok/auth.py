"""
TikTok 로그인 상태 확인 및 세션 보장.

CDP 모드에서는 이미 로그인된 Chrome을 사용하므로
세션 체크만 수행한다.
"""
import asyncio
from playwright.async_api import Page
from bot.config import config
from bot.tiktok.browser import new_page, connection_mode
from bot.utils.logger import get_logger

logger = get_logger(__name__)

FORYOU_URL = "https://www.tiktok.com/foryou"
LOGIN_URL  = "https://www.tiktok.com/login/phone-or-email/email"


async def is_logged_in(page: Page) -> bool:
    """현재 페이지 또는 TikTok 홈에서 로그인 여부 확인."""
    try:
        # 현재 URL이 이미 TikTok이면 프로필 아이콘 바로 확인
        if "tiktok.com" in page.url:
            try:
                await page.wait_for_selector('[data-e2e="profile-icon"]', timeout=5000)
                return True
            except Exception:
                pass

        await page.goto(FORYOU_URL, wait_until="domcontentloaded", timeout=20000)
        await asyncio.sleep(2)
        await page.wait_for_selector('[data-e2e="profile-icon"]', timeout=8000)
        return True
    except Exception:
        return False


async def ensure_logged_in() -> Page:
    """
    로그인된 TikTok 페이지를 반환한다.

    CDP 모드: 기존 Chrome에서 이미 열린 TikTok 탭을 재사용하거나
              새 탭을 열어 세션을 확인한다.
    프로필/새 브라우저 모드: 세션 쿠키 확인 후 필요 시 수동 로그인 안내.
    """
    mode = connection_mode()

    # ── CDP 모드: 기존 Chrome의 TikTok 탭 우선 재사용 ──────────────────────
    if mode == "cdp":
        from bot.tiktok.browser import get_context
        ctx = await get_context()

        # 이미 TikTok이 열린 탭 찾기
        for pg in ctx.pages:
            if "tiktok.com" in pg.url:
                try:
                    await pg.bring_to_front()
                    if await is_logged_in(pg):
                        logger.info("CDP: 기존 TikTok 탭 재사용 (%s)", pg.url[:60])
                        return pg
                except Exception:
                    pass

        # 없으면 새 탭에서 TikTok 열기
        page = await new_page()
        if await is_logged_in(page):
            logger.info("CDP: 새 탭에서 기존 TikTok 세션 확인됨")
            return page

        # 로그아웃 상태 — 로그인 페이지로 안내
        logger.warning("CDP 모드인데 TikTok 로그아웃 상태입니다. Chrome에서 수동 로그인하세요.")
        await page.goto(LOGIN_URL, wait_until="domcontentloaded")
        await _wait_manual_login(page)
        return page

    # ── 프로필/새 브라우저 모드 ──────────────────────────────────────────────
    page = await new_page()

    if await is_logged_in(page):
        logger.info("기존 세션 쿠키로 로그인 확인 (모드: %s)", mode)
        return page

    # 자격증명 자동 로그인 시도
    if config.tiktok_username and config.tiktok_password:
        if await _auto_login(page):
            return page

    # 수동 로그인 대기
    await page.goto(LOGIN_URL, wait_until="domcontentloaded")
    await _notify_manual_login()
    await _wait_manual_login(page)
    return page


async def _auto_login(page: Page) -> bool:
    """이메일/비밀번호로 자동 로그인."""
    import random
    logger.info("자동 로그인 시도: %s", config.tiktok_username)
    await page.goto(LOGIN_URL, wait_until="domcontentloaded")
    await asyncio.sleep(2)
    for char in config.tiktok_username:
        await page.type('input[name="username"]', char, delay=random.randint(60, 160))
    await asyncio.sleep(0.5)
    for char in config.tiktok_password:
        await page.type('input[type="password"]', char, delay=random.randint(60, 160))
    await asyncio.sleep(1)
    await page.click('button[type="submit"]')
    await asyncio.sleep(5)
    result = await is_logged_in(page)
    logger.info("자동 로그인 %s", "성공" if result else "실패")
    return result


async def _notify_manual_login() -> None:
    """텔레그램으로 수동 로그인 안내 (import 순환 방지를 위해 지연 import)."""
    try:
        from bot.telegram.notifier import notify
        await notify(
            "🔐 TikTok 로그인 필요\n\n"
            "브라우저에서 TikTok에 로그인해 주세요.\n"
            "로그인 완료 후 봇이 자동으로 시작됩니다. (5분 내)"
        )
    except Exception:
        pass


async def _wait_manual_login(page: Page, timeout: int = 300) -> None:
    """로그인될 때까지 최대 timeout초 대기."""
    logger.info("수동 로그인 대기 중... (최대 %d초)", timeout)
    deadline = asyncio.get_event_loop().time() + timeout
    while asyncio.get_event_loop().time() < deadline:
        try:
            await page.wait_for_selector('[data-e2e="profile-icon"]', timeout=5000)
            logger.info("수동 로그인 감지됨!")
            try:
                from bot.telegram.notifier import notify
                await notify("✅ TikTok 로그인 완료! 봇이 시작됩니다.")
            except Exception:
                pass
            return
        except Exception:
            await asyncio.sleep(3)
    raise RuntimeError("TikTok 수동 로그인 시간 초과 (5분)")
