# 27S ver8 solve report

Solver input: `out/27S/ver7/27S_ver7.csv` (58 atomic classes, 80 rows)

Change baseline: `work/27S/ver8/draft/starting.csv` (58 atomic classes, 80 rows)

Configuration version: `d4374d61d4a1`

Ran 5 independent attempt(s), each with a 45s CP-SAT budget. Selected attempt 1 by lowest worst instructor overload, then lowest solver objective, then lowest reported soft penalty.

## Selected result

- Solver status: feasible
- Solver objective: -830
- Best objective bound: -1330
- Solve time: 45.0111 seconds
- Candidate assignments: 5581
- Hard violations: 0
- Soft penalty: 40 (5 findings)
- Worst instructor overload: 3 credit hours
- Remaining placeholder identities: Staff, Staff 2

## Attempt comparison

| Attempt | Status | Objective | Bound | Seconds | Soft | Worst overload | Hard |
|---:|---|---:|---:|---:|---:|---:|---:|
| 1 | feasible | -830 | -1330 | 45.0111 | 40 | 3 | 0 |
| 2 | feasible | -830 | -1340 | 45.0069 | 40 | 3 | 0 |
| 3 | feasible | -830 | -1405 | 45.0163 | 40 | 3 | 0 |
| 4 | feasible | -830 | -1410 | 45.0077 | 40 | 3 | 0 |
| 5 | feasible | -830 | -1185 | 45.0167 | 40 | 3 | 0 |

## Before and after

| Metric | Before | After |
|---|---:|---:|
| Hard violations | 0 | 0 |
| Soft penalty | 375 | 40 |
| Soft findings | 7 | 5 |
| Worst overload | 1 | 3 |

## Teaching loads

| Instructor | Target | Before | After | Delta |
|---|---:|---:|---:|---:|
| Bain, Leslie M. | 15 | 15 | 15 | +0 |
| Ballard, Kasey L. | 12 | 13 | 12 | -1 |
| Cox, Allie M. | 15 | 16 | 15 | -1 |
| Growns, Landon C. | 15 | 11 | 18 | +7 |
| Jordan, Scott M. | 12 | 12 | 12 | +0 |
| Jordan, Susan M. | 15 | 14 | 15 | +1 |
| King, Jamie L. | 15 | 15 | 15 | +0 |
| Limperis, Thomas G. | 12 | 13 | 14 | +1 |
| Overduin, Matthew D. | 12 | 9 | 12 | +3 |
| Staff | n/a | 25 | 13 | -12 |
| Staff 2 | n/a | 6 | 6 | +0 |
| Staff 3 | n/a | 4 | 0 | -4 |
| Taylor, Teresa L. | 15 | 15 | 15 | +0 |
| Winn, Janet L. | 15 | 15 | 15 | +0 |
| Xiao, Xinli | 12 | 10 | 14 | +4 |
| Yousuf, Marium | 15 | 15 | 17 | +2 |

## Changes from baseline

- **MATH 1914-001** instructor: `Cox, Allie M.` -> `Jordan, Susan M.`
- **MATH 1914-003** instructor: `Ballard, Kasey L.` -> `Growns, Landon C.`
- **MATH 1914-003** room: `Corley 268` -> `Corley 103`
- **MATH 2924-002** instructor: `Yousuf, Marium` -> `Limperis, Thomas G.`
- **MATH 2934-001** instructor: `Staff` -> `Xiao, Xinli`
- **MATH 2934-001** room: `Rothwell 207` -> `Corley 268`
- **MATH 2934-002** instructor: `Staff 3` -> `Staff`
- **MATH 1003-002** time: `MWF 10:00am` -> `MWF 8:00am`
- **MATH 0903-001** instructor: `Staff` -> `Yousuf, Marium`
- **MATH 1113-001** instructor: `Staff` -> `Yousuf, Marium`
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
- [custom_rule] (10) MATH 2934-001: matches a custom dislike rule (weight 10)
- [custom_rule] (10) MATH 2934-001: matches a custom dislike rule (weight 10)
- [disliked_time] (5) MATH 0803-001: falls in a disliked time (Prefers MWF only)
- [disliked_time] (5) MATH 1113-002: falls in a disliked time (Prefers MWF only)
