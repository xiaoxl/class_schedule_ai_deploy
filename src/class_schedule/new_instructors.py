"""Rules for the dynamic New Instructor pool."""

from __future__ import annotations

import math

from .class_model import Class, Section

def can_new_instructor_teach(
    section: Section, *, max_course_number_exclusive: int,
) -> bool:
    """Apply the package-configured exclusive numeric course limit."""
    try:
        return int(section.number) < max_course_number_exclusive
    except ValueError:
        return False


def class_is_eligible(
    item: Class, *, max_course_number_exclusive: int,
) -> bool:
    return all(can_new_instructor_teach(
        section, max_course_number_exclusive=max_course_number_exclusive,
    ) for section in item.sections)


def required_by_load(
    classes: list[Class], *, contract_load: float,
    max_course_number_exclusive: int,
) -> int:
    credits = sum(item.credit_hours for item in classes if class_is_eligible(
        item, max_course_number_exclusive=max_course_number_exclusive,
    ))
    return math.ceil(credits / contract_load) if credits else 0


def required_by_concurrency(
    classes: list[Class], *, max_course_number_exclusive: int,
) -> int:
    """Current-grid peak eligible concurrency, counted by atomic class."""
    eligible = [item for item in classes if class_is_eligible(
        item, max_course_number_exclusive=max_course_number_exclusive,
    )]
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
