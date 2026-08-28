# API Inventory and Audit (2026-08-28)

A full pass over the backend function/method surface, looking for (a)
functions that overlap and could merge, and (b) functions superseded by
newer code and safe to delete. Scope: `class_model.py`, `schedule_model.py`,
`config_schema.py`, `config_inference.py`, `solver/constraints.py`,
`overrides.py`, and the `webapp.py` helper layer -- the modules that do
computation. Frontend (`app.js`) and CLI wiring (`cli.py`,
`schedule_run.py`) are not re-audited here; they're thin callers of this
layer, already covered by the `docs/codes.md` addenda on `/api/edit` and
`Schedule.evaluate`.

Verdicts: **很重要** = keep, no better alternative. **可合并** = works fine
but duplicates another function's job; names the counterpart. **可以删** =
superseded, dead, or nearly dead; names what replaced it.

## The one actionable finding: a whole dead editing API

`NormalClass.change_time` / `change_room` / `change_instructor` / `_change`
(`class_model.py:296-326`), their per-kind overrides
(`FourCreditClass.change_time`, `HybridClass.change_time`/`change_room`,
`CoreqClass.change_time`), and `Schedule.change_time`/`change_room`/
`change_instructor` (`schedule_model.py:226-254`) are the *pre-`/api/edit`*
editing API. They were superseded by `edit_targets`/`apply_edit`, which the
web app actually calls. Checked every caller in the repo:

- `change_time`/`change_room`: no production caller anywhere. Only
  `tests/test_class_model.py` and their own recursive definitions.
- `change_instructor`: one production caller,
  `initial_builder.py:56` (`recolored.change_instructor(item.course_ids[0], name)`),
  used while synthesizing the initial working view, not interactive editing.
- `overrides.py`'s `apply_overrides` (the CLI revision-file feature) does
  **not** call any of these -- it reimplements its own field-replacement
  loop with its own hand-rolled Hybrid-physical-row special case
  (`overrides.py:184-217`), duplicating `apply_edit`/`edit_targets` a third
  way instead of reusing either.

Recommendation: point `initial_builder.py:56` at `apply_edit("instructor",
0, instructor=name)` (or a plain `dataclasses.replace`, since it only ever
touches a fresh single-row class), then delete the whole `change_*`/`_change`
family from both `class_model.py` and `schedule_model.py`. Separately,
`overrides.py` could be rewritten on top of `edit_targets`/`apply_edit`
instead of its own duplicate, but that's a bigger, riskier change (it has
its own record/lock semantics) -- worth a follow-up, not bundled with the
straightforward deletion above.

---

## `class_model.py`

### `Section` (the one-row primitive)

| Function | Verdict | Note |
|---|---|---|
| `infer_credit_hours` | 很重要 | Canonical credit fallback; `config_schema.resolved_credits` now delegates here (2026-08-28 fix). |
| `Section.__post_init__` | 很重要 | Normalizes/validates one raw row. |
| `course_id`, `identity` | 很重要 | `course_id` is the display key; `identity` (subject, number, section) is the grouping key `_take_same_course` uses. |
| `delivery_mode`, `is_online` | 很重要 | `is_online` is a one-line derived read of `delivery_mode`; not worth merging, `is_online` is the one callers actually want. |
| `has_meeting_time` | 很重要 | Distinguishes a real physical row from a placeholder/online row; used across Hybrid/checks. |
| `credit_hours` | 可合并-adjacent | Per-row credit; distinct from every `Class.credit_hours` (per-class, kind-specific aggregation) -- same name, different level, worth a docstring cross-reference but not a merge. |
| `days`, `start`, `end` | 很重要 | Parsed-time accessors everything else (overlap checks, back-to-back, solver slots) is built on. |
| `from_record` / `to_record` | 很重要 | The only CSV row <-> `Section` boundary. |

### `NormalClass` (base: 1 row)

