"""Security and data-integrity checks that go beyond the happy path."""

import json
from concurrent.futures import ThreadPoolExecutor

import pytest

from tests.conftest import PASSWORD

MSG = "Здравствуйте! Хочу присоединиться к проекту, есть опыт."


# ---------- privacy: contacts never leak before acceptance ----------


def test_contacts_do_not_leak_anywhere_before_acceptance(make_member):
    author = make_member("Author", contact="@secret_author", skills=["Python"])
    applicant = make_member("Applicant", contact="@secret_applicant", skills=["Python"], telegram_id=31337)
    post = author.create_post(skills=["Python"])
    rid = applicant.post(f"/api/posts/{post['id']}/responses", {"message": MSG}).json()["id"]

    def dump(member, urls):
        return " ".join(json.dumps(member.get(u).json(), ensure_ascii=False) for u in urls)

    seen_by_applicant = dump(applicant, ["/api/posts", f"/api/posts/{post['id']}", f"/api/users/{author.user.id}",
                                         "/api/me/responses/sent"])
    seen_by_author = dump(author, [f"/api/posts/{post['id']}/responses", "/api/me/responses/received",
                                   f"/api/posts/{post['id']}/candidates", f"/api/users/{applicant.user.id}"])
    assert "@secret_author" not in seen_by_applicant
    assert "@secret_applicant" not in seen_by_author and "31337" not in seen_by_author  # nor the Telegram id

    author.post(f"/api/responses/{rid}/decision", {"status": "accepted"})
    assert "@secret_author" in dump(applicant, ["/api/me/responses/sent"])
    assert "@secret_applicant" in dump(author, ["/api/me/responses/received"])


def test_rejected_response_keeps_contacts_hidden(make_member):
    author = make_member("Author", contact="@hidden_a")
    applicant = make_member("Applicant", contact="@hidden_b")
    post = author.create_post()
    rid = applicant.post(f"/api/posts/{post['id']}/responses", {"message": MSG}).json()["id"]
    author.post(f"/api/responses/{rid}/decision", {"status": "rejected"})
    assert "@hidden_a" not in json.dumps(applicant.get("/api/me/responses/sent").json())
    assert "@hidden_b" not in json.dumps(author.get("/api/me/responses/received").json())


# ---------- access control: a stranger can't touch other people's data ----------


def test_stranger_cannot_act_on_foreign_resources(make_member):
    author, applicant, stranger = make_member("A"), make_member("B"), make_member("Stranger")
    post = author.create_post()
    rid = applicant.post(f"/api/posts/{post['id']}/responses", {"message": MSG}).json()["id"]
    pid = post["id"]

    attempts = [
        ("patch", f"/api/posts/{pid}", {"title": "Взломано"}),
        ("patch", f"/api/posts/{pid}", {"status": "closed"}),
        ("get", f"/api/posts/{pid}/responses", None),
        ("get", f"/api/posts/{pid}/candidates", None),
        ("post", f"/api/posts/{pid}/invite/{applicant.user.id}", None),
        ("post", f"/api/responses/{rid}/decision", {"status": "accepted"}),
        ("post", f"/api/responses/{rid}/withdraw", None),
    ]
    for method, url, body in attempts:
        kwargs = {"json": body} if body is not None else {}
        r = getattr(stranger, method)(url, **kwargs)
        assert r.status_code in (403, 404), (method, url, r.status_code)

    # nothing changed
    assert author.get(f"/api/posts/{pid}").json()["title"] == post["title"]
    assert applicant.get("/api/me/responses/sent").json()[0]["status"] == "pending"
    assert stranger.get("/api/me/responses/received").json() == []


def test_mass_assignment_is_ignored(make_member):
    author, other = make_member("Author"), make_member("Other")
    post = author.create_post(kind="startup")
    r = author.patch(f"/api/posts/{post['id']}", {"kind": "vacancy", "author_id": other.user.id, "title": "Новое название"})
    assert r.status_code == 200
    body = author.get(f"/api/posts/{post['id']}").json()
    assert body["kind"] == "startup" and body["is_own"] is True and body["title"] == "Новое название"
    me = author.patch("/api/me", {"email": "hijack@x.y", "telegram_id": 1, "full_name": "Новое имя"}).json()
    assert me["email"] == author.user.email and me["telegram_id"] is None


# ---------- concurrency: invariants hold under parallel requests ----------


