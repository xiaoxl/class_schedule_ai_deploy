"""Eligibility and capacity rules for both dynamic position pools."""

from __future__ import annotations

from .class_model import Section

def can_new_instructor_teach(
    section: Section, *, max_course_number_exclusive: int,
) -> bool:
    """Apply the package-configured exclusive numeric course limit."""
    try:
        return int(section.number) < max_course_number_exclusive
    except ValueError:
        return False


def can_new_professor_teach(
    section: Section, *, min_course_number_inclusive: int,
) -> bool:
    try:
        return int(section.number) >= min_course_number_inclusive
    except ValueError:
        return False
