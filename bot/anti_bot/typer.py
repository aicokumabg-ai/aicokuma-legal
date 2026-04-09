"""
휴먼-라이크 타이핑 시뮬레이션.
- 문자별 랜덤 딜레이
- 가끔 오타 후 백스페이스 수정
- 붙여넣기 없이 항상 키 입력
"""
import asyncio
import random
from playwright.async_api import Page
from bot.utils.logger import get_logger

logger = get_logger(__name__)

# 오타 낼 확률 (0~1)
TYPO_PROBABILITY = 0.08
# 인접 키 오타 맵 (간단한 QWERTY 기반)
TYPO_MAP: dict[str, list[str]] = {
    "q": ["w", "a"], "w": ["q", "e", "s"], "e": ["w", "r", "d"],
    "r": ["e", "t", "f"], "t": ["r", "y", "g"], "y": ["t", "u", "h"],
    "u": ["y", "i", "j"], "i": ["u", "o", "k"], "o": ["i", "p", "l"],
    "a": ["q", "s", "z"], "s": ["a", "d", "w", "x"], "d": ["s", "f", "e", "c"],
    "f": ["d", "g", "r", "v"], "g": ["f", "h", "t", "b"], "h": ["g", "j", "y"],
    "j": ["h", "k", "u"], "k": ["j", "l", "i"], "l": ["k", "o"],
    "z": ["a", "x"], "x": ["z", "c", "s"], "c": ["x", "v", "d"],
    "v": ["c", "b", "f"], "b": ["v", "n", "g"], "n": ["b", "m", "h"],
    "m": ["n", "j"],
}


async def type_text(page: Page, selector: str, text: str) -> None:
    """
    selector에 해당하는 입력창에 text를 사람처럼 타이핑한다.
    """
    element = page.locator(selector).last
    await element.click()
    await asyncio.sleep(random.uniform(0.2, 0.6))

    for char in text:
        # 오타 삽입 여부 결정
        if (
            char.lower() in TYPO_MAP
            and random.random() < TYPO_PROBABILITY
        ):
            typo_char = random.choice(TYPO_MAP[char.lower()])
            await page.keyboard.type(typo_char, delay=_char_delay())
            await asyncio.sleep(random.uniform(0.15, 0.45))
            # 백스페이스로 수정
            await page.keyboard.press("Backspace")
            await asyncio.sleep(random.uniform(0.1, 0.3))

        await page.keyboard.type(char, delay=_char_delay())

        # 단어 끝(공백)에서 가끔 짧은 멈춤 (생각하는 척)
        if char == " " and random.random() < 0.2:
            await asyncio.sleep(random.uniform(0.3, 0.9))


def _char_delay() -> int:
    """문자 하나 타이핑 딜레이 (ms). 60~200ms 사이 정규분포."""
    return max(40, int(random.gauss(110, 35)))
