"""Telegram notifications from the bot.

Sent from FastAPI background tasks after the DB transaction commits, so a slow or failing
Telegram API never breaks or slows down the user's request. Members who never logged in via
Telegram (no telegram_id) are skipped silently.
"""

import html
import logging
import re
import time
import urllib.request
import json

from .config import settings
from .models import Post, Response, User

log = logging.getLogger("notify")

_url_cache: tuple[float, str | None] = (0.0, None)


def public_url() -> str | None:
    """Public https address of the app: PUBLIC_URL, else the current quick-tunnel address."""
    global _url_cache
    if settings.public_url:
        return settings.public_url
    if not settings.tunnel_metrics_url:
        return None
    ts, cached = _url_cache
    if time.time() - ts < 60:
        return cached
    url = None
    try:
        with urllib.request.urlopen(settings.tunnel_metrics_url, timeout=3) as r:
            host = json.loads(r.read().decode()).get("hostname")
            url = f"https://{host}" if host else None
    except (OSError, ValueError):
        pass
    _url_cache = (time.time(), url)
    return url


def _bot_call(method: str, payload: dict) -> None:
    from .telegram_setup import bot_call

    bot_call(settings.telegram_bot_token, method, payload)


# Replaced in tests to capture messages instead of calling Telegram.
transport = _bot_call


def contact_link(user: User) -> str | None:
    """A link that opens a chat with the member: @username → t.me, otherwise by Telegram id."""
    m = re.fullmatch(r"@?([A-Za-z0-9_]{5,32})", (user.contact or "").strip())
    if m:
        return f"https://t.me/{m.group(1)}"
    if user.telegram_id:
        return f"tg://user?id={user.telegram_id}"
    return None


def _open_button(text: str, route: str) -> dict | None:
    base = public_url()
    # Telegram puts its own data into the URL fragment, so the route goes into the query string.
    return {"text": text, "web_app": {"url": f"{base}/?open={route}"}} if base else None


def send(user: User, text: str, buttons: list[dict | None] = ()) -> bool:
    if not settings.telegram_bot_token or not user.telegram_id:
        return False
    rows = [[b] for b in buttons if b]
    payload = {"chat_id": user.telegram_id, "text": text, "parse_mode": "HTML", "disable_web_page_preview": True}
    if rows:
        payload["reply_markup"] = {"inline_keyboard": rows}
    try:
        transport("sendMessage", payload)
        return True
    except Exception as e:  # noqa: BLE001 - a notification must never break the app
        log.warning("notification to %s failed: %s", user.telegram_id, e)
        return False


def _e(s: str) -> str:
    return html.escape(s or "")


def _quote(text: str, limit: int = 300) -> str:
    text = text.strip()
    return _e(text if len(text) <= limit else text[: limit - 1] + "…")


KIND_ACC = {"startup": "ваш стартап", "vacancy": "вашу вакансию"}


# ---------- events ----------


def new_response(response: Response) -> bool:
    post, applicant = response.post, response.applicant
    who = _e(applicant.full_name) + (f" · {_e(applicant.headline)}" if applicant.headline else "")
    text = (
        f"📨 <b>Новый отклик на {KIND_ACC[post.kind]}</b>\n«{_e(post.title)}»\n\n"
        f"<b>{who}</b>\n<i>{_quote(response.message)}</i>"
    )
    return send(post.author, text, [_open_button("Посмотреть отклик", f"post/{post.id}")])


def decision(response: Response) -> bool:
    post, author = response.post, response.post.author
    note = f"\n\n💬 <i>{_quote(response.author_note)}</i>" if response.author_note else ""
    if response.status == "accepted":
        link = contact_link(author)
        contact = _e(author.contact) if author.contact else "откройте чат по кнопке ниже"
        text = (
            f"🎉 <b>Ваш отклик приняли!</b>\n«{_e(post.title)}»\n\n"
            f"{_e(author.full_name)} ждёт вашего сообщения.\nКонтакт: <b>{contact}</b>{note}"
        )
        buttons = [{"text": f"✉️ Написать {author.full_name.split()[0]}", "url": link} if link else None,
                   _open_button("Открыть в приложении", f"post/{post.id}")]
    else:
        text = f"Отклик на «{_e(post.title)}» не принят.{note}\n\nВ ленте есть и другие проекты — загляните 🙌"
        buttons = [_open_button("Открыть ленту", "feed")]
    return send(response.applicant, text, buttons)


def post_closed(response: Response) -> bool:
    text = (
        f"Публикация «{_e(response.post.title)}» закрыта автором, поэтому ваш отклик не будет рассмотрен.\n\n"
        "Посмотрите похожие проекты в ленте 👇"
    )
    return send(response.applicant, text, [_open_button("Открыть ленту", "feed")])


def invite(post: Post, user: User) -> bool:
    author = post.author
    text = (
        f"✨ <b>{_e(author.full_name)} приглашает вас откликнуться</b>\n"
        f"на {'стартап' if post.kind == 'startup' else 'вакансию'} «{_e(post.title)}»\n\n"
        f"<i>{_quote(post.summary)}</i>\n\nВаши навыки подходят под эту публикацию."
    )
    return send(user, text, [_open_button("Посмотреть и откликнуться", f"post/{post.id}")])


EVENTS = {"new_response": new_response, "decision": decision, "post_closed": post_closed}


def deliver(event: str, *, response_id: int | None = None, post_id: int | None = None,
            user_id: int | None = None) -> None:
    """Background-task entry point: loads fresh rows in its own session (the request's is closed)."""
    from .db import SessionLocal

    if not settings.telegram_bot_token:
        return
    with SessionLocal() as db:
        if event == "invite":
            post, user = db.get(Post, post_id), db.get(User, user_id)
            if post and user:
                invite(post, user)
            return
        response = db.get(Response, response_id)
        if response is not None:
            EVENTS[event](response)
