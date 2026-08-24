"""Generate and price legal instructor/time/room candidates per section."""

from __future__ import annotations

import datetime
from dataclasses import replace

from .. import record_utils
from ..class_model import Class, Section
from ..pattern_rules import pattern_applies, section_pattern_role
from ..schedule_model import (
    DISLIKED_COURSE_PENALTY,
    DISLIKED_LOCATION_PENALTY,
    DISLIKED_TIME_PENALTY,
    PREFERS_ONLINE_PENALTY,
    PersonRecord,
    PreferenceRecord,
    PreferenceRule,
    location_matches,
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
) -> list[str]:
    course = f"{section.subject} {section.number}"
    names = {name for name, person in persons.items() if course in person.courses}
    if section.instructor:
        names.add(section.instructor)
    if section.instructor in placeholder_instructors:
        names.update(placeholder_instructors)
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
) -> float:
    preference = preferences.get(instructor)
    cost = 0.0
    rules = list(global_rules)
    if preference is not None:
        rules.extend(preference.rules)
    for rule in rules:
        if rule.matches(
            course=course, section=section, building=building, room=room,
            days=days, start=start, end=end,
        ):
            cost += rule.signed_weight
    if preference is None:
        return cost
    cost -= sum(
        DISLIKED_TIME_PENALTY
        for window in preference.preferred_times
        if window.overlaps(days, start, end)
    )
    cost += sum(
        DISLIKED_TIME_PENALTY
        for window in preference.disliked_times
        if window.overlaps(days, start, end)
    )
    if preference.preferred_locations and location_matches(
        building, room, preference.preferred_locations
    ):
        cost -= DISLIKED_LOCATION_PENALTY
    if preference.disliked_locations and location_matches(
        building, room, preference.disliked_locations
    ):
        cost += DISLIKED_LOCATION_PENALTY
    if course in preference.preferred_courses:
        cost -= DISLIKED_COURSE_PENALTY
    if course in preference.disliked_courses:
        cost += DISLIKED_COURSE_PENALTY
    if preference.prefers_online and days is not None:
        cost += PREFERS_ONLINE_PENALTY
    return cost


def section_candidates(
    item: Class,
    section: Section,
    config: SolverConfig,
    max_candidates: int,
    locked_fields: frozenset[str] = frozenset(),
    placeholder_instructors: tuple[str, ...] = (),
) -> list[SectionCandidate]:
    course = f"{section.subject} {section.number}"
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
        ),
    )
    instructors = candidate_instructors(
        section, config.persons, placeholder_instructors
    ) or [section.instructor]
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
                    section.instructor, instructor, placeholder_instructors
                )
                + preference_cost(
                    instructor, None, None, None, section.building, section.room,
                    course, section.section, config.preferences, config.global_rules,
                ),
            )
            for instructor in instructors
        ), key=lambda candidate: candidate.cost)
        return [candidate for candidate in result if _matches_locks(section, candidate, locked_fields)]

    patterns = [
        pattern for pattern in config.meeting_patterns
        if pattern.duration_minutes == section.duration
        and pattern_applies(item, section, pattern)
    ]
    current_is_allowed = (
        (
            not config.meeting_patterns
            or section.start is not None
            and any(
                pattern.days == section.days and section.start in pattern.starts
                for pattern in patterns
            )
        )
        and not any(
            window.overlaps(section.days, section.start, section.end)
            for window in config.blackouts
        )
    )
    if not config.meeting_patterns and section.days and section.start:
        patterns = [MeetingPattern(
            section.days, section.duration or 0, (section.start,),
            frozenset({section_pattern_role(item, section)}),
        )]
    rooms = config.rooms or [
        RoomRecord(building=section.building, room=section.room)
    ]
    by_instructor: dict[str, dict[tuple[str, str, str], SectionCandidate]] = {
        instructor: {} for instructor in instructors
    }
    for instructor in instructors:
        bucket = by_instructor[instructor]
        for pattern in patterns:
            for start in pattern.starts:
                end = record_utils.add_minutes(start, pattern.duration_minutes)
                if any(window.overlaps(pattern.days, start, end) for window in config.blackouts):
                    continue
                time_slot = record_utils.format_slot(pattern.days, start)
                for room in rooms:
                    cost = (
                        instructor_change_cost(
                            section.instructor, instructor, placeholder_instructors
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
                    bucket[(time_slot, room.building, room.room)] = SectionCandidate(
                        instructor, time_slot, pattern.duration_minutes,
                        pattern.days, start, end, room.room, room.building, cost,
                    )
        if instructor == section.instructor and current_is_allowed:
            bucket[(current.time_slot, current.building, current.room)] = current

    result = []
    for bucket in by_instructor.values():
        result.extend(sorted(bucket.values(), key=lambda candidate: candidate.cost)[:max_candidates])
    if current_is_allowed and current not in result:
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
