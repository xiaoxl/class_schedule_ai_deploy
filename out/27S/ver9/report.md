# 27S ver9 solve report

Solver input: `work/27S/ver9/draft/starting.csv` (58 atomic classes, 80 rows)

Change baseline: `work/27S/ver9/draft/starting.csv` (58 atomic classes, 80 rows)

Configuration version: `b23b6042112a`

Ran 5 independent attempt(s), each with a 45s CP-SAT budget. Selected attempt 1 by lowest worst instructor overload, then lowest solver objective, then lowest reported soft penalty.

## Selected result

- Solver status: feasible
- Solver objective: -635
- Best objective bound: -1315
- Solve time: 45.0122 seconds
- Candidate assignments: 5993
- Hard violations: 0
- Soft penalty: 30 (4 findings)
- Worst instructor overload: 2 credit hours
- Remaining placeholder identities: Staff, Staff 2

## Attempt comparison

| Attempt | Status | Objective | Bound | Seconds | Soft | Worst overload | Hard |
|---:|---|---:|---:|---:|---:|---:|---:|
| 1 | feasible | -635 | -1315 | 45.0122 | 30 | 2 | 0 |
| 2 | feasible | -705 | -1315 | 45.0084 | 110 | 3 | 0 |
| 3 | feasible | -745 | -1365 | 45.01 | 110 | 4 | 0 |
| 4 | feasible | -615 | -1305 | 45.0144 | 295 | 6 | 0 |
| 5 | feasible | -740 | -1315 | 45.0116 | 130 | 6 | 0 |

## Before and after

| Metric | Before | After |
|---|---:|---:|
| Hard violations | 0 | 0 |
| Soft penalty | 375 | 30 |
| Soft findings | 7 | 4 |
| Worst overload | 1 | 2 |

## Teaching loads

| Instructor | Target | Before | After | Delta |
|---|---:|---:|---:|---:|
| Bain, Leslie M. | 15 | 15 | 15 | +0 |
| Ballard, Kasey L. | 12 | 13 | 13 | +0 |
| Cox, Allie M. | 15 | 16 | 15 | -1 |
| Growns, Landon C. | 15 | 11 | 17 | +6 |
| Jordan, Scott M. | 12 | 12 | 12 | +0 |
| Jordan, Susan M. | 15 | 14 | 17 | +3 |
| King, Jamie L. | 15 | 15 | 15 | +0 |
| Limperis, Thomas G. | 12 | 13 | 14 | +1 |
| Overduin, Matthew D. | 12 | 9 | 12 | +3 |
| Staff | n/a | 25 | 13 | -12 |
| Staff 2 | n/a | 4 | 6 | +2 |
| Staff 3 | n/a | 6 | 0 | -6 |
| Taylor, Teresa L. | 15 | 15 | 15 | +0 |
| Winn, Janet L. | 15 | 15 | 15 | +0 |
| Xiao, Xinli | 12 | 10 | 14 | +4 |
| Yousuf, Marium | 15 | 15 | 15 | +0 |

## Changes from baseline

- **MATH 1914-001** instructor: `Cox, Allie M.` -> `Jordan, Susan M.`
- **MATH 2914-002** instructor: `Jordan, Susan M.` -> `Yousuf, Marium`
- **MATH 2914-003** room: `Corley 101` -> `Corley 102`
- **MATH 2924-001** instructor: `Yousuf, Marium` -> `Limperis, Thomas G.`
- **MATH 2934-001** instructor: `Staff` -> `Xiao, Xinli`
- **MATH 2934-001** time: `MWF 10:00am` -> `MWF 8:00am`
- **MATH 2934-002** instructor: `Staff 2` -> `Staff`
- **MATH 2934-002** room: `Corley 101` -> `Corley 268`
- **MATH 2934-002** room: `Corley 101` -> `Corley 269`
- **MATH 0903-001** instructor: `Staff` -> `Growns, Landon C.`
- **MATH 1113-001** instructor: `Staff` -> `Growns, Landon C.`
- **MATH 0803-004** instructor: `Staff 3` -> `Staff 2`
- **MATH 1003-004** instructor: `Staff 3` -> `Staff 2`
- **MATH 1003-006** instructor: `King, Jamie L.` -> `Ballard, Kasey L.`
- **MATH 1113-TC2** instructor: `Ballard, Kasey L.` -> `Cox, Allie M.`
- **MATH 2703-002** instructor: `Limperis, Thomas G.` -> `Jordan, Susan M.`
- **MATH 2703-002** room: `Rothwell 206` -> `Corley 101`
- **MATH 2703-TC1** instructor: `Jordan, Susan M.` -> `Overduin, Matthew D.`
- **MATH 4971-001** time: `T 11:00am` -> `TR 8:00am`
- **MATH 1003-007** instructor: `Staff` -> `Jordan, Susan M.`
- **MATH 1003-007** time: `MWF 1:00pm` -> `MWF 11:00am`
- **MATH 1003-007** room: `` -> `Corley 101`
- **STAT 2163-004** instructor: `Staff` -> `King, Jamie L.`
- **STAT 2163-004** room: `` -> `Corley 269`

## Remaining hard violations

- none

## Remaining soft findings

- [custom_rule] (10) MATH 2934-001: matches a custom dislike rule (weight 10)
- [custom_rule] (10) MATH 2934-001: matches a custom dislike rule (weight 10)
- [disliked_time] (5) MATH 0803-001: falls in a disliked time (Prefers MWF only)
- [disliked_time] (5) MATH 1113-002: falls in a disliked time (Prefers MWF only)
