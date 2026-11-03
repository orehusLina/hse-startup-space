import os

# Must be set before the app is imported: tests run against a separate Postgres database.
os.environ.setdefault(
    "TEST_DATABASE_URL", "postgresql+psycopg://club:club@localhost:5432/club_test"
)
os.environ["DATABASE_URL"] = os.environ["TEST_DATABASE_URL"]
os.environ["PASSWORD_ITERATIONS"] = "1000"  # fast hashing in tests
os.environ["SEED_ON_START"] = "false"
os.environ["TELEGRAM_BOT_TOKEN"] = "123456:TEST-BOT-TOKEN"
os.environ["DEMO_AUTOREPLY_DELAY"] = "0"  # demo autopilot acts immediately in tests
os.environ["PUBLIC_URL"] = "https://club.example"

import itertools  # noqa: E402

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402
from sqlalchemy import text  # noqa: E402

from app import notify  # noqa: E402
from app.db import Base, SessionLocal, engine  # noqa: E402
from app.main import app  # noqa: E402
from app.models import User  # noqa: E402
from app.security import hash_password  # noqa: E402

PASSWORD = "secret123"
_counter = itertools.count(1)


@pytest.fixture(scope="session", autouse=True)
def _schema():
    Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)
    yield
    engine.dispose()


@pytest.fixture(autouse=True)
def _clean_db():
    yield
    with engine.begin() as conn:
        tables = ", ".join(t.name for t in Base.metadata.sorted_tables)
        conn.execute(text(f"TRUNCATE {tables} RESTART IDENTITY CASCADE"))


@pytest.fixture(autouse=True)
def sent(monkeypatch):
    """Bot messages captured instead of being sent to Telegram: list of sendMessage payloads."""
    messages = []
    monkeypatch.setattr(notify, "transport", lambda method, payload: messages.append(payload))
    return messages


@pytest.fixture
def client():
    with TestClient(app) as c:
        yield c


class Member:
    """A logged-in user with a ready-to-use API client."""

    def __init__(self, client: TestClient, user: User, token: str):
        self.c = client
        self.user = user
        self.headers = {"Authorization": f"Bearer {token}"}

    def get(self, url, **kw):
        return self.c.get(url, headers=self.headers, **kw)

    def post(self, url, json=None, **kw):
        return self.c.post(url, json=json, headers=self.headers, **kw)

    def patch(self, url, json=None, **kw):
        return self.c.patch(url, json=json, headers=self.headers, **kw)

    def create_post(self, **overrides):
        payload = {
            "kind": "startup",
            "title": "Тестовый стартап",
            "summary": "Короткое описание стартапа для ленты",
            "skills": ["Python"],
        } | overrides
        r = self.post("/api/posts", payload)
        assert r.status_code == 201, r.text
        return r.json()


@pytest.fixture
def make_member(client):
    def _make(name: str | None = None, contact: str = "", skills: list[str] | None = None,
              telegram_id: int | None = None, email: str | None = None) -> Member:
        n = next(_counter)
        email = email or f"user{n}@test.local"
        with SessionLocal() as db:
            user = User(
                email=email,
                password_hash=hash_password(PASSWORD),
                full_name=name or f"User {n}",
                contact=contact or f"@user{n}",
                skills=skills or [],
                telegram_id=telegram_id,
            )
            db.add(user)
            db.commit()
            db.refresh(user)
        r = client.post("/api/auth/login", json={"email": email, "password": PASSWORD})
        assert r.status_code == 200, r.text
        return Member(client, user, r.json()["token"])

    return _make


@pytest.fixture
def author(make_member):
    return make_member("Author", contact="@author_tg")


@pytest.fixture
def applicant(make_member):
    return make_member("Applicant", contact="@applicant_tg")
