# 27S ver3 solve report

Input: `out/27S/starting.csv` (59 atomic classes, 80 rows)

Configuration version: `805b4de3f20e`

Ran 5 independent attempt(s), each with a 45s CP-SAT budget. Selected attempt 5 by lowest worst instructor overload, then lowest reported soft penalty, then lowest solver objective.

## Selected result

- Solver status: feasible
- Solver objective: -565
- Best objective bound: -1055
- Solve time: 45.0112 seconds
- Candidate assignments: 5619
- Hard violations: 0
- Soft penalty: 140 (6 findings)
- Worst instructor overload: 3 credit hours
- Remaining placeholder identities: Staff, Staff 2

## Attempt comparison

| Attempt | Status | Objective | Bound | Seconds | Soft | Worst overload | Hard |
|---:|---|---:|---:|---:|---:|---:|---:|
| 1 | feasible | -645 | -1205 | 45.0127 | 210 | 6 | 0 |
| 2 | feasible | -520 | -1205 | 45.0115 | 200 | 3 | 0 |
| 3 | feasible | -610 | -1045 | 45.0151 | 230 | 6 | 0 |
| 4 | feasible | -570 | -1285 | 45.0088 | 295 | 6 | 0 |
| 5 | feasible | -565 | -1055 | 45.0112 | 140 | 3 | 0 |

## Before and after

| Metric | Before | After |
|---|---:|---:|
| Hard violations | 0 | 0 |
| Soft penalty | 575 | 140 |
| Soft findings | 9 | 6 |
| Worst overload | 5 | 3 |

## Teaching loads

| Instructor | Target | Before | After | Delta |
|---|---:|---:|---:|---:|
| Bain, Leslie M. | 15 | 15 | 15 | +0 |
| Ballard, Kasey L. | 12 | 13 | 12 | -1 |
| Cox, Allie M. | 15 | 16 | 15 | -1 |
| Growns, Landon C. | 15 | 11 | 18 | +7 |
| Jordan, Scott M. | 12 | 15 | 15 | +0 |
| Jordan, Susan M. | 15 | 14 | 15 | +1 |
| King, Jamie L. | 15 | 15 | 15 | +0 |
| Limperis, Thomas G. | 12 | 17 | 14 | -3 |
| Overduin, Matthew D. | 12 | 9 | 12 | +3 |
| Staff | n/a | 23 | 13 | -10 |
| Staff 2 | n/a | 6 | 6 | +0 |
| Taylor, Teresa L. | 15 | 15 | 15 | +0 |
| Winn, Janet L. | 15 | 15 | 15 | +0 |
| Xiao, Xinli | 12 | 10 | 14 | +4 |
| Yousuf, Marium | 15 | 17 | 17 | +0 |

## Changes from input

- **MATH 1914-001** instructor: `Cox, Allie M.` -> `Jordan, Susan M.`
- **MATH 1914-003** instructor: `Ballard, Kasey L.` -> `Growns, Landon C.`
- **MATH 1914-003** room: `Corley 268` -> `Corley 103`
- **MATH 2934-001** instructor: `Staff` -> `Xiao, Xinli`
- **MATH 2934-001** room: `Rothwell 207` -> `Corley 268`
- **MATH 1003-002** time: `MWF 10:00am` -> `MWF 8:00am`
- **MATH 1113-001** room: `Corley 104` -> `Corley 268`
- **MATH 1003-005** instructor: `Winn, Janet L.` -> `Growns, Landon C.`
- **MATH 1003-005** time: `MWF 10:00am` -> `MWF 11:00am`
- **MATH 1203-TC1** instructor: `Bain, Leslie M.` -> `Cox, Allie M.`
- **MATH 2223-003** room: `Corley 103` -> `Corley 104`
- **MATH 2703-002** instructor: `Limperis, Thomas G.` -> `Overduin, Matthew D.`
- **MATH 2703-TC1** instructor: `Jordan, Susan M.` -> `Ballard, Kasey L.`
- **MATH 3243-001** time: `MWF 10:00am` -> `MWF 1:00pm`
- **MATH 1003-007** instructor: `Staff` -> `Winn, Janet L.`
- **MATH 1003-007** room: `` -> `Rothwell 306`
- **STAT 2163-004** instructor: `Staff` -> `Bain, Leslie M.`
- **STAT 2163-004** room: `` -> `Corley 104`

## Remaining hard violations

- none

## Remaining soft findings

- [overload] (10) Growns, Landon C.: 18 credit hours exceeds max_load 15
- [overload] (100) Jordan, Scott M.: 15 credit hours exceeds max_load 12
- [custom_rule] (10) MATH 2934-001: matches a custom dislike rule (weight 10)
- [custom_rule] (10) MATH 2934-001: matches a custom dislike rule (weight 10)
- [disliked_time] (5) MATH 0803-001: falls in a disliked time (Prefers MWF only)
- [disliked_time] (5) MATH 1113-002: falls in a disliked time (Prefers MWF only)
