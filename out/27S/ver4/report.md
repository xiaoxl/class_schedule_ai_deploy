# 27S ver4 solve report

Validated solver input: `work/27S/initial/initial.csv` (57 atomic classes, 79 rows)

Initial baseline: `work/27S/initial/initial.csv` (57 atomic classes, 79 rows)

Term changes snapshot: `inputs/27S/changes.toml`; cancelled-course validation passed

Configuration version: `a80bcdabebff`

Ran 3 independent attempt(s), each with a 20s CP-SAT budget. Selected attempt 1 by lowest worst instructor overload, then lowest solver objective, then lowest reported soft penalty.

## Selected result

- Solver status: feasible
- Solver objective: -1025
- Best objective bound: -2125
- Solve time: 20.0074 seconds
- Candidate assignments: 6094
- Hard violations: 0
- Soft penalty: 125 (7 findings)
- Worst instructor overload: 2 credit hours
- Remaining placeholder identities: Staff, Staff 2, Staff 3

## Attempt comparison

| Attempt | Status | Objective | Bound | Seconds | Soft | Worst overload | Hard |
|---:|---|---:|---:|---:|---:|---:|---:|
| 1 | feasible | -1025 | -2125 | 20.0074 | 125 | 2 | 0 |
| 2 | feasible | -1045 | -2125 | 20.0057 | 310 | 6 | 0 |
| 3 | feasible | -1045 | -2075 | 20.0082 | 415 | 6 | 0 |

## Before and after

| Metric | Before | After |
|---|---:|---:|
| Hard violations | 2 | 0 |
| Soft penalty | 520 | 125 |
| Soft findings | 10 | 7 |
| Worst overload | 1 | 2 |

## Teaching loads

| Instructor | Target | Before | After | Delta |
|---|---:|---:|---:|---:|
| Bain, Leslie M. | 15 | 15 | 15 | +0 |
| Ballard, Kasey L. | 12 | 13 | 12 | -1 |
| Cox, Allie M. | 15 | 16 | 9 | -7 |
| Growns, Landon C. | 15 | 11 | 17 | +6 |
| Jordan, Scott M. | 12 | 12 | 12 | +0 |
| Jordan, Susan M. | 15 | 14 | 15 | +1 |
| King, Jamie L. | 15 | 15 | 15 | +0 |
| Limperis, Thomas G. | 12 | 10 | 12 | +2 |
| Overduin, Matthew D. | 12 | 9 | 12 | +3 |
| Staff | n/a | 23 | 18 | -5 |
| Staff 2 | n/a | 6 | 6 | +0 |
| Staff 3 | n/a | 6 | 4 | -2 |
| Taylor, Teresa L. | 15 | 15 | 15 | +0 |
| Winn, Janet L. | 15 | 15 | 15 | +0 |
| Xiao, Xinli | 12 | 10 | 13 | +3 |
| Yousuf, Marium | 15 | 15 | 15 | +0 |

## Simplified changes from initial

- **MATH 1914-001** instructor: `Cox, Allie M.` -> `Jordan, Susan M.`
- **MATH 1914-001** time: `MWF 8:00am` -> `MWF 9:00am`
- **MATH 1914-003** instructor: `Ballard, Kasey L.` -> `Jordan, Susan M.`
- **MATH 1914-003** room: `Corley 102` -> `Corley 101`
- **MATH 1914-003** room: `Corley 268` -> `Corley 101`
- **MATH 2914-001** instructor: `Jordan, Susan M.` -> `Yousuf, Marium`
- **MATH 2914-001** room: `Corley 101` -> `Ross Pendergraft Library 220`
- **MATH 2914-001** room: `Corley 101` -> `Ross Pendergraft Library 332`
- **MATH 2914-002** instructor: `Jordan, Susan M.` -> `Yousuf, Marium`
- **MATH 2914-002** time: `MWF 1:00pm` -> `MWF 11:00am`
- **MATH 2914-003** instructor: `Yousuf, Marium` -> `Jordan, Susan M.`
- **MATH 2924-001** room: `Corley 102` -> `Corley 268`
- **MATH 2924-001** time: `R 1:00pm` -> `R 11:00am`
- **MATH 2924-002** instructor: `Yousuf, Marium` -> `Limperis, Thomas G.`
- **MATH 2924-002** time: `MWF 12:00pm` -> `MWF 1:00pm`
- **MATH 2924-003** time: `MWF 10:00am` -> `MWF 11:00am`
- **MATH 2934-001** instructor: `Staff` -> `Limperis, Thomas G.`
- **MATH 2934-002** instructor: `Staff` -> `Staff 3`
- **MATH 2934-002** room: `Corley 101` -> `Corley 269`
- **MATH 0903-001** instructor: `Staff 3` -> `Staff 2`
- **MATH 1113-001** instructor: `Staff 3` -> `Staff 2`
- **MATH 0803-004** instructor: `Staff 2` -> `Staff`
- **MATH 1003-004** instructor: `Staff 2` -> `Staff`
- **MATH 1113-006** room: `Corley 104` -> `Corley 102`
- **MATH 1113-TC2** instructor: `Ballard, Kasey L.` -> `Growns, Landon C.`
- **MATH 1203-TC1** instructor: `Bain, Leslie M.` -> `Growns, Landon C.`
- **MATH 2223-TC1** instructor: `Cox, Allie M.` -> `Ballard, Kasey L.`
- **MATH 2703-001** instructor: `Jordan, Susan M.` -> `Ballard, Kasey L.`
- **MATH 2703-001** room: `Corley 101` -> `Rothwell 306`
- **MATH 2703-002** instructor: `Limperis, Thomas G.` -> `Jordan, Susan M.`
- **MATH 2703-002** time: `TR 11:00am` -> `TR 8:00am`
- **MATH 2703-002** room: `Rothwell 206` -> `Corley 101`
- **MATH 2703-TC1** instructor: `Jordan, Susan M.` -> `Overduin, Matthew D.`
- **MATH 3033-001** time: `TR 11:00am` -> `TR 1:00pm`
- **MATH 3243-002** instructor: `Limperis, Thomas G.` -> `Xiao, Xinli`
- **MATH 3243-002** time: `MWF 9:00am` -> `MWF 8:00am`
- **STAT 2163-004** instructor: `Staff` -> `Bain, Leslie M.`
- **STAT 2163-004** room: `` -> `Corley 104`

## Remaining hard violations

- none

## Remaining soft findings

- [overload] (10) Growns, Landon C.: 17 credit hours exceeds max_load 15
- [under_load] (90) Cox, Allie M.: 9 credit hours is under max_load 15
- [disliked_time] (5) MATH 0803-001: falls in a disliked time (Prefers MWF only)
- [disliked_time] (5) MATH 0903-002: falls in a disliked time (No 8am classes)
- [disliked_time] (5) MATH 1113-002: falls in a disliked time (Prefers MWF only)
- [disliked_time] (5) MATH 1113-002: falls in a disliked time (No 8am classes)
- [disliked_time] (5) MATH 2703-002: falls in a disliked time (No 8am classes)