def test_parallel_duplicate_responses_create_exactly_one(make_member):
    author, applicant = make_member("A"), make_member("B")
    post = author.create_post()
    with ThreadPoolExecutor(max_workers=10) as pool:
        codes = list(pool.map(
            lambda _: applicant.post(f"/api/posts/{post['id']}/responses", {"message": MSG}).status_code, range(10)
        ))
    assert sorted(codes).count(201) == 1 and codes.count(409) == 9
    assert len(author.get(f"/api/posts/{post['id']}/responses").json()) == 1


def test_parallel_accept_and_withdraw_have_one_winner(make_member):
    for _ in range(5):  # a few rounds to give the race a chance
        author, applicant = make_member("A"), make_member("B")
        post = author.create_post()
        rid = applicant.post(f"/api/posts/{post['id']}/responses", {"message": MSG}).json()["id"]
        with ThreadPoolExecutor(max_workers=2) as pool:
            accept = pool.submit(author.post, f"/api/responses/{rid}/decision", {"status": "accepted"})
            withdraw = pool.submit(applicant.post, f"/api/responses/{rid}/withdraw")
            codes = sorted([accept.result().status_code, withdraw.result().status_code])
        assert codes == [200, 409]  # exactly one action wins, the other sees the new state
        final = applicant.get("/api/me/responses/sent").json()[0]["status"]
        assert final in ("accepted", "withdrawn")


def test_parallel_close_and_respond_leave_no_pending_on_closed_post(make_member):
    author = make_member("A")
    applicants = [make_member(f"B{i}") for i in range(6)]
    post = author.create_post()
    with ThreadPoolExecutor(max_workers=7) as pool:
        futures = [pool.submit(a.post, f"/api/posts/{post['id']}/responses", {"message": MSG}) for a in applicants]
        futures.append(pool.submit(author.patch, f"/api/posts/{post['id']}", {"status": "closed"}))
        [f.result() for f in futures]
    statuses = {r["status"] for r in author.get("/api/me/responses/received").json()}
    assert "pending" not in statuses


# ---------- authentication hardening ----------


def test_login_is_throttled_after_repeated_failures(client, make_member):
    member = make_member("Victim")
    for _ in range(10):
        assert client.post("/api/auth/login", json={"email": member.user.email, "password": "wrong"}).status_code == 401
    r = client.post("/api/auth/login", json={"email": member.user.email, "password": PASSWORD})
    assert r.status_code == 429 and int(r.headers["Retry-After"]) > 0
    # other accounts are not affected
    other = make_member("Other")
    assert client.post("/api/auth/login", json={"email": other.user.email, "password": PASSWORD}).status_code == 200


def test_unknown_email_and_wrong_password_look_the_same(client, make_member):
    member = make_member("M")
    a = client.post("/api/auth/login", json={"email": "nobody@nowhere.test", "password": "x"})
    b = client.post("/api/auth/login", json={"email": member.user.email, "password": "x"})
    assert a.status_code == b.status_code == 401 and a.json() == b.json()


def test_tokens_are_stored_hashed(make_member):
    from sqlalchemy import select

    from app.db import SessionLocal
    from app.models import AuthSession

    member = make_member("M")
    raw = member.headers["Authorization"].split()[1]
    with SessionLocal() as db:
        stored = db.scalars(select(AuthSession.token_hash).where(AuthSession.user_id == member.user.id)).all()
    assert stored and raw not in stored and all(len(h) == 64 for h in stored)


@pytest.mark.parametrize("bad", ["<script>", "ADMIN", "🚀🚀🚀🚀🚀🚀🚀🚀🚀", "a🚀"])
def test_avatar_must_be_an_emoji(make_member, bad):
    assert make_member("M").patch("/api/me", {"avatar_emoji": bad}).status_code == 422


def test_security_headers(client):
    r = client.get("/api/health")
    assert r.headers["X-Content-Type-Options"] == "nosniff"
    assert "frame-ancestors" in r.headers["Content-Security-Policy"]
    assert r.headers["Cache-Control"] == "no-store"
    assert "Cache-Control" not in client.get("/").headers or client.get("/").headers["Cache-Control"] != "no-store"


# ---------- input limits ----------


def test_oversized_and_malformed_input_is_rejected(make_member):
    m = make_member("M")
    base = {"kind": "startup", "title": "Норм", "summary": "Нормальное описание публикации"}
    assert m.post("/api/posts", base | {"title": "x" * 141}).status_code == 422
    assert m.post("/api/posts", base | {"skills": [f"s{i}" for i in range(16)]}).status_code == 422
    assert m.post("/api/posts", base | {"stage": "unicorn"}).status_code == 422
    assert m.get("/api/posts", params={"page_size": 1000}).status_code == 422
    assert m.get("/api/posts", params={"q": "x" * 101}).status_code == 422
    assert m.get("/api/posts/not-a-number").status_code == 422
