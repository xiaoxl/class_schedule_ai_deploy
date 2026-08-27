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
