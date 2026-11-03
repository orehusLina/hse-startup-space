"""Skill matching between members and publications.

Deliberately simple and explainable: a post "fits" a member if they share skills,
and the UI shows exactly which ones ("Совпадает 2 из 3"), instead of an opaque score.
"""

from collections.abc import Iterable

from . import schemas


def _norm(skills: Iterable[str] | None) -> set[str]:
    return {s.strip().lower() for s in skills or [] if s and s.strip()}


def match(member_skills: Iterable[str] | None, post_skills: Iterable[str] | None) -> schemas.Match | None:
    """Which of the post's skills the member has. None if either side has no skills."""
    have = _norm(member_skills)
    wanted = list(post_skills or [])
    if not have or not wanted:
        return None
    return schemas.Match(matched=[s for s in wanted if s.lower() in have], total=len(wanted))


def score(m: schemas.Match | None) -> tuple[int, float]:
    """Sort key: number of shared skills first, then the share of the post's skills covered."""
    if m is None or not m.matched:
        return (0, 0.0)
    return (len(m.matched), len(m.matched) / m.total)
