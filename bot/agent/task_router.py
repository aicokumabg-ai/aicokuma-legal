"""
파싱된 명령을 실제 DB 작업으로 라우팅.
"""
from bot.config import config
from bot.database.db import get_connection
from bot.database import models
from bot.tiktok.monitor import extract_video_id
from bot.utils.logger import get_logger

logger = get_logger(__name__)


async def route(command: dict) -> str:
    """
    command dict를 받아 실행하고 텔레그램에 보낼 응답 문자열을 반환한다.
    """
    action = command.get("action", "unknown")

    if action == "add_post":
        return await _add_post(command)
    elif action == "add_rule":
        return await _add_rule(command)
    elif action == "add_rules_batch":
        return await _add_rules_batch(command)
    elif action == "status":
        return await _status()
    elif action == "pause":
        return await _set_active(command, False)
    elif action == "resume":
        return await _set_active(command, True)
    elif action == "set_delay":
        return _set_delay(command)
    elif action == "list_rules":
        return await _list_rules(command)
    elif action == "help":
        return _help_text()
    elif action == "unknown":
        return "❓ 명령을 이해하지 못했어요. 예: '이 영상 모니터링 해줘: [URL]'"
    else:
        return f"⚠️ 처리 중 오류: {command.get('message', '')}"


# ── 라우터 구현 ───────────────────────────────────────────────────────────────

async def _add_post(cmd: dict) -> str:
    url = cmd.get("url", "").strip()
    if not url:
        return "❌ URL이 필요합니다."
    video_id = extract_video_id(url)
    if not video_id:
        return "❌ 유효한 TikTok 영상 URL을 입력해주세요."

    conn = get_connection()
    try:
        post_id = models.add_post(conn, url, video_id)
        return f"✅ 게시글 모니터링 등록 완료!\n🎬 video_id: {video_id}\n📋 post_id: {post_id}"
    finally:
        conn.close()


async def _add_rule(cmd: dict) -> str:
    url = cmd.get("url", "").strip()
    keyword = cmd.get("keyword", "").strip()
    reply_text = cmd.get("reply_text", "").strip()
    dm_text = cmd.get("dm_text") or None

    if not keyword or not reply_text:
        return "❌ keyword와 reply_text가 필요합니다."

    conn = get_connection()
    try:
        if url and url != "all":
            video_id = extract_video_id(url)
            post = conn.execute(
                "SELECT id FROM monitored_posts WHERE video_id = ?", (video_id,)
            ).fetchone()
            if not post:
                return f"❌ 먼저 해당 URL을 모니터링 등록해주세요."
            post_id = post["id"]
            models.add_rule(conn, post_id, keyword, reply_text, dm_text)
            return (
                f"✅ 규칙 추가!\n"
                f"🔑 키워드: {keyword}\n"
                f"💬 대댓글: {reply_text}\n"
                f"📩 DM: {dm_text or '없음'}"
            )
        else:
            # 전체 게시글에 규칙 추가
            posts = models.get_active_posts(conn)
            for p in posts:
                models.add_rule(conn, p["id"], keyword, reply_text, dm_text)
            return f"✅ 모든 게시글에 규칙 추가 완료 (키워드: {keyword})"
    finally:
        conn.close()


async def _add_rules_batch(cmd: dict) -> str:
    url = cmd.get("url", "").strip()
    rules = cmd.get("rules", [])
    if not rules:
        return "❌ 규칙이 없습니다."

    video_id = extract_video_id(url) if url and url != "all" else None
    conn = get_connection()
    try:
        if video_id:
            post = conn.execute(
                "SELECT id FROM monitored_posts WHERE video_id = ?", (video_id,)
            ).fetchone()
            if not post:
                return "❌ 먼저 해당 URL을 모니터링 등록해주세요."
            post_ids = [post["id"]]
        else:
            post_ids = [p["id"] for p in models.get_active_posts(conn)]

        added = 0
        for post_id in post_ids:
            for rule in rules:
                models.add_rule(
                    conn, post_id,
                    rule.get("keyword", ""),
                    rule.get("reply_text", ""),
                    rule.get("dm_text"),
                )
                added += 1

        return f"✅ 규칙 {added}개 일괄 추가 완료!"
    finally:
        conn.close()


