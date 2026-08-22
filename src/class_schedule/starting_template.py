"""Build next term's starting-point schedule CSVs from last term's file
plus a change list -- what this whole rollover process ends up feeding
into a real ``solver.solve()`` pass later.

Two outputs, both by ``build_starting_templates``:

  - **starting.csv** -- ``term_builder``'s full draft (departures
    reassigned to a placeholder, cancelled courses dropped, new courses
    from ``changes.new_sections`` appended);
  - **starting_noadding.csv** -- the same, minus the new-course
    additions: instructor changes only, nothing newly offered. Useful to
    see the roster impact on its own, separate from whatever new
    sections were also decided for the term.

On top of both, two more passes run in this order:

1. **``place_new_hires``** -- ``changes.new_hires`` (see
   ``term_builder.TermChanges``) are seated into open positions, each up
   to their own ``persons.toml`` ``max_load``: first by taking over a
   placeholder-assigned ("Staff") class they're qualified for, and --
   only once no open, qualified, non-conflicting placeholder class is
   left -- by taking a class from an instructor currently over their own
   max_load (relieving that overload). If neither is available for a
   given slot, placement simply stops there rather than forcing a bad
   assignment; whatever's left unplaced stays open for the solver.
2. **``recolor_placeholder``** -- every class still on the placeholder
   after that gets split across as few distinct placeholder identities
   (``"Staff"``, ``"Staff 2"``, ``"Staff 3"``, ...) as it takes so that
   no two of them ever overlap in time. Two *different* open positions
   landing at an overlapping time would otherwise read as a same-
   instructor double-booking to ``check_conflicts`` -- not real, just an
   artifact of sharing one placeholder label. This showed up twice
   rolling 27S over by hand (two departures' vacated sections colliding,
   then again with a newly-added section) before this pass existed.
   Whatever count of distinct identities this step still needs, after
   already-known hires are seated, is a lower bound on *further* new
   hires -- not the final answer (that still wants a real
   ``solver.solve()`` pass against the real qualified-instructor pool),
   but a concrete signal available before running the solver at all.

Placement runs before recoloring, not after -- a real name only ever
*removes* a class from the placeholder pool, so it can only shrink the
conflict graph recoloring has to color, never complicate it.
"""

from __future__ import annotations

import random
from dataclasses import replace
from pathlib import Path

import pandas as pd

from .class_model import Class
from .schedule_model import PersonRecord, Schedule, load_persons, overlaps_in_time
from .term_builder import (
    DEFAULT_PLACEHOLDER_INSTRUCTOR,
    DraftReport,
    TermChanges,
    build_draft_schedule,
    load_changes,
)


def _classes_conflict(a: Class, b: Class) -> bool:
    """True if any in-person section of ``a`` overlaps in time with any
    in-person section of ``b``. Online/TBA sections never conflict here
    (mirrors ``check_conflicts``'s own room-conflict scope -- no clock
    time to overlap on)."""
    return any(
        not sa.is_online and not sb.is_online and overlaps_in_time(sa, sb)
        for sa in a.sections
        for sb in b.sections
    )


def _conflicts_with_any(item: Class, others: list[Class]) -> bool:
    return any(_classes_conflict(item, other) for other in others)


def _qualifies(item: Class, person: PersonRecord) -> bool:
    courses = {f"{s.subject} {s.number}" for s in item.sections}
    return courses.issubset(person.courses)


def _teaching_loads(schedule: Schedule) -> dict[str, float]:
    """Total credit hours per instructor -- one class counts once per
    distinct instructor teaching it, matching the load contract
    ``schedule_model.check_soft_preferences`` and ``solver`` both use."""
    totals: dict[str, float] = {}
    for item in schedule.classes:
        instructors = {s.instructor for s in item.sections if s.instructor}
        for instructor in instructors:
            totals[instructor] = totals.get(instructor, 0.0) + item.credit_hours
    return totals


