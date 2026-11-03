"""Bot notifications: who gets what, and that nothing breaks without Telegram."""

from app import notify

MSG = "Здравствуйте! Хочу присоединиться, есть релевантный опыт."


def test_author_is_notified_about_new_response(make_member, sent):
    author = make_member("Анна", telegram_id=111)
    applicant = make_member("Борис <b>", skills=["Python"])
    post = author.create_post(title="Learnly")
    applicant.post(f"/api/posts/{post['id']}/responses", {"message": MSG})

    msg = sent[-1]
    assert msg["chat_id"] == 111
    assert "Новый отклик" in msg["text"] and "Learnly" in msg["text"]
    assert "Борис &lt;b&gt;" in msg["text"]  # user input is HTML-escaped
    button = msg["reply_markup"]["inline_keyboard"][0][0]
    assert button["web_app"]["url"] == f"https://club.example/?open=post/{post['id']}"


def test_applicant_gets_contact_and_chat_button_on_accept(make_member, sent):
    author = make_member("Анна Смирнова", contact="@anna_s")
    applicant = make_member("Борис", telegram_id=222)
    post = author.create_post()
    rid = applicant.post(f"/api/posts/{post['id']}/responses", {"message": MSG}).json()["id"]
    author.post(f"/api/responses/{rid}/decision", {"status": "accepted", "note": "Созвонимся!"})

    msg = sent[-1]
    assert msg["chat_id"] == 222 and "приняли" in msg["text"] and "@anna_s" in msg["text"]
    assert "Созвонимся!" in msg["text"]
    buttons = [row[0] for row in msg["reply_markup"]["inline_keyboard"]]
    assert buttons[0] == {"text": "✉️ Написать Анна", "url": "https://t.me/anna_s"}


def test_rejection_and_closing_notify_applicants(make_member, sent):
    author = make_member("Author")
    a, b = make_member("A", telegram_id=1), make_member("B", telegram_id=2)
    post = author.create_post()
    ra = a.post(f"/api/posts/{post['id']}/responses", {"message": MSG}).json()["id"]
    b.post(f"/api/posts/{post['id']}/responses", {"message": MSG})
    author.post(f"/api/responses/{ra}/decision", {"status": "rejected"})
    assert sent[-1]["chat_id"] == 1 and "не принят" in sent[-1]["text"]

    author.patch(f"/api/posts/{post['id']}", {"status": "closed"})
    assert sent[-1]["chat_id"] == 2 and "закрыта" in sent[-1]["text"]


def test_members_without_telegram_get_nothing(author, applicant, sent):
    post = author.create_post()
    applicant.post(f"/api/posts/{post['id']}/responses", {"message": MSG})
    assert sent == []


def test_telegram_failure_does_not_break_request(make_member, monkeypatch):
    def boom(method, payload):
        raise RuntimeError("Telegram is down")

    monkeypatch.setattr(notify, "transport", boom)
    author = make_member("Author", telegram_id=5)
    post_id = author.create_post()["id"]
    r = make_member("Y").post(f"/api/posts/{post_id}/responses", {"message": MSG})
    assert r.status_code == 201


def test_contact_link_falls_back_to_telegram_id(make_member):
    author = make_member("Без username", contact="+7 900 000-00-00", telegram_id=777)
    applicant = make_member("Applicant")
    post = author.create_post()
    rid = applicant.post(f"/api/posts/{post['id']}/responses", {"message": MSG}).json()["id"]
    author.post(f"/api/responses/{rid}/decision", {"status": "accepted"})
    sent_resp = applicant.get("/api/me/responses/sent").json()[0]
    assert sent_resp["author_contact_link"] == "tg://user?id=777"
    received = author.get("/api/me/responses/received").json()[0]
    assert received["applicant"]["contact_link"] == "https://t.me/" + applicant.user.contact.lstrip("@")


def test_closing_startup_closes_its_vacancies(make_member, sent):
    author = make_member("Founder")
    applicant = make_member("Dev", telegram_id=9)
    startup = author.create_post(kind="startup")
    vacancy = author.create_post(kind="vacancy", title="CTO", startup_id=startup["id"])
    applicant.post(f"/api/posts/{vacancy['id']}/responses", {"message": MSG})

    assert author.patch(f"/api/posts/{startup['id']}", {"status": "closed"}).status_code == 200
    assert author.get(f"/api/posts/{vacancy['id']}").json()["status"] == "closed"
    resp = applicant.get("/api/me/responses/sent").json()[0]
    assert resp["status"] == "rejected" and resp["author_note"] == "Стартап закрыт автором"
    assert sent[-1]["chat_id"] == 9
