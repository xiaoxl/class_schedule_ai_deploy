# Class Schedule

Upload a semester's schedule (CSV or Excel, including ATU's Banner
"Course_Catalog" export), parse it into logical classes, check it for
instructor/room conflicts and soft-preference violations, and optionally
run an OR-Tools solver to fix what it can.

## Setup

```powershell
uv sync
```

## Project layout

Code is shared across every term; data is not -- kept apart on purpose
so a term's own files are never mixed into the code, or into another
term's files:

```
src/class_schedule/   shared code -- term-agnostic, never edited per term
config/                durable, cross-term facts: persons.toml, preferences.toml,
                       timeslot.toml, locations.toml (see "Config" below --
                       preferences.toml is per-term *content* but stays here;
                       see that section for why)
inputs/TEMPLATE/       the reusable changes.toml template -- copy it per term
inputs/<term>/         e.g. inputs/27S/ -- that term's own changes.toml, the
                       schedule file it rolled over from, and its Cube1 export
out/<term>/            e.g. out/27S/ -- that term's generated files: starting.csv,
                       starting_noadding.csv, and anything else built for it
docs/                  tool documentation (section_demand.md, ...)
examples/              reference files not tied to any one term's rollover
```

`out/` is this project's per-term results; `output/` (already existed) is
unrelated -- just the running web app's own log file. New terms add a new
`inputs/<term>/` + `out/<term>/` pair; nothing under `src/` changes.

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

Four files under `config/`, each with a different lifetime. All four
stay here rather than moving into a term's own `inputs/<term>/` folder
(see "Project layout" above) -- `solver.SolverConfig.load(config_dir)`
and the live webapp both read all four from one hardcoded directory, so
splitting `preferences.toml` out despite it being per-term *content*
would break both. It just gets edited in place each term instead.

- `persons.toml` -- contractual facts: `max_load`, name-matching
  `aliases` (optionally scoped by `subject`, e.g. MATH Jordan vs. STAT
  Jordan), and the `courses` an instructor is qualified to teach.
- `preferences.toml` -- this term's wishes per instructor:
  `allow_overload` (bool -- `true` is fine with going over `max_load`,
  `false` avoids it at essentially any cost, but it's always soft, and
  never applies within 2 credit hours of `max_load` -- that's the
  definition of overload, not a leniency knob; see `OVERLOAD_TOLERANCE`/
  `OVERLOAD_FAR_THRESHOLD` in `schedule_model.py` for how far over
  actually costs), `allow_back_to_back`, `max_back_to_back` (an optional
  cap on same-day consecutive meetings -- only meaningful when
  `allow_back_to_back` is `true`; each meeting past the cap is its own
  soft finding, same tier as a plain back-to-back), `prefers_online` (a
  blanket, not course-scoped, soft affinity for online/hyflex sections),
  `preferred_times`/`disliked_times`, `preferred_locations`/
  `disliked_locations`, `preferred_courses`/`disliked_courses`, and
  free-form `rules` (course/section/room/time-scoped `prefer`/`dislike`
  rules, see the file's own header comment). `preferred_*` fields are
  informational only -- never scored.
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

## Rolling over to a new term

Turn last term's schedule file into next term's starting draft from just
two small lists -- who left, and what's newly offered/cancelled -- via
`class_schedule.term_builder`:

```powershell
uv run python -m class_schedule.term_builder "inputs/27S/Course Schedule Report.csv" inputs/27S/changes.toml -o out/27S/27S_draft.xlsx
```

Copy `inputs/TEMPLATE/changes.toml` into `inputs/<term>/changes.toml` per
term and fill in `departures`, `new_hires`, `cancel_courses`, and
`new_courses` (see that file's own header for the format).
`build_draft_schedule` then does the rest: cancelled courses are
dropped, every section a departed instructor was teaching is reassigned
to a placeholder ("Staff") rather than deleted -- so the course stays on
the draft as *open*, not gone -- and new offerings are appended, grouped
into four-credit/hybrid/coreq/cross-listed pairs automatically, exactly
the way an uploaded CSV is grouped. The draft is a normal schedule file
from there: upload it to the web app (or feed it to `solver.solve()`
directly) to see conflicts and run the solver against the current
roster.

After solving, any section still assigned to "Staff" is nobody on staff
being qualified/available for it -- a concrete hiring signal, not just a
vague sense the department is stretched thin. `term_builder` never edits
`config/persons.toml`/`preferences.toml` itself; `summarize_roster_impact`
only checks whether each departure name matches a real persons.toml
entry (a mismatch is almost always a typo) -- removing that person's
block from both files is still a manual step.

## Which courses need another section

`class_schedule.section_demand` cross-references a schedule export
against a Cube1-style enrollment headcount export (join key: CRN) and
flags courses full enough to justify one more section:

```powershell
uv run python -m class_schedule.section_demand "inputs/27S/Course Schedule Report.csv" inputs/27S/Cube1.xlsx
```

See [`docs/section_demand.md`](docs/section_demand.md) for the exact
input formats (both are specific, non-obvious shapes -- worth reading
before pointing this at a new export) and the recommendation rule.

## Building conflict-free starting CSVs

`class_schedule.starting_template` runs `term_builder.build_draft_schedule`
and adds two more passes on top, writing **two** files:
`starting.csv` (the full draft, new courses included) and
`starting_noadding.csv` (instructor changes only, nothing newly offered
-- useful to see the roster impact on its own):

1. **`place_new_hires`** seats each `changes.new_hires` name (see
   `term_builder.TermChanges`) into the draft, up to their own
   `persons.toml` `max_load`: first by taking over a placeholder
   ("Staff") class they're qualified for, and only once none of those is
   available by taking a class from an instructor currently over their
   own max_load. Neither available for a given slot just stops there --
   it never forces a bad fit.
2. **`recolor_placeholder`** splits every class still on the placeholder
   after that across as few distinct identities (`"Staff"`, `"Staff 2"`,
   ...) as it takes to guarantee none of them overlap in time -- two
   unrelated open positions landing at the same time otherwise reads as
   a same-instructor double-booking that isn't real. However many
   identities that still takes is a lower bound on *further* hires
   beyond the ones already placed, available before running the solver
   at all.

```powershell
uv run python -m class_schedule.starting_template `
  "inputs/27S/Course Schedule Report.csv" inputs/27S/changes.toml `
  -d out/27S --seed 42
```

See the module's own docstring in
[`src/class_schedule/starting_template.py`](src/class_schedule/starting_template.py)
for the full method.

## Tests

```powershell
uv run python -m unittest discover -s tests
```

`.dep/` holds the previous implementation (a LangGraph/Ollama scheduling
agent, a different `Class`/`Schedule` model, a CLI) -- kept for reference,
not part of the installed package or the test suite above.