| Function | Verdict | Note |
|---|---|---|
| `validation_report` / `validate` | 很重要 | The unified validation API; every subclass overrides `validation_report`, `validate` stays inherited (`not self.validation_report()`). |
| `_exact_row_count_report` | 很重要 | Shared row-count check called by every kind's `validation_report`/`__post_init__`. |
| `from_records` | 很重要 | Construction from raw CSV rows for this one kind. |
| `course_ids` | 很重要 | Every catalog id this atomic class covers (>1 for Cross-Listing). |
| `credit_hours` | 很重要 | Base (single-row) implementation; each special kind overrides with its own rule. |
| `to_records` | 很重要 | Flatten back to CSV rows; `HybridClass` overrides to regenerate the ONLINE companion. |
| `pairwise_predicate` | 很重要 | Base returns `None` (no cross-row rule); the hook the solver uses uniformly across kinds (see `solver/constraints.py:predicate_for`). |
| `change_time` / `change_room` / `change_instructor` / `_change` | **可以删** | See "The one actionable finding" above. |
| `edit_targets` / `apply_edit` | 很重要 | The current editing API `/api/edit` actually uses; per-kind overrides answer "which rows must move together." |

### `SpecialClass` (2-row base) / `FourCreditClass`

| Function | Verdict | Note |
|---|---|---|
| `SpecialClass.__post_init__` | 很重要 | The 2-row construction gate, kept separate from the report-only business rules by design (see the earlier `_issues` Q&A). |
| `FourCreditClass.__post_init__`, `validation_report`, `_issues` | 很重要 | `_issues` is the shared predicate core; `validation_report` (self) and `is_valid_schedule` (solver) both call it -- do not inline, see below. |
| `is_four_credit` | 很重要 | Recognition-only predicate used by `_take_same_course`; distinct from `_issues` (business-rule validity) on purpose. |
| `start_difference_minutes` | 可合并 | Small helper only `_issues` calls; could be inlined there, harmless either way. |
| `is_valid_schedule` | 很重要 | `not cls._issues(left, right)`, handed to the solver via `pairwise_predicate`. |
| `pairwise_predicate` | 很重要 | Returns `is_valid_schedule`. |
| `edit_targets` | 很重要 | Both rows move together for every field (whole-class pair). |
| `change_time` | **可以删** | Part of the dead family above. |

### `HybridClass`

| Function | Verdict | Note |
|---|---|---|
| `__post_init__`, `validation_report` | 很重要 | 2-row construction + business rules (same section, same instructor, one physical/one online). |
| `_online_companion` | 很重要 | Synthesizes the derived ONLINE row `to_records()` regenerates. |
| `physical_section` / `online_section` | 很重要 | Hardened against `StopIteration`, don't assume row 0 is physical. |
| `building` / `room` / `time_slot` | 可合并 | Three one-line passthroughs to `physical_section`'s own fields -- could be collapsed to one `physical_section` read at each call site, but they're cheap and self-documenting; low priority. |
| `is_hybrid` | 很重要, flagged | Recognition **and** still gates `is_valid_schedule` via the `[FM]\d\d` section-prefix regex -- see "Still-open gap" in Current Work; this conflates identification with validation, unlike every other kind. Not touched this pass (no instruction to fix it yet). |
| `is_hybrid_physical` | 很重要 | Recognition-only; used by `_group_records`'s leftover-row fallback. |
| `is_valid_schedule` | 很重要 | Wraps `is_hybrid`; see the flag above. |
| `pairwise_predicate` | 很重要 | Returns `is_valid_schedule`. |
| `edit_targets` | 很重要 | Redirects instructor edits to both rows, time/room to the physical row only. |
| `to_records` | 很重要 | Regenerates the ONLINE row rather than trusting stored data (source of truth is the physical row). |
| `change_time` / `change_room` | **可以删** | Part of the dead family above. |

### `CrossListingClass` (N >= 2 rows)

