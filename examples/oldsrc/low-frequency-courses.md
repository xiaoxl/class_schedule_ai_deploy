# Course numbers not in Course_Catalog.csv

These six course numbers show up in someone's `26S.md`/`26F.md` entry but
have no row in
`examples/Course Information by Department - Dashboard - Course_Catalog.csv`.
That catalog file is a snapshot of a handful of recent terms, not a full
history -- confirmed (2026-08-20) that these are real courses offered
once every few semesters, not typos or retired numbers. Recorded here so
future passes over the preference docs don't re-flag them as unmapped.

Titles confirmed 2026-08-20 are listed where known; the rest are still
unconfirmed -- guessing would just be a second layer of unverified data
on top of the first.

| Course | Title | Also called | Mentioned by | Where |
|---|---|---|---|---|
| MATH 3203 | Intro to Analysis | analysis, real analysis | Overduin, Limperis, Myers | 26S "able to teach" / preferred lists |
| MATH 4123 | Mathematical Modeling | modeling | Limperis, Myers | 26S "able to teach" / preferred lists |
| MATH 4033 | Abstract Algebra | | Overduin | 26S "able to teach" list (also present in Xiao's `persons.toml` entry) |
| STAT 3183 | *unconfirmed* | | Scott Jordan | 26S and 26F, both "able to teach" and preferred lists |
| STAT 4173 / STAT 5173 | *unconfirmed* | | Scott Jordan | 26S and 26F "able to teach" lists -- catalog has 4113/5113 instead, which `persons.toml` also uses for him; both number pairs are now in his course list side by side, not confirmed to be the same course |

Two more, not originally in this list but confirmed the same day and
worth recording here since they're not in the catalog snapshot either:

| Course | Title | Also called | Notes |
|---|---|---|---|
| STAT 3113 | Regression | regression | Already used in Xiao's and (as of 2026-08-20) Scott Jordan's `persons.toml` entries |
| MATH 2703 | Discrete Mathematics | discrete math | Already in the catalog snapshot under this exact title -- listed here only because it also showed up as an unqualified "discrete" mention worth cross-referencing |
| MATH 4273 | Complex Variables | complex analysis | Already in the catalog snapshot. Overduin's 26S "MATH 4723" was a typo for this (confirmed 2026-08-20) -- not a distinct low-frequency course, no separate entry needed. |
| MATH 4971 | Mathematics Senior Seminar | seminar | Already in the catalog snapshot; "seminar" is a newly-confirmed alias |
| MATH 2914 / 2924 / 2934 | Calculus I / II / III | cal 1 / cal 2 / cal 3 | Already in the catalog snapshot; recorded here only to confirm the "cal N" shorthand used throughout both preference docs |
