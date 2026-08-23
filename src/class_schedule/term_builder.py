"""Turn last term's schedule plus a small per-term change list into next
term's starting draft.

Two inputs feed ``build_draft_schedule``:

  - a template ``Schedule`` -- last term's parsed schedule, normally loaded
    through ``schedule_io.read_schedule``;
  - a ``TermChanges`` -- this term's departures, new hires, additions, and
    cancellations, loaded from a small TOML file via
    ``load_changes``. See ``inputs/TEMPLATE/changes.toml`` for the file format
    and a full walkthrough.

The result is a draft ``Schedule`` ready for the CLI or Python solve stage:
cancelled courses are dropped, every
section a departed instructor was teaching is reassigned to a
placeholder instructor (so the solver treats it as open rather than
pinned to someone who's gone), and newly offered courses are appended,
grouped exactly the way ``Schedule.from_records`` groups any other CSV
rows -- a four-credit/hybrid/coreq/cross-listed new offering is
recognized automatically from its own two rows, same as an upload.

This module never writes persons.toml or preferences.toml. A departed
person's max_load/preferences entry still needs to be removed by hand.
"""

from __future__ import annotations

import tomllib
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from pathlib import Path

from . import record_utils
from .class_model import Class
from .schedule_model import Schedule

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
