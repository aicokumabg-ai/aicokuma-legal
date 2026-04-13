"""
텔레그램 봇 핸들러.
수신된 자연어 메시지를 LLM으로 파싱하고 task_router로 실행한다.
"""
from telegram import Update
from telegram.ext import (
    Application,
    MessageHandler,
    ContextTypes,
    filters,
)
from bot.config import config
from bot.agent.llm_parser import parse_command
from bot.agent.task_router import route
from bot.utils.logger import get_logger

logger = get_logger(__name__)


def _is_allowed(user_id: int) -> bool:
    return user_id in config.telegram_allowed_users


async def message_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """모든 텍스트 메시지를 처리한다."""
    if not update.message or not update.effective_user:
        return

    user_id = update.effective_user.id
    if not _is_allowed(user_id):
        await update.message.reply_text("⛔ 접근 권한이 없습니다.")
        logger.warning("Unauthorized access attempt from user %d", user_id)
        return

    text = update.message.text or ""
    logger.info("Message from %d: %s", user_id, text[:80])

    # 처리 중 표시
    await update.message.reply_text("⏳ 처리 중...")

    # LLM 파싱
    command = await parse_command(text)
    # 라우팅 및 실행
    response = await route(command)

    await update.message.reply_text(response)


def build_application() -> Application:
    """Telegram Application 인스턴스를 생성하고 핸들러를 등록한다."""
    app = Application.builder().token(config.telegram_bot_token).build()
    app.add_handler(
        MessageHandler(filters.TEXT & ~filters.COMMAND, message_handler)
    )
    return app
