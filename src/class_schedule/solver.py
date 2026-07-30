"""Search for the best legal reassignment of an existing ``Schedule``.

Given a ``Schedule`` plus config (persons.toml, preferences.toml,
timeslot.toml, locations.toml), find new (instructor, time, room)
assignments for every class such that:

  - hard requirements (``schedule_model.check_conflicts`` -- the only hard-
    violation source; see its docstring) are enforced as genuine CP-SAT
    hard constraints (``add_no_overlap`` over per-candidate optional
    intervals, bucketed by room/day and instructor/day -- see
    ``_add_scheduling_constraints``), not a penalized objective term. If no
    conflict-free assignment exists within the candidate pool,
    ``solve()`` raises ``NoFeasibleSchedule`` rather than returning a
    best-effort schedule with conflicts still in it -- see its docstring;
  - the total soft-preference penalty (``schedule_model.check_soft_preferences``'s
    scoring, replicated here as CP-SAT objective terms -- including
    max_load, which is always soft) is as low as possible;
  - among equally-good solutions, prefer changing as few classes as
    possible from the input (a small stability tiebreaker).

This is a real assignment/optimization problem (OR-Tools CP-SAT), not a
heuristic -- each class-kind's own pairing rule (FourCreditClass's day
pairing, CoreqClass's is_valid_schedule, HybridClass's is_hybrid,
CrossListingClass's is_honors_pair) is enforced during model-building by
calling that class's own predicate on throwaway candidate Sections, never
re-derived here. The winning assignment is applied by reconstructing each
class through its own constructor (``type(item)(new_sections)``), which
re-runs the exact same ``validate()`` -- not by mutating a Section
directly, and not by chaining ``change_time``/``change_room``/
``change_instructor`` one field at a time, which can spuriously reject a
valid final state via an invalid intermediate one on two-section classes.
"""

from __future__ import annotations

import datetime
import random
import tomllib
from dataclasses import dataclass, replace
from pathlib import Path

from ortools.sat.python import cp_model

from . import record_utils
from .class_model import (
    Class,
    CoreqClass,
    CrossListingClass,
    FourCreditClass,
    HybridClass,
    Section,
)
from .schedule_model import (
    OVERLOAD_TOLERANCE,
    OVERLOAD_FAR_THRESHOLD,
    OVERLOAD_FAR_PENALTY,
    BACK_TO_BACK_PENALTY,
    DISLIKED_COURSE_PENALTY,
    DISLIKED_LOCATION_PENALTY,
    DISLIKED_TIME_PENALTY,
    PersonRecord,
    PreferenceRecord,
    PreferenceRule,
    Schedule,
    TimeWindow,
    UNDER_LOAD_PENALTY,
    load_global_rules,
    load_persons,
    load_preferences,
    location_matches,
)


class NoFeasibleSchedule(RuntimeError):
    """No assignment exists with zero hard violations, or the solver
    couldn't find one within the time limit."""


# ---- stability tiebreaker: "prefer not to move things" -- on the same
# 0-100 penalty scale as schedule_model.py's own constants, scaled down
# proportionally so a real preference/load violation always outweighs
# pure churn.
INSTRUCTOR_CHANGE_COST = 10.0
TIME_CHANGE_COST = 5.0
ROOM_CHANGE_COST = 5.0

# Cap candidates *per qualified instructor*, not per section overall --
# ranked by cost within each instructor's own bucket, so every qualified
# instructor keeps some representation (needed e.g. to fix an overload by
# reassigning). The cap itself depends on whether the section's class has
# one row or two: a two-section class's pairwise validity check is
# O(candidates_left x candidates_right), so it gets the tighter cap; a
# one-section class (NormalClass) never gets compared against its own
# other half, so it can afford a somewhat larger one.
#
# These specific numbers (halved from a prior 80/20) come from profiling
# solve() against real production files after the add_no_overlap rewrite
# (see _add_scheduling_constraints): even with conflicts no longer
# enumerated pairwise, CP-SAT's own search-time memory for an 80/20 model
# still peaked around 520 MB on a real ~60-class schedule -- over Render's
# 512 MB instance limit -- and, worse, only reached a FEASIBLE (not
# OPTIMAL) result in the full 60s budget, i.e. the larger candidate pool
# was making the search *worse*, not just more expensive. At 40/10, the
# same file peaked at ~216 MB and solved to OPTIMAL in ~15s. The
# trade-off is real -- fewer candidates per instructor means a genuine
# structural conflict has fewer chances to be resolved before solve()
# gives up and raises NoFeasibleSchedule -- but it wasn't observed on
# either real file profiled here.
MAX_CANDIDATES_PAIRED_SECTION = 10
MAX_CANDIDATES_SINGLE_SECTION = 40


