# Lecture/lab classes

`LectureLabClass` represents one offering with one lecture row and two lab
rows. It preserves all three source rows but exposes only two scheduling
decisions: the lecture and the 170-minute lab. Its catalog credits count once.

## Import recognition

After explicitly configured relationships, the same-course grouping step
recognizes a three-row group when all of these conditions hold:

- Identical `Subject`, `Number`, and `Section`, using the existing normalized
  identity rules. CRN and row order do not determine the group.
- One lecture (`CLAS`, `LEC`, or `Lecture`, ignoring case) and two `LAB` rows.
  `Meeting Type` is accepted as an alias of `Type`, alongside `Schedule Type`.
- One identical, nonblank instructor across all three rows.
- Physical times and nonblank rooms on all three rows.
- The labs have the same weekdays and start time, different `(Building, Room)`
  locations, and durations of exactly 50 and 170 minutes.

This recognition precedes the old rejection of more than two same-identity
rows and precedes automatic cross-list processing. Cross-list markers on these
rows remain source data; they do not turn the two labs into separate classes.
A three-row group that fails recognition is rejected with the specific reason.
There is no four-credit requirement.

Lecture/lab time overlap is a reportable `lecture_lab_invalid` issue, so an
imported lecture can be moved out of its lab's way. The solver forbids that
overlap. Wrong row counts, roles, identities, instructors, or fixed assignments
are rejected during construction.

## Editing and scheduling

| Field | Lecture | Labs |
| --- | --- | --- |
| Instructor | Editing any row updates all three | Same instructor as lecture |
| Building and room | Fixed to imported assignment | Each lab keeps its own imported location |
| Weekdays and start | Editable | Fixed by default; optionally move together |
| Duration | Keeps imported duration | Always 50 / 170 minutes |

Use an explicit source record index for time edits. Record indexes refer to the
original three-row order, including when the lab rows precede the lecture.
Changing either lab's time, when enabled, changes both lab starts and weekdays
without changing either duration. Web edits, Python `change_*` methods, and
TOML overrides enforce the same restrictions. The web UI disables fixed room
controls and fixed lab time controls/dragging.

For a Monday lab starting at 13:00, one solver decision reserves:

| Resource | Reservation |
| --- | --- |
| Instructor | Monday 13:00–15:50 |
| Long lab room | Monday 13:00–15:50 |
| Short lab room | Monday 13:00–13:50 |

The short reservation uses the long lab's selection variable and adds no
independent instructor decision or duplicate teaching load. Another class may
use the short room starting at 13:50. Lecture and lab must share an instructor
and cannot overlap on any common weekday. Fixed locations remain available as
the class's candidates even if the general room list contains alternatives;
applicable hard constraints still apply to both lab locations.

General teaching preferences are evaluated on the two scheduling entries.
The short room additionally evaluates preferences with an explicit room
selector. It does not repeat general course/time preferences or create an
extra meeting in back-to-back calculations.

## Configuration

Template inference writes this relationship to `courses.toml`:

```toml
[[relationships]]
kind = "lecture_lab"
members = ["CHEM 3245 1"]
lab_time_editable = false
```

There is exactly one offering member, selecting all three of its source rows.
Course-level members are supported through the existing common-section
expansion. This type requires its source template rows: configuration-only
synthesis is rejected because it cannot invent the fixed rooms and lab time.

Time patterns use roles `lecture_lab_lecture` and `lecture_lab_lab`. Inference
emits the lecture and 170-minute lab patterns, not a separate 50-minute lab
decision. A fixed lab is allowed to retain its source time without a matching
general calendar pattern. The lecture still follows its configured domain.

To enable future lab moves, set `lab_time_editable = true` and provide legal
170-minute `lecture_lab_lab` patterns. Both labs then move together. The
50-minute room occupancy follows the selected lab start. Rooms and durations
remain fixed. Reverting to `false` while a saved schedule differs from its
original lab time rejects that schedule; restore the original time before
re-locking, or deliberately import a new baseline template.

## Persistence and views

Source record order is preserved. Flat CSV/XLSX exports retain three rows. The
instructor timetable displays the lecture and long lab; the room timetable
displays all three location occupancies. Course view retains all source rows.

Normalized lecture/lab rows carry a `Lecture Lab Baseline` JSON column holding
the original room, building, lab time, and duration for each source row. This
metadata survives cleaning, export, API round trips, and reload, so a changed
assignment does not silently become a new fixed baseline. Fresh external
templates without this column establish the initial baseline. Keep this column
in generated files; removing it and reimporting explicitly establishes a new
baseline. `lab_time_editable` remains configuration policy, not spreadsheet
metadata.

## Implementation

- `class_model.py`: structural recognition, fixed baselines, editing rules,
  and lecture/lab overlap predicate.
- `schedule_model.py`: explicit/intrinsic grouping and timetable selection.
- `config_schema.py`, `config_inference.py`, `solver/config.py`: relationship
  policy, inference, and calendar coverage.
- `NormalClass.scheduling_entries()`: default one decision per source row;
  `LectureLabClass` returns lecture and long lab.
- `scheduling_record_indexes()`: maps each decision to its source rows for
  locks; short and long lab locks constrain the same decision.
- `resource_usage()`: additional room-only reservations for a decision.
- `with_scheduling_assignments()`: writes decisions back to source rows while
  preserving per-instance policy and fixed baselines.
- `solver/engine.py`, `candidates.py`, `constraints.py`, `result.py`: consume
  those interfaces and preserve three-row output from two decisions.
- `webapp.py`: per-record editable/link metadata; `web/app.js` consumes it.

Run the focused regression tests with:

```powershell
uv run python -m unittest tests.test_lecture_lab -v
```

The tests cover recognition independent of source order, invalid near-matches,
editing and override restrictions, persistent baselines, two solver decisions,
short-room boundary conflicts, internal overlap, unlocked lab moves, excluding
previous solutions, web upload/editing, and three-row Excel exports. An optional
local check also reads `config/27/202720 maps.xlsx` and verifies all three
lecture/lab groups through configuration inference and reconciliation.
