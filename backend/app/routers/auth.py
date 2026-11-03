from datetime import UTC, datetime, timedelta
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials
from sqlalchemy import delete, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from .. import schemas
from ..config import settings
from ..deps import DB, CurrentUser, bearer_scheme
from ..models import AuthSession, User
from ..security import (
    InvalidInitData,
    hash_token,
    new_token,
    verify_password,
    verify_telegram_init_data,
)
from ..seed import DEMO_PASSWORD, DEMO_USERS

router = APIRouter(prefix="/api/auth", tags=["auth"])


def _issue_session(db: Session, user: User) -> schemas.LoginOut:
    token = new_token()
    db.add(
        AuthSession(
            token_hash=hash_token(token),
            user_id=user.id,
            expires_at=datetime.now(UTC) + timedelta(days=settings.session_ttl_days),
        )
    )
    db.commit()
    return schemas.LoginOut(token=token, user=schemas.UserMe.model_validate(user))


@router.post("/telegram", response_model=schemas.LoginOut)
def telegram_login(data: schemas.TelegramLoginIn, db: DB):
    """Main entry point inside Telegram: the mini-app sends `Telegram.WebApp.initData`.

    The signature is checked with the bot token, so the user cannot be spoofed by the client.
    The first login creates a club profile from the Telegram data.
    """
    if not settings.telegram_bot_token:
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, "Вход через Telegram не настроен")
    try:
        tg = verify_telegram_init_data(
            data.init_data, settings.telegram_bot_token, settings.telegram_init_data_max_age
        )
    except InvalidInitData as e:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, f"Не удалось проверить данные Telegram: {e}")

    photo = str(tg.get("photo_url") or "")
    photo = photo[:512] if photo.startswith("https://") else ""  # rendered as <img src>, so https only

    user = db.scalar(select(User).where(User.telegram_id == tg["id"]))
    if user is None:
        full_name = " ".join(p for p in (tg.get("first_name"), tg.get("last_name")) if p) or "Участник клуба"
        user = User(
            telegram_id=tg["id"],
            full_name=full_name[:120],
            contact=f"@{tg['username']}" if tg.get("username") else "",
            photo_url=photo,
            skills=[],
        )
        db.add(user)
        try:
            db.commit()
        except IntegrityError:  # two parallel first logins of the same person
            db.rollback()
            user = db.scalar(select(User).where(User.telegram_id == tg["id"]))
    elif photo and photo != user.photo_url:
        user.photo_url = photo  # keep the Telegram photo fresh
        db.commit()
    return _issue_session(db, user)


@router.post("/login", response_model=schemas.LoginOut)
def login(data: schemas.LoginIn, db: DB):
    """Email/password login: for test accounts and opening the app outside Telegram."""
    user = db.scalar(select(User).where(User.email == data.email))
    if user is None or not user.password_hash or not verify_password(data.password, user.password_hash):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Неверный email или пароль")
    return _issue_session(db, user)


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
def logout(
    _: CurrentUser,
    db: DB,
    creds: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer_scheme)],
):
    db.execute(delete(AuthSession).where(AuthSession.token_hash == hash_token(creds.credentials)))
    db.commit()


@router.get("/demo-accounts", response_model=list[schemas.DemoAccount])
def demo_accounts():
    """Test accounts for one-tap login. Disabled outside demo mode."""
    if not settings.demo_mode:
        return []
    return [
        schemas.DemoAccount(
            email=u["email"], password=DEMO_PASSWORD, full_name=u["full_name"], headline=u["headline"],
            avatar_emoji=u.get("avatar_emoji", ""),
        )
        for u in DEMO_USERS
    ]