# ---- config: meeting patterns + rooms (config/timeslot.toml, config/locations.toml) ----
#
# Neither file is read anywhere else in the codebase yet -- this is the
# first thing that needs a legal-time/legal-room catalog rather than just
# validating whatever a CSV already contains.

@dataclass(frozen=True)
class MeetingPattern:
    days: str
    duration_minutes: int
    starts: tuple[datetime.time, ...]
    types: frozenset[str] = frozenset()


@dataclass(frozen=True)
class RoomRecord:
    building: str
    room: str


def load_meeting_patterns(path: str | Path) -> list[MeetingPattern]:
    """Parse ``timeslot.toml``'s ``[[calendar.meeting_patterns]]``."""
    with open(path, "rb") as handle:
        raw = tomllib.load(handle)
    return [
        MeetingPattern(
            days=str(entry["days"]),
            duration_minutes=int(entry["duration_minutes"]),
            starts=tuple(record_utils.clock(s) for s in entry["starts"]),
            types=frozenset(entry.get("types", ())),
        )
        for entry in raw.get("calendar", {}).get("meeting_patterns", ())
    ]


def load_blackouts(path: str | Path) -> list[TimeWindow]:
    """Parse ``timeslot.toml``'s ``[[calendar.blackouts]]``."""
    with open(path, "rb") as handle:
        raw = tomllib.load(handle)
    return [
        TimeWindow.from_config(window)
        for window in raw.get("calendar", {}).get("blackouts", ())
    ]


def load_rooms(path: str | Path) -> list[RoomRecord]:
    """Parse ``locations.toml``'s ``[[rooms]]`` (skips unavailable ones).

    A room's ``name`` is the full "Building Room" string (matching
    ``Section``'s own convention) and ``location`` is just the building.
    """
    with open(path, "rb") as handle:
        raw = tomllib.load(handle)
    rooms = []
    for entry in raw.get("rooms", ()):
        if not entry.get("available", True):
            continue
        name = str(entry["name"])
        building = str(entry.get("location", ""))
        room = (
            name[len(building):].strip()
            if building and name.startswith(building)
            else name
        )
        rooms.append(RoomRecord(building=building, room=room))
    return rooms


@dataclass(frozen=True)
class SolverConfig:
    """Everything the solver needs from ``config/``, bundled for one call."""

    persons: dict[str, PersonRecord]
    preferences: dict[str, PreferenceRecord]
    meeting_patterns: list[MeetingPattern]
    rooms: list[RoomRecord]
    blackouts: list[TimeWindow]
    global_rules: tuple[PreferenceRule, ...] = ()

    @classmethod
    def load(cls, config_dir: str | Path) -> "SolverConfig":
        config_dir = Path(config_dir)
        return cls(
            persons=load_persons(config_dir / "persons.toml"),
            preferences=load_preferences(config_dir / "preferences.toml"),
            meeting_patterns=load_meeting_patterns(config_dir / "timeslot.toml"),
            rooms=load_rooms(config_dir / "locations.toml"),
            blackouts=load_blackouts(config_dir / "timeslot.toml"),
            global_rules=load_global_rules(config_dir / "preferences.toml"),
        )


# ---- candidates: legal (instructor, time, room) options per section ----

@dataclass(frozen=True)
class SectionCandidate:
    instructor: str
    time_slot: str
    duration: int | None
    days: str | None
    start: datetime.time | None
    end: datetime.time | None
    room: str
    building: str
    cost: float


# The one whitelisted coreq pair (class_model.CoreqClass.COURSE_PAIRS)
# with mismatched credit hours -- MATH 1110 is 2 credits, not 3 like
# every other whitelisted partner -- so its own legal meeting patterns
# are the shorter "coreq_short" set (see timeslot.toml's own header
# comment), not the "standard" set every other coreq pair searches.
_COREQ_SHORT_PAIR = frozenset({"MATH 1113", "MATH 1110"})