| Function | Verdict | Note |
|---|---|---|
| `__post_init__`, `_row_count_report`, `validation_report` | 很重要 | N-member row-count gate (`>=2`, not `==2`) plus `_issues` + `_sync_issues`. |
| `credit_hours` | 很重要 | `max(member credits)`, charged once per distinct instructor -- see `teaching_loads`/`add_load_terms`. |
| `_synced_fields` | 很重要 | Detects which fields actually agree across N rows; feeds inference, not runtime policy. |
| `from_configured_sections` | 很重要 | The `courses.toml`-driven constructor; resolves `unsynced`/`synced_fields` into the instance's locked-field set. |
| `_issues` | 很重要 | Business-rule core (no mutual conflict, same catalog identity story); shared by `validation_report` and `is_valid_schedule`. |
| `is_valid_schedule` | 很重要 | Wraps `_issues` for the solver. |
| `_sync_issues` | 很重要 | Separately reports "does the current data honor its own locked-field set" -- kept apart from `_issues` because it's about *this instance's* declared policy, not universal cross-listing legality. |
| `is_cross_listing` | 可合并 | Legacy pairwise recognition predicate (two-row, field-agreement based). Still used by `_take_known_cross_list_pairs`/`_take_honors_pairs`/`is_honors_pair`, which only run when `infer_legacy_relationships=True` -- see the grouping-helpers table below; not reachable in normal loading. |
| `is_known_pair` | 可合并 | Same status: whitelist-pair recognition, legacy-inference-only caller. |
| `is_shared_meeting` | 很重要 | Still used by `is_cross_listing`'s field-agreement check itself, so kept even though its only caller is legacy-only. |
| `pairwise_predicate` | 很重要 | Builds the N-way locked-field constraint for the solver from `synced_fields`. |
| `edit_targets` / `apply_edit` | 很重要 | `apply_edit` is overridden (not just `edit_targets`) specifically to never silently re-guess `synced_fields` from post-edit rows -- see the 2026-08-27 addendum in `docs/codes.md`. |
| `is_honors_pair` | 可合并 | Same status as `is_cross_listing`/`is_known_pair` -- legacy-inference-only. |

### `CoreqClass`