async def _status() -> str:
    conn = get_connection()
    try:
        posts = conn.execute("SELECT * FROM monitored_posts").fetchall()
        if not posts:
            return "📭 모니터링 중인 게시글이 없습니다."

        lines = ["📊 현재 상태\n"]
        for p in posts:
            status = "🟢 활성" if p["active"] else "🔴 중지"
            rule_count = conn.execute(
                "SELECT COUNT(*) as c FROM keyword_rules WHERE post_id = ? AND active = 1",
                (p["id"],),
            ).fetchone()["c"]
            processed = conn.execute(
                "SELECT COUNT(*) as c FROM processed_comments WHERE post_id = ?",
                (p["id"],),
            ).fetchone()["c"]
            lines.append(
                f"{status} [{p['id']}] {p['url'][-40:]}\n"
                f"   규칙: {rule_count}개 | 처리됨: {processed}개\n"
            )

        pending_q = conn.execute(
            "SELECT COUNT(*) as c FROM action_queue WHERE status='pending'"
        ).fetchone()["c"]
        lines.append(f"\n⏳ 대기 중인 액션: {pending_q}개")
        return "\n".join(lines)
    finally:
        conn.close()


async def _set_active(cmd: dict, active: bool) -> str:
    url = cmd.get("url", "").strip()
    conn = get_connection()
    try:
        if url and url != "all":
            video_id = extract_video_id(url)
            post = conn.execute(
                "SELECT id FROM monitored_posts WHERE video_id = ?", (video_id,)
            ).fetchone()
            if not post:
                return "❌ 해당 게시글을 찾을 수 없습니다."
            models.set_post_active(conn, post["id"], active)
        else:
            posts = conn.execute("SELECT id FROM monitored_posts").fetchall()
            for p in posts:
                models.set_post_active(conn, p["id"], active)

        state = "재개" if active else "일시정지"
        return f"{'▶️' if active else '⏸️'} 모니터링 {state} 완료"
    finally:
        conn.close()


def _set_delay(cmd: dict) -> str:
    if "reply_min" in cmd:
        config.reply_delay_min = int(cmd["reply_min"])
    if "reply_max" in cmd:
        config.reply_delay_max = int(cmd["reply_max"])
    if "dm_min" in cmd:
        config.dm_delay_min = int(cmd["dm_min"])
    if "dm_max" in cmd:
        config.dm_delay_max = int(cmd["dm_max"])
    return (
        f"⏱️ 딜레이 설정 업데이트\n"
        f"대댓글: {config.reply_delay_min}~{config.reply_delay_max}초\n"
        f"DM: {config.dm_delay_min}~{config.dm_delay_max}초"
    )


async def _list_rules(cmd: dict) -> str:
    url = cmd.get("url", "").strip()
    conn = get_connection()
    try:
        if url and url != "all":
            video_id = extract_video_id(url)
            post = conn.execute(
                "SELECT id FROM monitored_posts WHERE video_id = ?", (video_id,)
            ).fetchone()
            if not post:
                return "❌ 해당 게시글을 찾을 수 없습니다."
            rules = conn.execute(
                "SELECT * FROM keyword_rules WHERE post_id = ? AND active = 1", (post["id"],)
            ).fetchall()
        else:
            rules = conn.execute(
                "SELECT * FROM keyword_rules WHERE active = 1"
            ).fetchall()

        if not rules:
            return "📭 등록된 규칙이 없습니다."

        lines = [f"📋 활성 규칙 {len(rules)}개\n"]
        for r in rules:
            lines.append(
                f"[{r['id']}] 키워드: {r['keyword']}\n"
                f"   대댓글: {r['reply_text'][:40]}...\n"
                f"   DM: {'있음' if r['dm_text'] else '없음'}\n"
            )
        return "\n".join(lines)
    finally:
        conn.close()


def _help_text() -> str:
    return """🤖 aicokuma TikTok 봇 도움말

📌 게시글 등록:
"이 영상 모니터링 해줘: [URL]"

🔑 키워드 규칙 추가:
"'가격' 댓글에 '링크인바이오 확인!' 대댓글 달고, DM으로 '안녕하세요...' 보내줘"

📊 상태 확인:
"현재 상태 보여줘"

⏸️ 일시정지:
"모니터링 잠깐 멈춰줘"

▶️ 재개:
"모니터링 다시 시작해줘"

📋 규칙 목록:
"등록된 규칙 보여줘"

⏱️ 딜레이 설정:
"대댓글 딜레이 1분~5분으로 설정해줘"
"""
