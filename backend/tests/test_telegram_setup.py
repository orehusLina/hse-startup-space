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
    monkeypatch.setattr(telegram_setup, "bot_call", fake_bot_call)
    monkeypatch.setattr(telegram_setup, "_get_json", lambda url, timeout=5: {"hostname": "abc.trycloudflare.com"})

    assert telegram_setup.main() == 0
    assert calls[1] == ("setChatMenuButton", telegram_setup.menu_button_payload("https://abc.trycloudflare.com"))
    assert "https://t.me/club_match_bot" in capsys.readouterr().out


def test_setup_without_token(monkeypatch):
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "")
    assert telegram_setup.main() == 1
