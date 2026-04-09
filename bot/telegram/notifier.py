"""
텔레그램 알림 발송 유틸리티.
봇이 실행되면 허용된 사용자 전체에게 알림을 보낸다.
"""
from telegram import Bot
from bot.config import config
from bot.utils.logger import get_logger

logger = get_logger(__name__)

_bot: Bot | None = None


def _get_bot() -> Bot:
    global _bot
    if _bot is None:
        _bot = Bot(token=config.telegram_bot_token)
    return _bot


async def notify(text: str) -> None:
    """모든 허용된 사용자에게 알림 발송."""
    bot = _get_bot()
    for user_id in config.telegram_allowed_users:
        try:
            await bot.send_message(chat_id=user_id, text=text)
        except Exception as e:
            logger.error("Failed to notify user %d: %s", user_id, e)
