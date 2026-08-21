# Section demand analysis

`class_schedule.section_demand` cross-references a term's schedule export
against a Cube1-style enrollment report to flag which courses are full
enough to justify one more section next term. See the module's own
docstring in
[`src/class_schedule/section_demand.py`](../src/class_schedule/section_demand.py)
for the full method; this file specifies the two input formats and gives
usage examples.

## Running it

```powershell
uv run python -m class_schedule.section_demand "Course Schedule Report.csv" "Cube1.xlsx"
```

Add `--all` to see every course's numbers, not just the ones flagged.
`-o analysis.csv` also writes the full table to a CSV; `-o analysis.md`
writes it as the same Markdown table shown below instead.

## Input 1: the schedule export

A CSV or XLSX with these columns present (extra columns are ignored):

| Column | Meaning |
|---|---|
| `Subject` | e.g. `MATH`, `STAT` |
| `Number` | course number, e.g. `1113` -- read as text, so a leading-zero number like `0803` survives |
| `Section` | section code, e.g. `001`, `F01`, `P01`, `TC1` |
| `Instructor` | used only to match a coreq/hybrid pair's two rows back to each other, same as elsewhere in this project |
| `CRN` | the registration record id -- the join key against the Cube1 export |
| `Seats_Avail` | `"seats_available / max_enrolled / room_capacity"`, three numbers separated by `/`. `room_capacity` is `"na"` for an online/TBA section (no physical room). |

Grouping rows into atomic courses is delegated to
`schedule_model.Schedule.from_dataframe`, so this file also needs
whatever *that* needs to build a legal `Section` from each row (a
Time Slot or Days+Start, a Duration or Credits, ...) -- in practice, this
is the same "Course Schedule Report" shape `class_schedule.term_builder`
reads (see its own docs in the main README); if you already have that
file for a term, it works here unchanged.

### `Seats_Avail`'s three numbers

Reverse-engineered against a real export by cross-referencing it against
that export's own Cube1 headcounts (not guessed) -- confirmed:

```
seats_available == max_enrolled - final_headcount
```

for every row checked, including the confusing case where several
remedial courses have `max_enrolled = 0` (every seat is filled through a
manual registration override, not the normal self-enroll cap), which
makes `seats_available` a negative number equal to `-final_headcount`.
Neither of the first two numbers is what this module actually uses --
`room_capacity` (the third number) is the one that matters here, since
it's the actual ceiling relevant to "would a new section have room to
fill."

### Concurrent-enrollment sections are dropped automatically

Any section whose code starts with `P`, `ET`, or `A` (high-school
dual-credit and satellite-campus sections) is excluded before any totals
are computed -- this comes for free from reusing
`Schedule.from_dataframe`'s own grouping (see "Atomic course grouping"
below), the same convention every other tool in this project already
uses. Confirmed against a real Cube1 export: these sections have no
Cube1 headcount row at all, so including them would only ever contribute
a spurious "missing headcount" warning, never real data.

## Input 2: the Cube1 headcount export

An XLSX shaped like a raw OLAP-cube pull, not a plain table -- this
module locates the header row itself rather than assuming a fixed row
number, so extra rows above or below the data block are fine:

```
                Total by ROWS
CRN             Course Start Date Headcount   Final Headcount
                Value                         Value
20450           26                            21
20470           12                            10
...
Total by COLUMNS  <sum>                        <sum>
```

- The header row is wherever the first column reads exactly `CRN`.
- The row directly below it ("Value"/"Value") is a sub-header and is
  skipped.
- Data rows follow, one per CRN.
- Reading stops at the first row whose first column isn't a plain CRN
  number -- normally the trailing `Total by COLUMNS` row.

**Course Start Date Headcount** is the enrollment snapshot taken at the
start of the term; **Final Headcount** is enrollment after that term's
drops. This module always uses the *start* number for its enrollment
totals -- capacity planning cares about who actually showed up wanting a
seat, not who was still registered after the add/drop window closed.

## Atomic course grouping

This is the same "atomic class" grouping used everywhere else in this
project (`schedule_model.Schedule.from_dataframe` -- concurrent-
enrollment sections dropped, four-credit/hybrid/coreq/cross-listed pairs
recognized from their own two rows), reused here directly rather than
reimplemented, plus one refinement specific to this module's "is this
one thing" question:

- a **coreq pair** (two different courses always taken together, e.g.
  MATH 1003 + MATH 0803) is its own bucket, `"MATH 0803 / MATH 1003"` --
  pooling it into either course's standalone bucket would be wrong in
  both directions;
- a **hybrid pairing** (the "F"/"M"-prefixed hyflex offering of a
  course) is its own bucket, `"MATH 1113 (Hybrid)"` -- a materially
  different offering from that course's plain sections;
- a **same-course honors pair** ("001"/"H01") folds into the plain
  course bucket -- still one ordinary section, just also open to honors
  students;
- everything else is the plain `"SUBJECT NUMBER"` bucket.

A CRN is one registration record, not one CSV row -- a four-credit or
hybrid pairing's two rows share one CRN, counted once. A coreq pair's
two rows are two different courses with two different CRNs; only the
first course's own headcount is used (coreq registration locks the two
together, so summing both would roughly double-count the same students).

## The recommendation rule

For each atomic course bucket (see above):

```
avg_capacity_per_section   = total_capacity / section_count
projected_avg_enrollment   = total_enrollment / (section_count + 1)

needs_new_section  =  projected_avg_enrollment > 0.5 * avg_capacity_per_section
```

In words: even after spreading this course's current total enrollment
across one *additional* section, would each section still average more
than half of one existing section's capacity? If yes, that's read as
real unmet demand rather than a marginal, likely-to-go-half-empty add.

An online/TBA section has no room, so no real capacity figure -- it's
assumed at a flat **30 seats** (`DEFAULT_ONLINE_CAPACITY` in the module)
rather than being excluded from `section_count`/`total_capacity`, so a
partly- or entirely-online course still gets a real recommendation
instead of being skipped. The CLI output lists which courses included an
assumed-capacity section, so the assumption stays visible rather than
silently baked into a number.

A CRN present in the schedule export but missing from the Cube1 export
(happens, rarely -- e.g. a brand-new section added after the Cube1 pull)
is excluded from that course's enrollment total and listed under
"CRNs with no Cube1 headcount match" in the output, rather than silently
treated as zero enrollment without a trace.
