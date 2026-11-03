from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

PostKind = Literal["startup", "vacancy"]
PostStatus = Literal["active", "paused", "closed"]
Stage = Literal["idea", "mvp", "early_revenue", "growth"]
WorkFormat = Literal["remote", "office", "hybrid"]
ResponseStatus = Literal["pending", "accepted", "rejected", "withdrawn"]

MAX_SKILLS = 15


def normalize_skills(value: list[str] | None) -> list[str]:
    """Trim, drop empties and case-insensitive duplicates, keep the first spelling."""
    seen: set[str] = set()
    result: list[str] = []
    for raw in value or []:
        skill = " ".join(str(raw).split())[:40]
        if skill and skill.lower() not in seen:
            seen.add(skill.lower())
            result.append(skill)
    if len(result) > MAX_SKILLS:
        raise ValueError(f"Не больше {MAX_SKILLS} навыков")
    return result


def _strip(value: str | None) -> str | None:
    return value.strip() if isinstance(value, str) else value


class ORM(BaseModel):
    model_config = ConfigDict(from_attributes=True)


# ---------- auth / users ----------


class LoginIn(BaseModel):
    email: str = Field(min_length=3, max_length=255, pattern=r"^[^@\s]+@[^@\s]+$")
    password: str = Field(min_length=1, max_length=200)

    @field_validator("email", mode="before")
    @classmethod
    def _email(cls, v: str) -> str:
        return v.strip().lower() if isinstance(v, str) else v


class UserPublic(ORM):
    id: int
    full_name: str
    headline: str
    bio: str
    city: str
    skills: list[str]
    photo_url: str = ""
    avatar_emoji: str = ""


class UserMe(UserPublic):
    email: str | None
    contact: str
    telegram_id: int | None = None


class TelegramLoginIn(BaseModel):
    init_data: str = Field(min_length=1, max_length=4096)


class LoginOut(BaseModel):
    token: str
    user: UserMe


class DemoAccount(BaseModel):
    email: str
    password: str
    full_name: str
    headline: str
    avatar_emoji: str = ""


class ProfileUpdate(BaseModel):
    full_name: str | None = Field(default=None, min_length=2, max_length=120)
    headline: str | None = Field(default=None, max_length=160)
    bio: str | None = Field(default=None, max_length=4000)
    city: str | None = Field(default=None, max_length=80)
    skills: list[str] | None = None
    contact: str | None = Field(default=None, max_length=120)
    avatar_emoji: str | None = Field(default=None, max_length=16)

    _strip_fields = field_validator("full_name", "headline", "bio", "city", "contact", "avatar_emoji", mode="before")(
        _strip
    )

    @field_validator("skills")
    @classmethod
    def _skills(cls, v: list[str] | None) -> list[str] | None:
        return None if v is None else normalize_skills(v)

    @field_validator("avatar_emoji")
    @classmethod
    def _emoji(cls, v: str | None) -> str | None:
        # An avatar is an emoji, not free text: no ASCII (letters, digits, markup), at most 8 code points.
        if v and (len(v) > 8 or any(ord(ch) < 128 for ch in v)):
            raise ValueError("Аватар — это один эмодзи")
        return v


# ---------- posts ----------


class PostBase(BaseModel):
    title: str = Field(min_length=3, max_length=140)
    summary: str = Field(min_length=10, max_length=280)
    description: str = Field(default="", max_length=8000)
    looking_for: str = Field(default="", max_length=4000)
    skills: list[str] = Field(default_factory=list)
    stage: Stage | None = None
    work_format: WorkFormat | None = None
    compensation: str = Field(default="", max_length=120)

    _strip_fields = field_validator(
        "title", "summary", "description", "looking_for", "compensation", mode="before"
    )(_strip)

    @field_validator("skills")
    @classmethod
    def _skills(cls, v: list[str]) -> list[str]:
        return normalize_skills(v)


class PostCreate(PostBase):
    kind: PostKind
    startup_id: int | None = None


class PostUpdate(BaseModel):
    """Partial update. `kind` and `author` are immutable."""

    title: str | None = Field(default=None, min_length=3, max_length=140)
    summary: str | None = Field(default=None, min_length=10, max_length=280)
    description: str | None = Field(default=None, max_length=8000)
    looking_for: str | None = Field(default=None, max_length=4000)
    skills: list[str] | None = None
    stage: Stage | None = None
    work_format: WorkFormat | None = None
    compensation: str | None = Field(default=None, max_length=120)
    startup_id: int | None = None
    status: PostStatus | None = None

    _strip_fields = field_validator(
        "title", "summary", "description", "looking_for", "compensation", mode="before"
    )(_strip)

    @field_validator("skills")
    @classmethod
    def _skills(cls, v: list[str] | None) -> list[str] | None:
        return None if v is None else normalize_skills(v)


class Match(BaseModel):
    """Skills of a post that the viewer (or an applicant) has."""

    matched: list[str]
    total: int


class StartupRef(BaseModel):
    id: int
    title: str
    status: PostStatus


class MyResponseRef(BaseModel):
    id: int
    status: ResponseStatus
    author_contact: str | None = None
    author_contact_link: str | None = None


class PostOut(BaseModel):
    id: int
    kind: PostKind
    title: str
    summary: str
    description: str
    looking_for: str
    skills: list[str]
    stage: Stage | None
    work_format: WorkFormat | None
    compensation: str
    status: PostStatus
    created_at: datetime
    updated_at: datetime
    author: UserPublic
    startup: StartupRef | None = None
    is_own: bool = False
    my_response: MyResponseRef | None = None
    match: Match | None = None
    invited: bool = False
    # Only filled for the author.
    responses_total: int | None = None
    responses_pending: int | None = None
    # For a startup: its open vacancies.
    vacancies: list[StartupRef] = Field(default_factory=list)


class Page(BaseModel):
    items: list[PostOut]
    total: int
    page: int
    page_size: int


# ---------- responses ----------


class ResponseCreate(BaseModel):
    message: str = Field(min_length=10, max_length=2000)

    _strip_fields = field_validator("message", mode="before")(_strip)


class DecisionIn(BaseModel):
    status: Literal["accepted", "rejected"]
    note: str = Field(default="", max_length=1000)

    _strip_fields = field_validator("note", mode="before")(_strip)


class PostBrief(BaseModel):
    id: int
    kind: PostKind
    title: str
    status: PostStatus
    author: UserPublic


class SentResponseOut(BaseModel):
    id: int
    status: ResponseStatus
    message: str
    author_note: str
    created_at: datetime
    decided_at: datetime | None
    post: PostBrief
    # Revealed only when the response is accepted.
    author_contact: str | None = None
    author_contact_link: str | None = None


class ApplicantOut(UserPublic):
    contact: str | None = None
    contact_link: str | None = None


class ReceivedResponseOut(BaseModel):
    id: int
    status: ResponseStatus
    message: str
    author_note: str
    created_at: datetime
    decided_at: datetime | None
    post: PostBrief
    applicant: ApplicantOut
    match: Match | None = None


class CandidateOut(BaseModel):
    user: UserPublic
    match: Match
    invited: bool
    # Only members who logged in via Telegram can receive an invitation message.
    can_notify: bool


class InviteOut(BaseModel):
    invited: bool
    notified: bool
