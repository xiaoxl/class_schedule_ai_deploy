"""Flag courses that could support one more section, by cross-referencing
a schedule export's enrollment against a Cube1-style headcount export.

Two inputs, joined on CRN:

  - a schedule export (see ``load_schedule_rows`` and
    ``docs/section_demand.md`` for the exact required shape -- the same
    "Course Schedule Report" CSV format ``term_builder`` reads);
  - a Cube1 headcount export (see ``load_headcounts`` /
    ``docs/section_demand.md``) -- one row per CRN with a
    "Course Start Date Headcount" and a "Final Headcount".

**Atomic course grouping.** This is the same "atomic class" grouping
``schedule_model.Schedule.from_dataframe`` already uses everywhere else
in this project (concurrent-enrollment "P"/"ET"/"A" sections dropped,
four-credit/hybrid/coreq/cross-listed pairs recognized from their own
two rows) -- reused here directly, not reimplemented, so "how many
sections does this atomic course have" always means the same thing
project-wide. One further refinement on top of ``Class.course_ids``,
specific to this module's own "is this one thing" question:

  - a coreq pair (e.g. MATH 1003 + MATH 0803) is its own bucket, keyed
    ``"MATH 0803 / MATH 1003"`` -- two different courses, but always
    taken together, so pooling them with either course's *standalone*
    sections would be wrong in both directions;
  - likewise a genuine cross-listing between two different subjects;
  - a hybrid pairing (one course, but the "F"/"M"-prefixed hyflex
    offering) is its own bucket, keyed ``"MATH 1113 (Hybrid)"`` -- a
    materially different offering from that course's plain sections, not
    pooled with them;
  - a same-course honors pair (e.g. "001"/"H01", ``CrossListingClass``
    but *not* a cross-subject listing) folds into the plain course
    bucket -- it's still one ordinary section, just also open to honors
    students;
  - everything else (``NormalClass``, ``FourCreditClass``) is the plain
    ``"SUBJECT NUMBER"`` bucket.

A CRN is one registration record, not one CSV row -- a four-credit or
hybrid pairing's two rows share one CRN, so its enrollment/capacity is
counted once, not twice. A coreq pair's two rows are two *different*
courses with two different CRNs; only the first course's own headcount
is used (coreq registration locks the two together, so they track each
other closely, and summing both would roughly double-count the same
group of students).

The recommendation rule (as specified): for each atomic course bucket,
take the total enrollment (each section's Cube1 *start-of-term*
headcount -- the number that matters for capacity planning is who showed
up, not who was left registered after drops) and total room capacity
(from the schedule export's own ``Seats_Avail`` column, see
``parse_seats_avail``). A bucket needs one more section when, even after
spreading that same total enrollment across one additional section, each
section would still average more than half of one existing section's
capacity:

    total_enrollment / (section_count + 1)  >  0.5 * (total_capacity / section_count)

An online/TBA section has no physical room, so no real capacity figure
-- assumed at a flat ``DEFAULT_ONLINE_CAPACITY`` (30 seats) instead of
being excluded, so a partly- or entirely-online bucket still gets a real
recommendation rather than being skipped.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import pandas as pd

from . import record_utils
from .class_model import Class, HybridClass
from .schedule_model import Schedule

REQUIRED_SCHEDULE_COLUMNS = ("Subject", "Number", "Section", "Instructor", "CRN", "Seats_Avail")

# An online/TBA section has no room, so no real capacity figure -- assumed
# flat instead of excluding it from the capacity math entirely, so a
# partly- or entirely-online course still gets a real recommendation.
DEFAULT_ONLINE_CAPACITY = 30.0


@dataclass(frozen=True)
class SeatsAvail:
    """One "Seats_Avail" cell, e.g. "-21 / 0 / 36" or "5 / 32 / 36".

    Reverse-engineered against a real Cube1 export (not guessed): cross-
    referencing ``seats_available``/``max_enrolled`` against Cube1's own
    ``final_headcount`` for the same CRNs confirms
    ``seats_available == max_enrolled - final_headcount`` exactly, for
    every row checked, including the confusing negative-``max_enrolled``
    sections (several remedial courses register everyone through an
    override, i.e. ``max_enrolled = 0``, hence a "seats available" of
    ``-headcount``). ``room_capacity`` is a separate, independent figure
    -- the physical room's own capacity -- and is what this module's
    aggregate math actually uses; ``None`` for an online/TBA section
    ("na" in the source column, no room to have a capacity).
    """

    seats_available: float | None
    max_enrolled: float | None
    room_capacity: float | None


def parse_seats_avail(value: object) -> SeatsAvail:
    """Parse one "Seats_Avail" cell. Any shape other than exactly three
    ``/``-separated parts (including a blank cell) parses as all-``None``
    -- callers that need capacity data treat that the same as an
    online/TBA section (no room capacity to size against)."""
    text = record_utils.text(value)
    parts = [p.strip() for p in text.split("/")]
    if len(parts) != 3:
        return SeatsAvail(None, None, None)

    def _number(part: str) -> float | None:
        return None if part.lower() == "na" or not part else float(part)

    return SeatsAvail(_number(parts[0]), _number(parts[1]), _number(parts[2]))


def load_headcounts(path: str | Path) -> dict[str, tuple[float, float]]:
    """Parse a Cube1-style enrollment export into
    ``{CRN: (start_headcount, final_headcount)}``.

    The header row ("CRN" in the first column) is located dynamically,
    not assumed to sit at a fixed row number -- everything above it (a
    merged title row) and the "Value" sub-header row right below it are
    skipped automatically. Reading stops at the first row whose first
    column isn't a plain CRN number (Cube exports end with a
    "Total by COLUMNS" summary row) -- see ``docs/section_demand.md`` for
    the exact expected shape.
    """
    raw = pd.read_excel(path, header=None)
    header_rows = raw.index[raw[0].astype(str).str.strip() == "CRN"]
    if len(header_rows) == 0:
        raise ValueError(
            f"{path}: no 'CRN' header row found -- see docs/section_demand.md "
            "for the expected Cube1 export shape"
        )
    data_start = header_rows[0] + 2  # header row itself, then the "Value" sub-header row

    result: dict[str, tuple[float, float]] = {}
    for _, row in raw.iloc[data_start:].iterrows():
        crn_cell = row[0]
        if pd.isna(crn_cell):
            continue
        crn_text = str(crn_cell).strip()
        try:
            crn = str(int(float(crn_text)))
        except ValueError:
            break  # the trailing "Total by COLUMNS" row (or any other non-CRN row)
        start_headcount = float(row[1]) if pd.notna(row[1]) else 0.0
        final_headcount = float(row[2]) if pd.notna(row[2]) else 0.0
        result[crn] = (start_headcount, final_headcount)
    return result


def load_schedule_rows(path: str | Path) -> pd.DataFrame:
    """Read a schedule export CSV/XLSX, ``dtype=str`` throughout (a CRN or
    course Number read as a numeric type silently strips leading zeros --
    the same reason ``term_builder``/``webapp`` both force this too), and
    validate it has every column this module needs directly (beyond what
    ``Schedule.from_dataframe`` itself already requires for grouping).
    Raises ``ValueError`` naming exactly what's missing rather than a
    bare ``KeyError`` deeper in the pipeline -- see
    ``docs/section_demand.md`` for the required shape.
    """
    path = Path(path)
    dataframe = (
        pd.read_csv(path, dtype=str)
        if path.suffix.lower() == ".csv"
        else pd.read_excel(path, dtype=str)
    )
    missing = [c for c in REQUIRED_SCHEDULE_COLUMNS if c not in dataframe.columns]
    if missing:
        raise ValueError(
            f"{path}: missing required column(s) {missing} -- "
            "see docs/section_demand.md for the required schedule export shape"
        )
    return dataframe.dropna(how="all")


def _row_key(subject: str, number: str, section: str, instructor: str) -> tuple[str, str, str, str]:
    """A raw schedule row's natural key, in exactly the normalized shape
    ``Section``'s own fields end up in (see ``class_model.Section.__post_init__``)
    -- used to match a grouped ``Class``'s ``Section`` back to the original
    row that carried its CRN, which the ``Section``/``Class`` model itself
    has no field for and so can't carry through its own grouping pass."""
    return (
        record_utils.text(subject).upper(), record_utils.text(number),
        record_utils.text(section).upper(), record_utils.text(instructor),
    )


