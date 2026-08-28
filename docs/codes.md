# Delivery Mode: One Rule for "Online"

This is a design note, not a user guide -- it records why the online/TBA/in-person
logic looked the way it did, what was wrong with that, and the single rule now in
force. Read it before touching anything that checks a section's time slot for
"is this online/TBA/arranged".

## Before: one boolean, one unused enum, three re-derivations

`Section` carried two properties over the same three raw `Time Slot` values
(`""`, `"TBA"`, `"ONLINE"`):

- `is_online` (`bool`): `time_slot.upper() in {"", "ONLINE", "TBA"}`. This was the
  one actually depended on -- about twenty call sites across `class_model.py`,
  `schedule_model.py`, `template_workspace.py`, `solver/candidates.py`, and
  `initial_builder.py` used it to decide whether a section needs a room/time
  candidate, participates in conflict checks, counts toward a room grid, etc.
- `delivery_mode` (`DeliveryMode`: `IN_PERSON` / `ONLINE` / `ARRANGED`): a finer
  three-way split added early in the project's history but consumed in exactly
  one place, `data_cleaning._mode_and_status`, which further split `ARRANGED`
  into human-facing `"tba"` / `"unscheduled"` labels for the cleaned-table
  report (`Delivery Mode` + `Scheduling Status` columns). That pair never left
  `data_cleaning.py` -- `Section.to_record()` didn't export either field, so
  nothing downstream (solver output, the web API, `app.js`) ever saw them.

The web frontend, having no field to read, re-derived "is this online" from the
raw `"Time Slot"` string itself, independently, in three places in `app.js`:
`resources()` (only matched the literal string `"ONLINE"`, silently letting
`"TBA"`/blank rows through), `isOnTimeGrid()` (checked whether a start time was
parseable and fell inside the visible grid range), and `renderOnlineSections()`
(checked for `"TBA"` specifically, to style its chip differently). Three
independent strings comparisons, not quite agreeing with each other.

`data_cleaning.py` also computed the same "is `Time Slot` blank" fallback twice:
once inside `Section.from_record()` (falling back to `Days`/`Start` when
`Time Slot` was empty) and once again, redundantly, in `clean_dataframe()`
just to feed `_mode_and_status`.

## Diagnosis

Two separate questions were being asked, and the code answered them with
overlapping, only-partially-consistent logic instead of one rule per question:

1. **Scheduling**: "does this section need a real time/room, and does it
   participate in conflict checks?" -- domain-correct answer, confirmed against
   `docs/data-cleaning.md` ("`ONLINE`, `TBA`, and blank times are
   non-physical") and against the absence of any code path that ever tries to
   solver-assign a TBA row a real slot: **online, TBA, and blank are the same
   answer.** This is exactly what `is_online` already computed -- it just also
   duplicated `delivery_mode`'s parsing instead of being derived from it.
2. **Reporting**: "what should a human reading the schedule be told this row
   is?" -- here online/TBA/blank are *not* the same answer (`data_cleaning`'s
   own three-way split proved that), but the finer answer never reached the
   layers that actually display schedules to people (the web app).

