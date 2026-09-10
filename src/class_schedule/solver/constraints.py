"""Translate cross-section, calendar, resource, and load rules into CP-SAT."""

from __future__ import annotations

import datetime
from dataclasses import dataclass

from ortools.sat.python import cp_model

from ..class_model import Class, Section
from ..config_schema import WorkloadPolicySchema
from ..schedule_model import (
    PersonRecord,
    PreferenceRecord,
)
from ..instructor_identity import is_new_instructor, is_new_professor
from .candidates import apply_candidate
from .types import SectionCandidate


def add_placeholder_count_terms(
    candidates: list[list[SectionCandidate]],
    chosen: list[list[cp_model.IntVar]],
    placeholder_instructors: tuple[str, ...],
    weight: float,
    model: cp_model.CpModel,
    *,
    enforce_contiguous: bool = True,
    variable_prefix: str = "placeholder",
    allowed_counts: tuple[int, ...] | None = None,
) -> list[cp_model.LinearExpr]:
    """Penalize each distinct placeholder identity selected anywhere."""
    objective_terms: list[cp_model.LinearExpr] = []
    used_variables: list[cp_model.IntVar] = []
    for rank, instructor in enumerate(placeholder_instructors, start=1):
        selected = [
            chosen[section_index][candidate_index]
            for section_index, section_candidates in enumerate(candidates)
            for candidate_index, candidate in enumerate(section_candidates)
            if candidate.instructor == instructor
        ]
        used = model.new_bool_var(f"{variable_prefix}_{rank}_used")
        if selected:
            for variable in selected:
                model.add(variable <= used)
            model.add(used <= sum(selected))
        else:
            model.add(used == 0)
        used_variables.append(used)
        objective_terms.append(weight * used)
    if enforce_contiguous:
        for previous, current in zip(used_variables, used_variables[1:]):
            model.add(previous >= current)
    if allowed_counts is not None:
        count = model.new_int_var(0, len(used_variables), f"{variable_prefix}_count")
        model.add(count == sum(used_variables))
        model.add_allowed_assignments([count], [[value] for value in allowed_counts])
    return objective_terms


def add_placeholder_load_terms(
    class_list: list[Class],
    sections_by_class: dict[int, list[int]],
    candidates: list[list[SectionCandidate]],
    chosen: list[list[cp_model.IntVar]],
    placeholder_instructors: tuple[str, ...],
    weight: float,
) -> list[cp_model.LinearExpr]:
    """Penalize each credit hour assigned to the placeholder pool."""
    placeholders = set(placeholder_instructors)
    return [
        item.credit_hours * weight * chosen[primary][candidate_index]
        for class_index, item in enumerate(class_list)
        for primary in (sections_by_class[class_index][0],)
        for candidate_index, candidate in enumerate(candidates[primary])
        if candidate.instructor in placeholders and item.credit_hours
    ]


