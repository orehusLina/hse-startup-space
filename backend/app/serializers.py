"""Turning ORM rows into API payloads that depend on *who* is looking."""

from collections.abc import Sequence

from sqlalchemy import case, func, select
from sqlalchemy.orm import Session

from . import matching, schemas
from .models import Invite, Post, Response, User
from .notify import contact_link


def user_public(user: User) -> schemas.UserPublic:
    return schemas.UserPublic.model_validate(user)


def startup_ref(post: Post | None) -> schemas.StartupRef | None:
    if post is None:
        return None
    return schemas.StartupRef(id=post.id, title=post.title, status=post.status)


def post_brief(post: Post) -> schemas.PostBrief:
    return schemas.PostBrief(
        id=post.id, kind=post.kind, title=post.title, status=post.status, author=user_public(post.author)
    )


def response_counts(db: Session, post_ids: Sequence[int]) -> dict[int, tuple[int, int]]:
    """post_id -> (total non-withdrawn, pending)."""
    if not post_ids:
        return {}
    rows = db.execute(
        select(
            Response.post_id,
            func.count().filter(Response.status != "withdrawn"),
            func.sum(case((Response.status == "pending", 1), else_=0)),
        )
        .where(Response.post_id.in_(post_ids))
        .group_by(Response.post_id)
    ).all()
    return {pid: (int(total), int(pending or 0)) for pid, total, pending in rows}


def posts_out(db: Session, posts: Sequence[Post], viewer: User) -> list[schemas.PostOut]:
    ids = [p.id for p in posts]
    my_responses: dict[int, Response] = {}
    if ids:
        my_responses = {
            r.post_id: r
            for r in db.scalars(
                select(Response).where(Response.post_id.in_(ids), Response.applicant_id == viewer.id)
            )
        }
    own_ids = [p.id for p in posts if p.author_id == viewer.id]
    counts = response_counts(db, own_ids)
    invited_ids = set(
        db.scalars(select(Invite.post_id).where(Invite.post_id.in_(ids), Invite.user_id == viewer.id))
    ) if ids else set()

    result = []
    for p in posts:
        out = schemas.PostOut(
            id=p.id,
            kind=p.kind,
            title=p.title,
            summary=p.summary,
            description=p.description,
            looking_for=p.looking_for,
            skills=p.skills or [],
            stage=p.stage,
            work_format=p.work_format,
            compensation=p.compensation,
            status=p.status,
            created_at=p.created_at,
            updated_at=p.updated_at,
            author=user_public(p.author),
            startup=startup_ref(p.startup),
            is_own=p.author_id == viewer.id,
            invited=p.id in invited_ids,
        )
        if not out.is_own:
            out.match = matching.match(viewer.skills, p.skills)
        if (r := my_responses.get(p.id)) is not None:
            accepted = r.status == "accepted"
            out.my_response = schemas.MyResponseRef(
                id=r.id,
                status=r.status,
                author_contact=p.author.contact if accepted else None,
                author_contact_link=contact_link(p.author) if accepted else None,
            )
        if out.is_own:
            out.responses_total, out.responses_pending = counts.get(p.id, (0, 0))
        result.append(out)
    return result


def sent_response(r: Response) -> schemas.SentResponseOut:
    return schemas.SentResponseOut(
        id=r.id,
        status=r.status,
        message=r.message,
        author_note=r.author_note,
        created_at=r.created_at,
        decided_at=r.decided_at,
        post=post_brief(r.post),
        author_contact=r.post.author.contact if r.status == "accepted" else None,
        author_contact_link=contact_link(r.post.author) if r.status == "accepted" else None,
    )


def received_response(r: Response) -> schemas.ReceivedResponseOut:
    applicant = schemas.ApplicantOut.model_validate(r.applicant)
    # Contacts are exchanged both ways only after the author accepts.
    accepted = r.status == "accepted"
    applicant.contact = r.applicant.contact if accepted else None
    applicant.contact_link = contact_link(r.applicant) if accepted else None
    return schemas.ReceivedResponseOut(
        id=r.id,
        status=r.status,
        message=r.message,
        author_note=r.author_note,
        created_at=r.created_at,
        decided_at=r.decided_at,
        post=post_brief(r.post),
        applicant=applicant,
        match=matching.match(r.applicant.skills, r.post.skills),
    )