Considered and rejected: an `OnlineSection` class. `HybridClass` already
encodes "one physical row + one derived online companion row" as its own
two-row structure (`class_model.py`'s `_online_companion`), which is the
course-*combination* dimension. Delivery mode is a orthogonal dimension of an
individual row. Crossing them would mean `OnlineSection` vs. `HybridClass` vs.
`CoreqClass` vs. `CrossListingClass` all needing to compose, which is worse
than the fragmentation being fixed.

## Final design: `delivery_mode` is the only place `time_slot` gets parsed

> `Section.delivery_mode` is computed once, from `time_slot`. Every other
> "does this need a physical slot" check derives from it (or, for a label a
> human should see, reads the raw `time_slot`/`"Time Slot"` text directly).
> Nothing else pattern-matches `{"", "ONLINE", "TBA"}` on its own.

### Scheduling layer -- unchanged behavior, now explicitly derived

```python
# class_model.py
@property
def delivery_mode(self) -> DeliveryMode:
    if self.time_slot.upper() == "ONLINE":
        return DeliveryMode.ONLINE
    if self.time_slot.upper() in {"", "TBA"}:
        return DeliveryMode.ARRANGED
    return DeliveryMode.IN_PERSON

@property
def is_online(self) -> bool:
    return self.delivery_mode is not DeliveryMode.IN_PERSON
```

The ~20 existing `is_online` call sites (`solver/candidates.py`,
`schedule_model.py`'s conflict/grouping/export code, `template_workspace.py`,
`class_model.py`'s hybrid/coreq/four-credit validity checks,
`initial_builder.py`) needed no changes: they already asked the right
question, they just now get the answer from one property instead of a second
parallel implementation of the same three-value check.

### Reporting layer -- the field now actually leaves `Section`

```python
# Section.to_record()
"Delivery Mode": self.delivery_mode.value,
```

Because every class kind's `to_records()` bottoms out in `Section.to_record()`
(directly, or via `HybridClass`'s regenerated companion row), this one line is
enough for `Delivery Mode` to flow through CSV export, the cleaned-template
report, and the web API's `_serialize_schedule` without any of those layers
doing extra work.

`data_cleaning.py`'s separate `"tba"` / `"unscheduled"` split (`_mode_and_status`,
the `Scheduling Status` column) was removed rather than piped through: that
distinction is already spelled out verbatim in the `Time Slot` column
(`"TBA"` vs. blank), which is already part of `NORMALIZED_COLUMNS`, so keeping
a second field in sync with it bought nothing. Anywhere a display needs to say
"TBA" specifically instead of just "not in-person", it reads `Time Slot`
directly, not a maintained-in-parallel status field.

### Frontend -- reads the field, no longer reconstructs it

```js
// app.js
function isPhysical(row){return row["Delivery Mode"]==="in_person";}
```

`resources()` and `isOnTimeGrid()` now call `isPhysical()` instead of
independently string-matching `"Time Slot"`; the two functions' answers can no
longer disagree. `renderOnlineSections()`'s `"TBA"` chip styling still reads
raw `Time Slot` text on purpose -- that is the human-label case above, not a
scheduling check.

The one place this rule needs a mirror rather than a read: the browser holds
mutable schedule state between reloads, and two handlers write `"Time Slot"`
locally without a round trip to the backend (`moveSection()`'s drag-and-drop,
and `renderCourseList()`'s time dropdown, which can assign an existing
`"ONLINE"` value borrowed from some other row, e.g. a Hybrid class's
companion). Both now also set `Delivery Mode` through one shared helper so it
never goes stale mid-session:

```js
function deliveryModeOf(slot){
  const s=String(slot||"").toUpperCase();
  if(s==="ONLINE")return "online";
  if(s===""||s==="TBA")return "arranged";
  return "in_person";
}
```

### What changed, file by file

| File | Change |
|---|---|
| `src/class_schedule/class_model.py` | `delivery_mode` is now the canonical computation; `is_online` derives from it. `Section.to_record()` exports `"Delivery Mode"`. |
| `src/class_schedule/data_cleaning.py` | Removed `_mode_and_status` and the `Scheduling Status` column; `Delivery Mode` comes from `section.to_record()` instead of being computed a second time. |
| `src/class_schedule/web/app.js` | `resources()`/`isOnTimeGrid()` read `row["Delivery Mode"]` via `isPhysical()`; `moveSection()` and the course-list time dropdown keep it in sync via `deliveryModeOf()` when they write `"Time Slot"` locally. |

No changes were needed in `solver/candidates.py`, `schedule_model.py`,
`template_workspace.py`, or `initial_builder.py` -- their `is_online` calls
already asked the scheduling question this design keeps answering the same
way. Full test suite (`tests/`, 275 tests) passes unchanged.

---

# Never-Block Scheduling: One Validation Rule for All Four Atomic-Class Kinds

*Added 2026-08-27, same day as the section below it (which was written
first, earlier the same day). Read this one second -- it assumes the
Delivery Mode design above and touches the same files again.*

This section documents a bigger, second change made the same day: how
`FourCreditClass`, `HybridClass`, `CoreqClass`, and `CrossListingClass`
decide what's legal, and why nothing about scheduling correctness -- not a
bad row-level edit, not a genuinely broken schedule -- blocks building a
view, running the solver, or publishing a version any more. Read it before
adding a fifth atomic-class kind, before changing what `validate()` does on
any of the four, or before touching `webapp.py`'s save endpoint or
`schedule_run.py`'s attempt loop.

## Before: construction was the enforcement point, and it disagreed with itself

Every one of the four two-row kinds mixed two different questions into one
`validate()` method that `raise`d `ValueError` on failure:

1. **Recognition** -- is this pairing even the kind of thing its type claims
   ("same course", "a whitelisted coreq pair", "an M/F-prefixed physical
   meeting", "two different courses that are cross-listed")?
2. **Scheduling compliance** -- given that it is, is it *well scheduled*
   (same instructor, close enough together, in the same room when it needs
   to be)?

Mixing them meant a single bad field -- one edit, one stale `courses.toml`
relationship, one malformed source row -- didn't just flag a problem, it
made the whole object impossible to construct. That, in turn, made it
impossible to construct the `Schedule` containing it, which made it
impossible to load, view, analyze, solve, or export *any* of the
schedule -- not just the one broken pairing. `FourCreditClass` had already
split its own two concerns apart (`schedule_issues`, added earlier): a bad
day/instructor pairing (`is_four_credit`) still raised, but an excessive
start-time gap didn't -- it constructed and reported itself instead. That
split turned out to be the right shape; the work this section describes is
generalizing it to all four kinds, uniformly, and removing the two
remaining places (`webapp.py`'s `/api/save`, `schedule_run.py`'s solve
loop) that still turned a validation problem into an outright refusal to
produce anything.

The guiding requirement, stated by the project owner over the course of
this discussion: **a schedule can always be viewed, edited, exported, and
solved, no matter how invalid it is -- the only thing that's allowed to
fail outright is building the view at all** (a row so malformed there's no
coherent `Section`/`Class` to construct -- a missing Subject/Number/Section,
an unparseable time string, a relationship declared with the wrong number
of members). Everything past that point becomes a report, never a refusal.

## Final design

> Each of the four two-row kinds defines its own `is_valid_schedule(left,
> right)` -- one canonical, full-strength boolean covering everything that
> kind cares about, recognition and scheduling compliance alike.
> Construction (`__post_init__`) never rejects a value on the strength of
> this function; it only records what's wrong (`schedule_issues`) so a
> caller can detect and describe an illegal state after a row-level
> adjustment. `pairwise_predicate()` hands this same function to the
> solver, unconditionally, so solved output is always fully compliant --
> and so a pairing too broken for the solver to ever fix (see
> `HybridClass` below) correctly reports the solve attempt as infeasible,
> rather than silently shipping something broken.

### Per-kind rule table

| Kind | Recognition (grouping only, unaffected by this change) | `is_valid_schedule(left, right)` -- everything ``schedule_issues``/the solver care about | `schedule_issue_rule` |
|---|---|---|---|
| `FourCreditClass` | Two rows sharing one identity, in `_take_same_course` | Same course identity, same instructor, MWF+T or MWF+R day pairing, start-time gap ≤ 90 minutes | `four_credit_invalid` |
| `CoreqClass` | Course-number whitelist match (`is_coreq_pair`, `_take_coreqs`) or an explicit `courses.toml` relationship | Two *different* course identities, same instructor, and either both online or a physical adjacency (back-to-back same room on a shared weekday, or starting within 30 minutes on disjoint weekdays) | `coreq_invalid` |
| `HybridClass` | An M/F-prefixed physical row (auto-synthesizes its companion) or an explicit relationship | Same course identity, same instructor, one M/F-prefixed physical meeting with a room, one companion without one | `hybrid_invalid` |
| `CrossListingClass` | A shared `Cross-List` marker, a whitelisted course pair, an honors/regular section pair (`is_cross_listing`), or an explicit relationship | Two *different* course identities and `is_cross_listing` -- **not** instructor/room/time; see `synced_fields` below | `cross_listing_invalid` |

`is_coreq_pair` (the whitelist) and the M/F-prefix/honors-suffix patterns
are used **only** at grouping time, to decide which rows become which
kind. None of them are re-checked afterward -- a `CoreqClass` that no
longer matches the whitelist, or a `HybridClass` whose physical row lost
its room, still exists, still reports through `schedule_issues`, and still
gets a `pairwise_predicate` requiring the solver to treat it as invalid
until it's fixed by hand. There is no per-instance memory of "was this
whitelisted/configured at construction" -- recognition happens once, at
grouping, and is never revisited.

### `CrossListingClass` is the one kind with a second, per-instance rule

Cross-listing rows are deliberately never required to match on
instructor/room/time -- unlike the other three kinds, divergence there
isn't a violation at all (see the earlier design discussion this
generalizes: a genuine cross-listing commonly uses two different rooms).
What *is* enforced is `synced_fields`: a `frozenset[str]` computed once at
construction (`_synced_fields`), recording which of `{"instructor",
"room", "time"}` the pair's two rows already agreed on. A field that
matched at construction stays locked for the life of the instance; a field
that didn't is free to diverge further, forever, with **no** conflict
between the two rows on that field (room/instructor-conflict checking
already exempts a class's own rows from each other -- see
`check_conflicts`'s `item_a is item_b` guard, which predates this change
and needed no updating). `pairwise_predicate()` combines
`is_cross_listing`-and-different-identities with whichever fields are
locked:

```python
def pairwise_predicate(self):
    locked = self.synced_fields
    def _predicate(left, right):
        if not self.is_valid_schedule(left, right):
            return False
        if "instructor" in locked and left.instructor != right.instructor:
            return False
        if "room" in locked and (left.room != right.room or left.building != right.building):
            return False
        if "time" in locked and (left.time_slot != right.time_slot or left.duration != right.duration):
            return False
        return True
    return _predicate
```

### `HybridClass`: the solver is never given a special exemption

An earlier iteration of this design special-cased `HybridClass.pairwise_predicate()`
to return `None` (no constraint at all) once a pairing was already
broken, reasoning that a section's online/physical shape isn't something
candidate selection can adjust, so asking the solver to enforce it would
just make solving infeasible instead of imperfect. **That exemption was
deliberately removed.** The final rule treats all four kinds identically:
`pairwise_predicate()` always returns the real `is_valid_schedule`, no
exceptions. The practical consequence -- solving a schedule containing a
genuinely broken hybrid pairing reports the attempt infeasible, since no
candidate combination can satisfy `is_valid_schedule` for it -- is not a
bug; it's the same "too broken to proceed" outcome already accepted for
malformed input rows, just realized at solve time through the ordinary
retry-then-give-up loop (see below) instead of a bespoke per-kind carve-out.
Viewing, editing, and exporting such a schedule still works fine, since
none of those paths invoke the solver.

### The publish/save layer: report, never refuse

Two remaining hard stops were removed to match:

- `webapp.py`'s `POST /api/save` no longer raises `HTTPException(422, ...)`
  when `evaluate_schedule()` finds hard violations. It always publishes,
  and returns `hard_violations` in the response (and in the version's
  `report.md`/`manifest.json`, whose `validation.hard_violations` count and
  per-attempt `HardViolations` field were previously hardcoded to `0` --
  dead code that only looked correct because the 422 branch made the
  nonzero case unreachable).
- `schedule_run.py`'s CLI `solve`/`final` attempt loop no longer requires
  a violation-free attempt to consider the run successful. `Attempt.ranking`
  now sorts by hard-violation count first, then the existing
  `(worst_overload, objective, soft_penalty)` tuple, so among several
  attempts the least-broken one still wins -- but *any* attempt that
  produced a `Schedule` at all is publishable. `InfeasibleSchedule` raised
  by an individual attempt (the solver's own model has no feasible
  assignment) is now caught and recorded like a timeout, not re-raised
  immediately; only when **every** attempt produced no schedule at all --
  nothing to report, nothing to view -- does the command fail.
- `POST /api/export/{view}` and `POST /api/analyze` never had this problem;
  they don't call `evaluate_schedule` at all before returning a file or a
  violation list, respectively. No change was needed there.

## `predicate_for`: sourced from the instance, not a second mapping

Solved earlier the same day, and still true: `solver/constraints.py` no
longer keeps its own `isinstance` chain mapping each kind to a validity
function. `Class.pairwise_predicate(self)` is an **instance** method (not a
classmethod -- `CrossListingClass` needs its own `synced_fields`, not just
its type, to answer), and `predicate_for(item)` is just `item.pairwise_predicate()`.
`add_pairwise_validity_constraints` also dropped a blanket
`left.instructor == right.instructor` pre-check that used to run ahead of
every kind's own predicate regardless of relevance; each kind's
`is_valid_schedule` now includes its own instructor requirement where it
has one (`CrossListingClass` doesn't, by design), so nothing was silently
lost by removing the blanket check -- confirmed by adding it explicitly to
`HybridClass.is_hybrid`, which had relied on the blanket check without
ever stating it.

## What changed, file by file (2026-08-27)

| File | Change |
|---|---|
| `src/class_schedule/class_model.py` | All four kinds: `validate()` overrides removed (only the inherited row-count check remains); each kind gained a canonical `is_valid_schedule`/`_issues` pair driving both `schedule_issues` and `pairwise_predicate`; `pairwise_predicate` became an instance method; `HybridClass.physical_section`/`online_section` hardened against `StopIteration`; `CrossListingClass` gained `synced_fields` (per-instance field-locking) and dropped its old hard `is_shared_meeting`/`is_cross_listing` requirements; `HybridClass.is_hybrid` gained an explicit instructor check. |
| `src/class_schedule/solver/constraints.py` | `predicate_for` calls `item.pairwise_predicate()`; the blanket instructor pre-check in `add_pairwise_validity_constraints` was removed. |
| `src/class_schedule/schedule_model.py` | `check_atomic_class_rules` generalized from a `FourCreditClass`-only `isinstance` check to reading any item's `schedule_issues`/`schedule_issue_rule` generically. |
| `src/class_schedule/webapp.py` | `/api/save` no longer 422s on hard violations; fixed two dead-code `HardViolations: 0` literals; response now includes `hard_violations`. |
| `src/class_schedule/schedule_run.py` | `Attempt.ranking` sorts by hard-violation count first; the attempt loop publishes the best available result instead of requiring zero violations; `InfeasibleSchedule` from one attempt no longer aborts the whole run. |
| `tests/test_class_model.py`, `tests/test_schedule_model.py`, `tests/test_architecture.py` | Updated/added coverage for the new per-kind `schedule_issues`, `CrossListingClass.synced_fields`/partial locking, and the removed forced-convergence behavior. |
| `docs/manual-adjustments.md`, `docs/scheduling-rules.md`, `docs/index.md` | Corrected user-facing claims that hard conflicts block saving -- they no longer do, anywhere. |

Full test suite (`tests/`, 279 tests) passes.

## Addendum, same day: `synced_fields` moved from computed-every-load to a persisted config setting

While designing the future live-edit API against the design above, a real
gap surfaced: `CrossListingClass.synced_fields` is computed fresh in
`__post_init__` every time a `Schedule` is rebuilt from records -- which is
*every* round trip (load, edit, save), since `Schedule`/`Class` are
stateless. So "whichever fields the source template started out sharing"
doesn't actually mean "decided once, permanently" -- it means "whatever the
most recent reconstruction observed", which quietly reinterprets a
temporary coincidence (two rows a user briefly nudged into matching) as a
newly locked field going forward. The fix: let a `cross_listing`
`courses.toml` relationship declare `synced_fields` explicitly, as a
persisted, human-editable decision, instead of only ever re-deriving it.

- `config_schema.py`: `CourseRelationshipSchema` gained an optional
  `synced_fields: list[Literal["instructor","room","time"]] | None`,
  rejected (`model_validator`) for any `kind` other than `cross_listing`.
- `class_model.py`: `CrossListingClass.from_configured_sections` takes an
  optional `synced_fields: frozenset[str] | None` keyword; given, it wins
  outright; omitted, it falls back to the existing auto-detection
  (`_synced_fields`) unchanged -- so relationships that don't declare it
  behave exactly as before.
- `schedule_model.py`: `_take_configured_relationships`'s `cross_listing`
  branch reads `relationship.synced_fields` off the config and passes it
  through.
- `config_inference.py`: `_inferred_relationships` now also captures each
  constructed `CrossListingClass.synced_fields` (already computed by the
  time inference builds the object, from the actual template data -- no
  new detection logic needed) and `_courses_toml` writes it as the
  relationship's `synced_fields` array. So running 从模板推断 (template
  inference) is what turns the one-shot "same at first" heuristic into a
  durable decision -- inference is the only place that heuristic still
  runs; every later load reads the config instead of re-guessing.

Recognition paths with no `courses.toml` relationship at all (Cross-List
marker, known course pair, honors-section pairing) are unaffected --
they still use the always-available auto-detection, since there is no
config entry to persist the decision into.

New coverage: `tests/test_pipeline.py` (`synced_fields` accepted only for
`cross_listing`; a configured relationship's declared `synced_fields`
overrides what the rows would auto-detect), `tests/test_config_inference.py`
(inference writes `synced_fields` matching what the template actually
showed). Full test suite (`tests/`, 281 tests) passes.

## Addendum, same day: the web UI's edit-linking now reads `synced_fields` instead of guessing from current values

An audit of "is manual scheduling in the web UI actually complete" (prompted
by the design above) found a bug this design directly caused: three
edit handlers in `app.js` decided whether changing one row of a two-row
class should also change its other row by checking whether the two rows'
**current** field values happened to already match -- not whether they were
*supposed* to stay matching. That distinction didn't matter before
`CrossListingClass` could have unlocked fields; now it does. A locked field
that had drifted apart wouldn't get re-synced by an edit; an unlocked field
that happened to coincide would get silently forced into sync by one.

**Fix**: a new `linkedField(item, field)` helper (`field` is `"instructor"`
or `"time"`) is now the single source of truth for "does editing this field
on one row propagate to the other row of `item`":

```js
function linkedField(item,field){
  if(item.kind==="CrossListingClass")return (item.synced_fields||[]).includes(field);
  if(field==="time")return false;          // MWF/TR, physical/online, coreq offsets are never the same value
  return item.kind!=="CoreqClass";         // Hybrid/FourCredit require a shared instructor; Coreq never shares one
}
```

`assignRoom`'s existing "match by current Time Slot" heuristic was *kept*
for every kind except `CrossListingClass` -- for Hybrid/FourCredit/Coreq it
already correctly means "the same physical meeting" (their two rows
reliably have different Time Slot values whenever they don't share a room,
by construction), so matching on it isn't a coincidence there the way it
was for cross-listing. Only `CrossListingClass`'s room-propagation now
reads its own `synced_fields` entry instead.

`webapp.py`'s `_serialize_schedule` gained a `"synced_fields"` field per
class (`null` for kinds that don't have one) so the frontend has something
to read. `moveSection`, `assignTeacher`, `$("#assignRoom")`'s click handler,
and the course-list `.slot-select` change handler all switched from their
old per-kind/per-field heuristics to `linkedField`. The context menu's hint
text (`#contextHint`) is now computed per open (`contextHintText`) instead
of being static, since whether an edit "applies to the whole atomic class"
or "only this section" now genuinely varies per `CrossListingClass`
instance, not just per kind.

Two other candidate gaps from the same audit were raised and explicitly
declined by the project owner, not oversights: a lock mechanism for
"Auto Schedule" (`overrides.toml`-style locks exist for the CLI's
solve-then-hand-edit-then-resolve workflow; dragging in the web UI *is*
the hand-edit, there is no second solve step to protect it from), and the
ability to give an unscheduled (TBA/blank) row a brand-new time slot from
the grid UI (the course-list view already shows it; that's enough).

## Addendum, same day: linking rules moved from `app.js` into the atomic-class model, behind `POST /api/edit`

The `linkedField()` fix above turned out to be a stopgap, not the real
design -- it was a second, JS-side reimplementation of a rule the Python
model already half-had (and, for Coreq's instructor field, had backwards:
`linkedField` returned `false`/"don't link" for the one field
`CoreqClass.is_valid_schedule` requires to *always* match). Two engines
computing the same linkage independently will drift; this section replaces
`linkedField()` with a single rule, in Python, that every edit path calls
through one endpoint instead of guessing locally.

### The linking matrix (now the literal contract, not prose)

| Kind | Instructor | Time | Room |
|---|---|---|---|
| Normal | this row | this row | this row |
| FourCredit | both rows | this meeting | this meeting |
| Hybrid | both rows | physical row only | physical row only |
| Coreq | both rows | this meeting (never shared) | both rows *iff currently back-to-back on a shared weekday*, else this meeting |
| CrossListing | per `synced_fields` | per `synced_fields` | per `synced_fields` |

### `Class.edit_targets` / `Class.apply_edit`

```python
# NormalClass (base)
def edit_targets(self, field: str, record_index: int) -> tuple[int, ...]:
    return (record_index,)                       # default: just this row

def apply_edit(self, field: str, record_index: int, **changes) -> "NormalClass":
    targets = self.edit_targets(field, record_index)
    updated = tuple(
        replace(section, **changes) if index in targets else section
        for index, section in enumerate(self.sections)
    )
    return replace(self, sections=updated)
```

Each kind overrides only `edit_targets` (`FourCreditClass`/`HybridClass`:
instructor links, time/room don't; `HybridClass` additionally always
routes time/room to `physical_section` regardless of which row the edit
named; `CrossListingClass`: `field in self.synced_fields`) -- except
`CoreqClass`, which needs one more thing `edit_targets` alone can't
express:

```python
# CoreqClass
def edit_targets(self, field, record_index):
    if field == "instructor": return (0, 1)
    if field == "room" and self._back_to_back(*self.sections): return (0, 1)
    return (record_index,)

def apply_edit(self, field, record_index, **changes):
    updated = super().apply_edit(field, record_index, **changes)
    if field == "time":
        left, right = updated.sections
        if self._back_to_back(left, right) and not (matching room):
            # just became back-to-back -- follow the row that wasn't
            # moved, instead of reporting a fresh coreq_invalid gap
            ... copy the other row's room/building onto the moved one ...
    return updated
```

A time edit that makes a disjoint-day coreq pair become back-to-back on a
shared weekday now auto-follows the untouched row's room (a detail the
project owner specified explicitly) -- otherwise a perfectly reasonable
drag would instantly report `coreq_invalid` for a room mismatch nobody
asked to create. `CoreqClass._issues`/`is_valid_schedule` also now share
this same `_back_to_back` staticmethod (previously duplicated inline).

### `POST /api/edit`: the one endpoint every edit path calls

Request: `{package, records, class_index, record_index, field, value}` --
`field` is `"instructor"` (`value`: a name string), `"room"` (`value`:
`{building, room}`), or `"time"` (`value`: `{days, start}`, 24-hour
`"HH:MM"`). The handler:

1. Rebuilds the `Schedule` from `records` (`_schedule_from_payload`,
   already shared with `/api/analyze`/`/api/solve`).
2. Rejects a `"time"`/`"room"` edit on an online/arranged row outright
   (`section.is_online`) -- per the project owner, those rows only ever
   take an instructor edit; there's no meeting to move or room to assign.
3. For `"time"`, resolves the duration via a new `_resolve_meeting_duration`
   helper -- the same `pattern_rules.pattern_applies` +
   `config.meeting_patterns` lookup `/api/solve`'s candidate generation and
   `evaluate_schedule`'s meeting-pattern check already use, so "what's a
   legal duration for this day" has one source, not a second copy
   (previously `app.js`'s `patternDuration`/`draggedPattern`).
4. Calls `item.apply_edit(field, record_index, **changes)` -- the atomic
   class decides linkage; the endpoint never does.
5. Returns `{"classes": ..., "violations": ...}`, the same shape
   `/api/solve` already returns, so the frontend's response handling
   doesn't need a separate code path.

Errors (unknown `class_index`/`record_index`, an edit that can't even be
parsed) are `HTTPException(400, ...)`; a semantically bad edit (e.g. an
instructor that breaks nothing) is never an error at all -- it just shows
up in the returned `violations`, per the never-block design above.

### What's done, what's next

Done and tested (`tests/test_class_model.py`, `tests/test_edit_api.py` via
`fastapi.testclient.TestClient`): the full `edit_targets`/`apply_edit`
matrix on all five kinds, the Coreq instructor-linking fix, the Coreq
room-follow rule, and `/api/edit` end-to-end including the online/arranged
rejection and the 400 error cases.

The frontend rewiring described as "not yet done" below is now done -- see
the next addendum.

## Addendum, 2026-08-27: `app.js`'s four edit paths now call `POST /api/edit`

All four web edit actions -- dragging a block, the course-list time
picker, "Assign instructor", "Assign room" -- used to mutate `data`
locally using `linkedField()`'s guesses (see the two addenda above) before
this phase's backend redesign made that logic wrong in one case (Coreq
instructor) and redundant everywhere else (the atomic-class model already
has the real answer, behind `POST /api/edit`). This addendum wires the
frontend to actually use it.

### The version that shipped: always wait, no local mutation

Before implementing, we discussed shipping a local optimistic update for
instructor/room edits (their `edit_targets` never depends on the new
value, so the frontend could apply them immediately and let the network
round trip only correct it if wrong) while still waiting on time edits
(duration depends on backend-resolved meeting patterns). The user chose
the simpler path first: **every edit path calls `/api/edit` and waits for
the response before touching the view at all**, with the decision on
whether the added latency is worth avoiding deferred until after trying
it ("先修改，测试看结果再说，有可能这个延迟我没有问题" -- implement it,
test it, the delay might not actually be a problem).

The honest trade-off, discussed explicitly: the old local-mutation
`moveSection`/`assignTeacher`/`assignRoom` never depended on the network
for the edit itself (only the decoupled, already-soft-failing
`/api/analyze` debounce touched the network) -- it could not have a
"network problem" for an edit, only a correctness bug (which is exactly
what it had: the Coreq instructor case). The new design trades that
zero-network-dependency property for correctness-by-construction (the
linking rule can never drift from the backend's, because there's only one
copy of it). On a localhost deployment this is expected to be cheap, but
it is a genuine new dependency, not a free change.

### What changed in `app.js`

- **`submitEdit(classIndex, recordIndex, field, value)`** -- the one
  function all four paths call. Posts `{package, records, class_index,
  record_index, field, value}` to `/api/edit`, and on success replaces
  `data.classes`/`data.violations` with the response (which already
  reflects whatever linking `edit_targets` decided, and fresh
  `violations` -- no separate `/api/analyze` call needed). Throws on a
  non-2xx response so callers can toast the error and leave `data`
  untouched.
- **`moveSection(minute, day)`** -- now `async`. Still uses
  `draggedPattern()` to translate the drop location into a day pattern
  (pure UI gesture translation, unrelated to linking, so it stays), then
  sends `{days, start}` via `submitEdit` with `field: "time"`. No longer
  computes duration, `Delivery Mode`, or which rows to touch locally.
- **`assignTeacher(name)`** and the `#assignRoom` click handler -- now
  `async`, call `submitEdit` with `field: "instructor"` / `field: "room"`.
- The course-list `.slot-select` change handler -- now `async`, calls
  `submitEdit` with `field: "time"`. Its `<select>` is now `disabled` for
  any row that isn't `in_person` (online/arranged rows don't get a new
  time from this view at all, matching the decision recorded in the
  Delivery Mode section above -- "tba只用在section view里面显示出来，不需要安排新时间").
- **`minuteToClock24(minute)`** -- new helper, drag-grid minute offset to
  a 24-hour `"HH:MM"` string (what `/api/edit`'s `time.start` expects;
  matches `Section.to_record()`'s `Start`/`End` serialization, see the
  Delivery Mode section).
- **`parseSlotValue(text)`** -- new helper, parses a course-list option's
  `"MWF 9:00am"`-style text (produced by `/api/edit`'s own
  `record_utils.clock`/`parse_slot` round trip) back into `{days,
  start:"HH:MM"}`.
- **`markDirty(skipAnalysis)`** -- gained an optional parameter; the four
  edit handlers pass `true` since `/api/edit`'s response already carries
  fresh `violations`, making the debounced `/api/analyze` call redundant
  for them. `markDirty()`'s other caller (`#solveButton`, after
  `/api/solve`) is unaffected.
