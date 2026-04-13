"""
FastAPI 웹 대시보드 — ManyChat 스타일 GUI.
REST API + Jinja2 HTML 템플릿.
"""
import json
from datetime import datetime, timezone
from typing import Optional
from fastapi import FastAPI, Request, Form, HTTPException
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pathlib import Path

from bot.config import config
from bot.database.db import get_connection
from bot.database import models as db_models
from bot.tiktok.monitor import extract_video_id
from bot.utils.logger import get_logger

logger = get_logger(__name__)

BASE_DIR = Path(__file__).parent
app = FastAPI(title="aicokuma Dashboard", docs_url=None, redoc_url=None)
app.mount("/static", StaticFiles(directory=str(BASE_DIR / "static")), name="static")
templates = Jinja2Templates(directory=str(BASE_DIR / "templates"))


# ─── Pages ────────────────────────────────────────────────────────────────────

@app.get("/", response_class=HTMLResponse)
async def dashboard(request: Request):
    conn = get_connection()
    posts = [dict(p) for p in conn.execute("SELECT * FROM monitored_posts ORDER BY created_at DESC").fetchall()]
    total_rules = conn.execute("SELECT COUNT(*) as c FROM keyword_rules WHERE active=1").fetchone()["c"]
    total_processed = conn.execute("SELECT COUNT(*) as c FROM processed_comments").fetchone()["c"]
    pending_q = conn.execute("SELECT COUNT(*) as c FROM action_queue WHERE status='pending'").fetchone()["c"]
    recent_actions = conn.execute(
        """SELECT a.id, a.type, a.status, a.scheduled_at, a.created_at, a.payload
           FROM action_queue a ORDER BY a.created_at DESC LIMIT 20"""
    ).fetchall()
    recent = []
    for row in recent_actions:
        d = dict(row)
        try:
            d["payload"] = json.loads(d["payload"])
        except Exception:
            pass
        recent.append(d)
    conn.close()
    return templates.TemplateResponse("index.html", {
        "request": request,
        "posts": posts,
        "total_rules": total_rules,
        "total_processed": total_processed,
        "pending_q": pending_q,
        "recent": recent,
        "active_page": "dashboard",
    })


@app.get("/posts", response_class=HTMLResponse)
async def posts_page(request: Request):
    conn = get_connection()
    posts = conn.execute("SELECT * FROM monitored_posts ORDER BY created_at DESC").fetchall()
    posts_with_rules = []
    for p in posts:
        rules = conn.execute(
            "SELECT * FROM keyword_rules WHERE post_id=? ORDER BY created_at DESC", (p["id"],)
        ).fetchall()
        processed_count = conn.execute(
            "SELECT COUNT(*) as c FROM processed_comments WHERE post_id=?", (p["id"],)
        ).fetchone()["c"]
        posts_with_rules.append({
            "post": dict(p),
            "rules": [dict(r) for r in rules],
            "processed_count": processed_count,
        })
    conn.close()
    return templates.TemplateResponse("posts.html", {
        "request": request,
        "posts_with_rules": posts_with_rules,
        "active_page": "posts",
    })


@app.get("/logs", response_class=HTMLResponse)
async def logs_page(request: Request, page: int = 1):
    per_page = 50
    offset = (page - 1) * per_page
    conn = get_connection()
    total = conn.execute("SELECT COUNT(*) as c FROM action_queue").fetchone()["c"]
    actions = conn.execute(
        """SELECT a.*, p.url as post_url FROM action_queue a
           LEFT JOIN monitored_posts p ON json_extract(a.payload, '$.post_id') = p.id
           ORDER BY a.created_at DESC LIMIT ? OFFSET ?""",
        (per_page, offset),
    ).fetchall()
    rows = []
    for row in actions:
        d = dict(row)
        try:
            d["payload"] = json.loads(d["payload"])
        except Exception:
            pass
        rows.append(d)
    conn.close()
    return templates.TemplateResponse("logs.html", {
        "request": request,
        "rows": rows,
        "total": total,
        "page": page,
        "per_page": per_page,
        "active_page": "logs",
    })