def _atomic_course_key(item: Class) -> str:
    """See the module docstring's "Atomic course grouping" section."""
    courses = sorted({f"{s.subject} {s.number}" for s in item.sections})
    if len(courses) > 1:
        return " / ".join(courses)  # a coreq pair, or a genuine cross-subject listing
    if isinstance(item, HybridClass):
        return f"{courses[0]} (Hybrid)"
    return courses[0]  # NormalClass, FourCreditClass, or a same-course honors pair


@dataclass(frozen=True)
class CourseDemand:
    """One atomic course bucket's pooled enrollment/capacity picture, and
    the "add one more section" recommendation derived from it.
    ``section_enrollments`` holds one entry per section in CRN-lookup
    order, ``None`` where that section's CRN had no Cube1 match --
    ``total_enrollment`` already excludes those, this is for a
    per-section breakdown report. ``online_section_count`` (out of
    ``section_count``) used ``DEFAULT_ONLINE_CAPACITY`` rather than a
    real room capacity -- kept separate for transparency even though
    it's already folded into ``total_capacity``.
    """

    course: str
    in_person_section_count: int
    online_section_count: int
    total_enrollment: float
    total_capacity: float
    section_enrollments: tuple[float | None, ...]
    missing_headcount_crns: tuple[str, ...]

    @property
    def section_count(self) -> int:
        return self.in_person_section_count + self.online_section_count

    @property
    def avg_capacity_per_section(self) -> float | None:
        return self.total_capacity / self.section_count if self.section_count else None

    @property
    def projected_avg_enrollment(self) -> float:
        return self.total_enrollment / (self.section_count + 1)

    @property
    def needs_new_section(self) -> bool:
        """True when, even spread across one additional section, average
        enrollment per section would still exceed half of one existing
        section's capacity. Always ``False`` for a bucket with no
        sections at all (shouldn't happen in practice -- a bucket is
        only created from at least one real class)."""
        avg_capacity = self.avg_capacity_per_section
        if avg_capacity is None:
            return False
        return self.projected_avg_enrollment > 0.5 * avg_capacity


