"""
Chrome 브라우저 연결 관리.

연결 우선순위:
  1. CDP (기존 Chrome에 원격 디버깅으로 연결) ← 권장
  2. 기존 Chrome 프로필 경로 사용 (Chrome 꺼진 상태에서)
  3. 새 브라우저 + 자체 세션 (fallback)

환경변수:
  CHROME_DEBUG_PORT    기본 9222  → Chrome에 --remote-debugging-port=9222 필요
  CHROME_USER_DATA_DIR             → 기존 Chrome 프로필 경로
  CHROME_PROFILE       기본 Default
"""
import os
import asyncio
import httpx
from playwright.async_api import (
    async_playwright,
    Browser,
    BrowserContext,
    Page,
    Playwright,
)
from bot.config import config
from bot.utils.logger import get_logger

logger = get_logger(__name__)

_playwright: Playwright | None = None
_browser: Browser | None = None
_context: BrowserContext | None = None
_connection_mode: str = "none"   # "cdp" | "profile" | "new"


# ─── 연결 방법 1: CDP (기존 Chrome에 붙기) ──────────────────────────────────

async def _try_cdp_connect() -> BrowserContext | None:
    """
    이미 실행 중인 Chrome에 CDP로 연결한다.
    Chrome이 --remote-debugging-port=9222 로 시작되어 있어야 한다.
    """
    global _playwright, _browser, _connection_mode

    url = f"http://localhost:{config.chrome_debug_port}"
    try:
        async with httpx.AsyncClient(timeout=3) as client:
            resp = await client.get(f"{url}/json/version")
            resp.raise_for_status()
            info = resp.json()
            logger.info(
                "CDP 연결 가능: %s (Chrome %s)",
                info.get("Browser", "?"),
                info.get("webSocketDebuggerUrl", "")[:40],
            )
    except Exception as e:
        logger.debug("CDP 연결 불가 (Chrome이 디버그 모드로 실행 중이 아님): %s", e)
        return None

    _playwright = await async_playwright().start()
    _browser = await _playwright.chromium.connect_over_cdp(
        f"http://localhost:{config.chrome_debug_port}"
    )

    # 기존 컨텍스트(이미 열린 TikTok 세션) 재사용
    contexts = _browser.contexts
    if contexts:
        ctx = contexts[0]
        logger.info("기존 Chrome 컨텍스트 재사용 (탭 수: %d)", len(ctx.pages))
    else:
        ctx = await _browser.new_context()
        logger.info("CDP 연결 성공 — 새 컨텍스트 생성")

    await _inject_stealth(ctx)
    _connection_mode = "cdp"
    return ctx


# ─── 연결 방법 2: 기존 Chrome 프로필 경로 ──────────────────────────────────

async def _try_profile_connect() -> BrowserContext | None:
    """
    CHROME_USER_DATA_DIR 에 지정된 실제 Chrome 프로필로 브라우저를 연다.
    Chrome이 완전히 종료된 상태에서만 동작한다.
    """
    global _playwright, _connection_mode

    udd = config.chrome_user_data_dir
    if not udd or not os.path.exists(udd):
        return None

    logger.info("기존 Chrome 프로필 사용: %s (profile=%s)", udd, config.chrome_profile)
    _playwright = await async_playwright().start()

    # 실제 Chrome 바이너리 경로 탐색
    chrome_exe = _find_chrome_executable()

    ctx = await _playwright.chromium.launch_persistent_context(
        user_data_dir=udd,
        executable_path=chrome_exe,   # None이면 Playwright 번들 Chromium 사용
        headless=False,
        channel="chrome" if not chrome_exe else None,
        args=[
            f"--profile-directory={config.chrome_profile}",
            "--disable-blink-features=AutomationControlled",
            "--no-first-run",
            "--no-sandbox",
        ],
        viewport=None,   # 기존 창 크기 유지
        locale="ko-KR",
        timezone_id="Asia/Seoul",
    )
    await _inject_stealth(ctx)
    _connection_mode = "profile"
    logger.info("기존 Chrome 프로필로 시작됨")
    return ctx


# ─── 연결 방법 3: 새 브라우저 (fallback) ────────────────────────────────────

async def _launch_new_browser() -> BrowserContext:
    """자체 세션 디렉토리로 새 Chromium 브라우저를 시작한다."""
    global _playwright, _connection_mode

    os.makedirs(config.session_dir, exist_ok=True)
    _playwright = await async_playwright().start()
    ctx = await _playwright.chromium.launch_persistent_context(
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
    await _inject_stealth(ctx)
    _connection_mode = "new"
    logger.info("새 Chromium 브라우저 시작 (headless=%s)", config.browser_headless)
    return ctx


# ─── 공통 ────────────────────────────────────────────────────────────────────

async def _inject_stealth(ctx: BrowserContext) -> None:
    """webdriver 속성 제거로 자동화 탐지 방지."""
    await ctx.add_init_script(
        "Object.defineProperty(navigator, 'webdriver', {get: () => undefined})"
    )


async def get_context() -> BrowserContext:
    global _context
    if _context is not None:
        return _context

    # 1순위: CDP
    _context = await _try_cdp_connect()
    if _context:
        return _context

    # 2순위: 기존 Chrome 프로필
    _context = await _try_profile_connect()
    if _context:
        return _context

    # 3순위: 새 브라우저
    _context = await _launch_new_browser()
    return _context


async def new_page() -> Page:
    """TikTok 전용 새 탭을 연다."""
    ctx = await get_context()
    page = await ctx.new_page()
    logger.debug("새 탭 열림 (연결방식: %s)", _connection_mode)
    return page


def connection_mode() -> str:
    return _connection_mode


async def close_browser() -> None:
    global _playwright, _browser, _context
    # CDP 모드에서는 Chrome을 닫지 않고 연결만 해제
    if _connection_mode == "cdp":
        if _browser:
            await _browser.close()   # disconnect only, Chrome keeps running
            _browser = None
    else:
        if _context:
            await _context.close()
            _context = None

    if _playwright:
        await _playwright.stop()
        _playwright = None

    _context = None
    logger.info("브라우저 연결 해제 (모드: %s)", _connection_mode)


def _find_chrome_executable() -> str | None:
    """OS별 Chrome 실행파일 경로 탐색."""
    candidates = [
        # Windows
        r"C:\Program Files\Google\Chrome\Application\chrome.exe",
        r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
        # Mac
        "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
        # Linux
        "/usr/bin/google-chrome",
        "/usr/bin/chromium-browser",
        "/usr/bin/chromium",
        "/snap/bin/chromium",
    ]
    for path in candidates:
        if os.path.exists(path):
            return path
    return None