@app.get("/settings", response_class=HTMLResponse)
async def settings_page(request: Request, saved: bool = False):
    return templates.TemplateResponse("settings.html", {
        "request": request,
        "config": config,
        "saved": saved,
        "active_page": "settings",
    })


# ─── API: Posts ───────────────────────────────────────────────────────────────

@app.post("/api/posts")
async def add_post(url: str = Form(...)):
    url = url.strip()
    video_id = extract_video_id(url)
    if not video_id:
        raise HTTPException(400, "유효한 TikTok URL이 아닙니다")
    conn = get_connection()
    post_id = db_models.add_post(conn, url, video_id)
    conn.close()
    return {"id": post_id, "video_id": video_id, "url": url}


@app.delete("/api/posts/{post_id}")
async def delete_post(post_id: int):
    conn = get_connection()
    conn.execute("DELETE FROM monitored_posts WHERE id=?", (post_id,))
    conn.commit()
    conn.close()
    return {"ok": True}


@app.put("/api/posts/{post_id}/active")
async def toggle_post(post_id: int, active: bool):
    conn = get_connection()
    db_models.set_post_active(conn, post_id, active)
    conn.close()
    return {"ok": True, "active": active}


# ─── API: Rules ───────────────────────────────────────────────────────────────

@app.post("/api/posts/{post_id}/rules")
async def add_rule(
    post_id: int,
    keyword: str = Form(...),
    reply_text: str = Form(...),
    dm_text: Optional[str] = Form(None),
):
    conn = get_connection()
    post = conn.execute("SELECT id FROM monitored_posts WHERE id=?", (post_id,)).fetchone()
    if not post:
        raise HTTPException(404, "게시글을 찾을 수 없습니다")
    rule_id = db_models.add_rule(conn, post_id, keyword.strip(), reply_text.strip(), dm_text or None)
    conn.close()
    return {"id": rule_id}


@app.put("/api/rules/{rule_id}/active")
async def toggle_rule(rule_id: int, active: bool):
    conn = get_connection()
    conn.execute("UPDATE keyword_rules SET active=? WHERE id=?", (1 if active else 0, rule_id))
    conn.commit()
    conn.close()
    return {"ok": True}


@app.delete("/api/rules/{rule_id}")
async def delete_rule(rule_id: int):
    conn = get_connection()
    conn.execute("DELETE FROM keyword_rules WHERE id=?", (rule_id,))
    conn.commit()
    conn.close()
    return {"ok": True}


# ─── API: Settings ────────────────────────────────────────────────────────────

@app.post("/api/settings")
async def save_settings(
    reply_delay_min: int = Form(...),
    reply_delay_max: int = Form(...),
    dm_delay_min: int = Form(...),
    dm_delay_max: int = Form(...),
    poll_interval_min: int = Form(...),
    poll_interval_max: int = Form(...),
    same_user_cooldown: int = Form(...),
):
    config.reply_delay_min = reply_delay_min
    config.reply_delay_max = reply_delay_max
    config.dm_delay_min = dm_delay_min
    config.dm_delay_max = dm_delay_max
    config.poll_interval_min = poll_interval_min
    config.poll_interval_max = poll_interval_max
    config.same_user_cooldown = same_user_cooldown
    return RedirectResponse("/settings?saved=true", status_code=303)


# ─── API: Stats (for live refresh) ────────────────────────────────────────────

@app.get("/api/stats")
async def get_stats():
    conn = get_connection()
    stats = {
        "active_posts": conn.execute(
            "SELECT COUNT(*) as c FROM monitored_posts WHERE active=1"
        ).fetchone()["c"],
        "pending_actions": conn.execute(
            "SELECT COUNT(*) as c FROM action_queue WHERE status='pending'"
        ).fetchone()["c"],
        "done_today": conn.execute(
            "SELECT COUNT(*) as c FROM action_queue WHERE status='done' AND date(created_at)=date('now')"
        ).fetchone()["c"],
        "total_processed": conn.execute(
            "SELECT COUNT(*) as c FROM processed_comments"
        ).fetchone()["c"],
    }
    conn.close()
    return stats
