"""One-shot helper for `docker compose --profile telegram up`.

1. Waits for the cloudflared quick tunnel to publish its public https address.
2. Points the bot's menu button ("Открыть") at that address via the Bot API.
3. Prints the link to the bot.
4. Keeps running and answers /start with an "open the app" button (long polling).

Only the standard library is used, so no extra dependencies are needed.
"""

import html
import json
import os
import sys
import time
import urllib.error
import urllib.request

API = "https://api.telegram.org/bot{token}/{method}"


def _get_json(url: str, timeout: float = 5) -> dict:
    with urllib.request.urlopen(url, timeout=timeout) as r:
        return json.loads(r.read().decode())


def bot_call(token: str, method: str, payload: dict | None = None) -> dict:
    req = urllib.request.Request(
        API.format(token=token, method=method),
        data=json.dumps(payload or {}).encode(),
        headers={"Content-Type": "application/json"},
    )
    try:
        # Long polling holds the request open for payload["timeout"] seconds.
        with urllib.request.urlopen(req, timeout=15 + (payload or {}).get("timeout", 0)) as r:
            data = json.loads(r.read().decode())
    except urllib.error.HTTPError as e:
        data = json.loads(e.read().decode() or "{}")
    if not data.get("ok"):
        raise RuntimeError(f"Telegram {method}: {data.get('description', 'unknown error')}")
    return data["result"]


def wait_for_tunnel(metrics_url: str, timeout_s: int = 90) -> str:
    deadline = time.time() + timeout_s
    while time.time() < deadline:
        try:
            host = _get_json(metrics_url).get("hostname")
            if host:
                return f"https://{host}"
        except (OSError, ValueError):
            pass
        time.sleep(2)
    raise RuntimeError("Туннель не поднялся. Посмотрите логи: docker compose logs tunnel")


def menu_button_payload(url: str) -> dict:
    return {"menu_button": {"type": "web_app", "text": "Открыть", "web_app": {"url": url}}}


BOT_DESCRIPTION = (
    "Startup Space — стартапы и вакансии участников бизнес-клуба.\n\n"
    "🚀 Найдите проект, в который хочется войти, или людей в свою команду\n"
    "💼 Разместите стартап или вакансию за минуту\n"
    "🤝 Откликайтесь — контакты откроются, когда автор примет отклик\n\n"
    "Нажмите «Запустить», чтобы начать."
)
BOT_SHORT_DESCRIPTION = "Стартапы и вакансии участников бизнес-клуба: размещайте, откликайтесь, собирайте команду."

WELCOME = (
    "👋 <b>{name}, добро пожаловать в Startup Space!</b>\n\n"
    "Это площадка бизнес-клуба, где участники находят друг друга:\n\n"
    "🚀 <b>Стартапы</b> — проекты, которые ищут кофаундеров, команду и инвестиции\n"
    "💼 <b>Вакансии</b> — работа и подработка у участников клуба\n\n"
    "<b>Как это работает</b>\n"
    "1. Смотрите ленту и фильтруйте по навыкам\n"
    "2. Откликайтесь с коротким сообщением о себе\n"
    "3. Автор принимает отклик — и вы оба видите контакты друг друга\n\n"
    "Свои публикации и отклики — во вкладке «Кабинет».\n"
    "Профиль создастся автоматически из Telegram, вход без пароля."
)


def open_app_message(chat_id: int, url: str, first_name: str = "") -> dict:
    return {
        "chat_id": chat_id,
        "text": WELCOME.format(name=html.escape(first_name or "Привет")),
        "parse_mode": "HTML",
        "reply_markup": {"inline_keyboard": [[{"text": "🚀 Открыть Startup Space", "web_app": {"url": url}}]]},
    }


def configure_bot(token: str, url: str) -> None:
    bot_call(token, "setChatMenuButton", menu_button_payload(url))
    bot_call(token, "setMyCommands", {"commands": [{"command": "start", "description": "Открыть приложение"}]})
    # Descriptions are cosmetic: don't fail the whole setup if Telegram rejects them.
    for method, payload in (
        ("setMyDescription", {"description": BOT_DESCRIPTION}),
        ("setMyShortDescription", {"short_description": BOT_SHORT_DESCRIPTION}),
    ):
        try:
            bot_call(token, method, payload)
        except (RuntimeError, OSError) as e:
            print(f"{method}: {e}", flush=True)


def serve_updates(token: str, url: str) -> None:
    """Reply to /start (and any other private message) with a welcome and an "open app" button."""
    bot_call(token, "deleteWebhook")  # getUpdates does not work while a webhook is set
    print("Бот слушает сообщения (long polling)…", flush=True)
    offset = 0
    while True:
        try:
            updates = bot_call(token, "getUpdates", {"offset": offset, "timeout": 30, "allowed_updates": ["message"]})
        except (RuntimeError, OSError, ValueError) as e:
            print(f"getUpdates: {e}", flush=True)
            time.sleep(3)
            continue
        for upd in updates:
            offset = upd["update_id"] + 1
            msg = upd.get("message")
            if not msg or msg.get("chat", {}).get("type") != "private":
                continue
            who = msg.get("from", {})
            print(f"Сообщение от {who.get('username') or who.get('id')}: {msg.get('text', '')[:40]!r}", flush=True)
            try:
                bot_call(token, "sendMessage", open_app_message(msg["chat"]["id"], url, who.get("first_name", "")))
            except (RuntimeError, OSError, ValueError) as e:
                print(f"sendMessage: {e}", flush=True)


def main() -> int:
    token = os.getenv("TELEGRAM_BOT_TOKEN", "").strip()
    if not token:
        print("TELEGRAM_BOT_TOKEN не задан. Впишите его в файл .env рядом с docker-compose.yml.")
        return 1
    metrics_url = os.getenv("TUNNEL_METRICS_URL", "http://tunnel:2000/quicktunnel")
    try:
        me = bot_call(token, "getMe")
        url = wait_for_tunnel(metrics_url)
        configure_bot(token, url)
    except (RuntimeError, OSError) as e:
        print(f"Ошибка: {e}")
        return 1
    line = "=" * 60
    print(f"\n{line}\n  Готово! Откройте бота в Telegram: https://t.me/{me['username']}\n"
          f"  и нажмите /start — бот пришлёт кнопку «Открыть приложение».\n"
          f"  Адрес приложения: {url}\n"
          f"  (проверка в браузере: {url}/api/health)\n{line}\n", flush=True)
    if os.getenv("BOT_POLLING", "true").lower() != "false":
        serve_updates(token, url)
    return 0


if __name__ == "__main__":
    sys.exit(main())