- **`editBusy`** -- new module-level flag (separate from the existing
  `busy`, which gates Auto Schedule/Save) so a second edit can't be fired
  while one is still in flight; it is not a lock in the "prevent Auto
  Schedule" sense discussed and declined earlier, just a guard against a
  literal double click/drop.
- **Removed as dead code**: `deliveryModeOf` (existed only so local
  mutation could keep `Delivery Mode` in sync with a locally-changed `Time
  Slot`; there is no local mutation left to keep in sync), and
  `patternRole`/`patternDuration` (existed only so `moveSection` could
  compute a new duration locally; `/api/edit` resolves it server-side via
  `_resolve_meeting_duration`, the same `pattern_rules`/
  `config.meeting_patterns` machinery `/api/solve` and `evaluate_schedule`
  already used).
- `linkedField()` and `contextHintText()` stayed as display-only helpers
  (neither decides an actual edit's targets any more -- `/api/edit` does),
  but see the next addendum: what they read changed a few minutes later.
- One corresponding test fix: `tests/test_configuration_web.py`'s static
  content sanity test asserted the literal substring
  `'startText=recordClock(minute)'` was present in `app.js` as a proxy for
  "`moveSection` exists and does the expected thing" -- updated to assert
  `moveSection` calls `submitEdit(classIndex,recordIndex,"time",...)`
  instead, since the local `startText` computation this checked for no
  longer exists.

### What's still open

The optimistic-update question above (skip the network wait for
instructor/room edits, since their targets don't depend on the new value)
is deferred pending manual testing of the always-wait version's felt
latency. No frontend automated test exercises the four rewired handlers
directly (the project has no JS test runner); `tests/test_edit_api.py`
covers the `/api/edit` contract they now depend on, and
`tests/test_configuration_web.py` sanity-checks that the expected call
sites still exist in the shipped `app.js`.

## Addendum, 2026-08-27: `linkedField()` reads the view payload instead of guessing

Immediately after the rewiring above shipped, a correction: this was
already the agreed design from an earlier same-day discussion --
"在构建视图的时候，把是否需要相同的信息从配置里面读出来，然后直接使用"
(when building the view, read whether fields need to match out of the
config, and use that directly) -- and the rewiring above left
`linkedField()` still computing its own answer from `item.kind`/
`item.synced_fields` in `app.js`, i.e. still a second, hand-maintained
copy of a rule the backend already has the real answer to. It happened to
be *correct* (the Coreq bug was fixed at the source, in
`CoreqClass.edit_targets`, not in this JS function), but it was still the
wrong shape: exactly the kind of duplication this whole redesign was
meant to eliminate.

Fixed by having `_serialize_schedule` (`webapp.py`) compute the answer
once, per class, and ship it:

```python
"linked_fields": {
    field: len(item.edit_targets(field, 0)) > 1
    for field in ("instructor", "room", "time")
},
```

`0` is an arbitrary row index, not a special one: for every current kind,
"does this field link the two rows" is a property of the class (or, for
Coreq's room field, of the pair's current back-to-back state) -- never of
*which* row you'd start the edit from -- so `edit_targets(field, 0)` and
`edit_targets(field, 1)` always agree. (This stops being true only if a
future kind's linking genuinely depends on which row was clicked, which
none of the current five do.)

`app.js`'s `linkedField()` shrank to a one-line read:

```js
function linkedField(item,field){return !!item.linked_fields?.[field];}
```

`contextHintText()` simplified to call it for both `"instructor"` and
`"room"` instead of special-casing `CrossListingClass`/`synced_fields`
itself. The `"synced_fields"` payload field stays as-is alongside the new
one -- it is the raw, persisted config knowledge (which fields a
CrossListingClass instance was configured/detected as sharing);
`linked_fields` is the generalized, always-present answer derived from it
(for CrossListingClass) or from each kind's fixed rule (for the other
four), and is what the UI should read from now on.

Tested by a new `tests/test_edit_api.py` case
(`test_view_payload_carries_linked_fields_from_edit_targets`), asserting a
disjoint-weekday Coreq pair's `linked_fields` comes back as
`{"instructor": True, "room": False, "time": False}`.

## Addendum, 2026-08-27: a real bug found in review -- `apply_edit` was silently discarding `CrossListingClass.synced_fields`

A review of the `/api/edit` work above caught a real, high-severity bug:
`NormalClass.apply_edit` (the base every kind's override calls into)
ends in `replace(self, sections=updated)`. For a regular dataclass,
`replace()` builds the new instance by calling `__init__` again, which for
`CrossListingClass` reruns `__post_init__` -- and `__post_init__`
*unconditionally* auto-detects `synced_fields` from whatever the rows look
like *after* the edit:

```python
def __post_init__(self) -> None:
    ...
    self.synced_fields = self._synced_fields(left, right)
```

So every `CrossListingClass` edit -- not just room edits, any edit --
silently replaced the instance's real `synced_fields` (whether it came
from auto-detection at load time or from an explicit `courses.toml`
`synced_fields = [...]`) with a fresh guess from the post-edit rows.
Concretely: a pair recorded as `["instructor", "time"]` (independent
rooms) where one row's room happened to get edited to equal the other's
would come back as `["instructor", "room", "time"]` -- a coincidence
permanently promoted to a locked rule, and a configured `synced_fields`
silently overwritten the first time either row was edited at all. This is
exactly the "re-guessed every time" failure mode `synced_fields` was
built to prevent (see the "persisted config setting" addendum above) --
un-done by the very code meant to use it.

Fixed with a `CrossListingClass.apply_edit` override that calls the base
behavior for the actual field mutation, then restores the original
instance's `synced_fields` (a fixed, per-instance decision that only a
fresh load -- `from_configured_sections` -- is allowed to set):

