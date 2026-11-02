import os
from dataclasses import dataclass


def _bool(name: str, default: bool) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


@dataclass(frozen=True)
class Settings:
    database_url: str = os.getenv(
        "DATABASE_URL", "postgresql+psycopg://club:club@localhost:5432/club"
    )
    # Demo mode exposes the list of test accounts for one-tap login on the login screen.
    demo_mode: bool = _bool("DEMO_MODE", True)
    seed_on_start: bool = _bool("SEED_ON_START", False)
    session_ttl_days: int = int(os.getenv("SESSION_TTL_DAYS", "30"))
    password_iterations: int = int(os.getenv("PASSWORD_ITERATIONS", "200000"))


settings = Settings()
