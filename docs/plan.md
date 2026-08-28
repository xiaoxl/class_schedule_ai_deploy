# Next-Step Plan (as of 2026-08-28)

This is the live "what's next" list. Completed work lives in `docs/codes.md`
(chronological, append-only -- each addendum states what it supersedes).
This file only tracks what's still open, so it should be edited in place
(not appended to) as items finish or get reprioritized.

## Just finished (2026-08-28 batch)

Coreq `_back_to_back` overlap-check regression, `infer_credit_hours`
unification, and Coreq template-inference ambiguity detection -- see
`docs/codes.md`'s "2026-08-28" addendum for the full writeup, and
`docs/api-audit.md` for the full function-by-function inventory that
produced items 1-3 below.

## 1. Delete the dead pre-`/api/edit` editing API

**What:** `NormalClass.change_time`/`change_room`/`change_instructor`/
`_change` (`class_model.py`), every subclass override
(`FourCreditClass.change_time`, `HybridClass.change_time`/`change_room`,
`CoreqClass.change_time`), and `Schedule.change_time`/`change_room`/
`change_instructor` (`schedule_model.py`).

**Why now:** Confirmed via a full caller audit (`docs/api-audit.md`) that
`change_time`/`change_room` have zero production callers, and
`change_instructor` has exactly one (`initial_builder.py:56`). Superseded by
`edit_targets`/`apply_edit`, which is what `/api/edit` actually uses.

**Steps:**
1. Repoint `initial_builder.py:56` at `apply_edit("instructor", 0, instructor=name)`
   (the class it's called on is always a fresh single-row class at that
   point, so this is a direct swap, not a redesign).
2. Delete the functions listed above.
3. Delete/update `tests/test_class_model.py` cases that exercise them
   directly (they test an API being removed, not a behavior still needed
   elsewhere -- confirm nothing else depends on the specific `_change`
   partial-row semantics before deleting each test).
4. Run the full suite; re-check `git diff --check` for trailing whitespace
   per this repo's usual discipline.

**Risk:** low -- purely subtractive, one call site to update.

## 2. Retire the legacy relationship-inference grouping helpers

**What:** `_take_cross_listed`, `_take_known_cross_list_pairs`,
`_take_honors_pairs`, `_take_coreqs` in `schedule_model.py`.

**Why:** Confirmed reachable only via `infer_legacy_relationships=True`,
which no production caller sets (`reconciliation.py` defaults it `False`;
only `tests/test_pipeline.py`/`tests/test_schedule_model.py` pass `True`).
The whitelist-based recognition they implement now lives in
`config_inference.py`'s template-inference pass instead (with the
2026-08-28 ambiguity fix already applied there).

**Do NOT delete `_take_cross_list_column`** -- it's reachable a second way,
via `infer_marked_cross_lists=True`, which `template_workspace.py:156-157`
*does* set in production (the template-inference verification reload).
Confirm that call site still needs it before touching anything nearby.

**Steps:**
1. Rewrite `tests/test_schedule_model.py`'s `infer_legacy_relationships=True`
   cases to instead exercise `config_inference.infer_relationships_from_template`
   directly (or drop them if `test_config_inference.py` already covers the
   same behavior -- check for overlap first).
2. Delete `_take_cross_listed`, `_take_known_cross_list_pairs`,
   `_take_honors_pairs`, `_take_coreqs`, and the now-unreachable
   `infer_legacy_relationships` branch in `_group_records` (keep the
   `infer_marked_cross_lists` branch).
3. Consider whether `infer_legacy_relationships` should be removed from
   `Schedule.from_records`/`from_dataframe`'s signature entirely, or kept as
   a documented no-op for one release -- decide based on whether anything
   outside this repo (scripts, notebooks) might still pass it.

**Risk:** medium -- touches test coverage, not just dead code; do this as
its own reviewed change, not bundled with item 1.

## 3. `overrides.py`'s `apply_overrides` duplicates `apply_edit` a third way

**What:** `apply_overrides` reimplements field-replacement and the
Hybrid-physical-row special case from scratch instead of calling
`Class.apply_edit`/`edit_targets`.

**Why it's lower priority than 1/2:** It has its own semantics
`apply_edit` doesn't (`record=None` means *every* row, not "the row this
edit was made through"; it also has to interact with the separate
`locks`/`LOCK_FIELDS` system). Not a quick swap -- a real design pass.

