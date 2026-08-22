"""Turn last term's schedule plus a small per-term change list into next
term's starting draft.

Two inputs feed ``build_draft_schedule``:

  - a template ``Schedule`` -- last term's parsed schedule (e.g.
    ``Schedule.from_dataframe(pd.read_csv("26S.csv"))``);
  - a ``TermChanges`` -- this term's edits (who left, what's newly
    offered, what's cancelled), loaded from a small TOML file via
    ``load_changes``. See ``inputs/TEMPLATE/changes.toml`` for the file format
    and a full walkthrough.

The result is a draft ``Schedule`` ready for the CLI solve stage or a direct
``solver.solve()`` call: cancelled courses are dropped, every
section a departed instructor was teaching is reassigned to a
placeholder instructor (so the solver treats it as open rather than
pinned to someone who's gone), and newly offered courses are appended,
grouped exactly the way ``Schedule.from_records`` groups any other CSV
rows -- a four-credit/hybrid/coreq/cross-listed new offering is
recognized automatically from its own two rows, same as an upload.

This module never writes persons.toml or preferences.toml --
``summarize_roster_impact`` only reports whether ``departures`` matches
real persons.toml names, it never writes either file. A departed
person's max_load/preferences entry still needs to be removed by hand.
"""

from __future__ import annotations

import tomllib
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from pathlib import Path

import pandas as pd

from . import record_utils
from .class_model import Class
from .schedule_model import PersonRecord, Schedule

DEFAULT_PLACEHOLDER_INSTRUCTOR = "Staff"


@dataclass(frozen=True)
class CancelSpec:
    """One course to drop from the template. ``section`` omitted cancels
    every section of that course number."""

    subject: str
    number: str
    section: str | None = None


@dataclass(frozen=True)
class TermChanges:
    """This term's edits, as loaded from a change-list TOML file.

    ``new_hires`` is separate from ``departures``/``cancel``/``new_sections``
    -- it doesn't affect ``build_draft_schedule`` at all (no schedule row
    is added, removed, or reassigned because of it). It's read by
    ``starting_template.place_new_hires`` instead, to know which
    persons.toml entries are new-for-this-term people to actually place
    into the draft, as opposed to someone added to persons.toml for
    later planning who isn't confirmed hired yet.
    """

    departures: tuple[str, ...] = ()
    new_hires: tuple[str, ...] = ()
    cancel: tuple[CancelSpec, ...] = ()
    new_sections: tuple[dict[str, object], ...] = ()


@dataclass(frozen=True)
class DraftReport:
    """What ``build_draft_schedule`` actually did.

    Exists so a typo in the change list -- a cancelled course number that
    doesn't exist in the template, a departure name spelled differently
    than the template's Instructor column -- shows up immediately instead
    of silently doing nothing.
    """

    cancelled: tuple[str, ...] = ()
    unmatched_cancels: tuple[CancelSpec, ...] = ()
    reassigned: tuple[str, ...] = ()
    departures_not_found: tuple[str, ...] = ()
    added: tuple[str, ...] = ()


def load_changes(path: str | Path) -> TermChanges:
    """Parse a change-list TOML file (see ``inputs/TEMPLATE/changes.toml``)."""
    with open(path, "rb") as handle:
        raw = tomllib.load(handle)
    cancel = tuple(
        CancelSpec(
            subject=record_utils.text(entry["subject"]).upper(),
            number=record_utils.text(entry["number"]),
            section=record_utils.text(entry.get("section")) or None,
        )
        for entry in raw.get("cancel_courses", ())
    )
    new_sections = tuple(dict(row) for row in raw.get("new_courses", ()))
    departures = tuple(
        record_utils.text(name) for name in raw.get("departures", ())
    )
    new_hires = tuple(
        record_utils.text(name) for name in raw.get("new_hires", ())
    )
    return TermChanges(
        departures=departures, new_hires=new_hires,
        cancel=cancel, new_sections=new_sections,
    )


def summarize_roster_impact(
    changes: TermChanges, persons: Mapping[str, PersonRecord]
) -> tuple[tuple[str, ...], tuple[str, ...]]:
    """Split ``changes.departures`` into (matches a persons.toml name,
    doesn't). The second group is almost always a typo -- this module
    never edits persons.toml itself, so every name in the first group
    still needs its ``[[persons]]``/``[[instructors]]`` block removed by
    hand before the roster actually reflects the departure.
    """
    confirmed = tuple(name for name in changes.departures if name in persons)
    unknown = tuple(name for name in changes.departures if name not in persons)
    return confirmed, unknown


def _cancels(item: Class, spec: CancelSpec) -> bool:
    return any(
        section.subject == spec.subject
        and section.number == spec.number
        and (spec.section is None or section.section == spec.section)
        for section in item.sections
    )


def _with_placeholder(
    records: Iterable[Mapping[str, object]], placeholder: str
) -> list[dict[str, object]]:
    result = []
    for row in records:
        normalized = record_utils.normalize_columns(row)
        if not record_utils.text(normalized.get("Instructor")):
            normalized["Instructor"] = placeholder
        result.append(normalized)
    return result


