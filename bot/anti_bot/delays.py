"""
랜덤 딜레이 생성기.
Beta 분포를 사용해 범위 내에서 자연스럽게 분포되는 대기 시간을 반환한다.
"""
import asyncio
import random
import math
from bot.config import config
from bot.utils.logger import get_logger

logger = get_logger(__name__)


def _beta_sample(min_sec: float, max_sec: float, alpha: float = 2.0, beta: float = 3.0) -> float:
    """
    Beta(alpha, beta) 분포를 [min_sec, max_sec] 범위로 스케일링.
    기본값(2,3)은 중간보다 약간 낮은 값에 집중되는 분포 → 사람처럼 느낌.
    """
    raw = random.betavariate(alpha, beta)
    return min_sec + raw * (max_sec - min_sec)


async def reply_delay() -> None:
    """댓글 감지 후 대댓글 작성 전 대기."""
    secs = _beta_sample(config.reply_delay_min, config.reply_delay_max)
    logger.info("Reply delay: %.1f seconds", secs)
    await asyncio.sleep(secs)


async def dm_delay() -> None:
    """대댓글 작성 후 DM 발송 전 대기."""
    secs = _beta_sample(config.dm_delay_min, config.dm_delay_max)
    logger.info("DM delay: %.1f seconds", secs)
    await asyncio.sleep(secs)


async def poll_delay() -> None:
    """폴링 사이클 간 대기."""
    secs = _beta_sample(config.poll_interval_min, config.poll_interval_max)
    logger.info("Next poll in: %.0f seconds", secs)
    await asyncio.sleep(secs)


async def action_gap() -> None:
    """
    연속 액션 사이의 짧은 자연스러운 휴식 (클릭-타이핑 사이 등).
    0.5~2.5초.
    """
    secs = random.uniform(0.5, 2.5)
    await asyncio.sleep(secs)


def jitter(base_seconds: float, pct: float = 0.3) -> float:
    """base ± pct% 범위 내 랜덤 값을 반환 (동기)."""
    delta = base_seconds * pct
    return random.uniform(base_seconds - delta, base_seconds + delta)