def _allowed_pattern_types(item: Class, section: Section) -> frozenset[str]:
    """Which MeetingPattern ``types`` this section may search over (see
    timeslot.toml's own header comment), per the scheduling convention
    for its class kind."""
    if isinstance(item, FourCreditClass):
        return (
            frozenset({"standard"}) if section.days == "MWF"
            else frozenset({"four_credit_partial"})
        )
    if isinstance(item, CoreqClass):
        course_ids = {f"{s.subject} {s.number}" for s in item.sections}
        if course_ids == _COREQ_SHORT_PAIR:
            return frozenset({"coreq_short"})
    return frozenset({"standard"})


def _candidate_instructors(
    section: Section, persons: dict[str, PersonRecord]
) -> list[str]:
    """Instructors eligible to teach this section: whoever's persons.toml
    ``courses`` list includes it, plus whoever's already on it (so the
    domain is never empty even for an unlisted course/instructor)."""
    course = f"{section.subject} {section.number}"
    names = {name for name, person in persons.items() if course in person.courses}
    if section.instructor:
        names.add(section.instructor)
    return sorted(names)


def _preference_cost(
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
    """The parts of ``check_soft_preferences`` decidable from one
    candidate alone (disliked_time/disliked_location/disliked_course,
    plus every matching ``PreferenceRule`` -- ``global_rules`` and, if
    this instructor has a preferences.toml entry, their own ``rules``
    too). Overload and back-to-back need cross-candidate context and are
    modeled separately as CP-SAT objective terms.
    ``preferred_courses``/``preferred_locations`` are intentionally not
    costed here either, matching ``check_soft_preferences``'s
    "informational, not scored" treatment of every ``preferred_*`` field
    -- unlike those, a ``PreferenceRule`` with ``direction="prefer"`` *is*
    costed here (as a negative cost/reward), since it's an explicit rule,
    not one of the old blanket-unscored fields."""
    preference = preferences.get(instructor)
    cost = 0.0
    applicable_rules = list(global_rules)
    if preference is not None:
        applicable_rules.extend(preference.rules)
    for rule in applicable_rules:
        if rule.matches(
            course=course, section=section, building=building, room=room,
            days=days, start=start, end=end,
        ):
            cost += rule.signed_weight
    if preference is None:
        return cost
    for window in preference.disliked_times:
        if window.overlaps(days, start, end):
            cost += DISLIKED_TIME_PENALTY
    if preference.disliked_locations and location_matches(
        building, room, preference.disliked_locations
    ):
        cost += DISLIKED_LOCATION_PENALTY
    if course in preference.disliked_courses:
        cost += DISLIKED_COURSE_PENALTY
    return cost


def _section_candidates(
    section: Section, config: SolverConfig, max_candidates: int,
    allowed_types: frozenset[str],
) -> list[SectionCandidate]:
    course = f"{section.subject} {section.number}"
    current_cost = _preference_cost(
        section.instructor, section.days, section.start, section.end,
        section.building, section.room, course, section.section,
        config.preferences, config.global_rules,
    )
    current = SectionCandidate(
        instructor=section.instructor,
        time_slot=section.time_slot,
        duration=section.duration,
        days=section.days,
        start=section.start,
        end=section.end,
        room=section.room,
        building=section.building,
        cost=current_cost,
    )
    if section.is_online:
        # Arranged/online meetings have no time or room to search over --
        # leave them exactly as they are.
        return [current]

    instructors = _candidate_instructors(section, config.persons) or [
        section.instructor
    ]
    patterns = [
        p for p in config.meeting_patterns
        if p.duration_minutes == section.duration and p.types & allowed_types
    ]
    if not patterns and section.days and section.start:
        # Nothing in timeslot.toml matches this section's own duration
        # *and* allowed_types -- fall back to its current pattern so it
        # isn't dropped from the search (an empty domain would make the
        # whole model infeasible).
        patterns = [MeetingPattern(
            days=section.days,
            duration_minutes=section.duration or 0,
            starts=(section.start,),
        )]
    rooms = config.rooms or [RoomRecord(building=section.building, room=section.room)]

    # Capped per instructor, not globally by raw cost -- a global top-K
    # would let the current instructor's (cheaper, no
    # INSTRUCTOR_CHANGE_COST) candidates crowd out every other qualified
    # instructor's options entirely, making instructor reassignment
    # (needed e.g. to fix an overload) impossible even when legal.
    by_instructor: dict[str, dict[tuple[str, str, str], SectionCandidate]] = {
        instructor: {} for instructor in instructors
    }
    for instructor in instructors:
        bucket = by_instructor[instructor]
        for pattern in patterns:
            for start in pattern.starts:
                end = record_utils.add_minutes(start, pattern.duration_minutes)
                if any(w.overlaps(pattern.days, start, end) for w in config.blackouts):
                    continue
                time_slot = record_utils.format_slot(pattern.days, start)
                for room in rooms:
                    cost = 0.0
                    if instructor != section.instructor:
                        cost += INSTRUCTOR_CHANGE_COST
                    if time_slot != section.time_slot:
                        cost += TIME_CHANGE_COST
                    if (room.building, room.room) != (section.building, section.room):
                        cost += ROOM_CHANGE_COST
                    cost += _preference_cost(
                        instructor, pattern.days, start, end,
                        room.building, room.room, course, section.section,
                        config.preferences, config.global_rules,
                    )
                    key = (time_slot, room.building, room.room)
                    bucket[key] = SectionCandidate(
                        instructor=instructor,
                        time_slot=time_slot,
                        duration=pattern.duration_minutes,
                        days=pattern.days,
                        start=start,
                        end=end,
                        room=room.room,
                        building=room.building,
                        cost=cost,
                    )
        if instructor == section.instructor:
            bucket[(current.time_slot, current.building, current.room)] = current

    result: list[SectionCandidate] = []
    for instructor, bucket in by_instructor.items():
        ranked = sorted(bucket.values(), key=lambda c: c.cost)
        result.extend(ranked[:max_candidates])
    if not any(
        c.instructor == current.instructor
        and c.time_slot == current.time_slot
        and c.room == current.room
        and c.building == current.building
        for c in result
    ):
        result.append(current)
    return result


def _apply_candidate(section: Section, candidate: SectionCandidate) -> Section:
    return replace(
        section,
        instructor=candidate.instructor,
        time_slot=candidate.time_slot,
        duration=candidate.duration,
        room=candidate.room,
        building=candidate.building,
    )


# ---- model building ----

def _predicate_for(item: Class):
    """The class-kind's own rule for whether two candidate Sections form
    a legal pair -- ``None`` means no cross-section coupling to enforce
    (e.g. an explicit Cross-List code pair: only the CSV's Cross-List
    value ties them together, not their time/room/instructor)."""
    if isinstance(item, FourCreditClass):
        return FourCreditClass.is_four_credit
    if isinstance(item, HybridClass):
        return HybridClass.is_hybrid
    if isinstance(item, CoreqClass):
        return CoreqClass.is_valid_schedule
    if isinstance(item, CrossListingClass):
        left, right = item.sections
        if left.cross_list and left.cross_list == right.cross_list:
            return None
        return CrossListingClass.is_honors_pair
    return None


def _add_pairwise_validity_constraints(
    class_list: list[Class],
    sections: list[Section],
    sections_by_class: dict[int, list[int]],
    candidates: list[list[SectionCandidate]],
    chosen: list[list],
    model: cp_model.CpModel,
) -> None:
    for class_index, item in enumerate(class_list):
        indices = sections_by_class.get(class_index, [])
        if len(indices) != 2:
            continue
        i0, i1 = indices
        predicate = _predicate_for(item)
        # One class, one instructor -- always, even for kinds whose own
        # is_xxx predicate doesn't happen to check this (HybridClass,
        # an explicit-Cross-List-code CrossListingClass pair). Without
        # this, the two sections could end up with different instructors
        # in the solved output, which _add_load_terms (keyed off just
        # the primary section) would never see coming.
        for j, candidate_a in enumerate(candidates[i0]):
            for m, candidate_b in enumerate(candidates[i1]):
                mismatched_instructor = candidate_a.instructor != candidate_b.instructor
                if mismatched_instructor:
                    model.add_bool_or([chosen[i0][j].Not(), chosen[i1][m].Not()])
                    continue
                if predicate is None:
                    continue
                section_a = _apply_candidate(sections[i0], candidate_a)
                section_b = _apply_candidate(sections[i1], candidate_b)
                if not predicate(section_a, section_b):
                    model.add_bool_or([chosen[i0][j].Not(), chosen[i1][m].Not()])


@dataclass(frozen=True)
class _Slot:
    section: int
    candidate: int
    class_index: int
    days: str
    start: datetime.time
    end: datetime.time
    room_key: str
    instructor: str


def _build_slots(
    sections: list[Section],
    owner: list[int],
    candidates: list[list[SectionCandidate]],
) -> list[_Slot]:
    slots = []
    for i in range(len(sections)):
        for j, candidate in enumerate(candidates[i]):
            if candidate.days is None or candidate.start is None or candidate.end is None:
                continue  # arranged/online -- nothing to conflict on
            room_key = f"{candidate.building} {candidate.room}".strip()
            slots.append(_Slot(
                section=i, candidate=j, class_index=owner[i],
                days=candidate.days, start=candidate.start, end=candidate.end,
                room_key=room_key, instructor=candidate.instructor,
            ))
    return slots


def _add_scheduling_constraints(
    slots: list[_Slot],
    chosen: list[list],
    preferences: dict[str, PreferenceRecord],
    model: cp_model.CpModel,
) -> list:
    """Room/instructor double-booking is a hard constraint (see the module
    docstring on why this replaced the old penalized-soft-term approach):
    bucketed by (room-or-instructor, weekday) into ``add_no_overlap`` over
    one optional interval per candidate, present iff that candidate is
    ``chosen`` -- O(candidates) intervals instead of the O(candidates^2)
    pairwise conflict BoolVars this replaced, which is what let a real
    85-section schedule's model-build alone reach ~3.8 GB RSS.

    A class's own two sections are never checked against *each other*
    (``schedule_model``'s "a class's own two rows are never compared"
    invariant -- a genuine cross-listing/four-credit/hybrid/coreq pair is
    meant to share room/time/instructor). ``add_no_overlap`` can't express
    that exemption directly, so a class that contributes two intervals to
    the same bucket is pulled out of that bucket's group call and checked
    against everyone *else* in the bucket via a handful of explicit
    pairwise constraints instead -- bounded by the number of two-section
    classes that happen to land in one bucket (essentially always 0-1 in
    practice), not by candidate-pool size, so it doesn't reintroduce the
    quadratic blowup.

    Also collects the back-to-back soft-penalty objective terms (still a
    preference, not a hard rule) via a start-time index rather than
    all-pairs, since only exactly-adjacent candidates ever qualify.
    """
    by_room_day: dict[tuple[str, str], list[int]] = {}
    by_instructor_day: dict[tuple[str, str], list[int]] = {}
    intervals: list = [None] * len(slots)

    for index, slot in enumerate(slots):
        start_minutes = slot.start.hour * 60 + slot.start.minute
        end_minutes = slot.end.hour * 60 + slot.end.minute
        if end_minutes <= start_minutes:
            end_minutes += 24 * 60
        intervals[index] = model.new_optional_interval_var(
            start_minutes, end_minutes - start_minutes, end_minutes,
            chosen[slot.section][slot.candidate], f"iv_{slot.section}_{slot.candidate}",
        )
        for day in slot.days:
            if slot.room_key:
                by_room_day.setdefault((slot.room_key, day), []).append(index)
            if slot.instructor:
                by_instructor_day.setdefault((slot.instructor, day), []).append(index)

    def _add_bucket_no_overlap(indices: list[int]) -> None:
        # Grouped by class, then by *distinct section* -- a single section
        # can legitimately contribute many of its own candidate-time
        # options to the same bucket (same room/day, different times),
        # and those never need the exemption below: `chosen`'s
        # exactly-one already keeps a section's own candidates mutually
        # exclusive, so sharing one add_no_overlap call is safe. Only a
        # class whose *two different sections* both land here needs to be
        # pulled out, since that's the only case add_no_overlap can't
        # express (see docstring).
        sections_by_class: dict[int, set[int]] = {}
        for i in indices:
            sections_by_class.setdefault(slots[i].class_index, set()).add(slots[i].section)
        exempt_classes = {c for c, secs in sections_by_class.items() if len(secs) > 1}
        solo = [i for i in indices if slots[i].class_index not in exempt_classes]
        paired = [i for i in indices if slots[i].class_index in exempt_classes]
        if len(solo) > 1:
            model.add_no_overlap([intervals[i] for i in solo])
        for i in paired:
            a = slots[i]
            for j in indices:
                if j == i or slots[j].class_index == a.class_index:
                    continue
                b = slots[j]
                if a.start < b.end and b.start < a.end:
                    model.add_bool_or([
                        chosen[a.section][a.candidate].Not(),
                        chosen[b.section][b.candidate].Not(),
                    ])

    for indices in by_room_day.values():
        if len(indices) > 1:
            _add_bucket_no_overlap(indices)

    objective_terms = []
    for (instructor, _day), indices in by_instructor_day.items():
        if len(indices) > 1:
            _add_bucket_no_overlap(indices)
        preference = preferences.get(instructor)
        if preference is None or preference.allow_back_to_back:
            continue
        by_start: dict[datetime.time, list[int]] = {}
        for i in indices:
            by_start.setdefault(slots[i].start, []).append(i)
        seen_pairs: set[tuple[int, int]] = set()
        for i in indices:
            a = slots[i]
            for j in by_start.get(a.end, ()):
                b = slots[j]
                if a.class_index == b.class_index:
                    continue
                key = (i, j) if i < j else (j, i)
                if key in seen_pairs:
                    continue
                seen_pairs.add(key)
                both = model.new_bool_var(
                    f"b2b_{a.section}_{a.candidate}_{b.section}_{b.candidate}"
                )
                model.add(both <= chosen[a.section][a.candidate])
                model.add(both <= chosen[b.section][b.candidate])
                model.add(
                    both >= chosen[a.section][a.candidate] + chosen[b.section][b.candidate] - 1
                )
                objective_terms.append(BACK_TO_BACK_PENALTY * both)
    return objective_terms


def _add_load_terms(
    class_list: list[Class],
    sections_by_class: dict[int, list[int]],
    candidates: list[list[SectionCandidate]],
    chosen: list[list],
    persons: dict[str, PersonRecord],
    preferences: dict[str, PreferenceRecord],
    model: cp_model.CpModel,
) -> list:
    """max_load is a per-instructor TARGET, not just a ceiling -- mirrors
    ``schedule_model``'s overload/under_load contract exactly (see its
    module docstring): always-soft terms, never a hard violation. A soft
    term weighted by ``preference.overload_penalty`` (derived from
    ``allow_overload``; see ``PreferenceRecord``) beyond
    max_load + OVERLOAD_TOLERANCE, flat and one-time rather than scaled by
    how many credit hours over -- see the module comment above
    OVERLOAD_TOLERANCE in schedule_model.py for why: scaling this (either
    a continuous excess-times-rate calculation, or a multi-tier cumulative
    boolean scheme) measurably slowed CP-SAT's search on a real schedule
    each time it was tried, for reasons that didn't reduce to any single
    identifiable modeling choice. A second, independent flat term
    (OVERLOAD_FAR_PENALTY) applies on top once an instructor goes more
    than OVERLOAD_FAR_THRESHOLD credit hours over their own max_load --
    identical convention to OVERLOAD_TOLERANCE, just a second,
    further-out line, for ``allow_overload=True`` only -- ``False``
    already sits at this system's 100-point ceiling. A heavily-weighted
    soft term (UNDER_LOAD_PENALTY) for anyone left short of their target
    -- "must reach max_load" should dominate ordinary soft preferences,
    but an instructor with no reachable course left to fill the gap is
    accepted rather than modeled as impossible. Load is attributed via
    each class's *first* section's instructor, matching how a class's own
    predicate already forces the two sections of FourCreditClass/CoreqClass
    to share one instructor; HybridClass/CrossListingClass don't enforce
    that, so a mismatched second section is a rare, accepted edge case.
    """
    load_scale = 10
    per_instructor: dict[str, list] = {}
    for class_index, item in enumerate(class_list):
        primary = sections_by_class[class_index][0]
        units = int(round(item.credit_hours * load_scale))
        if not units:
            continue
        for j, candidate in enumerate(candidates[primary]):
            per_instructor.setdefault(candidate.instructor, []).append(
                units * chosen[primary][j]
            )

    objective_terms = []
    for instructor, terms in per_instructor.items():
        person = persons.get(instructor)
        if person is None:
            continue
        total = sum(terms)
        target = int(round(person.max_load * load_scale))
        limit = int(round((person.max_load + OVERLOAD_TOLERANCE) * load_scale))
        preference = preferences.get(instructor)
        penalty_weight = preference.overload_penalty if preference else 0.0
        if penalty_weight:
            over = model.new_bool_var(f"overload_{instructor}")
            model.add(total > limit).only_enforce_if(over)
            model.add(total <= limit).only_enforce_if(over.Not())
            objective_terms.append(penalty_weight * over)

            if preference.allow_overload:
                far_limit = int(round((person.max_load + OVERLOAD_FAR_THRESHOLD) * load_scale))
                far_over = model.new_bool_var(f"overload_far_{instructor}")
                model.add(total > far_limit).only_enforce_if(far_over)
                model.add(total <= far_limit).only_enforce_if(far_over.Not())
                objective_terms.append(OVERLOAD_FAR_PENALTY * far_over)

        under = model.new_bool_var(f"under_load_{instructor}")
        model.add(total < target).only_enforce_if(under)
        model.add(total >= target).only_enforce_if(under.Not())
        objective_terms.append(UNDER_LOAD_PENALTY * under)
    return objective_terms


def _apply_solution(
    class_list: list[Class],
    sections: list[Section],
    sections_by_class: dict[int, list[int]],
    candidates: list[list[SectionCandidate]],
    chosen: list[list],
    solver: cp_model.CpSolver,
) -> Schedule:
    new_classes = []
    for class_index, item in enumerate(class_list):
        new_sections = []
        for i in sections_by_class[class_index]:
            picked = next(j for j, var in enumerate(chosen[i]) if solver.value(var))
            new_sections.append(_apply_candidate(sections[i], candidates[i][picked]))
        new_classes.append(type(item)(tuple(new_sections)))
    return Schedule(new_classes)


@dataclass(frozen=True)
class SectionChange:
    course_id: str
    field: str  # "instructor" | "time" | "room"
    before: str
    after: str


def diff_schedules(before: Schedule, after: Schedule) -> list[SectionChange]:
    """Describe what ``solve()`` actually changed.

    Assumes ``after`` came from ``solve(before, ...)``: same classes in
    the same order, each with the same number of sections -- the solver
    only ever adjusts instructor/time/room, never restructures the
    schedule, so this holds by construction.
    """
    changes: list[SectionChange] = []
    for before_item, after_item in zip(before.classes, after.classes):
        for before_section, after_section in zip(
            before_item.sections, after_item.sections
        ):
            course_id = before_section.course_id
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
                changes.append(SectionChange(course_id, "room", before_room, after_room))
    return changes


def solve(
    schedule: Schedule,
    config: SolverConfig,
    *,
    time_limit_seconds: float = 30.0,
    previous: Schedule | None = None,
) -> Schedule:
    """Return a new ``Schedule`` with the best reassignment found.

    "Hard" requirements (room/instructor conflicts -- see
    ``schedule_model.check_conflicts``) are unconditional CP-SAT
    constraints (``add_no_overlap``), not a penalized objective term --
    a solved result therefore always has zero conflicts, never a
    best-effort schedule with conflicts still in it.

    Raises ``NoFeasibleSchedule`` whenever no conflict-free assignment
    exists within the candidate pool -- a section with zero legal
    candidates, a genuine structural conflict no reassignment can avoid,
    or the solver finding no assignment whatsoever (not even a bad one)
    within ``time_limit_seconds``. Callers should treat this as "nothing
    to offer for this input," not as a bug to retry.

    Every call uses a fresh random search seed, so re-solving the same
    input twice isn't guaranteed to reproduce the exact same result. Pass
    ``previous`` (typically the caller's own prior solve output) to make
    that a *guarantee* rather than a possibility: a "no-good" cut forbids
    reproducing ``previous``'s exact full assignment, so the result is
    always different from it by at least one section -- useful for "give
    me another option" re-solves. It can still score worse than
    ``previous``; nothing about the cut favors a better solution, only a
    different one.
    """
    class_list = list(schedule.classes)
    sections: list[Section] = []
    owner: list[int] = []
    for class_index, item in enumerate(class_list):
        for section in item.sections:
            sections.append(section)
            owner.append(class_index)

    candidates = [
        _section_candidates(
            section, config,
            MAX_CANDIDATES_SINGLE_SECTION
            if len(class_list[owner[i]].sections) == 1
            else MAX_CANDIDATES_PAIRED_SECTION,
            _allowed_pattern_types(class_list[owner[i]], section),
        )
        for i, section in enumerate(sections)
    ]
    empty = [sections[i].course_id for i, c in enumerate(candidates) if not c]
    if empty:
        raise NoFeasibleSchedule(f"No legal candidates for: {', '.join(empty)}")

    sections_by_class: dict[int, list[int]] = {}
    for i, class_index in enumerate(owner):
        sections_by_class.setdefault(class_index, []).append(i)

    model = cp_model.CpModel()
    chosen = [
        [model.new_bool_var(f"s{i}_c{j}") for j in range(len(candidates[i]))]
        for i in range(len(sections))
    ]
    for variables in chosen:
        model.add_exactly_one(variables)

    _add_pairwise_validity_constraints(
        class_list, sections, sections_by_class, candidates, chosen, model
    )
    slots = _build_slots(sections, owner, candidates)
    back_to_back_terms = _add_scheduling_constraints(
        slots, chosen, config.preferences, model
    )
    load_terms = _add_load_terms(
        class_list, sections_by_class, candidates, chosen,
        config.persons, config.preferences, model,
    )

    stability_terms = [
        candidate.cost * chosen[i][j]
        for i, section_candidates in enumerate(candidates)
        for j, candidate in enumerate(section_candidates)
    ]
    model.minimize(sum(stability_terms) + sum(back_to_back_terms) + sum(load_terms))

    # "Leave everything exactly as it is" always satisfies every
    # remaining unconditional constraint (each section's own current
    # values are always one of its candidates, and the input schedule
    # was already class-valid) -- hinting it gives CP-SAT an instant,
    # guaranteed-feasible starting incumbent instead of having to search
    # for one from scratch.
    for i, section in enumerate(sections):
        for j, candidate in enumerate(candidates[i]):
            is_current = (
                candidate.instructor == section.instructor
                and candidate.time_slot == section.time_slot
                and candidate.room == section.room
                and candidate.building == section.building
            )
            model.add_hint(chosen[i][j], is_current)

    if previous is not None:
        # No-good cut: forbid reproducing `previous`'s exact full
        # assignment, section by section, using the same candidate-match
        # logic as the hint above. A section whose `previous` value isn't
        # among its own candidates just contributes nothing -- it already
        # can't match, so it doesn't need to be part of the cut.
        previous_sections = [
            section for item in previous.classes for section in item.sections
        ]
        matched_vars = []
        for i, prev_section in enumerate(previous_sections):
            for j, candidate in enumerate(candidates[i]):
                if (
                    candidate.instructor == prev_section.instructor
                    and candidate.time_slot == prev_section.time_slot
                    and candidate.room == prev_section.room
                    and candidate.building == prev_section.building
                ):
                    matched_vars.append(chosen[i][j])
                    break
        if matched_vars:
            model.add(sum(matched_vars) <= len(matched_vars) - 1)

    solver = cp_model.CpSolver()
    solver.parameters.max_time_in_seconds = time_limit_seconds
    # 1, not CP-SAT's usual multi-worker default -- each parallel search
    # worker keeps its own copy of the model's search state, which was
    # multiplying peak RSS several-fold on top of the already-large model
    # this replaced (see _add_scheduling_constraints); memory mattered
    # more here than shaving solve time via parallel search.
    solver.parameters.num_search_workers = 1
    solver.parameters.random_seed = random.SystemRandom().randrange(1, 2**31 - 1)
    status = solver.solve(model)
    if status not in (cp_model.OPTIMAL, cp_model.FEASIBLE):
        raise NoFeasibleSchedule(
            f"No feasible schedule found (solver status: {solver.status_name(status)})"
        )

    return _apply_solution(
        class_list, sections, sections_by_class, candidates, chosen, solver
    )
