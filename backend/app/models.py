from __future__ import annotations

from datetime import datetime

from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import ARRAY
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .db import Base

POST_KINDS = ("startup", "vacancy")
POST_STATUSES = ("active", "paused", "closed")
STARTUP_STAGES = ("idea", "mvp", "early_revenue", "growth")
WORK_FORMATS = ("remote", "office", "hybrid")
RESPONSE_STATUSES = ("pending", "accepted", "rejected", "withdrawn")


def _in(column: str, values: tuple[str, ...]) -> str:
    return f"{column} IN ({', '.join(repr(v) for v in values)})"


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    # Telegram users log in via initData and have no email/password;
    # test accounts have email/password and no telegram_id.
    telegram_id: Mapped[int | None] = mapped_column(BigInteger, unique=True, nullable=True)
    email: Mapped[str | None] = mapped_column(String(255), unique=True, nullable=True)
    password_hash: Mapped[str | None] = mapped_column(String(255), nullable=True)
    full_name: Mapped[str] = mapped_column(String(120))
    headline: Mapped[str] = mapped_column(String(160), default="")
    bio: Mapped[str] = mapped_column(Text, default="")
    city: Mapped[str] = mapped_column(String(80), default="")
    skills: Mapped[list[str]] = mapped_column(ARRAY(String(40)), default=list)
    # How to reach the person (Telegram handle, phone...). Revealed only after an accepted response.
    contact: Mapped[str] = mapped_column(String(120), default="")
    # Avatar: Telegram profile photo if available, otherwise an emoji chosen in the profile.
    photo_url: Mapped[str] = mapped_column(String(512), default="")
    avatar_emoji: Mapped[str] = mapped_column(String(16), default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class AuthSession(Base):
    __tablename__ = "sessions"

    # sha256 of the bearer token; the raw token is never stored.
    token_hash: Mapped[str] = mapped_column(String(64), primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))

    user: Mapped[User] = relationship()


class Post(Base):
    __tablename__ = "posts"
    __table_args__ = (
        CheckConstraint(_in("kind", POST_KINDS), name="posts_kind_check"),
        CheckConstraint(_in("status", POST_STATUSES), name="posts_status_check"),
        CheckConstraint(f"stage IS NULL OR {_in('stage', STARTUP_STAGES)}", name="posts_stage_check"),
        CheckConstraint(
            f"work_format IS NULL OR {_in('work_format', WORK_FORMATS)}", name="posts_format_check"
        ),
        CheckConstraint("kind = 'vacancy' OR startup_id IS NULL", name="posts_startup_link_check"),
        Index("ix_posts_feed", "status", "kind", "created_at"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    author_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    kind: Mapped[str] = mapped_column(String(16))
    # A vacancy may belong to one of the author's startups.
    startup_id: Mapped[int | None] = mapped_column(
        ForeignKey("posts.id", ondelete="SET NULL"), nullable=True, index=True
    )
    title: Mapped[str] = mapped_column(String(140))
    summary: Mapped[str] = mapped_column(String(280))
    description: Mapped[str] = mapped_column(Text, default="")
    looking_for: Mapped[str] = mapped_column(Text, default="")
    skills: Mapped[list[str]] = mapped_column(ARRAY(String(40)), default=list)
    stage: Mapped[str | None] = mapped_column(String(20), nullable=True)
    work_format: Mapped[str | None] = mapped_column(String(20), nullable=True)
    compensation: Mapped[str] = mapped_column(String(120), default="")
    status: Mapped[str] = mapped_column(String(16), default="active")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    author: Mapped[User] = relationship()
    startup: Mapped[Post | None] = relationship(remote_side=[id])


class Response(Base):
    __tablename__ = "responses"
    __table_args__ = (
        UniqueConstraint("post_id", "applicant_id", name="responses_post_applicant_uq"),
        CheckConstraint(_in("status", RESPONSE_STATUSES), name="responses_status_check"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    post_id: Mapped[int] = mapped_column(ForeignKey("posts.id", ondelete="CASCADE"), index=True)
    applicant_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    message: Mapped[str] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(16), default="pending")
    # Optional note from the author when accepting/rejecting.
    author_note: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
    decided_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    post: Mapped[Post] = relationship()
    applicant: Mapped[User] = relationship()
