# 27S ver4 solve report

Input: `out/27S/ver3/27S_ver3.csv` (59 atomic classes, 80 rows)

Configuration version: `b23b6042112a`

Ran 5 independent attempt(s), each with a 45s CP-SAT budget. Selected attempt 2 by lowest worst instructor overload, then lowest solver objective, then lowest reported soft penalty.

## Selected result

- Solver status: feasible
- Solver objective: -730
- Best objective bound: -1245
- Solve time: 45.0116 seconds
- Candidate assignments: 5519
- Hard violations: 0
- Soft penalty: 140 (6 findings)
- Worst instructor overload: 3 credit hours
- Remaining placeholder identities: Staff, Staff 2

## Attempt comparison

| Attempt | Status | Objective | Bound | Seconds | Soft | Worst overload | Hard |
|---:|---|---:|---:|---:|---:|---:|---:|
| 1 | feasible | -780 | -1075 | 45.0115 | 230 | 6 | 0 |
| 2 | feasible | -730 | -1245 | 45.0116 | 140 | 3 | 0 |
| 3 | feasible | -755 | -1245 | 45.0091 | 230 | 6 | 0 |
| 4 | feasible | -780 | -1080 | 45.0115 | 230 | 6 | 0 |
| 5 | feasible | -750 | -1080 | 45.0106 | 230 | 6 | 0 |

## Before and after

| Metric | Before | After |
|---|---:|---:|
| Hard violations | 0 | 0 |
| Soft penalty | 140 | 140 |
| Soft findings | 6 | 6 |
| Worst overload | 3 | 3 |

## Teaching loads

| Instructor | Target | Before | After | Delta |
|---|---:|---:|---:|---:|
| Bain, Leslie M. | 15 | 15 | 15 | +0 |
| Ballard, Kasey L. | 12 | 12 | 12 | +0 |
| Cox, Allie M. | 15 | 15 | 15 | +0 |
| Growns, Landon C. | 15 | 18 | 18 | +0 |
| Jordan, Scott M. | 12 | 15 | 15 | +0 |
| Jordan, Susan M. | 15 | 15 | 15 | +0 |
| King, Jamie L. | 15 | 15 | 15 | +0 |
| Limperis, Thomas G. | 12 | 14 | 14 | +0 |
| Overduin, Matthew D. | 12 | 12 | 12 | +0 |
| Staff | n/a | 13 | 13 | +0 |
| Staff 2 | n/a | 6 | 6 | +0 |
| Taylor, Teresa L. | 15 | 15 | 15 | +0 |
| Winn, Janet L. | 15 | 15 | 15 | +0 |
| Xiao, Xinli | 12 | 14 | 14 | +0 |
| Yousuf, Marium | 15 | 17 | 17 | +0 |

## Changes from input

- none

## Remaining hard violations

- none

## Remaining soft findings

- [overload] (10) Growns, Landon C.: 18 credit hours exceeds max_load 15
- [overload] (100) Jordan, Scott M.: 15 credit hours exceeds max_load 12
- [custom_rule] (10) MATH 2934-001: matches a custom dislike rule (weight 10)
- [custom_rule] (10) MATH 2934-001: matches a custom dislike rule (weight 10)
- [disliked_time] (5) MATH 0803-001: falls in a disliked time (Prefers MWF only)
- [disliked_time] (5) MATH 1113-002: falls in a disliked time (Prefers MWF only)
