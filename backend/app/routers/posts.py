from datetime import UTC, datetime
from typing import Annotated

from fastapi import APIRouter, HTTPException, Query, status
from sqlalchemy import any_, func, literal, or_, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import joinedload

from .. import schemas, serializers
from ..deps import DB, CurrentUser
from ..models import Post, Response, User

router = APIRouter(prefix="/api/posts", tags=["posts"])

# Allowed manual status transitions. `closed` is final: closing auto-rejects pending responses.
STATUS_TRANSITIONS = {
    "active": {"paused", "closed"},
    "paused": {"active", "closed"},
    "closed": set(),
}


def _load_post(db: DB, post_id: int, *, for_update: bool = False, for_share: bool = False) -> Post:
    stmt = select(Post).where(Post.id == post_id)
    if for_update or for_share:
        stmt = stmt.with_for_update(read=for_share)
    else:
        stmt = stmt.options(joinedload(Post.author), joinedload(Post.startup))
    post = db.scalar(stmt)
    if post is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Публикация не найдена")
    return post


def _validate_startup_link(db: DB, user: User, kind: str, startup_id: int | None) -> None:
    if startup_id is None:
        return
    if kind != "vacancy":
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_CONTENT, "Привязать к стартапу можно только вакансию"
        )
    startup = db.get(Post, startup_id)
    if startup is None or startup.kind != "startup" or startup.author_id != user.id:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_CONTENT, "Вакансию можно привязать только к своему стартапу"
        )
    if startup.status == "closed":
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "Стартап закрыт")


@router.get("", response_model=schemas.Page)
def feed(
    db: DB,
    user: CurrentUser,
    kind: schemas.PostKind | None = None,
    q: Annotated[str | None, Query(max_length=100)] = None,
    skill: Annotated[str | None, Query(max_length=40)] = None,
    include_own: bool = False,
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=50)] = 20,
):
    """Active publications of other members, newest first."""
    conds = [Post.status == "active"]
    if not include_own:
        conds.append(Post.author_id != user.id)
    if kind:
        conds.append(Post.kind == kind)
    if q and q.strip():
        pattern = f"%{q.strip().replace('\\', '\\\\').replace('%', '\\%').replace('_', '\\_')}%"
        conds.append(
            or_(
                Post.title.ilike(pattern),
                Post.summary.ilike(pattern),
                Post.description.ilike(pattern),
                Post.looking_for.ilike(pattern),
                func.array_to_string(Post.skills, " ").ilike(pattern),
            )
        )
    if skill and skill.strip():
        lowered = func.string_to_array(func.lower(func.array_to_string(Post.skills, "\x1f")), "\x1f")
        conds.append(literal(skill.strip().lower()) == any_(lowered))

    total = db.scalar(select(func.count()).select_from(Post).where(*conds)) or 0
    posts = db.scalars(
        select(Post)
        .where(*conds)
        .options(joinedload(Post.author), joinedload(Post.startup))
        .order_by(Post.created_at.desc(), Post.id.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    ).all()
    return schemas.Page(
        items=serializers.posts_out(db, posts, user), total=total, page=page, page_size=page_size
    )


@router.post("", response_model=schemas.PostOut, status_code=status.HTTP_201_CREATED)
def create_post(data: schemas.PostCreate, db: DB, user: CurrentUser):
    _validate_startup_link(db, user, data.kind, data.startup_id)
    fields = data.model_dump()
    if data.kind == "vacancy":
        fields["stage"] = None  # stage describes startups only
    post = Post(author_id=user.id, status="active", **fields)
    db.add(post)
    db.commit()
    return serializers.posts_out(db, [_load_post(db, post.id)], user)[0]


@router.get("/{post_id}", response_model=schemas.PostOut)
def get_post(post_id: int, db: DB, user: CurrentUser):
    post = _load_post(db, post_id)
    if post.status != "active" and post.author_id != user.id:
        # Hidden posts stay visible to people who already responded, so they keep the context.
        responded = db.scalar(
            select(Response.id).where(Response.post_id == post.id, Response.applicant_id == user.id)
        )
        if responded is None:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "Публикация не найдена")
    out = serializers.posts_out(db, [post], user)[0]
    if post.kind == "startup":
        vacancy_conds = [Post.startup_id == post.id]
        if post.author_id != user.id:
            vacancy_conds.append(Post.status == "active")
        out.vacancies = [
            serializers.startup_ref(v)
            for v in db.scalars(select(Post).where(*vacancy_conds).order_by(Post.created_at.desc()))
        ]
    return out


