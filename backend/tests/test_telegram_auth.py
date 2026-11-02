import hashlib
import hmac
import json
import time
from dataclasses import replace
from urllib.parse import urlencode

from app.routers import auth as auth_router

BOT_TOKEN = "123456:TEST-BOT-TOKEN"


def make_init_data(user: dict, *, auth_date: int | None = None, token: str = BOT_TOKEN) -> str:
    """Build initData exactly as Telegram does, signed with the bot token."""
    fields = {
        "query_id": "AAHdF6IQAAAAAN0XohDhrOrc",
        "user": json.dumps(user, ensure_ascii=False, separators=(",", ":")),
        "auth_date": str(auth_date or int(time.time())),
    }
    dcs = "\n".join(f"{k}={v}" for k, v in sorted(fields.items()))
    secret = hmac.new(b"WebAppData", token.encode(), hashlib.sha256).digest()
    fields["hash"] = hmac.new(secret, dcs.encode(), hashlib.sha256).hexdigest()
    return urlencode(fields)


TG_USER = {"id": 777000111, "first_name": "Ольга", "last_name": "Петрова", "username": "olga_p"}


def _login(client, init_data):
    return client.post("/api/auth/telegram", json={"init_data": init_data})


def test_first_telegram_login_creates_profile_and_session(client):
    r = _login(client, make_init_data(TG_USER))
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["user"]["full_name"] == "Ольга Петрова"
    assert body["user"]["contact"] == "@olga_p"
    assert body["user"]["telegram_id"] == TG_USER["id"]
    assert body["user"]["email"] is None

    headers = {"Authorization": f"Bearer {body['token']}"}
    assert client.get("/api/me", headers=headers).json()["full_name"] == "Ольга Петрова"


def test_repeat_telegram_login_reuses_same_user(client):
    first = _login(client, make_init_data(TG_USER)).json()["user"]["id"]
    # Profile edits survive: Telegram data does not overwrite them on the next login.
    token = _login(client, make_init_data(TG_USER)).json()["token"]
    client.patch("/api/me", json={"full_name": "Ольга П."}, headers={"Authorization": f"Bearer {token}"})
    again = _login(client, make_init_data(TG_USER)).json()["user"]
    assert again["id"] == first and again["full_name"] == "Ольга П."


def test_telegram_user_can_use_the_module(client, author):
    post = author.create_post()
    token = _login(client, make_init_data(TG_USER)).json()["token"]
    r = client.post(
        f"/api/posts/{post['id']}/responses",
        json={"message": "Пишу прямо из Telegram mini-app!"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r.status_code == 201


def test_tampered_init_data_is_rejected(client):
    init_data = make_init_data(TG_USER).replace("777000111", "1")  # pretend to be another user
    assert _login(client, init_data).status_code == 401
    assert _login(client, make_init_data(TG_USER, token="999:OTHER-BOT")).status_code == 401
    assert _login(client, "user=%7B%7D&auth_date=1").status_code == 401  # no hash


def test_stale_init_data_is_rejected(client):
    old = int(time.time()) - 2 * 86400
    assert _login(client, make_init_data(TG_USER, auth_date=old)).status_code == 401


def test_telegram_login_disabled_without_bot_token(client, monkeypatch):
    monkeypatch.setattr(auth_router, "settings", replace(auth_router.settings, telegram_bot_token=""))
    assert _login(client, make_init_data(TG_USER)).status_code == 503
