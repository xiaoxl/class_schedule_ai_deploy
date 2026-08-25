"""Rules for the dynamic New Instructor pool."""

from __future__ import annotations

import math

from .class_model import Class, Section

NEW_INSTRUCTOR_MAX_LOAD = 15.0
NEW_INSTRUCTOR_COURSE_LIMIT = 2703


def can_new_instructor_teach(section: Section) -> bool:
    """New instructors may teach any numeric course strictly below 2703."""
    try:
        return int(section.number) < NEW_INSTRUCTOR_COURSE_LIMIT
    except ValueError:
        return False


def class_is_eligible(item: Class) -> bool:
    return all(can_new_instructor_teach(section) for section in item.sections)


def required_by_load(classes: list[Class]) -> int:
    credits = sum(item.credit_hours for item in classes if class_is_eligible(item))
    return math.ceil(credits / NEW_INSTRUCTOR_MAX_LOAD) if credits else 0


def required_by_concurrency(classes: list[Class]) -> int:
    """Current-grid peak eligible concurrency, counted by atomic class."""
    eligible = [item for item in classes if class_is_eligible(item)]
    peak = 0
    for day in "MTWRF":
        boundaries = sorted({
            minute
            for item in eligible
            for section in item.sections
            if section.start is not None and section.end is not None
            and day in (section.days or "")
            for minute in (
                section.start.hour * 60 + section.start.minute,
                section.end.hour * 60 + section.end.minute,
            )
        })
        for minute in boundaries:
            active = sum(any(
                section.start is not None and section.end is not None
                and day in (section.days or "")
                and section.start.hour * 60 + section.start.minute <= minute
                < section.end.hour * 60 + section.end.minute
                for section in item.sections
            ) for item in eligible)
            peak = max(peak, active)
    return peak
