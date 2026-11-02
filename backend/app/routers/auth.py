from datetime import UTC, datetime, timedelta
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials
from sqlalchemy import delete, select

from .. import schemas
from ..config import settings
from ..deps import DB, CurrentUser, bearer_scheme
from ..models import AuthSession, User
from ..security import hash_token, new_token, verify_password
from ..seed import DEMO_PASSWORD, DEMO_USERS

router = APIRouter(prefix="/api/auth", tags=["auth"])


@router.post("/login", response_model=schemas.LoginOut)
def login(data: schemas.LoginIn, db: DB):
    user = db.scalar(select(User).where(User.email == data.email))
    if user is None or not verify_password(data.password, user.password_hash):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Неверный email или пароль")
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
            email=u["email"], password=DEMO_PASSWORD, full_name=u["full_name"], headline=u["headline"]
        )
        for u in DEMO_USERS
    ]