def analyze(schedule_path: str | Path, cube_path: str | Path) -> list[CourseDemand]:
    """Cross-reference ``schedule_path`` against ``cube_path`` and return
    one ``CourseDemand`` per atomic course bucket, sorted by bucket name.
    See the module docstring for the full method.
    """
    schedule_df = load_schedule_rows(schedule_path)
    headcounts = load_headcounts(cube_path)

    parsed_capacity = schedule_df["Seats_Avail"].apply(
        lambda v: parse_seats_avail(v).room_capacity
    )
    rows = schedule_df.assign(_room_capacity=parsed_capacity)

    # Natural-key lookup back to (CRN, room_capacity) for the raw row a
    # grouped Section came from -- see _row_key. A hybrid pair's two rows
    # share one key (same section code and instructor on both); prefer
    # whichever of them carries a real capacity when that happens (the
    # other is the TBA row, which never does).
    lookup: dict[tuple[str, str, str, str], tuple[str, float | None]] = {}
    for _, row in rows.iterrows():
        key = _row_key(row["Subject"], row["Number"], row["Section"], row["Instructor"])
        capacity = row["_room_capacity"]
        # pandas silently upcasts this column's None entries to NaN once
        # any real float is mixed in -- pd.isna() catches both, a plain
        # `is None`/`is not None` check would miss the NaN case and never
        # let a real capacity win over an already-cached blank one.
        existing = lookup.get(key)
        if existing is None or (pd.isna(existing[1]) and pd.notna(capacity)):
            lookup[key] = (record_utils.text(row["CRN"]), capacity)

    grouped = Schedule.from_dataframe(schedule_df)

    buckets: dict[str, dict] = {}
    unmatched: list[str] = []
    for item in grouped.classes:
        section = item.sections[0]
        match = lookup.get(_row_key(
            section.subject, section.number, section.section, section.instructor
        ))
        bucket = buckets.setdefault(_atomic_course_key(item), {
            "in_person_section_count": 0, "online_section_count": 0,
            "total_enrollment": 0.0, "total_capacity": 0.0,
            "section_enrollments": [], "missing": [],
        })
        if match is None:
            unmatched.append(section.course_id)
            continue
        crn, capacity = match

        headcount = headcounts.get(crn)
        if headcount is None:
            bucket["missing"].append(crn)
            bucket["section_enrollments"].append(None)
        else:
            bucket["total_enrollment"] += headcount[0]  # start-of-term
            bucket["section_enrollments"].append(headcount[0])

        if capacity is None or pd.isna(capacity):
            bucket["online_section_count"] += 1
            bucket["total_capacity"] += DEFAULT_ONLINE_CAPACITY
        else:
            bucket["in_person_section_count"] += 1
            bucket["total_capacity"] += capacity

    if unmatched:
        raise ValueError(
            "Internal error: could not match these grouped sections back "
            f"to a raw schedule row (please report): {unmatched}"
        )

    return sorted(
        (
            CourseDemand(
                course=course,
                in_person_section_count=b["in_person_section_count"],
                online_section_count=b["online_section_count"],
                total_enrollment=b["total_enrollment"],
                total_capacity=b["total_capacity"],
                section_enrollments=tuple(b["section_enrollments"]),
                missing_headcount_crns=tuple(b["missing"]),
            )
            for course, b in buckets.items()
        ),
        key=lambda d: d.course,
    )


