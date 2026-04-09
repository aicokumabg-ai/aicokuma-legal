"""
aicokuma TikTok 자동화 봇 진입점.

실행되는 루프:
  - Telegram polling (봇 명령 수신)
  - monitor_loop (TikTok 게시글 댓글 폴링)
  - executor_loop (action_queue 처리)
"""
import asyncio
import sys
from bot.config import config
from bot.database.db import init_db
from bot.telegram.handler import build_application
from bot.queue.worker import monitor_loop, executor_loop
from bot.tiktok.browser import close_browser
from bot.utils.logger import get_logger

logger = get_logger(__name__)


async def main() -> None:
    # 설정 유효성 검사
    if not config.telegram_bot_token:
        logger.error("TELEGRAM_BOT_TOKEN이 설정되지 않았습니다.")
        sys.exit(1)
    if not config.telegram_allowed_users:
        logger.error("TELEGRAM_ALLOWED_USERS가 설정되지 않았습니다.")
        sys.exit(1)

    # DB 초기화
    init_db()

    # 텔레그램 앱 빌드
    tg_app = build_application()

    logger.info("aicokuma bot starting...")

    # 텔레그램 polling, 모니터 루프, 실행 루프를 동시에 실행
    async with tg_app:
        await tg_app.initialize()
        await tg_app.start()
        await tg_app.updater.start_polling(drop_pending_updates=True)
        logger.info("Telegram bot polling started")

        try:
            await asyncio.gather(
                monitor_loop(),
                executor_loop(),
            )
        except asyncio.CancelledError:
            logger.info("Shutdown signal received")
        finally:
            await tg_app.updater.stop()
            await tg_app.stop()
            await close_browser()
            logger.info("Bot stopped cleanly")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Interrupted by user")