@router.patch("/{post_id}", response_model=schemas.PostOut)
def update_post(post_id: int, data: schemas.PostUpdate, db: DB, user: CurrentUser):
    post = _load_post(db, post_id, for_update=True)
    if post.author_id != user.id:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Редактировать может только автор")
    changes = data.model_dump(exclude_unset=True)

    if post.status == "closed" and changes:
        raise HTTPException(status.HTTP_409_CONFLICT, "Закрытую публикацию нельзя изменить")

    new_status = changes.pop("status", None)
    if new_status is not None and new_status != post.status:
        if new_status not in STATUS_TRANSITIONS[post.status]:
            raise HTTPException(status.HTTP_409_CONFLICT, "Недопустимая смена статуса")
        post.status = new_status
        if new_status == "closed":
            db.execute(
                update(Response)
                .where(Response.post_id == post.id, Response.status == "pending")
                .values(
                    status="rejected",
                    author_note="Публикация закрыта автором",
                    decided_at=datetime.now(UTC),
                )
            )

    if "startup_id" in changes:
        _validate_startup_link(db, user, post.kind, changes["startup_id"])
    if post.kind == "vacancy":
        changes.pop("stage", None)
    for required in ("title", "summary"):
        if required in changes and changes[required] is None:
            raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, f"Поле {required} обязательно")
    for key in ("description", "looking_for", "compensation"):
        if key in changes and changes[key] is None:
            changes[key] = ""
    if "skills" in changes and changes["skills"] is None:
        changes["skills"] = []
    for key, value in changes.items():
        setattr(post, key, value)

    db.commit()
    db.expire_all()
    return get_post(post_id, db, user)


@router.post(
    "/{post_id}/responses",
    response_model=schemas.SentResponseOut,
    status_code=status.HTTP_201_CREATED,
)
def respond(post_id: int, data: schemas.ResponseCreate, db: DB, user: CurrentUser):
    # Shared lock: closing the post (FOR UPDATE) waits for us, so no pending response slips past it.
    post = _load_post(db, post_id, for_share=True)
    if post.author_id == user.id:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Нельзя откликнуться на свою публикацию")
    if post.status != "active":
        raise HTTPException(status.HTTP_409_CONFLICT, "Публикация сейчас не принимает отклики")

    existing = db.scalar(
        select(Response)
        .where(Response.post_id == post.id, Response.applicant_id == user.id)
        .with_for_update()
    )
    if existing is not None:
        if existing.status != "withdrawn":
            raise HTTPException(status.HTTP_409_CONFLICT, "Вы уже откликнулись на эту публикацию")
        # Re-apply after withdrawing: reuse the row, keep one response per (post, applicant).
        existing.status = "pending"
        existing.message = data.message
        existing.author_note = ""
        existing.decided_at = None
        existing.created_at = datetime.now(UTC)
        response = existing
    else:
        response = Response(post_id=post.id, applicant_id=user.id, message=data.message)
        db.add(response)
    try:
        db.commit()
    except IntegrityError:  # concurrent duplicate request
        db.rollback()
        raise HTTPException(status.HTTP_409_CONFLICT, "Вы уже откликнулись на эту публикацию")
    db.refresh(response)
    return serializers.sent_response(response)


@router.get("/{post_id}/responses", response_model=list[schemas.ReceivedResponseOut])
def post_responses(post_id: int, db: DB, user: CurrentUser):
    post = _load_post(db, post_id)
    if post.author_id != user.id:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Отклики видит только автор публикации")
    responses = db.scalars(
        select(Response)
        .where(Response.post_id == post.id, Response.status != "withdrawn")
        .options(joinedload(Response.applicant))
        .order_by(Response.created_at.desc())
    ).all()
    return [serializers.received_response(r) for r in responses]
