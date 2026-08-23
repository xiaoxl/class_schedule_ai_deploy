"""Translate cross-section, calendar, resource, and load rules into CP-SAT."""

from __future__ import annotations

import datetime
from dataclasses import dataclass

from ortools.sat.python import cp_model

from ..class_model import (
    Class,
    CoreqClass,
    CrossListingClass,
    FourCreditClass,
    HybridClass,
    Section,
)
from ..schedule_model import (
    BACK_TO_BACK_PENALTY,
    OVERLOAD_FAR_PENALTY,
    OVERLOAD_FAR_THRESHOLD,
    OVERLOAD_TOLERANCE,
    UNDER_LOAD_PENALTY,
    PersonRecord,
    PreferenceRecord,
)
from .candidates import apply_candidate
from .types import SectionCandidate


HARD_LOAD_CAP_TOLERANCE = 6.0


def predicate_for(item: Class):
    if isinstance(item, FourCreditClass):
        return FourCreditClass.is_four_credit
    if isinstance(item, HybridClass):
        return HybridClass.is_hybrid
    if isinstance(item, CoreqClass):
        return CoreqClass.is_valid_schedule
    if isinstance(item, CrossListingClass):
        return CrossListingClass.is_shared_meeting
    return None


def add_pairwise_validity_constraints(
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
        left_index, right_index = indices
        predicate = predicate_for(item)
        for left_candidate, left in enumerate(candidates[left_index]):
            for right_candidate, right in enumerate(candidates[right_index]):
                valid = left.instructor == right.instructor
                if valid and predicate is not None:
                    valid = predicate(
                        apply_candidate(sections[left_index], left),
                        apply_candidate(sections[right_index], right),
                    )
                if not valid:
                    model.add_bool_or([
                        chosen[left_index][left_candidate].Not(),
                        chosen[right_index][right_candidate].Not(),
                    ])


@dataclass(frozen=True)
class Slot:
    section: int
    candidate: int
    class_index: int
    days: str
    start: datetime.time
    end: datetime.time
    room_key: str
    instructor: str


def build_slots(
    sections: list[Section],
    owner: list[int],
    candidates: list[list[SectionCandidate]],
) -> list[Slot]:
    slots = []
    for section_index, section_candidates in enumerate(candidates):
        for candidate_index, candidate in enumerate(section_candidates):
            if candidate.days is None or candidate.start is None or candidate.end is None:
                continue
            slots.append(Slot(
                section=section_index,
                candidate=candidate_index,
                class_index=owner[section_index],
                days=candidate.days,
                start=candidate.start,
                end=candidate.end,
                room_key=f"{candidate.building} {candidate.room}".strip(),
                instructor=candidate.instructor,
            ))
    return slots


def back_to_back_chains(
    start: int,
    length: int,
    slots: list[Slot],
    by_start: dict[datetime.time, list[int]],
    used_classes: frozenset[int],
) -> list[tuple[int, ...]]:
    if length == 1:
        return [(start,)]
    chains = []
    for next_index in by_start.get(slots[start].end, ()):
        next_slot = slots[next_index]
        if next_slot.class_index in used_classes:
            continue
        for rest in back_to_back_chains(
            next_index, length - 1, slots, by_start,
            used_classes | {next_slot.class_index},
        ):
            chains.append((start,) + rest)
    return chains


def add_scheduling_constraints(
    slots: list[Slot],
    chosen: list[list],
    preferences: dict[str, PreferenceRecord],
    model: cp_model.CpModel,
) -> list:
    by_room_day: dict[tuple[str, str], list[int]] = {}
    by_instructor_day: dict[tuple[str, str], list[int]] = {}
    intervals: list = [None] * len(slots)
    for index, slot in enumerate(slots):
        start = slot.start.hour * 60 + slot.start.minute
        end = slot.end.hour * 60 + slot.end.minute
        if end <= start:
            end += 24 * 60
        intervals[index] = model.new_optional_interval_var(
            start, end - start, end,
            chosen[slot.section][slot.candidate],
            f"iv_{slot.section}_{slot.candidate}",
        )
        for day in slot.days:
            if slot.room_key:
                by_room_day.setdefault((slot.room_key, day), []).append(index)
            if slot.instructor:
                by_instructor_day.setdefault((slot.instructor, day), []).append(index)

    def add_bucket_no_overlap(indices: list[int]) -> None:
        sections_by_class: dict[int, set[int]] = {}
        for index in indices:
            slot = slots[index]
            sections_by_class.setdefault(slot.class_index, set()).add(slot.section)
        exempt = {owner for owner, values in sections_by_class.items() if len(values) > 1}
        solo = [index for index in indices if slots[index].class_index not in exempt]
        paired = [index for index in indices if slots[index].class_index in exempt]
        if len(solo) > 1:
            model.add_no_overlap([intervals[index] for index in solo])
        for left_index in paired:
            left = slots[left_index]
            for right_index in indices:
                right = slots[right_index]
                if right_index == left_index or right.class_index == left.class_index:
                    continue
                if left.start < right.end and right.start < left.end:
                    model.add_bool_or([
                        chosen[left.section][left.candidate].Not(),
                        chosen[right.section][right.candidate].Not(),
                    ])

    for indices in by_room_day.values():
        if len(indices) > 1:
            add_bucket_no_overlap(indices)

    objective_terms = []
    seen_pairs: set[tuple[int, int]] = set()
    seen_chains: set[tuple[int, ...]] = set()
    for (instructor, _day), indices in by_instructor_day.items():
        if len(indices) > 1:
            add_bucket_no_overlap(indices)
        preference = preferences.get(instructor)
        if preference is None:
            continue
        by_start: dict[datetime.time, list[int]] = {}
        for index in indices:
            by_start.setdefault(slots[index].start, []).append(index)
        if not preference.allow_back_to_back:
            for left_index in indices:
                left = slots[left_index]
                for right_index in by_start.get(left.end, ()):
                    right = slots[right_index]
                    if left.class_index == right.class_index:
                        continue
                    key = tuple(sorted((left_index, right_index)))
                    if key in seen_pairs:
                        continue
                    seen_pairs.add(key)
                    both = model.new_bool_var(
                        f"b2b_{left.section}_{left.candidate}_{right.section}_{right.candidate}"
                    )
                    model.add(both <= chosen[left.section][left.candidate])
                    model.add(both <= chosen[right.section][right.candidate])
                    model.add(
                        both >= chosen[left.section][left.candidate]
                        + chosen[right.section][right.candidate] - 1
                    )
                    objective_terms.append(BACK_TO_BACK_PENALTY * both)
        elif preference.max_back_to_back is not None:
            length = preference.max_back_to_back + 1
            for index in indices:
                for chain in back_to_back_chains(
                    index, length, slots, by_start,
                    frozenset({slots[index].class_index}),
                ):
                    key = tuple(sorted(chain))
                    if key in seen_chains:
                        continue
                    seen_chains.add(key)
                    variables = [
                        chosen[slots[item].section][slots[item].candidate]
                        for item in chain
                    ]
                    all_chosen = model.new_bool_var(
                        "chain_" + "_".join(
                            f"{slots[item].section}_{slots[item].candidate}" for item in chain
                        )
                    )
                    for variable in variables:
                        model.add(all_chosen <= variable)
                    model.add(all_chosen >= sum(variables) - (len(variables) - 1))
                    objective_terms.append(BACK_TO_BACK_PENALTY * all_chosen)
    return objective_terms


def add_load_terms(
    class_list: list[Class],
    sections_by_class: dict[int, list[int]],
    candidates: list[list[SectionCandidate]],
    chosen: list[list],
    persons: dict[str, PersonRecord],
    preferences: dict[str, PreferenceRecord],
    model: cp_model.CpModel,
) -> list:
    scale = 10
    per_instructor: dict[str, list] = {}
    for class_index, item in enumerate(class_list):
        primary = sections_by_class[class_index][0]
        units = int(round(item.credit_hours * scale))
        if not units:
            continue
        for candidate_index, candidate in enumerate(candidates[primary]):
            per_instructor.setdefault(candidate.instructor, []).append(
                units * chosen[primary][candidate_index]
            )

    objective_terms = []
    for instructor, terms in per_instructor.items():
        person = persons.get(instructor)
        if person is None:
            continue
        total = sum(terms)
        target = int(round(person.max_load * scale))
        limit = int(round((person.max_load + OVERLOAD_TOLERANCE) * scale))
        hard_cap = int(round((person.max_load + HARD_LOAD_CAP_TOLERANCE) * scale))
        model.add(total <= hard_cap)
        preference = preferences.get(instructor)
        penalty = preference.overload_penalty if preference else 0.0
        if penalty:
            overloaded = model.new_bool_var(f"overload_{instructor}")
            model.add(total > limit).only_enforce_if(overloaded)
            model.add(total <= limit).only_enforce_if(overloaded.Not())
            objective_terms.append(penalty * overloaded)
            if preference.allow_overload:
                far_limit = int(round(
                    (person.max_load + OVERLOAD_FAR_THRESHOLD) * scale
                ))
                far_over = model.new_bool_var(f"overload_far_{instructor}")
                model.add(total > far_limit).only_enforce_if(far_over)
                model.add(total <= far_limit).only_enforce_if(far_over.Not())
                objective_terms.append(OVERLOAD_FAR_PENALTY * far_over)
        under = model.new_bool_var(f"under_load_{instructor}")
        model.add(total < target).only_enforce_if(under)
        model.add(total >= target).only_enforce_if(under.Not())
        objective_terms.append(UNDER_LOAD_PENALTY * under)
    return objective_terms
