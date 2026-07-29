# Class Schedule

Upload a semester's schedule (CSV or Excel, including ATU's Banner
"Course_Catalog" export), parse it into logical classes, check it for
instructor/room conflicts and soft-preference violations, and optionally
run an OR-Tools solver to fix what it can.

## Setup

```powershell
uv sync
```

## Running the web app

```powershell
uv run uvicorn class_schedule.webapp:app --reload --port 8000
```

Then visit `http://127.0.0.1:8000`. The page:

- accepts a dragged-or-selected CSV/XLSX/XLS schedule and parses it immediately;
- shows the result four ways -- atomic rows, grouped by course, by
  instructor, or by room -- and a violations summary (hard conflicts in
  red, soft preferences in orange/yellow by penalty);
- on "Solve Schedule", runs the solver and shows a solve plan (what
  changed, merged across every attempt back to the original upload, not
  just the last click);
- clicking "Solve Schedule" again on an already-solved result asks for a
  *different* solution rather than risking the same one back -- each
  attempt stays browsable/downloadable via its own tab;
- offers three Excel downloads after every parse or solve: the schedule
  as-is, one worksheet per instructor, and one worksheet per room (each a
  Monday-Friday weekly grid; a real double-booking is shown as one red
  cell listing both classes, not silently dropped).

The backend is stateless per request -- nothing is written to disk or
kept in server memory between calls; the "attempt history" and "solve
plan" above are entirely client-side, reconstructed from what each
`/api/solve` response already returns.

## Data model

- `Section` (`class_model.py`): one CSV row, normalized -- subject,
  number, section, time slot, duration, room, building, instructor, plus
  optional type/title/credits/cross-list.
- `Class`: one atomic, logical class a student enrolls in. Built from one
  or two `Section`s and automatically classified by shape:
  - `NormalClass` -- a single record.
  - `FourCreditClass` -- two records for the *same* course, one MWF and
    one T/R meeting, same instructor.
  - `HybridClass` -- two records for the same course, an M- or F-prefixed
    section, one with a room and one without.
  - `CrossListingClass` -- two records for *different* courses sharing a
    non-empty cross-listing value (accepted from a `Cross-List`-spelled
    column or Banner's `XL Group Code`; either counts, whichever the file
    actually populates), or an honors-section pair (`001`/`H01`) meeting
    at the identical time/room/instructor.
  - `CoreqClass` -- two records for a specific whitelisted course pair
    (`MATH 1003`/`MATH 0803`, `MATH 1113`/`MATH 0903`,
    `MATH 1113`/`MATH 1110`) in the same section, same instructor,
    scheduled back-to-back (or, for a fully online "TC"-prefixed pair,
    same instructor is all that's checked -- there's no physical time to
    validate).
- `Schedule` (`schedule_model.py`): an ordered collection of `Class`
  objects, with import/export, editing, and evaluation.

```python
from class_schedule.schedule_model import Schedule, check_conflicts, check_soft_preferences
from class_schedule.schedule_model import load_persons, load_preferences

schedule = Schedule.from_dataframe(dataframe)   # or Schedule.from_records(list_of_dicts)

for item in schedule:
    print(item.course_ids, type(item).__name__, item.credit_hours)

schedule.change_instructor("MATH 1113-001", "Alice")
schedule.change_time("MATH 1113-001", "TR 9:30am")
schedule.change_room("MATH 1113-001", "Corley 101")

persons = load_persons("config/persons.toml")
preferences = load_preferences("config/preferences.toml")
hard = check_conflicts(schedule)                              # room/instructor double-booking
soft_total, soft = check_soft_preferences(schedule, preferences, persons)  # everything else, including max_load

schedule.to_raw_excel("schedule.xlsx")
schedule.to_instructor_excel("schedule_instructor.xlsx")
schedule.to_room_excel("schedule_room.xlsx")
```

`check_conflicts` is the *only* hard-violation source (a class's own two
rows are never compared against each other -- a genuine cross-listing or
four-credit pair is meant to share room/time/instructor). Everything else
-- including `max_load` -- is scored by `check_soft_preferences`; see the
comment above `OVERLOAD_TOLERANCE` in `schedule_model.py` for the full
over/under-load contract. See `examples/basic_usage.py` for a small
runnable script.

## Config

Four files under `config/`, each with a different lifetime:

- `persons.toml` -- contractual facts: `max_load`, name-matching
  `aliases` (optionally scoped by `subject`, e.g. MATH Jordan vs. STAT
  Jordan), and the `courses` an instructor is qualified to teach.
- `preferences.toml` -- this term's wishes per instructor:
  `overload_penalty` (0-100 -- 0 is entirely fine with going over
  `max_load`, 100 avoids it at essentially any cost, but it's always
  soft, and never applies within +2 credit hours of `max_load` -- that's
  the definition of overload, not a leniency knob), `allow_back_to_back`,
  `preferred_times`/`disliked_times`, `preferred_locations`/
  `disliked_locations`, `preferred_courses`/`disliked_courses`.
  `preferred_*` fields are informational only -- never scored.
- `timeslot.toml` -- the day/duration/start-time combinations
  (`[[calendar.meeting_patterns]]`) the solver may assign, plus
  `[[calendar.blackouts]]` periods nothing may overlap.
- `locations.toml` -- rooms (`[[rooms]]`) the solver may assign as a new
  candidate. A class's existing room stays available as a fallback even
  if it's not listed here.

`reference/historical_rooms.md`, `reference/historical_time_slots.md`,
and `reference/historical_course_variants.md` document how these were
derived from past `MATH`/`STAT` schedules.

## Solver

```python
from class_schedule import solver

config = solver.SolverConfig.load("config")   # reads all four files above
solved = solver.solve(schedule, config, time_limit_seconds=60)

changes = solver.diff_schedules(schedule, solved)   # what actually moved
```

`solve()` searches for the best (instructor, time, room) reassignment per
class using OR-Tools CP-SAT: room/instructor conflicts are weighted so
far above every other term that the optimizer always eliminates them when
an assignment doing so exists, but if it genuinely can't, this still
returns its closest best-effort attempt rather than raising -- call
`check_conflicts`/`check_soft_preferences` on the result to see whether
it's fully clean. `solver.NoFeasibleSchedule` is only raised for a
structural dead end this module can't work around (a section with zero
legal candidates, or no assignment at all -- not even a bad one -- found
within `time_limit_seconds`).

Pass `previous=` (typically the caller's own prior solve output) to
guarantee the result differs from it by at least one section -- this is
what powers the web UI's "solve again for a different option."

## Tests

```powershell
uv run python -m unittest discover -s tests
```

`.dep/` holds the previous implementation (a LangGraph/Ollama scheduling
agent, a different `Class`/`Schedule` model, a CLI) -- kept for reference,
not part of the installed package or the test suite above.
