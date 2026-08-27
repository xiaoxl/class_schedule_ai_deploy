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