def place_new_hires(
    schedule: Schedule,
    hire_names: tuple[str, ...],
    persons: dict[str, PersonRecord],
    *,
    placeholder: str = DEFAULT_PLACEHOLDER_INSTRUCTOR,
) -> tuple[Schedule, dict[str, tuple[str, ...]]]:
    """Seat each of ``hire_names`` (processed in the given order) into
    ``schedule``, up to their own ``max_load``. See the module docstring
    for the two-tier placement rule. A name not present in ``persons``
    is skipped entirely -- there's no ``max_load``/``courses`` to place
    them against.
    """
    result = Schedule(list(schedule.classes))
    assignments: dict[str, tuple[str, ...]] = {}

    for hire_name in hire_names:
        person = persons.get(hire_name)
        if person is None:
            continue

        assigned: list[Class] = []
        load = 0.0
        while load < person.max_load:
            candidate = next(
                (
                    item for item in result.classes
                    if any(s.instructor == placeholder for s in item.sections)
                    and load + item.credit_hours <= person.max_load
                    and _qualifies(item, person)
                    and not _conflicts_with_any(item, assigned)
                ),
                None,
            )
            if candidate is None:
                loads = _teaching_loads(result)
                candidate = next(
                    (
                        item for item in result.classes
                        if (holder := persons.get(item.sections[0].instructor)) is not None
                        and holder.name != hire_name
                        and loads.get(holder.name, 0.0) > holder.max_load
                        and load + item.credit_hours <= person.max_load
                        and _qualifies(item, person)
                        and not _conflicts_with_any(item, assigned)
                    ),
                    None,
                )
            if candidate is None:
                break  # neither tier has anything left -- stop, don't force a bad fit
            result.change_instructor(candidate.course_ids[0], hire_name)
            assigned.append(candidate)
            load += candidate.credit_hours

        if assigned:
            assignments[hire_name] = tuple(item.course_ids[0] for item in assigned)

    return result, assignments


def recolor_placeholder(
    schedule: Schedule,
    *,
    placeholder: str = DEFAULT_PLACEHOLDER_INSTRUCTOR,
    seed: int | None = None,
) -> tuple[Schedule, dict[str, tuple[str, ...]]]:
    """Split every class currently assigned to ``placeholder`` across as
    few distinct placeholder identities as a greedy graph coloring finds,
    such that no two classes sharing one identity ever overlap in time.
    Returns the recolored ``Schedule`` and ``{identity: (course_ids...)}``
    for every identity that ended up used (including plain ``placeholder``
    itself, if anything kept it).

    Not necessarily the *minimum* possible number of identities (that's
    graph coloring in general, NP-hard) -- a greedy pass in shuffled
    order, which is exact (a valid coloring, zero same-identity overlaps)
    even though it isn't guaranteed optimal. In practice these conflict
    graphs are sparse (most open positions don't overlap at all), so a
    greedy pass tends to land close to the true minimum anyway.
    """
    placeholder_classes = [
        item for item in schedule.classes
        if any(s.instructor == placeholder for s in item.sections)
    ]

    order = list(range(len(placeholder_classes)))
    random.Random(seed).shuffle(order)

    conflicts: dict[int, set[int]] = {i: set() for i in order}
    for i in range(len(placeholder_classes)):
        for j in range(i + 1, len(placeholder_classes)):
            if _classes_conflict(placeholder_classes[i], placeholder_classes[j]):
                conflicts[i].add(j)
                conflicts[j].add(i)

    color_of: dict[int, str] = {}
    for i in order:
        used = {color_of[n] for n in conflicts[i] if n in color_of}
        rank = 1
        while True:
            name = placeholder if rank == 1 else f"{placeholder} {rank}"
            if name not in used:
                color_of[i] = name
                break
            rank += 1

    recolored = Schedule(list(schedule.classes))
    assignments: dict[str, list[str]] = {}
    for i, item in enumerate(placeholder_classes):
        name = color_of[i]
        course_id = item.course_ids[0]
        if name != placeholder:
            recolored.change_instructor(course_id, name)
        assignments.setdefault(name, []).append(course_id)

    return recolored, {name: tuple(ids) for name, ids in assignments.items()}


