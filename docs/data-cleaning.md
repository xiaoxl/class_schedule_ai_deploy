# Data Cleaning

The input boundary accepts CSV and XLSX files. Column aliases are normalized before rows become `Section` objects and atomic classes.

Every row needs subject, course number, and section. Course numbers remain text so leading zeroes survive. Subjects are uppercase. Physical meetings require a valid time and duration; `ONLINE`, `TBA`, and blank times are non-physical.

Legacy instructor values `Staff` and `Staff N` are accepted at input and immediately converted to `new_instructor` and `new_instructor N`. All new output uses the canonical names.

```powershell
uv run class-schedule import-template 27S inputs/27S/source.xlsx
```

Template import validates and normalizes the table, installs it as the package's sole CSV/XLSX file, and rebuilds the working views transactionally. Rejected rows include their source location and reason. If validation or rebuilding fails, neither the package template nor its existing working views are changed.

Cleaning follows these rules:

- Never invent missing course identity fields.
- Preserve valid source values and normalize only documented aliases.
- Reject malformed physical meeting data before solving.
- Group through the domain model, not spreadsheet row position.
- Count load by atomic class, not flattened rows.

The import already publishes the reconciled working schedule. Run `initial <configuration>` only when a template was placed into the configuration directory outside the importer and its working views need to be rebuilt. Extra offerings are removed, missing offerings are generated, unknown instructors become a qualifying dynamic position, and the generated audit is written to `reconciliation.toml`.