```python
def apply_edit(
    self, field: str, record_index: int, **changes: object,
) -> "CrossListingClass":
    updated = super(CrossListingClass, self).apply_edit(
        field, record_index, **changes,
    )
    updated.synced_fields = self.synced_fields
    return updated
```

(Note the explicit `super(CrossListingClass, self)` form, not bare
`super()` -- this codebase's `@dataclass(slots=True)` classes rebuild the
class object, so the zero-arg form's implicit `__class__` cell resolves
to a stale class and raises `TypeError: super(type, obj): obj is not an
instance or subtype of type`. Every other override in this hierarchy
already uses the explicit form for the same reason; this one had to
follow suit.)

Regression test:
`tests/test_class_model.py::CrossListingClassTests::test_apply_edit_keeps_the_original_synced_fields_even_when_rows_coincidentally_match`
-- edits one row's room to coincidentally match the other's and asserts
`synced_fields` is unchanged.

### Also from that review: two smaller, confirmed issues fixed alongside it

- **The context menu still offered "Assign room" on online/arranged
  rows.** `/api/edit` has always rejected a `room` (or `time`) edit on a
  row where `section.is_online` (see the `edit_schedule_class` handler
  above) -- but `openContextMenu()` populated and enabled `#contextRoom`/
  `#assignRoom` unconditionally, so clicking them on an online chip could
  only ever end in a 400 toast. Fixed: both are now `disabled` when the
  clicked row isn't `in_person`, and `contextHintText()` (now taking the
  clicked `row` as well as `item`) says so instead of describing a
  linking rule that was never going to get the chance to apply.
