from app import telegram_setup


def test_menu_button_points_to_tunnel_url():
    payload = telegram_setup.menu_button_payload("https://abc.trycloudflare.com")
    assert payload["menu_button"]["type"] == "web_app"
    assert payload["menu_button"]["web_app"]["url"] == "https://abc.trycloudflare.com"


def test_setup_flow(monkeypatch, capsys):
    calls = []

    def fake_bot_call(token, method, payload=None):
        calls.append((method, payload))
        return {"username": "club_match_bot"} if method == "getMe" else True

    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "1:x")
    monkeypatch.setenv("BOT_POLLING", "false")
    monkeypatch.setattr(telegram_setup, "bot_call", fake_bot_call)
    monkeypatch.setattr(telegram_setup, "_get_json", lambda url, timeout=5: {"hostname": "abc.trycloudflare.com"})

    assert telegram_setup.main() == 0
    assert calls[1] == ("setChatMenuButton", telegram_setup.menu_button_payload("https://abc.trycloudflare.com"))
    methods = [m for m, _ in calls]
    assert {"setMyCommands", "setMyDescription", "setMyShortDescription"} <= set(methods)
    assert "https://t.me/club_match_bot" in capsys.readouterr().out


def test_start_reply_has_web_app_button():
    msg = telegram_setup.open_app_message(42, "https://abc.trycloudflare.com", "<Аня>")
    assert "&lt;Аня&gt;, добро пожаловать" in msg["text"] and msg["parse_mode"] == "HTML"
    button = msg["reply_markup"]["inline_keyboard"][0][0]
    assert msg["chat_id"] == 42 and button["web_app"]["url"] == "https://abc.trycloudflare.com"


def test_setup_without_token(monkeypatch):
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "")
    assert telegram_setup.main() == 1


def test_menu_button_follows_new_tunnel_address(monkeypatch):
    """After a cloudflared restart the bot is re-pointed to the new address."""
    calls = []
    hosts = iter(["new.trycloudflare.com"])

    class Stop(Exception):
        pass

    def fake_bot_call(token, method, payload=None):
        calls.append((method, payload))
        if method == "getUpdates":
            raise Stop
        return True

    monkeypatch.setattr(telegram_setup, "bot_call", fake_bot_call)
    monkeypatch.setattr(telegram_setup, "_get_json", lambda url, timeout=5: {"hostname": next(hosts)})
    try:
        telegram_setup.serve_updates("1:x", "https://old.trycloudflare.com", "http://tunnel:2000/quicktunnel")
    except Stop:
        pass
    assert ("setChatMenuButton", telegram_setup.menu_button_payload("https://new.trycloudflare.com")) in calls
