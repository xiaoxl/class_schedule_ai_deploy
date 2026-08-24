# 27S ver23 solve report

Solver input: `out/27S/ver22/27S_ver22.csv` (57 atomic classes, 79 rows)

Change baseline: `work/27S/runs/ver17/draft/starting.csv` (58 atomic classes, 80 rows)

Term changes: `inputs/27S/changes.toml`; solve-time cancel guard removed MATH 4993-001

Configuration version: `f1d7cf69b459`

Ran 3 independent attempt(s), each with a 20s CP-SAT budget. Selected attempt 1 by lowest worst instructor overload, then lowest solver objective, then lowest reported soft penalty.

## Selected result

- Solver status: feasible
- Solver objective: -1160
- Best objective bound: -1640
- Solve time: 20.01 seconds
- Candidate assignments: 5630
- Hard violations: 0
- Soft penalty: 30 (6 findings)
- Worst instructor overload: 2 credit hours
- Remaining placeholder identities: Staff, Staff 2

## Attempt comparison

| Attempt | Status | Objective | Bound | Seconds | Soft | Worst overload | Hard |
|---:|---|---:|---:|---:|---:|---:|---:|
| 1 | feasible | -1160 | -1640 | 20.01 | 30 | 2 | 0 |
| 2 | feasible | -1160 | -1565 | 20.0142 | 30 | 2 | 0 |
| 3 | feasible | -1090 | -1420 | 20.0061 | 120 | 2 | 0 |

## Before and after

| Metric | Before | After |
|---|---:|---:|
| Hard violations | 2 | 0 |
| Soft penalty | 385 | 30 |
| Soft findings | 9 | 6 |
| Worst overload | 1 | 2 |

## Teaching loads

| Instructor | Target | Before | After | Delta |
|---|---:|---:|---:|---:|
| Bain, Leslie M. | 15 | 15 | 15 | +0 |
| Ballard, Kasey L. | 12 | 13 | 12 | -1 |
| Cox, Allie M. | 15 | 16 | 15 | -1 |
| Growns, Landon C. | 15 | 11 | 17 | +6 |
| Jordan, Scott M. | 12 | 12 | 12 | +0 |
| Jordan, Susan M. | 15 | 14 | 16 | +2 |
| King, Jamie L. | 15 | 15 | 15 | +0 |
| Limperis, Thomas G. | 12 | 13 | 14 | +1 |
| Overduin, Matthew D. | 12 | 9 | 12 | +3 |
| Staff | n/a | 23 | 15 | -8 |
| Staff 2 | n/a | 6 | 4 | -2 |
| Staff 3 | n/a | 6 | 0 | -6 |
| Taylor, Teresa L. | 15 | 15 | 15 | +0 |
| Winn, Janet L. | 15 | 15 | 15 | +0 |
| Xiao, Xinli | 12 | 10 | 13 | +3 |
| Yousuf, Marium | 15 | 15 | 15 | +0 |

## Simplified changes from baseline

- **MATH 1914-001** instructor: `Cox, Allie M.` -> `Jordan, Susan M.`
- **MATH 1914-003** instructor: `Ballard, Kasey L.` -> `Jordan, Susan M.`
- **MATH 1914-003** time: `R 9:30am` -> `T 8:00am`
- **MATH 1914-003** room: `Corley 102` -> `Corley 101`
- **MATH 1914-003** time: `MWF 10:00am` -> `MWF 11:00am`
- **MATH 1914-003** room: `Corley 268` -> `Corley 101`
- **MATH 2924-002** time: `MWF 12:00pm` -> `MWF 8:00am`
- **MATH 2934-001** instructor: `Staff` -> `Staff 2`
- **MATH 2934-002** instructor: `Staff` -> `Limperis, Thomas G.`
- **MATH 2934-002** room: `Corley 101` -> `Corley 269`
- **MATH 4123-001** instructor: `Staff` -> `Limperis, Thomas G.`
- **MATH 4123-001** time: `MWF 8:00am` -> `MWF 1:00pm`
- **MATH 4123-H01** instructor: `Staff` -> `Limperis, Thomas G.`
- **MATH 4123-H01** time: `MWF 8:00am` -> `MWF 1:00pm`
- **MATH 0903-001** instructor: `Staff 3` -> `Growns, Landon C.`
- **MATH 1113-001** instructor: `Staff 3` -> `Growns, Landon C.`
- **MATH 0803-004** instructor: `Staff 2` -> `Staff`
- **MATH 1003-004** instructor: `Staff 2` -> `Staff`
- **MATH 1113-006** room: `Corley 104` -> `Corley 102`
- **MATH 1203-TC1** instructor: `Bain, Leslie M.` -> `Cox, Allie M.`
- **MATH 2703-001** instructor: `Jordan, Susan M.` -> `Overduin, Matthew D.`
- **MATH 2703-002** time: `TR 11:00am` -> `TR 1:00pm`
- **MATH 2703-002** room: `Rothwell 206` -> `Corley 268`
- **MATH 2703-TC1** instructor: `Jordan, Susan M.` -> `Ballard, Kasey L.`
- **MATH 3243-002** instructor: `Limperis, Thomas G.` -> `Xiao, Xinli`
- **MATH 3243-002** time: `MWF 9:00am` -> `MWF 8:00am`
- **MATH 4993-001** status: `present` -> `removed`
- **STAT 2163-004** instructor: `Staff` -> `Bain, Leslie M.`
- **STAT 2163-004** room: `` -> `Corley 104`

## Remaining hard violations

- none

## Remaining soft findings

- [disliked_time] (5) MATH 1914-001: falls in a disliked time (No 8am classes)
- [disliked_time] (5) MATH 1914-003: falls in a disliked time (No 8am classes)
- [disliked_time] (5) MATH 0803-001: falls in a disliked time (Prefers MWF only)
- [disliked_time] (5) MATH 0903-002: falls in a disliked time (No 8am classes)
- [disliked_time] (5) MATH 1113-002: falls in a disliked time (Prefers MWF only)
- [disliked_time] (5) MATH 1113-002: falls in a disliked time (No 8am classes)
