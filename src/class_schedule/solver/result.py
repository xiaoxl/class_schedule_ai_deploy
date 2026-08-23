"""Reconstruct domain objects from a CP-SAT solution and describe changes."""

from __future__ import annotations

from ortools.sat.python import cp_model

from ..class_model import Class, Section
from ..schedule_model import Schedule
from .candidates import apply_candidate
from .types import SectionCandidate, SectionChange


def apply_solution(
    class_list: list[Class],
    sections: list[Section],
    sections_by_class: dict[int, list[int]],
    candidates: list[list[SectionCandidate]],
    chosen: list[list],
    solver: cp_model.CpSolver,
) -> Schedule:
    classes = []
    for class_index, item in enumerate(class_list):
        rebuilt = []
        for section_index in sections_by_class[class_index]:
            picked = next(
                index for index, variable in enumerate(chosen[section_index])
                if solver.value(variable)
            )
            rebuilt.append(apply_candidate(
                sections[section_index], candidates[section_index][picked]
            ))
        classes.append(type(item)(tuple(rebuilt)))
    return Schedule(classes)


def diff_schedules(before: Schedule, after: Schedule) -> list[SectionChange]:
    def indexed(schedule: Schedule) -> tuple[
        list[tuple[str, int]], dict[tuple[str, int], Section]
    ]:
        order: list[tuple[str, int]] = []
        result: dict[tuple[str, int], Section] = {}
        counts: dict[str, int] = {}
        for item in schedule.classes:
            for section in item.sections:
                occurrence = counts.get(section.course_id, 0)
                counts[section.course_id] = occurrence + 1
                key = (section.course_id, occurrence)
                order.append(key)
                result[key] = section
        return order, result

    before_order, before_sections = indexed(before)
    after_order, after_sections = indexed(after)
    changes = []
    ordered_keys = before_order + [key for key in after_order if key not in before_sections]
    for key in ordered_keys:
        before_section = before_sections.get(key)
        after_section = after_sections.get(key)
        course_id = key[0]
        if before_section is None:
            changes.append(SectionChange(course_id, "status", "", "added"))
            continue
        if after_section is None:
            changes.append(SectionChange(course_id, "status", "present", "removed"))
            continue
        if before_section.instructor != after_section.instructor:
            changes.append(SectionChange(
                course_id, "instructor",
                before_section.instructor, after_section.instructor,
            ))
        if before_section.time_slot != after_section.time_slot:
            changes.append(SectionChange(
                course_id, "time",
                before_section.time_slot, after_section.time_slot,
            ))
        before_room = f"{before_section.building} {before_section.room}".strip()
        after_room = f"{after_section.building} {after_section.room}".strip()
        if before_room != after_room:
            changes.append(SectionChange(
                course_id, "room", before_room, after_room
            ))
    return changes
