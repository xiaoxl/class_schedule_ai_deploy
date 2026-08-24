"""Shared mapping and validation for configured meeting patterns."""

from __future__ import annotations

from collections.abc import Iterable
from typing import Protocol

from .class_model import (
    Class,
    CoreqClass,
    CrossListingClass,
    FourCreditClass,
    HybridClass,
    NormalClass,
    Section,
)


class MeetingPatternLike(Protocol):
    days: str
    duration_minutes: int
    starts: tuple
    roles: frozenset[str]
    courses: frozenset[str]
    atomic_courses: frozenset[str]


class TimeWindowLike(Protocol):
    def overlaps(self, days, start, end) -> bool: ...


def section_pattern_role(item: Class, section: Section) -> str:
    """Return one structural role without consulting any course number."""
    if isinstance(item, FourCreditClass):
        return (
            "four_credit_primary" if section.days == "MWF"
            else "four_credit_partial"
        )
    if isinstance(item, CoreqClass):
        credits = [part.credit_hours for part in item.sections]
        if min(credits) < max(credits) and section.credit_hours == min(credits):
            return "coreq_supplement"
        return "coreq"
    if isinstance(item, CrossListingClass):
        return "cross_listing"
    if isinstance(item, HybridClass):
        return "hybrid_physical"
    if isinstance(item, NormalClass):
        return "normal"
    raise TypeError(f"Unsupported atomic class type: {type(item).__name__}")


def pattern_applies(
    item: Class, section: Section, pattern: MeetingPatternLike
) -> bool:
    """Match generic structural and course selectors from configuration."""
    if section_pattern_role(item, section) not in pattern.roles:
        return False
    course = f"{section.subject} {section.number}"
    if pattern.courses and course not in pattern.courses:
        return False
    atomic_courses = {
        f"{part.subject} {part.number}" for part in item.sections
    }
    return not pattern.atomic_courses or atomic_courses == pattern.atomic_courses


def matches_configured_pattern(
    item: Class,
    section: Section,
    patterns: Iterable[MeetingPatternLike],
) -> bool:
    """Whether a physical section exactly matches a legal configured slot."""
    return any(
        pattern.days == section.days
        and pattern.duration_minutes == section.duration
        and section.start in pattern.starts
        and pattern_applies(item, section, pattern)
        for pattern in patterns
    )


def overlaps_blackout(
    section: Section, blackouts: Iterable[TimeWindowLike],
) -> bool:
    return any(
        window.overlaps(section.days, section.start, section.end)
        for window in blackouts
    )
