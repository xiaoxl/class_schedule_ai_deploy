"""Assemble and run the CP-SAT model; domain logic lives in sibling modules."""

from __future__ import annotations

import random

from ortools.sat.python import cp_model

from ..class_model import Section
from ..overrides import LockMap, locks_for_section
from ..schedule_model import Schedule
from .candidates import (
    MAX_CANDIDATES_PAIRED_SECTION,
    MAX_CANDIDATES_SINGLE_SECTION,
    allowed_pattern_types,
    section_candidates,
)
from .config import SolverConfig
from .constraints import (
    add_load_terms,
    add_pairwise_validity_constraints,
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


def solve_detailed(
    schedule: Schedule,
    config: SolverConfig,
    *,
    time_limit_seconds: float = 30.0,
    previous: Schedule | None = None,
    locks: LockMap | None = None,
    random_seed: int | None = None,
) -> SolveResult:
    class_list = list(schedule.classes)
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
            section,
            config,
            MAX_CANDIDATES_SINGLE_SECTION
            if len(item.sections) == 1 else MAX_CANDIDATES_PAIRED_SECTION,
            allowed_pattern_types(item, section),
            locks_for_section(locks, item.course_ids, record),
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
    back_to_back_terms = add_scheduling_constraints(
        slots, chosen, config.preferences, model
    )
    load_terms = add_load_terms(
        class_list, sections_by_class, candidates, chosen,
        config.persons, config.preferences, model,
    )
    candidate_terms = [
        candidate.cost * chosen[section_index][candidate_index]
        for section_index, values in enumerate(candidates)
        for candidate_index, candidate in enumerate(values)
    ]
    model.minimize(sum(candidate_terms) + sum(back_to_back_terms) + sum(load_terms))

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
    cp_solver.parameters.num_search_workers = 1
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

    return SolveResult(
        schedule=apply_solution(
            class_list, sections, sections_by_class, candidates, chosen, cp_solver
        ),
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
    )


def solve(
    schedule: Schedule,
    config: SolverConfig,
    *,
    time_limit_seconds: float = 30.0,
    previous: Schedule | None = None,
    locks: LockMap | None = None,
    random_seed: int | None = None,
) -> Schedule:
    return solve_detailed(
        schedule,
        config,
        time_limit_seconds=time_limit_seconds,
        previous=previous,
        locks=locks,
        random_seed=random_seed,
    ).schedule
