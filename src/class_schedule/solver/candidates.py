"""Generate and price legal instructor/time/room candidates per section."""

from __future__ import annotations

import datetime
from dataclasses import replace

from .. import record_utils
from ..class_model import Class, HybridClass, LabClass, LectureLabClass, Section
from ..new_instructors import can_new_instructor_teach, can_new_professor_teach
from ..instructor_identity import is_new_instructor, is_new_professor
from ..pattern_rules import pattern_applies, section_pattern_role
from ..schedule_model import (
    PersonRecord,
    PreferenceRecord,
    PreferenceRule,
)
from .config import SolverConfig
from .types import MeetingPattern, RoomRecord, SectionCandidate


INSTRUCTOR_CHANGE_COST = 10.0
TIME_CHANGE_COST = 5.0
ROOM_CHANGE_COST = 5.0
MAX_CANDIDATES_PAIRED_SECTION = 10
MAX_CANDIDATES_SINGLE_SECTION = 40


def candidate_instructors(
    section: Section,
    persons: dict[str, PersonRecord],
    placeholder_instructors: tuple[str, ...] = (),
    new_professors: tuple[str, ...] = (),
    *, new_instructor_course_limit: int,
    new_professor_course_minimum: int,
) -> list[str]:
    course = f"{section.subject} {section.number}"
    names = {name for name, person in persons.items() if course in person.courses}
    eligible_for_new = can_new_instructor_teach(
        section, max_course_number_exclusive=new_instructor_course_limit,
    )
    if section.instructor and (
        not is_new_instructor(section.instructor)
        and not is_new_professor(section.instructor)
    ):
        names.add(section.instructor)
    if section.instructor and is_new_instructor(section.instructor) and eligible_for_new:
        names.add(section.instructor)
    if eligible_for_new:
        names.update(placeholder_instructors)
    eligible_for_professor = can_new_professor_teach(
        section, min_course_number_inclusive=new_professor_course_minimum,
    )
    if section.instructor and is_new_professor(section.instructor) and eligible_for_professor:
        names.add(section.instructor)
    if eligible_for_professor:
        names.update(new_professors)
    return sorted(names)


def instructor_change_cost(
    before: str, after: str, placeholder_instructors: tuple[str, ...]
) -> float:
    if before == after:
        return 0.0
    if before in placeholder_instructors and after in placeholder_instructors:
        return 0.0
    return INSTRUCTOR_CHANGE_COST


def preference_cost(
    instructor: str,
    days: str | None,
    start: datetime.time | None,
    end: datetime.time | None,
    building: str,
    room: str,
    course: str,
    section: str,
    preferences: dict[str, PreferenceRecord],
    global_rules: tuple[PreferenceRule, ...] = (),
    *, hybrid_companion: bool = False, room_reservation: bool = False,
) -> float:
    preference = preferences.get(instructor)
    cost = 0.0
    rules = list(global_rules)
    if preference is not None:
        rules.extend(preference.rules)
    for rule in rules:
        if room_reservation and rule.room is None:
            continue
        if rule.matches(
            course=course, section=section, building=building, room=room,
            days=days, start=start, end=end,
            hybrid_companion=hybrid_companion,
        ):
            cost += rule.signed_weight
    return cost