def build_draft_schedule(
    template: Schedule,
    changes: TermChanges,
    *,
    placeholder_instructor: str = DEFAULT_PLACEHOLDER_INSTRUCTOR,
) -> tuple[Schedule, DraftReport]:
    """Apply ``changes`` on top of ``template``; return the draft plus a
    report of what actually happened.

    - cancelled courses are dropped outright;
    - every remaining section a departed instructor was teaching is
      reassigned to ``placeholder_instructor`` (open, not deleted -- the
      course is usually still needed, just needs a new teacher). A class
      whose two rows must share one instructor by its own validation
      (``FourCreditClass``, ``CoreqClass``) gets both rows reassigned
      together, since replacing only one would break that pairing;
    - new offerings are appended, grouped by ``Schedule.from_records``
      exactly the way an uploaded CSV is grouped -- a two-row entry
      (four-credit, hybrid, coreq, cross-listed) is recognized
      automatically from its own rows.
    """
    matched_specs: set[int] = set()
    kept: list[Class] = []
    cancelled: list[str] = []
    for item in template.classes:
        hits = [i for i, spec in enumerate(changes.cancel) if _cancels(item, spec)]
        if hits:
            matched_specs.update(hits)
            cancelled.append(item.course_ids[0])
        else:
            kept.append(item)
    unmatched_cancels = tuple(
        spec for i, spec in enumerate(changes.cancel) if i not in matched_specs
    )

    draft = Schedule(kept)

    departed = set(changes.departures)
    seen_instructors = {
        section.instructor for item in template.classes for section in item.sections
    }
    departures_not_found = tuple(
        name for name in changes.departures if name not in seen_instructors
    )

    reassigned: list[str] = []
    for item in list(draft.classes):
        matches = [i for i, s in enumerate(item.sections) if s.instructor in departed]
        if not matches:
            continue
        course_id = item.course_ids[0]
        for index in matches:
            try:
                draft.change_instructor(course_id, placeholder_instructor, record=index)
            except ValueError:
                # Paired kind requires both rows to share one instructor
                # (FourCreditClass, CoreqClass) -- replacing only one row
                # would leave the pair invalid, so replace both.
                draft.change_instructor(course_id, placeholder_instructor)
                break
        reassigned.append(course_id)

    added: list[str] = []
    if changes.new_sections:
        rows = _with_placeholder(changes.new_sections, placeholder_instructor)
        for item in Schedule.from_records(rows).classes:
            draft.add(item)
            added.append(item.course_ids[0])

    report = DraftReport(
        cancelled=tuple(cancelled),
        unmatched_cancels=unmatched_cancels,
        reassigned=tuple(reassigned),
        departures_not_found=departures_not_found,
        added=tuple(added),
    )
    return draft, report


def build_draft(
    template_path: str | Path,
    changes_path: str | Path,
    *,
    output_path: str | Path | None = None,
    placeholder_instructor: str = DEFAULT_PLACEHOLDER_INSTRUCTOR,
) -> tuple[Schedule, DraftReport]:
    """Read last term's schedule file plus this term's change-list TOML,
    and return next term's draft ``Schedule`` plus a report of what
    changed. Pass ``output_path`` to also write the draft out as an
    Excel file, ready to feed into the CLI solve stage or directly into
    ``solver.solve()``.
    """
    template_path = Path(template_path)
    # dtype=str -- without it pandas silently infers numeric types for
    # numeric-looking text columns (course "Number", "Room", "Section",
    # ...), stripping leading zeros ("0803" -> 803, "001" -> 1). See the
    # identical comment on webapp._read_dataframe, which this mirrors.
    dataframe = (
        pd.read_csv(template_path, dtype=str)
        if template_path.suffix.lower() == ".csv"
        else pd.read_excel(template_path, dtype=str)
    )
    template = Schedule.from_dataframe(dataframe.dropna(how="all"))
    changes = load_changes(changes_path)
    draft, report = build_draft_schedule(
        template, changes, placeholder_instructor=placeholder_instructor
    )
    if output_path is not None:
        draft.to_raw_excel(output_path)
    return draft, report


def _main() -> None:
    import argparse

    parser = argparse.ArgumentParser(
        description=(
            "Build next term's draft schedule from last term's file plus "
            "a change-list TOML (see inputs/TEMPLATE/changes.toml)."
        )
    )
    parser.add_argument("template", help="last term's schedule (CSV/XLSX)")
    parser.add_argument("changes", help="this term's change-list TOML")
    parser.add_argument("-o", "--output", help="write the draft here (.xlsx)")
    parser.add_argument(
        "--placeholder",
        default=DEFAULT_PLACEHOLDER_INSTRUCTOR,
        help=(
            "instructor placeholder for open sections "
            f"(default: {DEFAULT_PLACEHOLDER_INSTRUCTOR!r})"
        ),
    )
    args = parser.parse_args()

    _, report = build_draft(
        args.template,
        args.changes,
        output_path=args.output,
        placeholder_instructor=args.placeholder,
    )

    print(f"Cancelled ({len(report.cancelled)}):")
    for course_id in report.cancelled:
        print(f"  - {course_id}")
    if report.unmatched_cancels:
        print("Cancel specs that matched nothing in the template (check for typos):")
        for spec in report.unmatched_cancels:
            section = f"-{spec.section}" if spec.section else " (all sections)"
            print(f"  - {spec.subject} {spec.number}{section}")
    print(f"Reassigned to placeholder ({len(report.reassigned)}):")
    for course_id in report.reassigned:
        print(f"  - {course_id}")
    if report.departures_not_found:
        print("Departures never seen as an instructor in the template (check spelling):")
        for name in report.departures_not_found:
            print(f"  - {name}")
    print(f"Added ({len(report.added)}):")
    for course_id in report.added:
        print(f"  - {course_id}")
    if args.output:
        print(f"\nDraft written to {args.output}")


if __name__ == "__main__":
    _main()