| Function | Verdict | Note |
|---|---|---|
| `__post_init__`, `validation_report` | 很重要 | 2-row gate + business rules. |
| `from_configured_sections` | 很重要 | `courses.toml`-driven constructor. |
| `credit_hours` | 很重要 | Kind-specific credit rule (see `class_model.py` for the exact formula). |
| `is_coreq_pair` | 很重要 | Recognition predicate; used both by `_take_coreqs` (legacy-only) and by `config_inference.py`'s template-inference whitelist scan (still load-bearing there). |
| `_back_to_back` | 很重要, recently fixed | Fixed 2026-08-28: `shared_days` reverted to an overlap check (real MW-lab/MWF-lecture pairs need this, see `docs/codes.md`). |
| `_issues` | 很重要 | Shared predicate core -- see the earlier "why can't `_issues` be inlined into `validation_report`" answer (used by both a zero-arg self-check and the solver's arbitrary-pair check). |
| `is_valid_schedule` | 很重要 | `not cls._issues(left, right)`. |
| `pairwise_predicate` | 很重要 | Returns `is_valid_schedule`. |
| `edit_targets`, `apply_edit` | 很重要 | Room-follow logic (see prior addenda) lives in the override. |
| `change_time` | **可以删** | Part of the dead family above; `record` has no default here specifically because a caller must pick which of the two meetings moves -- deleting this still requires that same explicitness from `apply_edit`, which it already has via `record_index`. |

---

## `schedule_model.py`

### `Schedule` (the collection)

| Function | Verdict | Note |
|---|---|---|
| `from_records` / `from_dataframe` | 很重要 | The two import entry points; `from_dataframe` is a one-line wrapper over `from_records` (fine, not worth merging away -- different callers want different input shapes). |
| `to_records` / `to_dataframe` | 很重要 | Export mirror of the above. |
| `to_raw_excel` / `to_instructor_excel` / `to_room_excel` | 很重要 | The three standard output views; thin wrappers over `_write_raw_excel`/`_weekly_workbook`. |
| `teaching_loads` (method) | 可合并 | One-line delegate to the module-level `teaching_loads(schedule)` function -- both are used (method form for `Schedule().teaching_loads()` call sites, function form because `check_workload_hard_caps` etc. take a bare `Schedule` positionally). Harmless duplication, not worth collapsing. |
| `evaluate` | 很重要 | The newer object-facing API (`schedule.evaluate(context)`); not yet adopted by `webapp.py`/`cli.py`/`schedule_run.py`, which still call `evaluate_schedule()` directly -- this is the still-open "API 收口" follow-up. |
| `course_ids`, `index_of`, `get` | 很重要 | Lookup primitives everything else (edits, overrides, references) is built on. |
| `add` / `remove` | 很重要 | Collection mutation with the course-id-clash guard. |
| `change_time` / `change_room` / `change_instructor` | **可以删** | Thin delegates to the dead `Class`-level family above; delete together. |

### Grouping / recognition (`_group_records` and helpers)

| Function | Verdict | Note |
|---|---|---|
| `_group_records` | 很重要 | The one loading pipeline: configured relationships -> hardcoded same-course (4C/Hybrid) -> optional legacy inference -> leftover Hybrid/Normal. |
| `_take_configured_relationships` | 很重要 | `courses.toml`-driven grouping; the only path normal loading uses for Coreq/CrossListing. |
| `_take_same_course` | 很重要 | Hardcoded, always-on FourCredit/Hybrid recognition (same `identity`, 2 rows). |
| `_take_cross_listed` | 可合并 | Thin dispatcher combining the three functions below; only reachable via `infer_legacy_relationships=True`, which no production caller sets (`reconciliation.py` defaults it `False`; only `tests/test_pipeline.py:73` and `tests/test_schedule_model.py` pass `True`). |
| `_take_cross_list_column` | 很重要-ish | Reachable two ways: via `_take_cross_listed` (legacy, unused in prod) **and** directly via `infer_marked_cross_lists=True`, which `template_workspace.py:156-157` *does* set in production (template-inference verification reload). Keep. |
| `_take_known_cross_list_pairs` | 可以删-candidate | Only reachable via `infer_legacy_relationships=True` -- confirmed no production caller sets that flag. Whitelisted-pair cross-listing recognition now lives in `config_inference.py`'s template-inference pass instead. Safe to delete once the `infer_legacy_relationships` tests are retired/rewritten against `config_inference` directly. |
| `_take_honors_pairs` | 可以删-candidate | Same status as above -- legacy-only, no production caller. |
| `_take_coreqs` | 可以删-candidate | Same status -- legacy-only; the whitelist-based Coreq recognition now lives in `config_inference.py:infer_relationships_from_template` (with the 2026-08-28 ambiguity fix). |

Net: three of these four (`_take_known_cross_list_pairs`, `_take_honors_pairs`,
`_take_coreqs`) plus the `_take_cross_listed` dispatcher are dead in
production and exist only to keep `infer_legacy_relationships=True` working
for their own tests. This matches the "Phase 3: 清理旧推断入口" item already
on the backlog (see `docs/codes.md`) -- not deleted in this pass since it
touches test coverage, not just dead code, but confirmed here with an actual
caller audit rather than assumption.

### Reference / finding model

| Function | Verdict | Note |
|---|---|---|
| `RecordReference` | 很重要 | Structured pointer replacing message-string guessing. |
| `_indexed_sections` | 很重要 | The single source of index semantics every `check_*` shares. |
| `_references_by_class` | 很重要 | Per-class grouping derived from the above; used by `check_atomic_class_rules` and `_class_references_by_instructor`. |
| `HardViolation` / `SoftFinding` | 很重要 | The two finding record types. |
| `teaching_loads` (function) | 很重要 | Authoritative per-instructor totals; "every distinct instructor counts once," matches `add_load_terms`. |
| `InstructorLoadSummary` / `summarize_instructor_loads` | 很重要 | Display-row shaping (target/delta/state) on top of `teaching_loads`; used by reports and the web load table. |
| `_class_references_by_instructor` | 很重要 | Reference-set counterpart to `teaching_loads` -- deliberately not "just rows naming them," see its own docstring. |

### Hard-violation checks

| Function | Verdict | Note |
|---|---|---|
| `location_matches` | 很重要 | Small shared helper (`"Corley"` or `"Corley 101"` both match) used by constraint/preference rule matching. |
| `is_back_to_back` | 可合并 | Module-level, general-purpose version; `_capped_back_to_back_findings` builds its own per-day-chain walk instead of reusing this directly (different granularity -- "any shared weekday" vs. "same-day ordered chain"). Documented distinction, not accidental duplication. |
| `_capped_back_to_back_findings` | 很重要 | The `max_back_to_back` soft-finding generator; uses the course-id-based dedup key flagged as fragile in an earlier review round (still open, low priority). |
| `_overload_statuses` | 很重要 | Shared overload/under-load classification `check_soft_preferences` reports from. |
| `overlaps_in_time` | 可合并 | One-line wrapper over `weekday_time_overlap`; kept as a `Section`-shaped convenience over the primitive's raw-field signature. |
| `check_conflicts` | 很重要 | Structural double-booking (room/instructor overlap) across *different* classes -- deliberately skips a class's own multi-row pairs. |
| `check_atomic_class_rules` | 很重要 | Generic `item.validation_report()` sweep -- no per-kind branch (this is what the earlier `schedule_issues` -> `validation_report` unification bought). |
| `check_constraint_rules` | 很重要 | `constraints.toml` hard-rule enforcement. |
| `check_meeting_patterns` | 很重要 | `timeslot.toml` pattern-domain enforcement. |
| `check_workload_hard_caps` | 很重要 | Now reads `teaching_loads`/`_class_references_by_instructor` directly (Phase 2 fix, no more "Plan A" narrower copy). |
| `check_new_hire_counts` | 很重要 | Distinct-identity count vs. `allowed_counts`; deliberately doesn't reuse the solver's `used`-variable contiguity assumption. |

### Config file loaders / rule matching

| Function | Verdict | Note |
|---|---|---|
| `weekday_time_overlap` | 很重要 | The one true overlap primitive on raw fields; `overlaps_in_time` wraps it for `Section`s. |
| `TimeWindow`, `.from_config`, `.overlaps` | 很重要 | Parsed time-window type used by constraint/preference/pattern selectors. |
| `PersonAlias`, `PersonRecord`, `ConstraintRule`, `PreferenceRule`, `PreferenceRecord` | 很重要 | Config-file record types; each carries its own `applies_to`/`allows`/`matches`/`signed_weight`/`rooms` -- no overlap between them, each answers a different selector question. |
| `load_persons` / `resolve_person_name` | 很重要 | `persons.toml` loading + alias resolution used at grouping time (instructor-name normalization) and reporting time. |
| `load_preferences` / `load_global_rules` | 很重要 | `preferences.toml` loading. |
| `_parse_flat_rule` / `_parse_rule` / `parse_rule_time` | 可合并 | Small parsing helpers only `load_preferences`/`load_global_rules` call; fine as private helpers, not worth inlining. |

### Evaluation and Excel export

| Function | Verdict | Note |
|---|---|---|
| `ScheduleEvaluation` | 很重要 | The one aggregate result type. |
| `EvaluationContext` / `.evaluate` | 很重要 | Newer object-facing wrapper over `evaluate_schedule`; not yet adopted by every entry point (open follow-up). |
| `evaluate_schedule` | 很重要 | The actual shared implementation every hard/soft check above is composed by; still the version `webapp.py`/`cli.py`/`schedule_run.py` call directly. |
| `_write_raw_excel` | 很重要 | Flat-table export. |
| `_weekly_workbook` (+ nested `key_of`) | 很重要 | Shared grid-builder for both instructor and room views. |
| `_add_issues_sheet` | 很重要 | The Issues worksheet. |
| `_highlight_referenced_issues` (+ nested `resource_for`) | 很重要 | Red/yellow highlighting driven by `RecordReference`, not message parsing. |
| `_merged_anchor` | 可合并 | Tiny openpyxl merged-cell lookup helper, single caller (`_build_weekly_sheet`). |
| `_build_weekly_sheet` | 很重要 | The core per-worksheet grid layout. |
| `_safe_sheet_title` | 很重要 | Excel's 31-char/illegal-character sheet-name constraint, with dedup. |
| `_minutes` / `_clock` / `_clock_range` | 可合并 | Tiny time-formatting helpers, single-purpose, low priority to touch. |

---

## `config_schema.py`

Almost entirely Pydantic `BaseModel`/`field_validator`/`model_validator`
definitions -- one validator per field-level rule, each with exactly one
job and no overlap with any other. Individually: 很重要 (schema validation
is the whole point of the module; removing any one silently widens what
`courses.toml`/`persons.toml`/etc. will accept). Notable exceptions:

| Function | Verdict | Note |
|---|---|---|
| `CatalogCourseSchema.resolved_credits` | 很重要 | Now delegates to `class_model.infer_credit_hours` (2026-08-28 fix) instead of its own separate regex -- the merge already happened here. |
| `CourseRelationshipSchema.locked_fields` | 很重要 | Resolves `unsynced` (preferred) / legacy `synced_fields` / default-all-locked into one `frozenset` -- the single place that duality is handled. |
| `CourseRelationshipSchema.key` / `.display_name` | 很重要 | `key` is the derived `(kind, sorted members)` identity replacing authored `id`; `display_name` is presentation-only. |
| `require_id` validator | 可合并/legacy | Accepts-but-ignores a legacy `id` field for migration; safe to delete once no configs in `config/` still author one (worth a quick grep before removing). |

---

## `config_inference.py`

| Function | Verdict | Note |
|---|---|---|
| `infer_configuration_from_template` | 很重要 | The top-level template -> seven-file package pipeline; rebuilds and reloads its own output before returning, as a self-check. |
| `_quote` / `_array` | 可合并 | Tiny TOML-literal formatting helpers shared by every `_*_toml` writer below. |
| `_catalogs_toml` / `_locations_toml` / `_timeslot_toml` / `_persons_toml` / `_preferences_toml` / `_courses_toml` | 很重要 | One writer per output file; each encodes that file's own inference rule, no cross-file overlap. |
| `_is_named_person` | 很重要 | Distinguishes a real name from "Staff"/blank for instructor-course-history inference. |
| `_person_courses` | 很重要 | Builds the `persons.toml` course-qualification list from template history. |
| `_member` | 可合并 | One-line `"SUBJECT NUMBER SECTION"` formatter, used everywhere a relationship member string is built; correctly centralized already (not a duplicate -- flagging it as the *reason* the coreq/cross-list writers don't each reimplement it). |
| `_same_assignment` | 很重要 | The field-agreement confidence gate for low-confidence recognition methods (same-course-number Cross-Listing, honors pairs) -- required before those methods commit a match. |
| `_cross_unsynced` | 很重要 | Computes the `unsynced` array actually written for a detected cross-listing group. |
| `infer_relationships_from_template` | 很重要, recently fixed | Now two-pass for Coreq (collect-then-check-ambiguity before committing) -- 2026-08-28 fix; Hybrid/FourCredit are not inferred here at all (intrinsic recognition handles them). |
| `_inferred_relationships` | 可合并 | Thin adapter converting `infer_relationships_from_template`'s output into `CourseRelationshipSchema` instances for `_courses_toml`; single caller. |

---

## `solver/constraints.py`

| Function | Verdict | Note |
|---|---|---|
| `add_placeholder_count_terms` | 很重要 | Distinct-placeholder-identity count objective + `allowed_counts` hard constraint; the "used"-indicator pattern reused by `add_load_terms`. |
| `add_placeholder_load_terms` | 很重要, known gap | Still reads only `sections_by_class[class_index][0]` (primary row) for the placeholder credit-weight objective -- explicitly left unfixed per user instruction 2026-08-28 (soft preference term, not a hard-correctness question); see `docs/codes.md`'s closing note. |
| `predicate_for` | 可合并 | One-line wrapper over `item.pairwise_predicate()`; kept as a named seam so `add_pairwise_validity_constraints` doesn't call the instance method inline (makes the "sourced from the instance, not a second mapping" intent explicit at the call site). |
| `add_pairwise_validity_constraints` | 很重要 | Compiles every kind's `pairwise_predicate` into CP-SAT forbidden-pair constraints ahead of search. |
| `Slot`, `build_slots` | 很重要 | The flat per-candidate scheduling-relevant view every calendar/room/instructor constraint below is built from. |
| `back_to_back_chains` | 很重要 | Recursive chain-walk powering the `max_back_to_back` soft constraint (solver-side counterpart to `_capped_back_to_back_findings` in `schedule_model.py` -- same concept, necessarily separate implementations: one over CP-SAT candidates, one over a concrete schedule). |
| `add_scheduling_constraints` (+ nested `add_bucket_no_overlap`) | 很重要 | Room/instructor no-overlap plus back-to-back preference objective terms. |
| `add_load_terms` | 很重要, recently fixed | Now builds a per-(class,instructor) "taught" OR-indicator across every row of a class, matching `teaching_loads()` -- Phase 2 fix, no longer primary-row-only. |

---

## `webapp.py` (helper layer only)

Endpoint-adjacent helpers, not the FastAPI route functions themselves
(those are thin and just call these). Grouped since most are single-purpose
with no overlap:

| Function | Verdict | Note |
|---|---|---|
| `_schedule_from_payload` / `_load_workspace_schedule` | 很重要 | The two ways a request gets a `Schedule`: from an uploaded/edited payload, or from the package's saved working view. |
| `_schedule_payload` / `_serialize_schedule` | 可合并-adjacent | `_serialize_schedule` does the real per-row/per-class serialization (including `linked_fields`); `_schedule_payload` wraps it plus metadata for one response shape. Not a true duplicate -- different response envelopes -- but worth knowing they're layered, not redundant. |
| `_analysis_payload` / `_evaluate_current_schedule` | 很重要 | Findings + load-summary response shaping on top of `evaluate_schedule`. |
| `_serialize_reference` / `_serialize_hard` / `_serialize_soft` / `_serialize_change` / `_serialize_record` | 很重要 | One JSON-shaping function per response type; each intentionally thin. |
| `_configuration_*` / `_replace_configuration_*` / `_delete_configuration_*` / `_package_*` / `_trash_destination` | 很重要 | The Configuration-editor file lifecycle (read, validate, upload/replace, delete-to-trash, rebuild working views). Each does one step of that pipeline; no pair of these does the same job. |
| `_excel_bytes` | 可合并 | Generic `getattr(schedule, method_name)(...)` -> bytes wrapper so the three download routes share one function instead of three near-identical bodies -- this *is* the already-applied merge, not a remaining duplicate. |
| `_resolve_meeting_duration` | 很重要 | Time-slot -> duration resolution for the drag-to-reschedule endpoint. |
| `_assignment_options` | 很重要 | Builds the room/instructor/time choice lists the web editor offers. |
| `_rss_mb`, `_default_package`, `_load_web_config`, `_configure_logging` | 很重要 | Process/startup plumbing, unrelated to each other. |

---

## `overrides.py` (CLI revision-file feature)

| Function | Verdict | Note |
|---|---|---|
| `load_overrides` | 很重要 | TOML parsing/validation for `edits`/`locks`/`unassign`. |
| `validate_override_context` | 很重要 | Term/source-version mismatch guard. |
| `render_override_template` | 很重要 | Generates the commented starter file plus the record-index reference map. |
| `apply_overrides` | 可合并, flagged | Reimplements field-replacement and Hybrid-physical-row special-casing from scratch instead of calling `Class.apply_edit`/`edit_targets` -- a third parallel implementation of "edit one field, know which rows follow." Not deleting it (it has its own `record=None`-means-every-row and lock semantics `apply_edit` doesn't), but a real candidate for a follow-up: rebuild it on top of `edit_targets`/`apply_edit` so there is one row-targeting rule instead of three (`_change`, `apply_edit`, and this). |
| `locks_for_section` | 很重要 | Solver-lock lookup by course id + record. |

---

## Summary of delete/merge actions worth actually doing

1. **Delete now** (dead in production, evidence-checked): `NormalClass.change_time`/`change_room`/`change_instructor`/`_change` and every subclass override, plus `Schedule.change_time`/`change_room`/`change_instructor`. Requires first repointing `initial_builder.py:56`'s one `change_instructor` call at `apply_edit` (or a direct `replace`).
2. **Delete after a test rewrite**: `_take_known_cross_list_pairs`, `_take_honors_pairs`, `_take_coreqs`, and the `_take_cross_listed` dispatcher in `schedule_model.py` -- confirmed reachable only through `infer_legacy_relationships=True`, which no production caller sets (only their own tests do). `_take_cross_list_column` is the one sibling to *keep*: `template_workspace.py` still sets `infer_marked_cross_lists=True` in production.
3. **Follow-up, not urgent**: rebuild `overrides.py`'s `apply_overrides` on `edit_targets`/`apply_edit` instead of its own third field-replacement implementation.
4. **Already-open, not re-litigated here**: `HybridClass.is_hybrid`'s section-prefix regex still gates ongoing validity, not just recognition (architectural inconsistency, no fix instructed yet); `add_placeholder_load_terms`'s primary-row-only credit weight (explicitly deferred).