def section_candidates(
    item: Class,
    section: Section,
    config: SolverConfig,
    max_candidates: int | None,
    locked_fields: frozenset[str] = frozenset(),
    placeholder_instructors: tuple[str, ...] = (),
    new_professors: tuple[str, ...] = (),
) -> list[SectionCandidate]:
    course = f"{section.subject} {section.number}"
    lecture_lab = isinstance(item, (LectureLabClass, LabClass))
    if lecture_lab:
        # The lecture is free; lab rooms are fixed and lab time is fixed
        # unless lab_time_editable (see class_model._LectureLabMixin).
        locked_fields = locked_fields | item.solver_locked_fields(section)
    hybrid_companion = isinstance(item, HybridClass) and section.is_online
    current = SectionCandidate(
        instructor=section.instructor,
        time_slot=section.time_slot,
        duration=section.duration,
        days=section.days,
        start=section.start,
        end=section.end,
        room=section.room,
        building=section.building,
        cost=preference_cost(
            section.instructor, section.days, section.start, section.end,
            section.building, section.room, course, section.section,
            config.preferences, config.global_rules,
            hybrid_companion=hybrid_companion,
        ),
    )
    constraints = config.constraints_for(course, section.section)

    def reservation_preference_cost(candidate: SectionCandidate) -> float:
        return sum(
            preference_cost(
                candidate.instructor, reservation.days, reservation.start, reservation.end,
                reservation.building, reservation.room, course, section.section,
                config.preferences, config.global_rules, room_reservation=True,
            )
            for reservation in item.resource_usage(section, apply_candidate(section, candidate))
        )

    current = replace(current, cost=current.cost + reservation_preference_cost(current))

    def constraints_allow(candidate: SectionCandidate) -> bool:
        reservations = (apply_candidate(section, candidate),) + item.resource_usage(
            section, apply_candidate(section, candidate),
        )
        return all(
            rule.allows(
                instructor=candidate.instructor,
                building=reservation.building,
                room=reservation.room,
                days=reservation.days,
                start=reservation.start,
                end=reservation.end,
                is_online=section.is_online,
            )
            for reservation in reservations for rule in constraints
        )

    instructors = (
        candidate_instructors(
            section, config.persons, placeholder_instructors, new_professors,
            new_instructor_course_limit=(
                config.new_instructor_policy.max_course_number_exclusive
            ),
            new_professor_course_minimum=(
                config.new_professor_policy.min_course_number_inclusive
            ),
        )
        or [section.instructor]
    )
    if section.is_online:
        result = sorted((
            SectionCandidate(
                instructor=instructor,
                time_slot=section.time_slot,
                duration=section.duration,
                days=None,
                start=None,
                end=None,
                room=section.room,
                building=section.building,
                cost=instructor_change_cost(
                    section.instructor, instructor, placeholder_instructors + new_professors
                )
                + preference_cost(
                    instructor, None, None, None, section.building, section.room,
                    course, section.section, config.preferences, config.global_rules,
                    hybrid_companion=hybrid_companion,
                ),
            )
            for instructor in instructors
        ), key=lambda candidate: candidate.cost)
        result = [candidate for candidate in result if constraints_allow(candidate)]
        return [candidate for candidate in result if _matches_locks(section, candidate, locked_fields)]

    applicable_patterns = [
        pattern for pattern in config.meeting_patterns
        if pattern_applies(item, section, pattern)
    ]
    explicit_course_patterns = [
        pattern for pattern in applicable_patterns
        if course in pattern.courses
    ]
    patterns = explicit_course_patterns or [
        pattern for pattern in applicable_patterns
        if pattern.duration_minutes == section.duration
    ]
    if lecture_lab:
        patterns = [p for p in patterns if p.duration_minutes == section.duration]
        if "time" in locked_fields:
            patterns = [MeetingPattern(
                section.days, section.duration, (section.start,),
                frozenset({section_pattern_role(item, section)}),
            )]
    current_is_allowed = (
        section.instructor in instructors
        and
        (
            not config.meeting_patterns
            or section.start is not None
            and any(
                pattern.days == section.days
                and pattern.duration_minutes == section.duration
                and section.start in pattern.starts
                for pattern in patterns
            )
        )
        and constraints_allow(current)
    )
    if not config.meeting_patterns and section.days and section.start:
        patterns = [MeetingPattern(
            section.days, section.duration or 0, (section.start,),
            frozenset({section_pattern_role(item, section)}),
        )]
    rooms = config.rooms or [
        RoomRecord(building=section.building, room=section.room)
    ]
    if {"room", "building"} & locked_fields:
        rooms = [RoomRecord(building=section.building, room=section.room)]
    by_instructor: dict[str, dict[tuple[str, str, str], SectionCandidate]] = {
        instructor: {} for instructor in instructors
    }
    for instructor in instructors:
        bucket = by_instructor[instructor]
        for pattern in patterns:
            for start in pattern.starts:
                end = record_utils.add_minutes(start, pattern.duration_minutes)
                time_slot = record_utils.format_slot(pattern.days, start)
                for room in rooms:
                    cost = (
                        instructor_change_cost(
                            section.instructor, instructor, placeholder_instructors + new_professors
                        )
                        + (TIME_CHANGE_COST if time_slot != section.time_slot else 0.0)
                        + (ROOM_CHANGE_COST if (room.building, room.room) != (
                            section.building, section.room
                        ) else 0.0)
                    )
                    cost += preference_cost(
                        instructor, pattern.days, start, end, room.building, room.room,
                        course, section.section, config.preferences, config.global_rules,
                    )
                    candidate = SectionCandidate(
                        instructor, time_slot, pattern.duration_minutes,
                        pattern.days, start, end, room.room, room.building, cost,
                    )
                    candidate = replace(candidate, cost=candidate.cost + reservation_preference_cost(candidate))
                    if constraints_allow(candidate):
                        bucket[(time_slot, room.building, room.room)] = candidate
        if instructor == section.instructor and current_is_allowed:
            bucket[(current.time_slot, current.building, current.room)] = current

    result = []
    for bucket in by_instructor.values():
        result.extend(sorted(bucket.values(), key=lambda candidate: candidate.cost)[:max_candidates])
    if (
        current_is_allowed
        and current not in result
    ):
        result.append(current)
    return [candidate for candidate in result if _matches_locks(section, candidate, locked_fields)]


def _matches_locks(
    section: Section, candidate: SectionCandidate, fields: frozenset[str]
) -> bool:
    return (
        ("instructor" not in fields or candidate.instructor == section.instructor)
        and ("time" not in fields or candidate.time_slot == section.time_slot)
        and ("room" not in fields or candidate.room == section.room)
        and ("building" not in fields or candidate.building == section.building)
    )


def apply_candidate(section: Section, candidate: SectionCandidate) -> Section:
    return replace(
        section,
        instructor=candidate.instructor,
        time_slot=candidate.time_slot,
        duration=candidate.duration,
        room=candidate.room,
        building=candidate.building,
    )