def predicate_for(item: Class):
    """The two-row legality check ``item``'s own ``validate`` also enforces.

    Sourced from the instance itself (``Class.pairwise_predicate``, see
    ``docs/codes.md``) rather than a second, separately maintained
    kind -> predicate mapping living here -- an instance method, not a
    classmethod, because a ``CrossListingClass`` pair's rule depends on
    what its own two rows started out sharing, not just its type.
    """
    return item.pairwise_predicate()


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
        if len(indices) < 2:
            continue
        predicate = predicate_for(item)
        if predicate is None:
            # No pairwise rule at all for this instance (e.g. a
            # CrossListingClass pair with nothing locked) -- the two rows
            # are free to be assigned completely independently.
            continue
        for offset, left_index in enumerate(indices):
            for right_index in indices[offset + 1:]:
                for left_candidate, left in enumerate(candidates[left_index]):
                    for right_candidate, right in enumerate(candidates[right_index]):
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
    *, class_list: list[Class] | None = None,
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
            if class_list is not None:
                source = sections[section_index]
                item = class_list[owner[section_index]]
                for reservation in item.resource_usage(source, apply_candidate(source, candidate)):
                    slots.append(Slot(
                        section=section_index, candidate=candidate_index,
                        class_index=owner[section_index], days=reservation.days,
                        start=reservation.start, end=reservation.end,
                        room_key=f"{reservation.building} {reservation.room}".strip(),
                        instructor="",
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
    *, back_to_back_penalty: float = 10.0,
) -> list:
    by_room_day: dict[tuple[str, str], list[int]] = {}
    by_instructor_day: dict[tuple[str, str], list[int]] = {}
    intervals: list = [None] * len(slots)
    forbidden_pairs: set[tuple[tuple[int, int], tuple[int, int]]] = set()
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
                    left_key = (left.section, left.candidate)
                    right_key = (right.section, right.candidate)
                    pair = tuple(sorted((left_key, right_key)))
                    if pair in forbidden_pairs:
                        continue
                    forbidden_pairs.add(pair)
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
                    objective_terms.append(back_to_back_penalty * both)
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
                    objective_terms.append(back_to_back_penalty * all_chosen)
    return objective_terms


def add_load_terms(
    class_list: list[Class],
    sections_by_class: dict[int, list[int]],
    candidates: list[list[SectionCandidate]],
    chosen: list[list],
    persons: dict[str, PersonRecord],
    preferences: dict[str, PreferenceRecord],
    model: cp_model.CpModel,
    *, workload_policy: WorkloadPolicySchema | None = None,
) -> list:
    policy = workload_policy or WorkloadPolicySchema()
    scale = 10
    assignments: dict[str, list] = {}
    for section_index, options in enumerate(candidates):
        for candidate_index, candidate in enumerate(options):
            assignments.setdefault(candidate.instructor, []).append(
                chosen[section_index][candidate_index]
            )
    per_instructor: dict[str, list] = {}
    for class_index, item in enumerate(class_list):
        units = int(round(item.credit_hours * scale))
        if not units:
            continue
        # Every distinct instructor possible anywhere among this class's
        # rows contributes at most one `units` charge for this class --
        # matching schedule_model.teaching_loads()'s "any row crediting
        # them counts the whole class once" definition, not just the
        # first row's candidate (see docs/codes.md). For every kind
        # except an instructor-unsynced CrossListingClass, every row's
        # candidates already have to agree on instructor in any feasible
        # solution (pairwise_predicate forbids otherwise), so this only
        # actually changes behavior for that one case; everywhere else it
        # computes the identical answer the old primary-row-only version
        # did, just by a more general route.
        by_instructor: dict[str, list] = {}
        for section_index in sections_by_class[class_index]:
            for candidate_index, candidate in enumerate(candidates[section_index]):
                by_instructor.setdefault(candidate.instructor, []).append(
                    chosen[section_index][candidate_index]
                )
        for instructor, selected in by_instructor.items():
            if len(selected) == 1:
                taught = selected[0]
            else:
                taught = model.new_bool_var(f"taught_c{class_index}_{instructor}")
                for variable in selected:
                    model.add(variable <= taught)
                model.add(taught <= sum(selected))
            per_instructor.setdefault(instructor, []).append(units * taught)

    objective_terms = []
    for instructor, selected in assignments.items():
        person = persons.get(instructor)
        if person is None:
            continue
        total = sum(per_instructor.get(instructor, ()))
        target = int(round(person.max_load * scale))
        active = 1
        if is_new_instructor(instructor) or is_new_professor(instructor):
            # Optional hires incur workload costs only once assigned a row,
            # including a zero-credit row. Their workload rules are shared.
            active = model.new_bool_var(f"load_active_{instructor}")
            model.add_max_equality(active, selected)
        hard_cap = int(round((person.max_load + policy.hard_load_cap_tolerance) * scale))
        model.add(total <= hard_cap)
        preference = preferences.get(instructor)

        # d = load - contract, scaled. `target * active` is 0 for an
        # unassigned optional hire, so its d is 0 -> the "ok" tier (0 is
        # always in `ok`). Mirrors schedule_model.check_soft_preferences.
        d_expr = total - target * active
        neg_d_expr = target * active - total
        max_over = max(hard_cap - target, 0)
        max_under = max(target, 0)

        def _at(value: int, tag: str):
            hit = model.new_bool_var(f"load_{tag}_{instructor}")
            model.add(d_expr == value).only_enforce_if(hit)
            model.add(d_expr != value).only_enforce_if(hit.Not())
            return hit

        ok_hits = [_at(k * scale, f"ok{i}") for i, k in enumerate(policy.ok)]
        light_hits = [_at(k * scale, f"light{i}") for i, k in enumerate(policy.light)]
        in_ok = model.new_bool_var(f"load_in_ok_{instructor}")
        model.add_max_equality(in_ok, ok_hits)
        in_light = model.new_bool_var(f"load_in_light_{instructor}")
        if light_hits:
            model.add_max_equality(in_light, light_hits)
        else:
            model.add(in_light == 0)
        heavy = model.new_bool_var(f"load_heavy_{instructor}")
        model.add(in_ok + in_light + heavy == 1)

        over = model.new_int_var(0, max_over, f"load_over_{instructor}")
        under = model.new_int_var(0, max_under, f"load_under_{instructor}")
        model.add_max_equality(over, [d_expr, 0])
        model.add_max_equality(under, [neg_d_expr, 0])
        over_heavy = model.new_int_var(0, max_over, f"load_over_heavy_{instructor}")
        under_heavy = model.new_int_var(0, max_under, f"load_under_heavy_{instructor}")
        model.add(over_heavy == over).only_enforce_if(heavy)
        model.add(over_heavy == 0).only_enforce_if(heavy.Not())
        model.add(under_heavy == under).only_enforce_if(heavy)
        model.add(under_heavy == 0).only_enforce_if(heavy.Not())

        over_unit = (
            0.0 if preference is None
            else policy.penalties.heavy_unit_over
            if preference.allow_overload
            else policy.penalties.heavy_unit_over_strict
        )
        # New hires carry a discounted workload penalty so the solver
        # sheds unavoidable under/overload onto them, not a named
        # instructor (see WorkloadPolicySchema.new_hire_penalty_scale).
        nh = (
            policy.new_hire_penalty_scale
            if is_new_instructor(instructor) or is_new_professor(instructor)
            else 1.0
        )
        objective_terms.append((over_unit * nh / scale) * over_heavy)
        objective_terms.append(
            (policy.penalties.heavy_unit_under * nh / scale) * under_heavy
        )
        objective_terms.append(policy.penalties.light_penalty * nh * in_light)
    return objective_terms
