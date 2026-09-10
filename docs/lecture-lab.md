# Lab and lecture/lab classes

Two atomic-class kinds model chemistry-style labs. Both share the
split-room machinery in `class_model._LectureLabMixin`.

- **`LabClass`** -- one student lab meeting on its own. Two LAB source
  rows under a single identity: a 170-minute row in the long room and a
  50-minute row in the short room, same weekdays and start, one shared
  instructor, two different `(Building, Room)` locations. One scheduling
  decision (the 170-minute lab); the short room rides along.
- **`LectureLabClass`** -- a lecture row linked to its lab. Two or three
  source rows: exactly one `CLAS`/`LEC`/`Lecture` row plus one or two
  `LAB` rows. The lab half is a `LabClass`-shaped split pair or a single
  ordinary LAB row. Two scheduling decisions: the lecture and the lab.

`Meeting Type` is accepted as an alias of `Type` (also `Schedule Type`).

## The split-room lab

A lab meeting books two rooms: the long room for the whole 170 minutes
and the short room only for the first 50. That is **one** solver decision
-- the 170-minute lab. The short room is an extra room-only reservation
on the same selection variable (`resource_usage`); it adds no independent
instructor decision, no duplicate teaching load, and is not a third
meeting in back-to-back or preference calculations. Another class may use
the short room starting at 13:50 for a 13:00 lab.

For a Monday lab starting at 13:00, one decision reserves:

| Resource | Reservation |
| --- | --- |
| Instructor | Monday 13:00-15:50 |
| Long lab room | Monday 13:00-15:50 |
| Short lab room | Monday 13:00-13:50 |

Applicable hard constraints and room-scoped preferences still apply to
both lab locations.

## Recognition

After explicit `[[relationships]]`, the same-course scan recognizes:

- **Three rows, one identity** -- identical `Subject`, `Number`,
  `Section`, one lecture and two 50/170 LAB rows -> `LectureLabClass`
  (shared course number).
- **Two rows, one identity, both LAB, 50 + 170 minutes** -> `LabClass`.
  A 50/170 pair that is otherwise malformed (same room, different start,
  instructor mismatch) is a hard `GroupingError`, never silently two
  classes. Two same-identity LAB rows that are *not* a 50/170 split fall
  through to ordinary single classes.
- **Catalog siblings** -- same `Subject`, `Section` and instructor, one
  CLAS row and one or two LAB rows whose course numbers share their stem
  and differ only in the last digit (e.g. `CHEM 3264` lecture +
  `CHEM 3260` lab, or `CHEM 1113` + `CHEM 1111`) -> `LectureLabClass`.
  The lab rows must have rooms; an arranged (roomless) lab links only
  through an explicit relationship. A lecture and lab that merely share
  an instructor and section but whose numbers are unrelated stay
  separate.

This precedes automatic cross-list processing; cross-list markers on
these rows remain source data.

## Editing and scheduling

| Field | Lecture | Lab |
| --- | --- | --- |
| Instructor | Editing any row updates all rows | Same instructor as lecture |
| Building and room | **Editable** | Fixed to the imported assignment |
| Weekdays and start | Editable | Fixed by default; optionally move together |
| Duration | Editable | Always 50 / 170 (or the single lab's length) |

The web UI merges the two lab rows into one entry that shows both fixed
rooms, and disables its room and time controls. Lecture and lab must
share an instructor and cannot overlap on any common weekday
(`lecture_lab_invalid`). A same-course-number lecture keeps its
configured `lecture_lab_lecture` domain; a catalog-sibling lecture is an
ordinary standalone lecture and follows the general calendar (role
`normal`).

Changing either lab's time, when enabled, moves both lab starts (and
weekdays) together without changing either duration. Web edits, Python
`change_*`/`apply_edit`, and TOML overrides enforce the same rules.

## Catalog credits

- `LectureLabClass`, shared course number: the number's inferred credits,
  once (`CHEM 3245` -> 5).
- `LectureLabClass`, catalog siblings: the two numbers' trailing digits
  add (`3264`/`3260` -> 4 + 0 = 4; `1113`/`1111` -> 3 + 1 = 4).
- `LabClass` (no lecture): estimated from the long lab's length at
  roughly one credit per 60 minutes (`round(170 / 60)` -> 3).

## Configuration

Template inference writes, for a shared-number bundle:

```toml
[[relationships]]
kind = "lecture_lab"
members = ["CHEM 3245 1"]
lab_time_editable = false
```

and, for a catalog-sibling pair, two members, lecture course first:

```toml
[[relationships]]
kind = "lecture_lab"
members = ["CHEM 3264 1", "CHEM 3260 1"]
lab_time_editable = false
```

`LabClass` is always structural and needs no relationship. A
`lecture_lab` relationship requires its source template rows;
configuration-only synthesis is rejected because it cannot invent the
fixed rooms and lab time.

Time patterns use roles `lecture_lab_lecture` (shared-number lecture
only) and `lecture_lab_lab`. A fixed lab keeps its source time without a
matching general calendar pattern. To allow future lab moves, set
`lab_time_editable = true` and provide legal 170-minute `lecture_lab_lab`
patterns; both lab rooms then move together and the 50-minute occupancy
follows the selected start. Rooms and durations stay fixed. Reverting to
`false` while a saved schedule differs from its original lab time rejects
that schedule; restore the original time before re-locking.

## Persistence and views

Source record order is preserved; flat CSV/XLSX exports keep every row.
The instructor timetable shows the lecture and the long lab; the room
timetable shows all location occupancies; course view collapses the two
lab rows into one.

LAB rows carry a `Lecture Lab Baseline` JSON column holding the original
room, building, lab time, and duration, so a changed assignment does not
silently become a new fixed baseline. This survives cleaning, export, API
round trips, and reload. Keep the column in generated files; removing it
and reimporting establishes a new baseline. `lab_time_editable` is
configuration policy, not spreadsheet metadata.

## Implementation

- `class_model.py`: `_LectureLabMixin` (roles, split-room `resource_usage`,
  fixed-room/fixed-time locks, `solver_locked_fields`, baseline column),
  `LabClass`, `LectureLabClass`, `lecture_lab_number_siblings`.
- `schedule_model.py`: `_take_lecture_lab_siblings` (catalog-sibling
  structural fallback), the 50/170 `LabClass` branch in
  `_take_same_course`, grouping precedence.
- `config_schema.py`, `config_inference.py`, `solver/config.py`:
  one-or-two-member `lecture_lab` relationships and calendar coverage.
- `solver/candidates.py`, `constraints.py`, `engine.py`, `result.py`:
  two decisions (or one) preserve every source row via
  `with_scheduling_assignments`.
- `pattern_rules.py`: structural roles and the fixed-lab-slot shortcut.
- `webapp.py` / `web/app.js`: per-record `editable_fields` metadata; the
  UI merges the lab rows and locks their controls.

Run the focused tests with:

```powershell
uv run python -m unittest tests.test_lab tests.test_lecture_lab -v
```

They cover recognition (shared number, catalog siblings, single vs split
lab, near-miss rejection), the editable lecture and locked lab, the
short-room boundary and hard rules, persistent baselines, two/one solver
decisions, override restrictions, web edit routing, inference of one- and
two-member relationships, and -- when the local workbook is present --
the real `config/27` template.
