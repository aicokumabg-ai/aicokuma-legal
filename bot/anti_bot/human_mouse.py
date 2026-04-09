"""
자연스러운 마우스 이동 시뮬레이션.
베지어 곡선을 사용해 요소까지 부드럽게 이동한다.
"""
import asyncio
import random
import math
from typing import Union
from playwright.async_api import Page, ElementHandle, Locator


def _bezier_point(t: float, p0, p1, p2, p3) -> tuple[float, float]:
    """3차 베지어 곡선 위의 점 계산."""
    x = (
        (1 - t) ** 3 * p0[0]
        + 3 * (1 - t) ** 2 * t * p1[0]
        + 3 * (1 - t) * t ** 2 * p2[0]
        + t ** 3 * p3[0]
    )
    y = (
        (1 - t) ** 3 * p0[1]
        + 3 * (1 - t) ** 2 * t * p1[1]
        + 3 * (1 - t) * t ** 2 * p2[1]
        + t ** 3 * p3[1]
    )
    return x, y


async def move_to_element(
    page: Page,
    element: Union[ElementHandle, Locator],
    steps: int = 20,
) -> None:
    """
    현재 마우스 위치에서 element 중앙으로 베지어 곡선을 따라 이동한다.
    """
    # 요소의 bounding box 가져오기
    if isinstance(element, Locator):
        box = await element.bounding_box()
    else:
        box = await element.bounding_box()

    if not box:
        return

    target_x = box["x"] + box["width"] / 2 + random.uniform(-5, 5)
    target_y = box["y"] + box["height"] / 2 + random.uniform(-3, 3)

    # 현재 위치 (알 수 없으면 화면 중앙 추정)
    viewport = page.viewport_size or {"width": 1366, "height": 768}
    start_x = random.uniform(viewport["width"] * 0.2, viewport["width"] * 0.8)
    start_y = random.uniform(viewport["height"] * 0.2, viewport["height"] * 0.8)

    # 제어점 랜덤 생성
    cp1 = (
        start_x + random.uniform(-100, 100),
        start_y + random.uniform(-80, 80),
    )
    cp2 = (
        target_x + random.uniform(-80, 80),
        target_y + random.uniform(-60, 60),
    )

    for i in range(steps + 1):
        t = i / steps
        px, py = _bezier_point(t, (start_x, start_y), cp1, cp2, (target_x, target_y))
        await page.mouse.move(px, py)
        # 가변 속도: 시작/끝이 느리고 중간이 빠름 (ease in-out)
        delay = 0.01 + 0.03 * math.sin(math.pi * t)
        await asyncio.sleep(delay)

    # 최종 위치에 정착 후 짧은 멈춤
    await asyncio.sleep(random.uniform(0.1, 0.4))


async def random_scroll(page: Page, direction: str = "down", amount: int = 300) -> None:
    """
    자연스러운 스크롤 (속도 변화 포함).
    """
    steps = random.randint(3, 8)
    per_step = amount // steps
    for _ in range(steps):
        delta = per_step + random.randint(-20, 20)
        if direction == "up":
            delta = -delta
        await page.mouse.wheel(0, delta)
        await asyncio.sleep(random.uniform(0.1, 0.4))