- **`tests/test_edit_api.py` depended on an undeclared package.**
  `fastapi.testclient.TestClient` requires `httpx`, which was importable
  only because this development environment happened to have it
  installed already -- it was in neither `pyproject.toml` nor `uv.lock`,
  so `uv run python -m unittest discover -s tests` on a clean checkout
  would fail to even collect that file. Fixed with `uv add --dev
  "httpx>=0.27"`, which added a `[dependency-groups] dev` entry to
  `pyproject.toml` and resolved it into `uv.lock`. Verified by running the
  full suite through `uv run` specifically (not the ad hoc venv used
  earlier in this session), which is the reproducible path the project's
  own docs (`docs/index.md`'s "Tests" section) tell a user to take.

### Raised, not yet acted on: `class_index`/`record_index` as the sole identity `/api/edit` trusts

The same review flagged that `/api/edit` locates the target class/row
purely by re-grouping the posted flat `records` into a `Schedule` and
indexing into it -- there is currently no defect (grouping order is a
deterministic function of each row's own identity fields, none of which
`/api/edit` can edit), but nothing would catch it if a future change to
grouping ever made the order data-dependent in a new way, silently
mis-targeting a different class. A cheap hardening would be having the
frontend also send the target class's `course_ids` and the target row's
own `Subject`/`Number`/`Section`, and having the handler verify those
against what it actually indexed to before applying anything. Not
implemented yet -- raised for a decision, not acted on unprompted, since
today it would be defensive code against a hypothetical, not a fix for an
observed failure.

## Addendum, 2026-08-27: `synced_fields` is opt-in, not opt-out -- omitting it now means "fully locked," not "auto-detect"

Follow-up to the review above: the fact that `27S`/`27F`'s two real
`cross_listing` relationships (MATH 5173 TC1/STAT 4173 TC1, MATH 4123
001/H01) don't declare `synced_fields` at all meant every schedule load
was still re-*auto-detecting* it from whatever the current rows showed --
harmless today only because all three fields happen to already match in
both packages' actual data, but still the same "re-guessed every time"
exposure `synced_fields` was built to close, just one level up (at
`courses.toml`, not at `apply_edit`). The first fix proposed was to just
write `synced_fields = ["instructor", "room", "time"]` into both files'
four relationships. Instead, the default itself changed, closing the gap
for every current and future declared relationship at once rather than
one config edit at a time:

**Before:** a declared `cross_listing` relationship without
`synced_fields` fell back to the same auto-detection an *undeclared*
(legacy-recognized) pair uses -- look at the current rows, lock whatever
already matches.

**Now:** `synced_fields` is opt-in to *divergence*, not opt-in to being
locked. A declared relationship without `synced_fields` defaults to
`CrossListingClass.ALL_SYNCED_FIELDS` (all three fields, fully locked) --
declaring a cross-listing relationship at all is now itself the signal
that this is meant to be one single, fully-shared offering; naming
`synced_fields` explicitly is how you opt specific fields *out* of that
lock (list only the ones that must still match; leave out the ones
allowed to diverge). This only changes `CrossListingClass.from_configured_sections`'s
default (used for a *declared* relationship) -- `__post_init__`'s
auto-detection is unchanged and still the only option for a pair
recognized without any relationship to consult at all (shared
`Cross-List` marker, known course pair, honors pairing).

```python
ALL_SYNCED_FIELDS: ClassVar[frozenset[str]] = frozenset(
    {"instructor", "room", "time"},
)
...
item.synced_fields = (
    synced_fields if synced_fields is not None
    else cls.ALL_SYNCED_FIELDS  # was: cls._synced_fields(left, right)
)
```

One practical consequence: writing `synced_fields` into `27S`/`27F`'s four
relationships, as first proposed, is no longer *necessary* -- omitting it
now gets the same fully-locked result the write would have produced,
automatically, and for any future declared cross-listing too, not just
these four. It may still be worth writing explicitly as documentation (a
reader of `courses.toml` sees the lock without having to know the
default), but it's no longer required to close the original gap.

Tested by two new `tests/test_pipeline.py` cases, one for each direction:
`test_configured_cross_listing_without_synced_fields_defaults_to_fully_locked`
declares a relationship with rooms/times/instructors that plainly differ
in the source rows and asserts `synced_fields` still comes back as all
three fields, proving the pair is no longer being re-derived from the
data at all; `test_configured_cross_listing_can_leave_a_currently_matching_field_free`
is the inverse -- room and time both *currently match* in the source
rows, but only `instructor` is declared, and `pairwise_predicate` still
has to let room/time move independently (while continuing to enforce
instructor) -- proving "the two rows happen to agree right now" is never
mistaken for "this field is locked."

## Addendum, 2026-08-27: template inference follows the same opt-in rule; end-to-end solver/workload proof

Three follow-ups from the `synced_fields` opt-in change above, closing out
the same discussion.

**`config_inference.py` now omits `synced_fields` when the template
already fully matches.** Inference (`_inferred_relationships`) still
detects, from the template, which of instructor/room/time the pair
already shares -- that part is unchanged, and still the only option for
this legacy-recognition-based path (there's no declared relationship yet
to default from). What changed is `_courses_toml`'s *writing* step: it
used to always write `synced_fields = [...]` explicitly, even when the
detected set was all three fields. Since omitting `synced_fields` now
defaults to fully locked, writing all three explicitly is redundant --
`_courses_toml` now skips the line entirely when the detected set equals
`CrossListingClass.ALL_SYNCED_FIELDS`, and still writes the narrower,
explicit list when the template shows a field genuinely diverging (that
case still needs the write, or the default would silently re-lock it).
`tests/test_config_inference.py`'s existing fully-matching-template case
was updated to assert the key is *absent*; a new
`test_infers_a_narrower_synced_fields_when_the_template_pair_diverges`
covers the still-explicit case with a template whose two rows differ on
room.

**Confirmed end-to-end: the solver actually enforces the new default,
not just the instance's own bookkeeping.** All the `synced_fields`
testing up to this point exercised `pairwise_predicate` directly, never
an actual CP-SAT solve. `tests/test_architecture.py` gained
`test_declared_cross_listing_without_synced_fields_actually_converges_when_solved`:
two rows built via `from_configured_sections` with no `synced_fields`
(so `ALL_SYNCED_FIELDS`), starting in different rooms with two rooms and
two start times genuinely available -- solving still converges them to
one shared instructor/room/time, proving the default lock is actually
binding on the solver, not just recorded on the object. This complements
the pre-existing `test_cross_listing_rows_are_never_forced_to_converge`
(the un-locked-field direction, via the legacy auto-detect path) -- the
two together cover both "must converge" and "must not be forced to
converge" at the actual solve layer.

**Confirmed: a cross-listing pair with two different instructors credits
both of them in full, not split.** `teaching_loads()`
(`schedule_model.py`) already did this correctly -- for each atomic
class, it credits *every distinct instructor* found across its rows with
the class's full `credit_hours`, never dividing it -- but there was no
test exercising a `CrossListingClass` whose two rows actually have
different instructors (every existing cross-listing test used the same
instructor on both rows). Added
`tests/test_schedule_model.py::GroupingTests::test_two_different_instructors_each_get_full_credit_for_a_diverging_cross_listing`:
two rows, two different instructors, `credit_hours` inferred as 3 either
way (`"5173"`/`"4173"`'s trailing digit) -- asserts `teaching_loads()`
gives *both* instructors the full 3, not 1.5 each. This is exactly the
semantics `synced_fields` excluding `"instructor"` is for: two people
each really teaching their own section of what the catalog treats as one
shared course, not one teaching load shared between them.

## Addendum, 2026-08-27: `/api/edit` verifies `class_index`/`record_index` against an identity snapshot; dev `httpx` swapped for `httpx2`

Two follow-ups, closing the last open item from the review two addenda
back (`class_index`/`record_index` as the sole identity `/api/edit`
trusts) and a dependency-hygiene fix noticed alongside it.

**`/api/edit` now rejects a stale/mis-targeted edit with 409 instead of
trusting `class_index`/`record_index` alone.** The browser now sends,
alongside the existing `class_index`/`record_index`: `expected_course_ids`
(the target atomic class's `course_ids`, exactly as the last view payload
gave them) and `expected_record` (`subject`/`number`/`section`/
`expected_time_slot` -- the target row's own pre-edit snapshot). The
handler re-groups `records` into a `Schedule` as before, indexes into it
as before, but now compares both against what it actually landed on
*before* touching anything:

```python
if (
    requested_course_ids != actual_course_ids
    or expected_identity != actual_identity
):
    raise HTTPException(
        409,
        "The schedule grouping changed before this edit; reload the "
        "schedule and try again",
    )
```

This is deliberately not a check against the flat `records` payload
itself (frontend and backend agree on that by construction, since the
frontend built both from the same `data`) -- it is a check against
whatever row *grouping* actually produced at `class_index`/`record_index`
this time, which is the thing that could silently drift if a future
change ever made grouping order depend on something an edit can touch.
`field`/`value` are still applied exactly as before once this passes;
`Time Slot` in the snapshot is read-only identity, never a second way to
set the new time (that's still `field`/`value`).

Two new `tests/test_edit_api.py` cases:
`test_changed_atomic_class_identity_is_rejected_without_editing` (wrong
`expected_course_ids`) and
`test_changed_target_row_snapshot_is_rejected_without_editing` (a
correct `expected_course_ids` but a stale `expected_time_slot`), both
asserting 409 and that nothing was applied.
`tests/test_configuration_web.py`'s static-content sanity test gained two
more `assertIn`s confirming `app.js`'s `submitEdit` actually sends both
fields.

**Dev dependency: `httpx` -> `httpx2`.** Every test run's
`fastapi.testclient.TestClient` import had been emitting
`StarletteDeprecationWarning: Using httpx with starlette.testclient is
deprecated; install httpx2 instead` -- coming from the installed
Starlette build itself, not a lint suggestion. `pyproject.toml`'s
`[dependency-groups] dev` entry moved from `"httpx>=0.27"` to `"httpx2"`,
`uv.lock` re-resolved. Verified: the warning is gone from a full `uv run
python -m unittest discover -s tests` run, and the suite still passes
(303 tests) -- `httpx2` really is what this environment's `TestClient`
now expects, not a name that merely happens to resolve.

## Addendum, 2026-08-27: `validate` renamed to `validate_structure`; `CrossListingClass.schedule_issues` was missing its own `synced_fields` lock

A review of the "Never-Block Scheduling" design (the four two-row kinds'
`_issues`/`schedule_issues`/`pairwise_predicate` split, described near the
top of this doc) surfaced two things: one a stale name, the other a real
gap unique to `CrossListingClass`.

**`NormalClass.validate` renamed to `validate_structure`.** Its own
docstring, and the class docstring above it, still said "subclasses
override `validate` to add their own recognition rule" -- true before
the redesign, false since (`git log` confirms all four kinds' `validate()`
overrides were removed in the same commit that introduced
`_issues`/`schedule_issues`; nothing has overridden it since). Left as
`validate`, the name itself invites exactly the confusion this caused: it
reads like "the place business rules live," when today it only checks row
count -- everything else construction still enforces. Renamed (five call
sites total, all inside `class_model.py`; nothing outside it called
`.validate()` directly) and both docstrings corrected to say plainly what
it does now and where the real rules live instead.

**`CrossListingClass.schedule_issues` never reflected whether the current
rows actually satisfied this instance's own `synced_fields` lock.** For
the other three two-row kinds, `_issues`/`is_valid_schedule` is the
*entire* rule both `schedule_issues` (hard-violation reporting) and
`pairwise_predicate` (solver enforcement) share -- the two can never
disagree, by construction. `CrossListingClass` broke that pattern without
anyone deciding to: `_issues` only ever checked recognition (different
courses, `is_cross_listing`); the `synced_fields` lock-consistency check
existed *only* inside `pairwise_predicate`'s closure. Recognition-only
issues meant a `CrossListingClass` whose current data violates its own
declared lock -- most concretely, a `from_configured_sections` pair that
defaults to `ALL_SYNCED_FIELDS` (see the opt-in addendum above) over
source rows that don't actually match -- was reported as clean by
`schedule_issues`, `evaluate_schedule`, `/api/analyze`, and every UI
surface, while the solver would have refused to accept it as-is. Two
engines silently checking different rules for the same instance is
exactly the failure mode this whole design exists to prevent.

Fixed with one new instance method, `_sync_issues(left, right)`, that
`schedule_issues` and `pairwise_predicate` now both call instead of
`pairwise_predicate` keeping its own inline copy:

```python
def _sync_issues(self, left: Section, right: Section) -> tuple[str, ...]:
    locked = self.synced_fields
    issues = []
    if "instructor" in locked and left.instructor != right.instructor:
        issues.append(...)
    if "room" in locked and (left.room != right.room or left.building != right.building):
        issues.append(...)
    if "time" in locked and (left.time_slot != right.time_slot or left.duration != right.duration):
        issues.append(...)
    return tuple(issues)
```

`schedule_issues` is now `self._issues(left, right) + self._sync_issues(left, right)`
in all three places it gets computed (`__post_init__`, `
from_configured_sections`, and the `apply_edit` override -- which needed
an explicit recompute, since the `replace()` inside it reruns
`__post_init__` with the *wrong*, not-yet-restored `synced_fields` before
the override puts the real ones back). `pairwise_predicate` shrank to
`is_valid_schedule(...) and not self._sync_issues(...)` -- same behavior
as before (confirmed by the pre-existing `pairwise_predicate` tests all
still passing unchanged), just no longer a second copy of the comparison
logic.

Right after ordinary construction (`__post_init__`'s auto-detect path),
`_sync_issues` is always empty by construction -- `synced_fields` there
*is* "whichever fields currently match," so there's nothing to violate
yet. The gap was only reachable through `from_configured_sections` (a
declared lock the data doesn't actually satisfy) or, in principle, an
edit -- though `edit_targets` already keeps every locked field's two rows
moving together through `/api/edit`, so a `synced_fields` mismatch can't
actually arise from that path today; the `apply_edit` recompute is
correctness hygiene (and tested for not false-positiving on an *unlocked*
field), not a fix for a reachable edit-time bug.

Three new `tests/test_class_model.py` cases:
`test_configured_pair_that_currently_violates_its_own_lock_reports_a_schedule_issue`
(3 issues, one per mismatched locked field, and `pairwise_predicate`
rejects the pair -- both agree),
`test_configured_pair_that_currently_satisfies_its_own_lock_has_no_schedule_issue`
(the clean case, both agree it's fine), and
`test_apply_edit_does_not_report_a_sync_issue_for_an_unlocked_field` (no
false positive after an edit to a field that was never locked). One
extended `tests/test_pipeline.py` case
(`test_configured_cross_listing_without_synced_fields_defaults_to_fully_locked`)
now also asserts `check_atomic_class_rules` reports exactly 3
`cross_listing_invalid` violations for the same fixture -- proving the fix
reaches actual hard-violation reporting, not just the instance's own
attribute.

## Addendum, 2026-08-27: `RecordReference` -- structured, precise references replace `message`-string guessing

Closing out a long design discussion (the "unified Rule Engine" proposal
that preceded this was explicitly rejected as over-scoped for the one
confirmed problem it was meant to fix -- see that discussion for why).
The concrete, narrower problem: `HardViolation.subject`/`SoftFinding.message`
were the *only* things the web UI had to work with for "which record is
this about" -- and `subject` means a different kind of thing per rule
(a room label for `room_conflict`, an instructor name for
`instructor_conflict`/`overload`/`under_load`, a `course_id` for
everything else), so the frontend fell back to guessing from `message`
text (`String(item.message).includes(row.course_id)`), which is fragile
and, for `room_conflict`/`instructor_conflict`, *never* worked at all
(`subject` there was never a `course_id` to begin with). This addendum
doesn't change what `subject`/`message` mean -- it adds a new, orthogonal,
uniformly-shaped field instead.

### `RecordReference`

```python
@dataclass(frozen=True)
class RecordReference:
    class_index: int
    record_index: int
    course_id: str
```

Points at one row of one atomic class in a specific `Schedule` --
`class_index`/`record_index` are positions in *that* `Schedule`'s own
`classes`/`sections` lists. Valid only for the serialized Schedule they
were computed from, or its deterministic same-configuration
flatten/regroup round trip (`to_records()` then `from_records()` with
the same relationships/catalogs) -- never to be persisted across
schedule revisions. `course_id` is a cheap, self-describing companion a
consumer checks before trusting the indices.

This was extensively re-litigated before landing on indices at all
(course-identity-only tuples were considered and rejected): `class_index`/
`record_index` are safe here in a way they are *not* for `/api/edit`'s
`class_index`/`record_index` (see the "identity snapshot" addendum
above) -- there, indices cross a request boundary holding client state
that might be stale by the time it's used. Here, `data.classes` and
`data.violations` are always replaced together from the same response
(`/api/analyze`, `/api/edit`, `/api/solve` all do this), computed by the
same `Schedule` object in the same request -- there is no staleness
window. Course-id-only references were also rejected on their own merits:
`FourCreditClass`'s two rows share one `course_id` (same course/section,
only the weekday pattern differs), so a scheme without record-level
indices literally cannot tell them apart.

### `_indexed_sections(schedule)`

```python
def _indexed_sections(schedule):
    for class_index, item in enumerate(schedule.classes):
        for record_index, section in enumerate(item.sections):
            yield RecordReference(class_index, record_index, section.course_id), item, section
```

The one place that decides what a reference's indices mean -- every
`check_*` function below consumes it instead of each re-deriving its own
`enumerate`. This directly closes two traps a per-function rewrite would
have hit: `HybridClass.physical_section` is not reliably row 0 (it's
found by content, not position -- confirmed by a new test that
deliberately puts the online/TBA row first), and
`_capped_back_to_back_findings` re-sorts/re-filters sections into
per-weekday runs, so by the time it builds a finding there is no way to
safely recover which atomic class/row a bare `Section` came from -- its
signature changed to take `(RecordReference, Section)` pairs instead of
bare `Section`s.

### Where `references` come from, per rule

- `check_conflicts` (`room_conflict`/`instructor_conflict`): both
  classes' rows.
- `check_atomic_class_rules`: **every record of the flagged atomic
  class** -- not the minimal faulty subset. This is "the problem belongs
  to this class," not a claim about which specific row is at fault (a
  Coreq issue references both of its two different courses now, fixing
  the old `item.course_ids[0]`-only report that silently dropped the
  second course).
- `check_constraint_rules`/`check_meeting_patterns`: the one row
  checked (correctly the physical row's own index for `HybridClass`, per
  above).
- `check_soft_preferences`'s `overload`/`under_load`: **every record of
  every atomic class the instructor appears in** -- via a new
  `_class_references_by_instructor(schedule)` helper that mirrors
  `teaching_loads()`'s own definition exactly (any row naming an
  instructor credits that instructor with the whole class's
  `credit_hours`; references have to cover the same set, or a
  `CrossListingClass` with two different instructors would silently
  lose the row that doesn't happen to name the one a finding is about).
  Legitimately empty for an instructor currently teaching nothing (a
  valid `under_load` case) -- not a bug.
- `custom_rule`/`back_to_back`: the specific row(s) involved.

### Web API and frontend

`webapp.py`'s `_serialize_hard`/`_serialize_soft` add a `"references"`
array (`{class_index, record_index, course_id}`). `app.js`:

- `validReferences(item)` filters `item.references` to ones where
  `courseId(data.classes[ref.class_index]?.sections[ref.record_index])`
  still matches `ref.course_id` -- cheap insurance, not because a
  mismatch is expected in practice.
- `conflictIds()` now builds its highlight set straight from references
  instead of `item.subject===row.course_id||message.includes(...)`.
- `issueViewModel(item)` replaces `softIssue()` and now runs for **both**
  hard and soft findings (`renderIssues()` used to pass `hard` straight
  to `renderIssueItem` with no transform at all -- hard conflicts were
  plain, unclickable text before this, a pre-existing gap this happened
  to also close). A small `RULE_VIEW` map (rule name -> `"room"` /
  `"instructor"` / `"course"`) decides which tab a finding's course links
  navigate to -- deliberately kept out of the Python model, since it's a
  display concern, not part of what a finding *is*. When `references` is
  non-empty, courses/resource come from the referenced records; when
  empty but `item.subject` is set (the zero-class `under_load` case),
  it still falls back to a plain instructor-tab link -- only the
  `message`-substring guess was deleted, not every fallback.
- `renderIssueItem`'s links and the click-to-scroll handler now carry
  and match on `data-record` as well as `data-class` (a `FourCreditClass`
  reference needs both to pick the right one of its two same-`course_id`
  rows). The course-list view's `.course-row` gained `data-class`/
  `data-record` too -- previously only `.course-block` (the calendar
  grid) had them, so a finding whose `RULE_VIEW` sends it to `"course"`
  had no element to find or highlight at all.

### Tests

`RoundTripReferenceStabilityTests` (`test_schedule_model.py`) locks the
flatten/regroup assumption `RecordReference` depends on: build a schedule
with one of each of the five atomic-class kinds through the same
`Schedule.from_records` pipeline the real system uses, then assert
`Schedule.from_records(schedule.to_records())` reproduces the identical
`(class_index, record_index, course_id)` set *and* class order. (An
earlier, simpler version of this test hand-assembled the five classes in
an arbitrary order via `Schedule([...])` directly and failed --
`_group_records`'s pipeline stage order, not input row order, decides
class order, so a schedule not itself produced by grouping isn't a valid
stand-in for one that is. Fixed by building through `from_records` both
times, which is what `/api/analyze` actually does.)

Also added/extended: `room_conflict`/`instructor_conflict` reference both
classes (`CheckConflictsTests`); `FourCreditClass`'s two same-`course_id`
rows stay distinguishable by `record_index`; a `HybridClass` built with
its physical row second still reports `record_index=1`, not 0; a
`CoreqClass` violation references both of its (different) courses;
overload references span a multi-row atomic class with two different
instructors; `under_load` references are empty for a zero-class
instructor; a capped back-to-back finding references exactly the two
joining records; `/api/edit`'s response carries `references` on a real
`coreq_invalid` violation; and a static-content check that `app.js` no
longer contains a `message`-substring guess anywhere.

## Addendum, 2026-08-27: three Solver-only hard limits now reported too (Plan A); qualification deliberately left out

Closes three of the four gaps raised in the "Solver-only limits" audit
(the fourth, qualification, turned out not to be one at all -- see
below). All three were previously enforced *only* during solving --
`evaluate_schedule()`/`/api/analyze` reported a schedule that already
broke one of them as clean.

**The `hard_load_cap` authority question, resolved as Plan A.**
`teaching_loads()` (used by `overload`/`under_load`) credits every
distinct instructor named anywhere in a class's rows with that class's
full `credit_hours`. `solver/constraints.py`'s `add_load_terms` attributes
a class's units to its *first row's* instructor only. These agree for
every class whose rows share one instructor (everything except an
instructor-unsynced `CrossListingClass`), and disagree only for that one
case. Two options were on the table: fix the solver's load model to
match `teaching_loads()`'s broader definition (Plan B), or have the new
hard-cap report match the solver's current, narrower definition as-is
(Plan A). Plan B was reconsidered mid-discussion and found to be a real
CP-SAT modeling project of its own -- it needs a boolean indicator per
(class, instructor) pair to avoid double-charging an instructor whose
name appears on more than one of a class's rows, not a one-line formula
change -- so it was set aside as separate, larger work. **Plan A
shipped**: the report mirrors the solver's actual (incomplete) model
exactly, so the two can never disagree about what's a hard violation,
even though the model itself has a known, documented blind spot (a
`CrossListingClass`'s second instructor's load isn't capped by either
side, for that class's contribution).

```python
def _primary_section_instructor_loads(schedule):
    """... item.sections[0].instructor gets the class's full
    credit_hours; every other row's instructor gets nothing for this
    class, matching add_load_terms exactly."""
```

**Three new rules, one shared helper.** `check_workload_hard_caps` reports
`hard_load_cap` (a configured instructor past `max_load +
hard_load_cap_tolerance`) and `new_hire_contract_load` (a New
Instructor/New Professor identity past `contract_load` -- with *no*
tolerance, matching the solver's own unconditional cap for dynamic
identities) from the same per-instructor totals.
`check_new_hire_counts` reports `new_instructor_count`/
`new_professor_count`: the number of *distinct* New Instructor/New
Professor identities actually in use, checked directly against
`allowed_counts` -- not by re-deriving the solver's own `used` CP-SAT
variables (`add_placeholder_count_terms`), which additionally assume
contiguous use (identity 2 only counted if 1 already is). A raw or
manually-edited schedule has no reason to satisfy that invariant, so
counting directly is both simpler and correct where re-deriving it would
risk being wrong. `references` for a count violation come back
legitimately empty when the count itself is the problem at zero
(`allowed_counts = [1]`, nobody currently in either dynamic pool).

`evaluate_schedule()` gained two new optional parameters
(`new_instructor_policy`/`new_professor_policy`) to reach these --
defaulting to schema defaults when omitted, but every one of its six call
sites (`cli.py`, both in `schedule_run.py`, both in `webapp.py`) was
updated to pass the package's real configured policy, not the default.

**Qualification is explicitly *not* one of these, and won't become a
Hard rule under the "solver would never produce this" reasoning that
justified the other three.** Re-reading `solver/candidates.py`'s
`candidate_instructors` during this same discussion found:

```python
if section.instructor and (
    not is_new_instructor(section.instructor)
    and not is_new_professor(section.instructor)
):
    names.add(section.instructor)  # unconditional -- ignores person.courses
```

plus a `... or [section.instructor]` fallback when the candidate list
would otherwise be empty. A section's *current* non-dynamic instructor is
never excluded from candidates for lacking the course in `persons.toml`
-- qualification only gates which *new* instructor the solver could
reassign someone to, not whether an existing assignment is legal. So
"the current instructor isn't qualified" is not something the solver
ever actually refuses, and reporting it as Hard would misrepresent what
the solver does. Leaning (not yet decided) toward a separate, unblocking
`qualification_review`-style informational category later -- not
implemented in this pass, since it would need a third UI bucket (not
Hard, not the existing penalty-bearing Soft) rather than just a new rule
name in the existing two, which is a bigger, separate design question
than the three rules above.

### Tests

`CheckWorkloadHardCapsTests`/`CheckNewHireCountsTests`
(`tests/test_schedule_model.py`): within-tolerance is clean; past it is a
hard violation with correct references; a New Instructor identity has
zero tolerance past its contract load (unlike a configured instructor);
a diverging `CrossListingClass`'s load is charged only to its primary
row's instructor (proving Plan A, not a bug); `allowed_counts` violations
both when over and when under (the zero-used, empty-references case).
`docs/scheduling-rules.md` updated to list what's now reported alongside
what's deliberately still solver-only.

## Addendum, 2026-08-27: cleanup pass on the `references` batch before moving on

A review of the `references`/Plan-A work above (still all uncommitted at
this point) before starting anything new found seven loose ends worth
closing first, rather than letting them compound into the next batch.

**`_indexed_sections` is now genuinely the only place index semantics are
decided.** `check_atomic_class_rules`, `_class_references_by_instructor`,
and `_primary_section_instructor_loads` each still had their own
`enumerate(schedule.classes)`/`enumerate(item.sections)` building
`RecordReference`s by hand -- correct today, but a second (third,
fourth) copy of the same derivation that could silently drift from
`_indexed_sections` if either ever changed independently. Added
`_references_by_class(schedule) -> dict[int, tuple[RecordReference, ...]]`,
grouping `_indexed_sections`' own output by `class_index`; all three
now call it (or, for `check_new_hire_counts`'s per-row filter, iterate
`_indexed_sections` directly) instead of re-deriving.

**The `app.js` comment claiming `data.classes`/`data.violations` are
"always replaced together" was wrong for `/api/analyze`** (`refreshAnalysis`
only ever does `data.violations=body`). References stay valid there
anyway, but for a different, more specific reason: `/api/analyze`
reloads `data.classes`' own flattened records through the same
deterministic grouping pipeline every time, which is exactly the
invariant `RoundTripReferenceStabilityTests` locks. Comment rewritten to
say that, not the false blanket claim.

**`issueViewModel`'s two remaining design gaps, fixed together.** Both
traced back to the same root cause: computing `resource` (which
tab/room/whatever a click selects) *per referenced row* instead of once
from the finding's own `subject`.

- The no-references fallback (`if (item.subject) { treat as instructor
  }`) fired for *any* finding with a truthy `subject` -- harmless for the
  rules that actually have one today, but wrong in shape: `room_conflict`'s
  `subject` is a room label, not an instructor, and a future room/course
  rule that happened to have empty references would have been silently
  sent to the instructor tab. Restricted to `view==="instructor"` (i.e.
  only rules `RULE_VIEW` itself already maps there) -- an unknown rule
  now defaults to `"course"`, not `"instructor"`, matching "don't
  assume `subject` is a teacher" for anything not already declared as one.
- The real bug: for `overload`/`under_load`, `references` spans a whole
  atomic class (see the earlier addendum) -- for a `CrossListingClass`
  with unsynced instructors, that means a reference can sit on a
  *different* instructor's row than the one the finding is actually
  about (an "Alice is overloaded" finding referencing both Alice's row
  and Bob's row). The old code read `resource` off each referenced row's
  own `Instructor` field, so clicking the Bob-row course link inside
  Alice's overload finding navigated to Bob's tab. Fixed by computing
  `resource` once, from `item.subject`, and reusing it for every course
  link in the finding -- never recomputed per row. This is also strictly
  simpler code (deleted the per-view `roomLabel(row)`/`row.Instructor`
  branch entirely: `item.subject` was already exactly what those computed,
  since a room/instructor conflict's two referenced rows share the
  conflicting value by definition).

**`_capped_back_to_back_findings`'s de-dup key switched from
`(prev.course_id, last.course_id)` to
`((class_index, record_index), (class_index, record_index))`.** Two
different physical meetings can share a `course_id` string (two distinct
single-weekday classes reusing one subject/number/section on different
days -- not the same `"MWF"`-spanning row recurring, which is what the
course-id key was originally *for*, and still correctly collapses under
the new key too, since it's the same reference both times). The old key
would have treated the second, unrelated join as a duplicate of the
first and silently dropped it. New regression test:
`test_two_unrelated_runs_that_share_a_course_id_pair_are_not_deduped`
(`tests/test_preference_rules.py`).

**Frontend behavior was only checked by static string presence, not by
tracing execution.** This sandbox has no Node/npm and no browser
automation library (`playwright`/`selenium` both absent) -- there is no
way to actually execute `app.js` here. In lieu of that, the five
scenarios raised were traced by hand against the code as it stands after
the fixes above:

1. A `room_conflict` link switches to Room view and its `currentResource`
   (the room label) is guaranteed to already be in that view's resource
   list, since the conflict requires two physical sections actually in
   that room.
2. A `meeting_pattern` link (Course view) lands on a `.course-row` with
   matching `data-class`/`data-record` -- confirmed those attributes are
   actually emitted there (added in the earlier `references` batch).
3. A zero-class `under_load` finding's link sets `currentResource` to the
   instructor's name, which is still present in the instructor resource
   list (via `instructor_loads`) even with no classes; the scroll/highlight
   step no-ops cleanly on `data-class===""` without erroring.
4. An overload finding on a diverging `CrossListingClass` now sends every
   course link to the correct instructor's tab (the fix above). One
   residual, honest wrinkle: clicking the link for the *other*
   instructor's row switches to the right tab but can't highlight that
   specific block, because that row isn't rendered under the filtered
   instructor view it just switched to -- the click-scroll step finds no
   matching element and quietly no-ops (`if(!block)return`), not an
   error, just no highlight for that one link.
5. An invalid/stale reference is dropped by `validReferences`' `courseId`
   check before it ever reaches rendering; a finding left with zero valid
   references degrades to the fallback (or plain text) path, never a
   crash (optional chaining guards an out-of-range index too).

This is code-reading verification, not executed verification -- flagged
here explicitly rather than implied as tested. A real manual check in a
running browser is still worth doing before treating this batch as fully
verified.

**Trailing whitespace** (`docs/codes.md:1067`, `git diff --check`) removed.

This addendum closes out the `RecordReference`/Plan-A batch described in
the two addenda above it. Nothing here touches the solver or adds new
reported rules -- `qualification_review` (still just a lean toward a
non-blocking, non-penalized category, not implemented) is the only piece
of the "Solver-only limits" work left open.

## Addendum, 2026-08-27: Plan A retired -- `add_load_terms` now counts every row of a class

Revisits the "Plan A vs Plan B" decision from the hard-load-cap addendum
above. Plan A shipped there deliberately, matching the solver's then
narrower (first-row-only) load model rather than fixing it, on the
grounds that fixing it looked like a real CP-SAT modeling project, not a
one-line change. On review, the actual fix turned out smaller than that
first estimate suggested -- implemented directly rather than staying with
the documented gap.

**`solver/constraints.py`'s `add_load_terms`** used to attribute a
class's `credit_hours` to its first row's chosen instructor only:

```python
primary = sections_by_class[class_index][0]
for candidate_index, candidate in enumerate(candidates[primary]):
    per_instructor.setdefault(candidate.instructor, []).append(
        units * chosen[primary][candidate_index]
    )
```

Now, for each class, every distinct instructor possible on *any* of its
rows gets one boolean "does this class's assignment include this
instructor" indicator -- the OR of that instructor's `chosen` variables
across every row of the class, reusing the same "used" pattern
`add_placeholder_count_terms` already used for a different purpose
(one linear inequality per contributing variable, plus one summed
upper bound) -- and that indicator, not a raw per-row `chosen` variable,
is what gets multiplied by `units` and credited to the instructor:

```python
by_instructor: dict[str, list] = {}
for section_index in sections_by_class[class_index]:
    for candidate_index, candidate in enumerate(candidates[section_index]):
        by_instructor.setdefault(candidate.instructor, []).append(
            chosen[section_index][candidate_index]
        )
for instructor, selected in by_instructor.items():
    taught = selected[0] if len(selected) == 1 else _or_indicator(selected, model)
    per_instructor.setdefault(instructor, []).append(units * taught)
```

The `len(selected) == 1` special case keeps the model exactly as small
as before for the overwhelming common case (a single-row class, or an
instructor who's only a plausible candidate on one of a class's rows) --
new variables are only created for a genuinely multi-row, multi-candidate
case. For every kind except an instructor-unsynced `CrossListingClass`,
`pairwise_predicate` already forbids any feasible solution where a
class's rows disagree on instructor, so the OR is computing the exact
same answer the old primary-row read did, just by a route that also
happens to be correct for the one case that disagreed. The hard-cap
constraint and the soft overload objective terms downstream of
`per_instructor`/`total` needed no changes at all -- they were already
correct given a correct `total`, they just never used to receive one for
this case.

**`schedule_model.check_workload_hard_caps`** dropped
`_primary_section_instructor_loads` entirely and now calls
`teaching_loads()`/`_class_references_by_instructor()` directly -- the
same functions `overload`/`under_load` already used. There is no longer
a "Plan A" definition to keep separate from `teaching_loads()`'s; fixing
the solver made them the same thing, so reporting can (and must, to stay
in sync) just use the one that already existed.

**`add_placeholder_load_terms`** (a separate, purely optimization-side
penalty for using New Instructor/New Professor credit hours at all, not
a hard cap) still reads only `sections_by_class[class_index][0]` and was
*not* changed here -- it's a soft preference weight, not a correctness
question the way the hard cap was, and expanding it to the same
multi-row treatment is a smaller, separate follow-up, not bundled into
this pass.

### Tests

`tests/test_architecture.py::SolverArchitectureTests::test_load_cap_counts_every_row_of_a_class_not_just_the_first`:
an actual `solve()` call, not just a unit check of the term-building
function -- Bob is the only usable instructor for both a 3-credit
`NormalClass` and the second (unsynced) row of a 3-credit
`CrossListingClass` (New Instructor/New Professor pools barred via
`allowed_counts=[0]`, no one else qualified), so with
`hard_load_cap_tolerance=0` and `max_load=3`, his true total of 6 is
unavoidably over cap -- `solve()` must raise `InfeasibleSchedule`.
Verified this test actually depends on the fix (not just incidentally
passing) by reverting `constraints.py` alone and re-running it in
isolation: it fails with `InfeasibleSchedule not raised`, exactly as
expected from the old primary-row-only model never seeing Bob's second
row at all.

`tests/test_schedule_model.py::CheckWorkloadHardCapsTests`'s Plan-A test
(previously asserting only the primary instructor got capped) was
rewritten to
`test_diverging_cross_listing_load_is_charged_to_every_instructor`,
asserting *both* instructors of a diverging pair get capped now, each
with references covering both rows of the class.

`docs/scheduling-rules.md`'s hard-constraints bullet updated to match
(no longer says "charged only to its first row's instructor").

## Addendum, 2026-08-27: configuration-authoritative relationships and unified validation

This addendum supersedes older passages above that describe automatic runtime
Coreq/CrossListing recognition, manual relationship IDs, two-member-only
cross-listings, `synced_fields` as the preferred syntax, or
`validate_structure`/`schedule_issues` as the evaluation entry point.

- Normal loading gets Coreq and CrossListing membership only from
  `courses.toml`. Template inference owns the legacy/default guesses and
  verifies its generated package by reloading the explicit relationships.
- Four-credit and same-section `Fxx`/`Mxx` Hybrid recognition remains
  intrinsic. Hybrid means two rows with the identical section name, one
  physical and one without time/location.
- Relationship identity is the derived `kind|sorted members` key. New files do
  not write `id`. Cross-listing policy is written as `unsynced`; omitted or
  empty means instructor, room, and time are all linked.
- CrossListing supports N members, uses the maximum member credit, and assigns
  that full credit once to every distinct instructor in the atomic class.
- The atomic validation API is `validate()` plus `validation_report()`.
  `Schedule` evaluation calls the report; the old `schedule_issues` mirror has
  been removed.
- `Schedule.evaluate(EvaluationContext(...))` is the object-facing evaluation
  API; `evaluate_schedule()` remains the pure shared implementation.
- Weekly exports include a complete Issues sheet and use structured
  `RecordReference` values for hard/soft highlighting. The web issue list no
  longer truncates after eight entries.
