from app.db import SessionLocal
from app.seed import DEMO_PASSWORD, DEMO_USERS, seed


def test_login_wrong_password_is_401(client, author):
    r = client.post("/api/auth/login", json={"email": author.user.email, "password": "nope"})
    assert r.status_code == 401


def test_protected_endpoints_require_token(client):
    assert client.get("/api/me").status_code == 401
    assert client.get("/api/posts").status_code == 401
    assert client.get("/api/me", headers={"Authorization": "Bearer garbage"}).status_code == 401


def test_logout_invalidates_token(author):
    assert author.get("/api/me").status_code == 200
    assert author.post("/api/auth/logout").status_code == 204
    assert author.get("/api/me").status_code == 401


def test_update_profile_normalizes_skills(author):
    r = author.patch(
        "/api/me",
        {"headline": "  CTO  ", "skills": ["Python", " python ", "", "Go"], "city": "Москва", "avatar_emoji": "🦄"},
    )
    assert r.status_code == 200
    body = r.json()
    assert body["headline"] == "CTO"
    assert body["skills"] == ["Python", "Go"]
    assert body["avatar_emoji"] == "🦄"
    assert author.get("/api/me").json()["city"] == "Москва"


def test_public_profile_hides_contact(author, applicant):
    body = applicant.get(f"/api/users/{author.user.id}").json()
    assert body["full_name"] == "Author"
    assert "contact" not in body and "email" not in body


def test_seed_accounts_can_log_in(client):
    with SessionLocal() as db:
        assert seed(db) is True
        assert seed(db) is False  # idempotent
    accounts = client.get("/api/auth/demo-accounts").json()
    assert {a["email"] for a in accounts} == {u["email"] for u in DEMO_USERS}
    r = client.post(
        "/api/auth/login", json={"email": DEMO_USERS[0]["email"].upper(), "password": DEMO_PASSWORD}
    )
    assert r.status_code == 200
    feed = client.get("/api/posts", headers={"Authorization": f"Bearer {r.json()['token']}"}).json()
    assert feed["total"] > 0