def build_starting_templates(
    template_path: str | Path,
    changes_path: str | Path,
    persons_path: str | Path = "config/persons.toml",
    *,
    output_dir: str | Path = ".",
    placeholder_instructor: str = DEFAULT_PLACEHOLDER_INSTRUCTOR,
    seed: int | None = None,
) -> dict[str, dict[str, object]]:
    """Build both starting-point CSVs (see the module docstring).

    Returns ``{"starting": {...}, "starting_noadding": {...}}``, each
    with ``schedule``, ``report`` (the underlying
    ``term_builder.DraftReport``), ``hire_assignments``, and
    ``placeholder_identities``. Both CSVs are written to
    ``output_dir/starting.csv`` and ``output_dir/starting_noadding.csv``.
    """
    template_path = Path(template_path)
    dataframe = (
        pd.read_csv(template_path, dtype=str)
        if template_path.suffix.lower() == ".csv"
        else pd.read_excel(template_path, dtype=str)
    )
    persons = load_persons(persons_path)
    template = Schedule.from_dataframe(dataframe.dropna(how="all"), persons=persons)
    changes = load_changes(changes_path)
    output_dir = Path(output_dir)

    results: dict[str, dict[str, object]] = {}
    variants: tuple[tuple[str, TermChanges], ...] = (
        ("starting", changes),
        ("starting_noadding", replace(changes, new_sections=())),
    )
    for label, variant_changes in variants:
        draft, report = build_draft_schedule(
            template, variant_changes, placeholder_instructor=placeholder_instructor,
        )
        placed, hire_assignments = place_new_hires(
            draft, variant_changes.new_hires, persons, placeholder=placeholder_instructor,
        )
        recolored, placeholder_identities = recolor_placeholder(
            placed, placeholder=placeholder_instructor, seed=seed,
        )
        recolored.to_dataframe().to_csv(output_dir / f"{label}.csv", index=False)
        results[label] = {
            "schedule": recolored,
            "report": report,
            "hire_assignments": hire_assignments,
            "placeholder_identities": placeholder_identities,
        }
    return results


def _print_result(label: str, result: dict[str, object]) -> None:
    report: DraftReport = result["report"]
    hire_assignments: dict[str, tuple[str, ...]] = result["hire_assignments"]
    placeholder_identities: dict[str, tuple[str, ...]] = result["placeholder_identities"]

    print(f"=== {label}.csv ===")
    print(f"Cancelled ({len(report.cancelled)}): {', '.join(report.cancelled) or '-'}")
    print(f"Reassigned from a departure ({len(report.reassigned)}): {', '.join(report.reassigned) or '-'}")
    print(f"Added ({len(report.added)}): {', '.join(report.added) or '-'}")
    if report.unmatched_cancels or report.departures_not_found:
        print("Check for typos:")
        for spec in report.unmatched_cancels:
            print(f"  cancel spec matched nothing: {spec}")
        for name in report.departures_not_found:
            print(f"  departure never seen in the template: {name}")

    print(f"New hires placed ({len(hire_assignments)}):")
    for name, course_ids in hire_assignments.items():
        print(f"  {name}: {', '.join(course_ids)}")

    print(f"Placeholder identities remaining ({len(placeholder_identities)}):")
    for name, course_ids in sorted(placeholder_identities.items()):
        print(f"  {name}: {', '.join(course_ids)}")
    if len(placeholder_identities) > 1:
        print(
            f"{len(placeholder_identities)} distinct identities were still needed "
            "to keep this draft conflict-free -- a lower bound on further hires "
            "beyond the ones already placed above, not the final answer (still "
            "run solver.solve() against the real qualified-instructor pool for "
            "that)."
        )
    print()


def _main() -> None:
    import argparse

    parser = argparse.ArgumentParser(
        description=(
            "Build next term's two starting-point schedule CSVs "
            "(starting.csv and starting_noadding.csv): apply a change "
            "list to last term's file, seat any new hires, then split "
            "whatever's left on the placeholder into non-conflicting "
            "identities."
        )
    )
    parser.add_argument("template", help="last term's schedule (CSV/XLSX)")
    parser.add_argument("changes", help="this term's change-list TOML")
    parser.add_argument(
        "-p", "--persons", default="config/persons.toml",
        help="persons.toml (default: config/persons.toml)",
    )
    parser.add_argument(
        "-d", "--output-dir", default=".",
        help="directory to write starting.csv/starting_noadding.csv into (default: .)",
    )
    parser.add_argument(
        "--seed", type=int, default=None,
        help="fix the recoloring shuffle for a reproducible result",
    )
    parser.add_argument(
        "--placeholder", default=DEFAULT_PLACEHOLDER_INSTRUCTOR,
        help=f"instructor placeholder base name (default: {DEFAULT_PLACEHOLDER_INSTRUCTOR!r})",
    )
    args = parser.parse_args()

    results = build_starting_templates(
        args.template, args.changes, args.persons,
        output_dir=args.output_dir,
        placeholder_instructor=args.placeholder,
        seed=args.seed,
    )
    for label, result in results.items():
        _print_result(label, result)

    output_dir = Path(args.output_dir)
    print(f"Written: {output_dir / 'starting.csv'}, {output_dir / 'starting_noadding.csv'}")


if __name__ == "__main__":
    _main()
