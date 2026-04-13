"""
TikTok DM(Direct Message) 발송 모듈.
유저 프로필 페이지의 Message 버튼을 통해 DM을 발송한다.
"""
import asyncio
from playwright.async_api import Page
from bot.anti_bot.typer import type_text
from bot.anti_bot.human_mouse import move_to_element
from bot.utils.logger import get_logger

logger = get_logger(__name__)


async def send_dm(
    page: Page,
    username: str,
    user_profile_url: str,
    dm_text: str,
) -> bool:
    """
    username 에게 DM을 발송한다.
    Returns True on success.
    """
    logger.info("Sending DM to @%s", username)

    # 유저 프로필 페이지로 이동
    await page.goto(user_profile_url, wait_until="domcontentloaded")
    await asyncio.sleep(3)

    # Message 버튼 찾기
    message_btn = page.locator('[data-e2e="message-btn"]')
    try:
        await message_btn.wait_for(timeout=10000)
    except Exception:
        # 일부 계정은 DM 비활성화
        logger.warning("Message button not found for @%s — DM may be disabled", username)
        return False

    await move_to_element(page, message_btn)
    await asyncio.sleep(0.6)
    await message_btn.click()
    await asyncio.sleep(2)

    # DM 입력창
    dm_input = page.locator('[data-e2e="message-input"]')
    try:
        await dm_input.wait_for(timeout=8000)
    except Exception:
        logger.error("DM input box not found for @%s", username)
        return False

    await dm_input.click()
    await asyncio.sleep(0.5)
    await type_text(page, '[data-e2e="message-input"]', dm_text)
    await asyncio.sleep(1)

    # 전송
    send_btn = page.locator('[data-e2e="message-send-btn"]')
    await move_to_element(page, send_btn)
    await asyncio.sleep(0.4)
    await send_btn.click()
    await asyncio.sleep(2)

    logger.info("DM sent to @%s", username)
    return True