**Suggested approach when picked up:** decide whether `edit_targets` should
grow a "record=None means everything" mode `apply_overrides` can reuse
directly, or whether the two use cases (interactive single-row web edit vs.
batch revision-file replay) are different enough to justify keeping
`apply_overrides`'s own loop but building it out of `edit_targets`'s
row-selection logic instead of re-deriving `hybrid_physical` inline.

## 4. API 收口: adopt `Schedule.evaluate(EvaluationContext(...))` everywhere

**What:** `webapp.py`, `schedule_run.py`, and `cli.py` still call the
long-parameter-list `evaluate_schedule(...)` function directly instead of
building one `EvaluationContext` and calling `schedule.evaluate(context)`.

**Why:** `EvaluationContext` already exists and is the intended public
surface (`schedule_model.py`); `evaluate_schedule` remains the shared
implementation underneath, so this is a call-site migration, not new logic.

**Steps:**
1. At each of the three call sites, replace the long positional/keyword
   `evaluate_schedule(schedule, preferences, persons, ...)` call with
   constructing one `EvaluationContext` (from the same already-loaded
   config values) and calling `schedule.evaluate(context)`.
2. Add a small parity test asserting a `Schedule.evaluate(context)` call and
   the equivalent `evaluate_schedule(...)` call produce identical
   `ScheduleEvaluation` results, so a future divergence between the two
   call shapes is caught immediately rather than silently drifting.
3. Once all three are migrated, consider whether `evaluate_schedule` should
   become a private (`_evaluate_schedule`) implementation detail of
   `EvaluationContext.evaluate`, or stay public for direct/scripted use --
   decide based on whether anything still wants the parameter-list form.

**Risk:** low -- signature-preserving at the boundary (same
`ScheduleEvaluation` result), but touches three entry points, so test
thoroughly before considering it done.

## 5. Still-open architectural gap: `HybridClass.is_hybrid`'s validation/recognition conflation

**What:** `is_hybrid`'s `[FM]\d\d` section-prefix regex check is used both
for *recognition* (deciding two rows form a Hybrid at grouping time) and,
via `is_valid_schedule`, for *ongoing validity* (the solver rejects a
candidate pairing that fails this regex). Every other kind keeps those two
questions separate (config/hardcoded recognition decides the type once;
`_issues`/`validation_report` covers business rules afterward, with no
recognition-shaped checks re-run).

**Status:** raised twice during review, not yet actioned -- no instruction
to fix it. Flagging here so it isn't lost, not proposing to fix it
unprompted.

**If picked up:** the fix is narrow -- move the section-prefix check out of
`is_valid_schedule`'s ongoing-validity path (a Hybrid's *identity* is fixed
at construction; the solver only needs to know if a *candidate time/room/
instructor* pairing is still legal, which shouldn't depend on re-deriving
the section-name pattern that decided its kind in the first place).

## 6. Deferred by explicit instruction: `add_placeholder_load_terms`

**What:** `solver/constraints.py`'s placeholder credit-weight objective term
still reads only `sections_by_class[class_index][0]` (the primary row), so
an instructor-unsynced `CrossListingClass` whose *second* row is a
placeholder identity is under-penalized in the objective.

**Status:** confirmed real, explicitly deferred by the user ("3可以默认一定不会有问题",
2026-08-28) because it can only under-count a soft preference weight, never
produce an incorrect hard result. Do not pick this up without being asked
again -- it's intentionally parked, not forgotten.

## Documentation currency check (2026-08-28)

Cross-checked every file in `docs/` against the current code as part of
this pass:

- `docs/scheduling-rules.md`, `docs/configuration.md`,
  `docs/data-cleaning.md`, `docs/manual-adjustments.md`,
  `docs/demand-analysis.md`, `docs/index.md` -- all already match current
  behavior (unified `validate()`/`validation_report()`, N-member
  CrossListing with `unsynced`, `Schedule.evaluate(EvaluationContext(...))`
  as the public entry point, `infer_credit_hours`'s digit-fallback rule,
  Coreq/CrossListing as config-only with template inference separate). No
  edits needed.
- `docs/codes.md` is an append-only chronological design log, not a live
  reference -- older addenda intentionally describe superseded behavior
  (`schedule_issues`, `validate_structure`, always-computed `synced_fields`,
  etc.); the newest addenda explicitly state what they supersede. This is
  the documented convention (see its own header), not staleness.
- `docs/api-audit.md` (new this pass) and `docs/plan.md` (this file, new
  this pass) are added to `docs/index.md`'s documentation list.
