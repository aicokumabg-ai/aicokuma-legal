"""
Ollama(로컬 LLM)를 사용하여 텔레그램 자연어 메시지를 구조화된 명령으로 파싱.
"""
import json
import httpx
from bot.config import config
from bot.utils.logger import get_logger

logger = get_logger(__name__)

SYSTEM_PROMPT = """당신은 TikTok 자동화 봇의 명령 파서입니다.
사용자의 자연어 메시지를 분석하여 정확히 아래 JSON 형식 중 하나로만 응답하세요.
설명 없이 JSON만 출력하세요.

가능한 액션:
1. 게시글 모니터링 추가:
{"action": "add_post", "url": "https://www.tiktok.com/@user/video/123"}

2. 키워드 규칙 추가:
{"action": "add_rule", "url": "게시글URL또는all", "keyword": "키워드", "reply_text": "대댓글내용", "dm_text": "DM내용 또는 null"}

3. 전체 상태 조회:
{"action": "status"}

4. 모니터링 일시정지:
{"action": "pause", "url": "게시글URL또는all"}

5. 모니터링 재개:
{"action": "resume", "url": "게시글URL또는all"}

6. 딜레이 설정:
{"action": "set_delay", "reply_min": 30, "reply_max": 300, "dm_min": 60, "dm_max": 180}

7. 규칙 목록 조회:
{"action": "list_rules", "url": "게시글URL또는all"}

8. 도움말:
{"action": "help"}

사용자가 여러 키워드를 한 번에 추가하면 각각을 별도 규칙으로 배열에 담아 반환:
{"action": "add_rules_batch", "url": "게시글URL", "rules": [{"keyword": "...", "reply_text": "...", "dm_text": "..."}, ...]}

파악 불가 메시지:
{"action": "unknown", "message": "원본메시지"}
"""


async def parse_command(user_message: str) -> dict:
    """
    자연어 메시지를 Ollama로 파싱하여 dict로 반환한다.
    Ollama가 응답 불가 시 {"action": "unknown"} 반환.
    """
    payload = {
        "model": config.ollama_model,
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user_message},
        ],
        "stream": False,
        "format": "json",
    }

    try:
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.post(
                f"{config.ollama_base_url}/api/chat",
                json=payload,
            )
            resp.raise_for_status()
            data = resp.json()
            content = data["message"]["content"]
            parsed = json.loads(content)
            logger.info("LLM parsed: %s → %s", user_message[:60], parsed.get("action"))
            return parsed
    except json.JSONDecodeError as e:
        logger.warning("LLM returned invalid JSON: %s", e)
        return {"action": "unknown", "message": user_message}
    except Exception as e:
        logger.error("Ollama request failed: %s", e)
        return {"action": "error", "message": str(e)}
