# Scheduling Rules

## Recognition and inference

Ordinary schedule loading is deterministic. `courses.toml` is authoritative
for Coreq and CrossListing relationships; when a relationship is absent those
rows remain normal classes. Four-credit and Hybrid classes retain intrinsic
recognition:

- two records with the same course/section and four credits form a
  `FourCreditClass`;
- an `Fxx` or `Mxx` section is a `HybridClass`; its two records have exactly
  the same section name, with one physical row and one online/arranged row.

Template inference is a separate operation. It emits explicit Coreq defaults,
honors and MATH 5173/STAT 4173 cross-listings only when their assignments are
shared, and every N-member group carrying the same nonblank `Cross-List`
marker. The generated seven-file package is reloaded using only the emitted
configuration before it is accepted.

Relationship IDs are not authored. The internal stable key is derived from
the relationship kind plus its sorted canonical members. Legacy `id` and
`synced_fields` input remain readable during migration, but newly generated
configuration writes `unsynced`.

## Atomic classes and validation

Every atomic class exposes `validate() -> bool` and
`validation_report() -> tuple[str, ...]`. The report is authoritative and the
boolean is its wrapper. Row-count and business rules live in the concrete
class validation implementation; there is no separate structural validation
API. A valid `Section` is still required for construction, and an unusable row
count remains constructor-fatal. Other business-invalid states remain editable
and are reported as hard findings.

- `NormalClass`: exactly one record.
- `FourCreditClass`: exactly two records for the same four-credit section;
  MWF plus T or R, same instructor, T/R duration exactly 80 minutes, and start
  times at most 90 minutes apart. Rooms may differ.
- `HybridClass`: exactly two records with the same `Fxx` or `Mxx` section and
  instructor. One has a physical time and room; the other has neither time nor
  location.
- `CoreqClass`: exactly two configured members with the same section number
  and instructor. Both may be online. Physical meetings are either MWF
  back-to-back with a 0–15 minute gap in the same room, or a strict MWF + TR
  five-day pair whose starts differ by at most 30 minutes; the latter rooms
  may differ.
- `CrossListingClass`: at least two configured members. Members do not
  conflict with each other. The class credit is the maximum member credit,
  and every distinct instructor appearing in the class receives that full
  credit once. All of instructor/room/time are synchronized by default;
  `unsynced = ["room"]`, for example, permits only rooms to diverge. Synced
  edits update every member.

Catalog credits are authoritative when present. If omitted, credits are
inferred from the final numeric digit of the course number. `teaching_loads()`
does not contain another credit rule; it aggregates each class's
`credit_hours`.

## Schedule evaluation and output

`Schedule.evaluate(EvaluationContext(...))` is the thin public entry point;
the pure `evaluate_schedule()` function remains the implementation shared by
CLI, solver attempts, reports, and the web API. Structured `RecordReference`
values locate findings within that same response's Schedule and are never
persisted identifiers.

Hard checks include atomic-class validation, instructor/room overlap,
configured meeting patterns and constraints, load caps, dynamic-position
contract caps, and allowed New Instructor/New Professor counts. Qualification
is not currently hard: the solver deliberately preserves a section's existing
instructor even when that course is absent from `persons.toml`.

All three current-view downloads remain available even when findings exist.
Instructor and location workbooks keep conflicting meetings visible, include
an `Issues` worksheet, mark referenced hard findings red, and mark referenced
soft findings yellow. The web issue panel displays the complete finding list
and uses structured references rather than parsing message text.
