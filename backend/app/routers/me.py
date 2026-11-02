from typing import Annotated

from fastapi import APIRouter, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.orm import joinedload

from .. import schemas, serializers
from ..deps import DB, CurrentUser
from ..models import Post, Response, User

router = APIRouter(prefix="/api", tags=["profile"])


@router.get("/me", response_model=schemas.UserMe)
def me(user: CurrentUser):
    return user


@router.patch("/me", response_model=schemas.UserMe)
def update_me(data: schemas.ProfileUpdate, db: DB, user: CurrentUser):
    changes = data.model_dump(exclude_unset=True)
    if "full_name" in changes and not changes["full_name"]:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "Укажите имя")
    for key, value in changes.items():
        setattr(user, key, value if value is not None else ([] if key == "skills" else ""))
    db.commit()
    db.refresh(user)
    return user


@router.get("/users/{user_id}", response_model=schemas.UserPublic)
def public_profile(user_id: int, db: DB, _: CurrentUser):
    user = db.get(User, user_id)
    if user is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Пользователь не найден")
    return user


@router.get("/me/posts", response_model=list[schemas.PostOut])
def my_posts(db: DB, user: CurrentUser, status_: Annotated[schemas.PostStatus | None, Query(alias="status")] = None):
    conds = [Post.author_id == user.id]
    if status_:
        conds.append(Post.status == status_)
    posts = db.scalars(
        select(Post)
        .where(*conds)
        .options(joinedload(Post.author), joinedload(Post.startup))
        .order_by(Post.created_at.desc(), Post.id.desc())
    ).all()
    return serializers.posts_out(db, posts, user)


@router.get("/me/responses/sent", response_model=list[schemas.SentResponseOut])
def sent_responses(db: DB, user: CurrentUser, status_: Annotated[schemas.ResponseStatus | None, Query(alias="status")] = None):
    conds = [Response.applicant_id == user.id]
    if status_:
        conds.append(Response.status == status_)
    rows = db.scalars(
        select(Response)
        .where(*conds)
        .options(joinedload(Response.post).joinedload(Post.author))
        .order_by(Response.created_at.desc())
    ).all()
    return [serializers.sent_response(r) for r in rows]


@router.get("/me/responses/received", response_model=list[schemas.ReceivedResponseOut])
def received_responses(
    db: DB,
    user: CurrentUser,
    status_: Annotated[schemas.ResponseStatus | None, Query(alias="status")] = None,
    post_id: int | None = None,
):
    conds = [Post.author_id == user.id, Response.status != "withdrawn"]
    if status_:
        conds.append(Response.status == status_)
    if post_id:
        conds.append(Response.post_id == post_id)
    rows = db.scalars(
        select(Response)
        .join(Response.post)
        .where(*conds)
        .options(joinedload(Response.applicant), joinedload(Response.post).joinedload(Post.author))
        .order_by(Response.created_at.desc())
    ).all()
    return [serializers.received_response(r) for r in rows]
