# Data Cleaning

The input boundary accepts CSV and XLSX files. Column aliases are normalized before rows become `Section` objects and atomic classes.

Every row needs subject, course number, and section. Course numbers remain text so leading zeroes survive. Subjects are uppercase. Physical meetings require a valid time and duration; `ONLINE`, `TBA`, and blank times are non-physical.

Legacy instructor values `Staff` and `Staff N` are accepted at input and immediately converted to `new_instructor` and `new_instructor N`. All new output uses the canonical names.

```powershell
uv run class-schedule --config config initialize 27S inputs/27S/source.xlsx
```

Initialization writes a cleaned, auditable working bundle. Rejected rows include their source location and reason. Instructor and room workbooks created here show the same pre-change draft; they are not solver output.

Cleaning follows these rules:

- Never invent missing course identity fields.
- Preserve valid source values and normalize only documented aliases.
- Reject malformed physical meeting data before solving.
- Group through the domain model, not spreadsheet row position.
- Count load by atomic class, not flattened rows.

Run `initial` afterward to reconcile the cleaned template against `courses.toml`. Extra offerings are removed, missing offerings are generated, unknown instructors become New Instructor, and the generated audit is written to `reconciliation.toml`.
