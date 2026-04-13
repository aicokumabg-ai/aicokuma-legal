"""
aicokuma TikTok 자동화 봇 진입점.

실행 순서:
  1. DB 초기화
  2. 웹 대시보드 (FastAPI, :8080) — 즉시 시작
  3. 텔레그램 봇 polling — 즉시 시작 (TikTok 불필요)
  4. TikTok monitor/executor — 로그인 완료 후 시작
"""
import asyncio
import sys
import uvicorn
from bot.config import config
from bot.database.db import init_db
from bot.telegram.handler import build_application
from bot.queue.worker import monitor_loop, executor_loop
from bot.tiktok.browser import close_browser
from bot.web.app import app as web_app
from bot.utils.logger import get_logger

logger = get_logger(__name__)


async def run_tiktok_workers() -> None:
    """TikTok 로그인 이후 모니터/실행 루프를 구동한다."""
    try:
        await asyncio.gather(
            monitor_loop(),
            executor_loop(),
        )
    except Exception as e:
        logger.error("TikTok worker error: %s", e)


async def main() -> None:
    if not config.telegram_bot_token:
        logger.error("TELEGRAM_BOT_TOKEN이 설정되지 않았습니다.")
        sys.exit(1)
    if not config.telegram_allowed_users:
        logger.error("TELEGRAM_ALLOWED_USERS가 설정되지 않았습니다.")
        sys.exit(1)

    init_db()

    tg_app = build_application()

    web_server = uvicorn.Server(
        uvicorn.Config(web_app, host="0.0.0.0", port=8080, log_level="warning")
    )

    logger.info("aicokuma bot starting...")

    async with tg_app:
        await tg_app.initialize()
        await tg_app.start()
        await tg_app.updater.start_polling(drop_pending_updates=True)
        logger.info("✅ Telegram bot polling started")

        try:
            await asyncio.gather(
                web_server.serve(),          # 웹 대시보드
                run_tiktok_workers(),        # TikTok 자동화
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
