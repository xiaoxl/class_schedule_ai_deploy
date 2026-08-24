# 27S ver12 solve report

Solver input: `work/27S/runs/ver12/draft/starting.csv` (58 atomic classes, 80 rows)

Change baseline: `work/27S/runs/ver12/draft/starting.csv` (58 atomic classes, 80 rows)

Configuration version: `24c5d4bf0cf9`

Ran 5 independent attempt(s), each with a 45s CP-SAT budget. Selected attempt 3 by lowest worst instructor overload, then lowest solver objective, then lowest reported soft penalty.

## Selected result

- Solver status: feasible
- Solver objective: -875
- Best objective bound: -1315
- Solve time: 45.0249 seconds
- Candidate assignments: 5973
- Hard violations: 0
- Soft penalty: 215 (7 findings)
- Worst instructor overload: 6 credit hours
- Remaining placeholder identities: Staff, Staff 2

## Attempt comparison

| Attempt | Status | Objective | Bound | Seconds | Soft | Worst overload | Hard |
|---:|---|---:|---:|---:|---:|---:|---:|
| 1 | feasible | -815 | -1550 | 45.0135 | 210 | 6 | 0 |
| 2 | feasible | -790 | -1490 | 45.0205 | 295 | 6 | 0 |
| 3 | feasible | -875 | -1315 | 45.0249 | 215 | 6 | 0 |
| 4 | feasible | -760 | -1335 | 45.0191 | 220 | 6 | 0 |
| 5 | feasible | -795 | -1535 | 45.0139 | 205 | 6 | 0 |

## Before and after

| Metric | Before | After |
|---|---:|---:|
| Hard violations | 0 | 0 |
| Soft penalty | 375 | 215 |
| Soft findings | 7 | 7 |
| Worst overload | 1 | 6 |

## Teaching loads

| Instructor | Target | Before | After | Delta |
|---|---:|---:|---:|---:|
| Bain, Leslie M. | 15 | 15 | 15 | +0 |
| Ballard, Kasey L. | 12 | 13 | 13 | +0 |
| Cox, Allie M. | 15 | 16 | 16 | +0 |
| Growns, Landon C. | 15 | 11 | 17 | +6 |
| Jordan, Scott M. | 12 | 12 | 12 | +0 |
| Jordan, Susan M. | 15 | 14 | 21 | +7 |
| King, Jamie L. | 15 | 15 | 15 | +0 |
| Limperis, Thomas G. | 12 | 13 | 13 | +0 |
| Overduin, Matthew D. | 12 | 9 | 12 | +3 |
| Staff | n/a | 25 | 17 | -8 |
| Staff 2 | n/a | 4 | 6 | +2 |
| Staff 3 | n/a | 6 | 0 | -6 |
| Taylor, Teresa L. | 15 | 15 | 15 | +0 |
| Winn, Janet L. | 15 | 15 | 15 | +0 |
| Xiao, Xinli | 12 | 10 | 14 | +4 |
| Yousuf, Marium | 15 | 15 | 7 | -8 |

## Simplified changes from baseline

- **MATH 1914-001** room: `Corley 101` -> `Corley 102`
- **MATH 1914-003** time: `MWF 10:00am` -> `MWF 9:00am`
- **MATH 2914-003** instructor: `Yousuf, Marium` -> `Jordan, Susan M.`
- **MATH 2924-001** instructor: `Yousuf, Marium` -> `Xiao, Xinli`
- **MATH 2934-002** instructor: `Staff 2` -> `Staff`
- **MATH 2934-002** time: `R 11:00am` -> `R 8:00am`
- **MATH 4123-001** instructor: `Staff` -> `Limperis, Thomas G.`
- **MATH 4123-H01** instructor: `Staff` -> `Limperis, Thomas G.`
- **MATH 1003-002** time: `MWF 10:00am` -> `MWF 8:00am`
- **MATH 0903-001** instructor: `Staff` -> `King, Jamie L.`
- **MATH 0903-001** room: `Corley 104` -> `Corley 267`
- **MATH 1113-001** instructor: `Staff` -> `King, Jamie L.`
- **MATH 0803-004** instructor: `Staff 3` -> `Staff 2`
- **MATH 1003-004** instructor: `Staff 3` -> `Staff 2`
- **MATH 1003-006** instructor: `King, Jamie L.` -> `Growns, Landon C.`
- **MATH 1003-006** time: `MWF 9:00am` -> `MWF 10:00am`
- **MATH 1003-TC2** instructor: `King, Jamie L.` -> `Growns, Landon C.`
- **MATH 2703-002** instructor: `Limperis, Thomas G.` -> `Jordan, Susan M.`
- **MATH 2703-002** room: `Rothwell 206` -> `Corley 101`
- **MATH 2703-TC1** instructor: `Jordan, Susan M.` -> `Overduin, Matthew D.`
- **MATH 4971-001** time: `T 11:00am` -> `TR 8:00am`
- **MATH 4971-001** room: `Corley 101` -> `Rothwell 207`
- **STAT 2163-001** room: `Rothwell 221` -> `Corley 268`
- **MATH 1003-007** instructor: `Staff` -> `Jordan, Susan M.`
- **MATH 1003-007** time: `MWF 1:00pm` -> `MWF 12:00pm`
- **MATH 1003-007** room: `` -> `Corley 101`

## Remaining hard violations

- none

## Remaining soft findings

- [overload] (100) Jordan, Susan M.: 21 credit hours exceeds max_load 15
- [under_load] (90) Yousuf, Marium: 7 credit hours is under max_load 15
- [disliked_time] (5) MATH 1914-001: falls in a disliked time (Prefers no early classes)
- [disliked_time] (5) MATH 0803-001: falls in a disliked time (Prefers MWF only)
- [disliked_course] (5) MATH 0903-001: King, Jamie L. dislikes teaching MATH 0903
- [disliked_course] (5) MATH 1113-001: King, Jamie L. dislikes teaching MATH 1113
- [disliked_time] (5) MATH 1113-002: falls in a disliked time (Prefers MWF only)
