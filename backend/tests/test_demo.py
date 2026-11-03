"""Demo autopilot: seeded members answer real Telegram users so a lone reviewer sees the full loop."""

MSG = "Здравствуйте! Интересный проект, хочу помочь с разработкой."


def test_demo_author_accepts_telegram_users_response(make_member, sent):
    demo_author = make_member("Анна (демо)", email="anna@club.test", contact="@anna_demo")
    tg_user = make_member("Ревьюер", telegram_id=4242)
    post = demo_author.create_post()

    tg_user.post(f"/api/posts/{post['id']}/responses", {"message": MSG})
    resp = tg_user.get("/api/me/responses/sent").json()[0]
    assert resp["status"] == "accepted" and resp["author_contact"] == "@anna_demo"
    assert sent[-1]["chat_id"] == 4242 and "приняли" in sent[-1]["text"]


def test_best_matching_demo_member_responds_to_new_post(make_member, sent):
    make_member("Дизайнер", email="vera@club.test", skills=["Figma"])
    make_member("Бэкендер", email="boris@club.test", skills=["Python", "PostgreSQL"])
    tg_author = make_member("Ревьюер", telegram_id=5151)
    post = tg_author.create_post(skills=["Python", "PostgreSQL"])

    received = tg_author.get("/api/me/responses/received").json()
    assert [r["applicant"]["full_name"] for r in received] == ["Бэкендер"]
    assert "Python, PostgreSQL" in received[0]["message"]
    assert sent[-1]["chat_id"] == 5151 and "Новый отклик" in sent[-1]["text"]
    assert post["id"] == received[0]["post"]["id"]


def test_autopilot_ignores_regular_members(make_member, sent):
    demo_author = make_member("Демо", email="dina@club.test")
    regular = make_member("Без телеграма")
    post = demo_author.create_post()
    regular.post(f"/api/posts/{post['id']}/responses", {"message": MSG})
    assert regular.get("/api/me/responses/sent").json()[0]["status"] == "pending"

    make_member("Демо 2", email="gleb@club.test", skills=["Python"])
    regular.create_post(skills=["Python"])
    assert regular.get("/api/me/responses/received").json() == []
