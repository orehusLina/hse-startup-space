"""Demo autopilot, only in DEMO_MODE.

A reviewer usually opens the mini-app alone, so nobody would ever answer them and they would
never see the bot notifications. To show the full loop, seeded demo members (…@club.test)
react to *real Telegram users* after a short delay:

* a Telegram user responds to a demo member's post → the demo author accepts it;
* a Telegram user publishes a post → the best-matching demo member responds to it.

Both actions go through the same code paths and notifications as real ones.
"""

import logging
import threading
from datetime import UTC, datetime

from sqlalchemy import select

from . import matching, notify
from .config import settings
from .db import SessionLocal
from .models import Post, Response, User

log = logging.getLogger("demo")
DEMO_DOMAIN = "@club.test"


def is_demo(user: User | None) -> bool:
    return bool(user and user.email and user.email.endswith(DEMO_DOMAIN))


def _later(fn, *args) -> None:
    if settings.demo_autoreply_delay <= 0:
        fn(*args)
    else:
        t = threading.Timer(settings.demo_autoreply_delay, fn, args)
        t.daemon = True
        t.start()


def on_response(response_id: int) -> None:
    """Background task after a response is created."""
    if not settings.demo_mode:
        return
    with SessionLocal() as db:
        r = db.get(Response, response_id)
        if r is None or not r.applicant.telegram_id or not is_demo(r.post.author):
            return
    _later(_auto_accept, response_id)


def on_post_created(post_id: int) -> None:
    """Background task after a post is published."""
    if not settings.demo_mode:
        return
    with SessionLocal() as db:
        post = db.get(Post, post_id)
        if post is None or not post.author.telegram_id or is_demo(post.author):
            return
    _later(_auto_respond, post_id)


def _auto_accept(response_id: int) -> None:
    try:
        with SessionLocal() as db:
            r = db.scalar(select(Response).where(Response.id == response_id).with_for_update())
            if r is None or r.status != "pending" or r.post.status == "closed":
                return
            r.status = "accepted"
            r.author_note = "Спасибо за отклик! Давайте созвонимся на этой неделе 🙌 (демо: автор ответил автоматически)"
            r.decided_at = datetime.now(UTC)
            db.commit()
            notify.decision(r)
    except Exception:  # noqa: BLE001
        log.exception("demo auto-accept failed")


def _auto_respond(post_id: int) -> None:
    try:
        with SessionLocal() as db:
            post = db.get(Post, post_id)
            if post is None or post.status != "active":
                return
            candidates = [u for u in db.scalars(select(User).where(User.email.like(f"%{DEMO_DOMAIN}"))) if u.id != post.author_id]
            if not candidates:
                return
            best = max(candidates, key=lambda u: matching.score(matching.match(u.skills, post.skills)))
            m = matching.match(best.skills, post.skills)
            skills = f" Мой стек: {', '.join(m.matched)}." if m and m.matched else ""
            message = (
                f"Здравствуйте! Заинтересовала ваша публикация «{post.title}». "
                f"{best.headline}.{skills} С удовольствием обсужу детали. (Демо-отклик от тестового резидента)"
            )
            if db.scalar(select(Response.id).where(Response.post_id == post.id, Response.applicant_id == best.id)):
                return
            r = Response(post_id=post.id, applicant_id=best.id, message=message)
            db.add(r)
            db.commit()
            notify.new_response(r)
    except Exception:  # noqa: BLE001
        log.exception("demo auto-respond failed")
