"""Assemble and run the CP-SAT model; domain logic lives in sibling modules."""

from __future__ import annotations

import random

from ortools.sat.python import cp_model

from ..class_model import Section
from ..overrides import LockMap, locks_for_section
from ..schedule_model import Schedule
from ..schedule_model import PersonRecord, PreferenceRecord
from ..initial_builder import is_placeholder_instructor, recolor_placeholder
from ..instructor_identity import new_instructor_name, new_instructor_rank
from ..new_instructors import required_by_concurrency, required_by_load
from .candidates import (
    MAX_CANDIDATES_PAIRED_SECTION,
    MAX_CANDIDATES_SINGLE_SECTION,
    section_candidates,
)
from .config import SolverConfig
from .constraints import (
    add_load_terms,
    add_pairwise_validity_constraints,
    add_placeholder_count_terms,
    add_placeholder_load_terms,
    add_scheduling_constraints,
    build_slots,
)
from .result import apply_solution
from .types import (
    InfeasibleSchedule,
    NoFeasibleSchedule,
    SolveResult,
    SolveStatus,
    SolveTimeout,
)


DEFAULT_SEARCH_WORKERS = 8


def solve_detailed(
    schedule: Schedule,
    config: SolverConfig,
    *,
    time_limit_seconds: float = 30.0,
    previous: Schedule | None = None,
    locks: LockMap | None = None,
    random_seed: int | None = None,
    search_workers: int = DEFAULT_SEARCH_WORKERS,
) -> SolveResult:
    if search_workers < 1:
        raise ValueError("search_workers must be at least 1")
    placeholder_lock = False
    for (course_id, record), fields in (locks or {}).items():
        if "instructor" not in fields:
            continue
        item = schedule.get(course_id)
        targets = item.sections if record is None else (item.sections[record],)
        if any(is_placeholder_instructor(section.instructor) for section in targets):
            placeholder_lock = True
            break
    if placeholder_lock:
        normalized_schedule = schedule
        placeholder_instructors = tuple(sorted({
            section.instructor
            for item in schedule.classes for section in item.sections
            if is_placeholder_instructor(section.instructor)
        }, key=new_instructor_rank))
    else:
        normalized_schedule, placeholder_assignments = recolor_placeholder(
            schedule, seed=0
        )
        placeholder_instructors = tuple(placeholder_assignments)
    class_list = list(normalized_schedule.classes)
    existing_count = max(
        (new_instructor_rank(name) for name in placeholder_instructors), default=0
    )
    pool_size = max(
        existing_count,
        required_by_load(
            class_list,
            contract_load=config.new_instructor_policy.contract_load,
            max_course_number_exclusive=config.new_instructor_policy.max_course_number_exclusive,
        ),
        required_by_concurrency(
            class_list,
            max_course_number_exclusive=config.new_instructor_policy.max_course_number_exclusive,
        ),
    )
    placeholder_instructors = tuple(
        new_instructor_name(rank) for rank in range(1, pool_size + 1)
    )
    sections: list[Section] = []
    owner: list[int] = []
    for class_index, item in enumerate(class_list):
        for section in item.sections:
            sections.append(section)
            owner.append(class_index)

    candidates = []
    record_indexes: dict[int, int] = {}
    for index, section in enumerate(sections):
        class_index = owner[index]
        record = record_indexes.get(class_index, 0)
        record_indexes[class_index] = record + 1
        item = class_list[class_index]
        candidates.append(section_candidates(
            item,
            section,
            config,
            MAX_CANDIDATES_SINGLE_SECTION
            if len(item.sections) == 1 else MAX_CANDIDATES_PAIRED_SECTION,
            locks_for_section(locks, item.course_ids, record),
            placeholder_instructors,
        ))
    empty = [
        sections[index].course_id
        for index, values in enumerate(candidates)
        if not values
    ]
    if empty:
        raise InfeasibleSchedule(f"No legal candidates for: {', '.join(empty)}")

    sections_by_class: dict[int, list[int]] = {}
    for index, class_index in enumerate(owner):
        sections_by_class.setdefault(class_index, []).append(index)

    model = cp_model.CpModel()
    chosen = [
        [model.new_bool_var(f"s{i}_c{j}") for j in range(len(values))]
        for i, values in enumerate(candidates)
    ]
    for variables in chosen:
        model.add_exactly_one(variables)

    add_pairwise_validity_constraints(
        class_list, sections, sections_by_class, candidates, chosen, model
    )
    slots = build_slots(sections, owner, candidates)
    effective_preferences = dict(config.preferences)
    effective_preferences.update({
        name: PreferenceRecord(
            name=name,
            allow_back_to_back=config.new_instructor_policy.allow_back_to_back,
        ) for name in placeholder_instructors
    })
    back_to_back_terms = add_scheduling_constraints(
        slots, chosen, effective_preferences, model,
        back_to_back_penalty=config.back_to_back_policy.penalty,
    )
    effective_persons = dict(config.persons)
    effective_persons.update({
        name: PersonRecord(
            name=name, max_load=config.new_instructor_policy.contract_load
        )
        for name in placeholder_instructors
    })
    load_terms = add_load_terms(
        class_list, sections_by_class, candidates, chosen,
        effective_persons, effective_preferences, model,
        workload_policy=config.workload_policy,
    )
    placeholder_terms = add_placeholder_count_terms(
        candidates, chosen, placeholder_instructors,
        config.staff_count_weight, model,
        enforce_contiguous=not placeholder_lock,
    )
    placeholder_terms.extend(add_placeholder_load_terms(
        class_list, sections_by_class, candidates, chosen,
        placeholder_instructors, config.staff_credit_weight,
    ))
    candidate_terms = [
        candidate.cost * chosen[section_index][candidate_index]
        for section_index, values in enumerate(candidates)
        for candidate_index, candidate in enumerate(values)
    ]
    model.minimize(
        sum(candidate_terms) + sum(back_to_back_terms)
        + sum(load_terms) + sum(placeholder_terms)
    )

    for section_index, section in enumerate(sections):
        for candidate_index, candidate in enumerate(candidates[section_index]):
            model.add_hint(chosen[section_index][candidate_index], (
                candidate.instructor == section.instructor
                and candidate.time_slot == section.time_slot
                and candidate.room == section.room
                and candidate.building == section.building
            ))

    if previous is not None:
        previous_sections = [
            section for item in previous.classes for section in item.sections
        ]
        matched = []
        for section_index, previous_section in enumerate(previous_sections):
            for candidate_index, candidate in enumerate(candidates[section_index]):
                if (
                    candidate.instructor == previous_section.instructor
                    and candidate.time_slot == previous_section.time_slot
                    and candidate.room == previous_section.room
                    and candidate.building == previous_section.building
                ):
                    matched.append(chosen[section_index][candidate_index])
                    break
        if matched:
            model.add(sum(matched) <= len(matched) - 1)

    cp_solver = cp_model.CpSolver()
    cp_solver.parameters.max_time_in_seconds = time_limit_seconds
    cp_solver.parameters.num_search_workers = search_workers
    seed = random_seed or random.SystemRandom().randrange(1, 2**31 - 1)
    cp_solver.parameters.random_seed = seed
    status = cp_solver.solve(model)
    if status == cp_model.INFEASIBLE:
        raise InfeasibleSchedule("The candidate model is infeasible")
    if status == cp_model.UNKNOWN:
        raise SolveTimeout(
            f"No feasible schedule found within {time_limit_seconds:g} seconds"
        )
    if status not in (cp_model.OPTIMAL, cp_model.FEASIBLE):
        raise NoFeasibleSchedule(f"Solver failed: {cp_solver.status_name(status)}")

    solved = apply_solution(
        class_list, sections, sections_by_class, candidates, chosen, cp_solver
    )
    return SolveResult(
        schedule=solved,
        status=(
            SolveStatus.OPTIMAL if status == cp_model.OPTIMAL
            else SolveStatus.FEASIBLE
        ),
        objective=cp_solver.objective_value,
        best_bound=cp_solver.best_objective_bound,
        solve_seconds=cp_solver.wall_time,
        candidate_count=sum(len(values) for values in candidates),
        config_version=config.version,
        random_seed=seed,
        search_workers=search_workers,
    )


def solve(
    schedule: Schedule,
    config: SolverConfig,
    *,
    time_limit_seconds: float = 30.0,
    previous: Schedule | None = None,
    locks: LockMap | None = None,
    random_seed: int | None = None,
    search_workers: int = DEFAULT_SEARCH_WORKERS,
) -> Schedule:
    return solve_detailed(
        schedule,
        config,
        time_limit_seconds=time_limit_seconds,
        previous=previous,
        locks=locks,
        random_seed=random_seed,
        search_workers=search_workers,
    ).schedule
