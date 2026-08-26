"""Normalize dynamic instructor identities before solving."""

from __future__ import annotations

import random

from .class_model import Class
from .instructor_identity import is_new_instructor, new_instructor_name, new_instructor_rank
from .schedule_model import Schedule, overlaps_in_time

def _classes_conflict(a: Class, b: Class) -> bool:
    return any(
        not left.is_online and not right.is_online and overlaps_in_time(left, right)
        for left in a.sections for right in b.sections
    )


def is_placeholder_instructor(instructor: str) -> bool:
    return is_new_instructor(instructor)


def _placeholder_rank(instructor: str) -> int:
    return new_instructor_rank(instructor)


def recolor_placeholder(
    schedule: Schedule,
    *,
    seed: int | None = None,
) -> tuple[Schedule, dict[str, tuple[str, ...]]]:
    """Split overlapping dynamic positions into numbered identities."""
    classes = [
        item for item in schedule.classes
        if any(is_placeholder_instructor(s.instructor) for s in item.sections)
    ]
    order = list(range(len(classes)))
    random.Random(seed).shuffle(order)
    conflicts: dict[int, set[int]] = {index: set() for index in order}
    for left in range(len(classes)):
        for right in range(left + 1, len(classes)):
            if _classes_conflict(classes[left], classes[right]):
                conflicts[left].add(right)
                conflicts[right].add(left)
    colors: dict[int, str] = {}
    for index in order:
        used = {colors[other] for other in conflicts[index] if other in colors}
        rank = 1
        while new_instructor_name(rank) in used:
            rank += 1
        colors[index] = new_instructor_name(rank)

    recolored = Schedule(list(schedule.classes))
    assignments: dict[str, list[str]] = {}
    for index, item in enumerate(classes):
        name = colors[index]
        recolored.change_instructor(item.course_ids[0], name)
        assignments.setdefault(name, []).extend(item.course_ids)
    ordered = sorted(assignments, key=_placeholder_rank)
    return recolored, {name: tuple(assignments[name]) for name in ordered}