def to_markdown(results: list[CourseDemand]) -> str:
    """Render the full analysis as a Markdown table -- one row per
    atomic course, each section's own enrollment listed individually
    (not just the pooled total), matching the report format this module
    was built to reproduce on demand."""
    lines = [
        "| Course | Sections | Enrollment per section | Total enrollment | Avg capacity/section | Recommend new section? |",
        "|---|---|---|---|---|---|",
    ]
    for d in results:
        per_section = ", ".join(
            "?" if e is None else f"{e:g}" for e in d.section_enrollments
        )
        avg_capacity = "n/a" if d.avg_capacity_per_section is None else f"{d.avg_capacity_per_section:g}"
        recommend = "**Yes**" if d.needs_new_section else "No"
        lines.append(
            f"| {d.course} | {d.section_count} | {per_section} | "
            f"{d.total_enrollment:g} | {avg_capacity} | {recommend} |"
        )
    return "\n".join(lines)


def _main() -> None:
    import argparse

    parser = argparse.ArgumentParser(
        description=(
            "Flag courses that could support one more section, by "
            "cross-referencing a schedule export against a Cube1-style "
            "enrollment headcount export. See docs/section_demand.md."
        )
    )
    parser.add_argument("schedule", help="schedule export (CSV/XLSX)")
    parser.add_argument("cube", help="Cube1-style headcount export (XLSX)")
    parser.add_argument(
        "--all", action="store_true",
        help="print every course, not just the ones flagged for a new section",
    )
    parser.add_argument(
        "-o", "--output",
        help="also write the full analysis here -- .md for a Markdown table, .csv otherwise",
    )
    args = parser.parse_args()

    results = analyze(args.schedule, args.cube)
    flagged = [d for d in results if d.needs_new_section]

    if args.output:
        if args.output.lower().endswith(".md"):
            Path(args.output).write_text(to_markdown(results), encoding="utf-8")
        else:
            pd.DataFrame([
                {
                    "Course": d.course,
                    "Sections": d.section_count,
                    "InPersonSections": d.in_person_section_count,
                    "OnlineSections": d.online_section_count,
                    "SectionEnrollments": ",".join(
                        "?" if e is None else f"{e:g}" for e in d.section_enrollments
                    ),
                    "TotalEnrollment": d.total_enrollment,
                    "TotalCapacity": d.total_capacity,
                    "AvgCapacityPerSection": d.avg_capacity_per_section,
                    "ProjectedAvgEnrollmentIfAdded": d.projected_avg_enrollment,
                    "NeedsNewSection": d.needs_new_section,
                    "MissingHeadcountCRNs": ",".join(d.missing_headcount_crns),
                }
                for d in results
            ]).to_csv(args.output, index=False)
        print(f"Full analysis written to {args.output}\n")

    print(f"Courses recommended for one more section ({len(flagged)}):")
    for d in flagged:
        print(
            f"  {d.course:20s} sections={d.section_count:2d}  "
            f"enrollment={d.total_enrollment:5.0f}  capacity={d.total_capacity:5.0f}  "
            f"avg/section={d.avg_capacity_per_section:5.1f}  "
            f"projected={d.projected_avg_enrollment:5.1f}"
        )

    has_online = [d for d in results if d.online_section_count]
    if has_online:
        print(
            f"\nCourses with online/TBA sections "
            f"(capacity assumed at {DEFAULT_ONLINE_CAPACITY:g}/section):"
        )
        for d in has_online:
            print(f"  {d.course:20s} {d.online_section_count} of {d.section_count} sections")

    with_missing = [d for d in results if d.missing_headcount_crns]
    if with_missing:
        print(f"\nCRNs with no Cube1 headcount match (excluded from enrollment totals):")
        for d in with_missing:
            print(f"  {d.course:20s} {', '.join(d.missing_headcount_crns)}")

    if args.all:
        print(f"\nAll {len(results)} courses:")
        for d in results:
            flag = "*" if d.needs_new_section else " "
            avg = f"{d.avg_capacity_per_section:5.1f}" if d.avg_capacity_per_section is not None else "  n/a"
            print(
                f"  {flag} {d.course:20s} sections={d.section_count:2d}  "
                f"enrollment={d.total_enrollment:5.0f}  capacity={d.total_capacity:5.0f}  "
                f"avg/section={avg}  projected={d.projected_avg_enrollment:5.1f}"
            )


if __name__ == "__main__":
    _main()
