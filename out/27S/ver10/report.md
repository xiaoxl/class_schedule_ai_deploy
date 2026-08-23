# 27S ver10 solve report

Solver input: `out/27S/starting.csv` (58 atomic classes, 80 rows)

Change baseline: `out/27S/starting.csv` (58 atomic classes, 80 rows)

Configuration version: `e7a325be64cb`

Ran 5 independent attempt(s), each with a 45s CP-SAT budget. Selected attempt 2 by lowest worst instructor overload, then lowest solver objective, then lowest reported soft penalty.

## Selected result

- Solver status: feasible
- Solver objective: -915
- Best objective bound: -1480
- Solve time: 45.0088 seconds
- Candidate assignments: 5973
- Hard violations: 0
- Soft penalty: 10 (2 findings)
- Worst instructor overload: 2 credit hours
- Remaining placeholder identities: Staff, Staff 2

## Attempt comparison

| Attempt | Status | Objective | Bound | Seconds | Soft | Worst overload | Hard |
|---:|---|---:|---:|---:|---:|---:|---:|
| 1 | feasible | -805 | -1480 | 45.0218 | 195 | 6 | 0 |
| 2 | feasible | -915 | -1480 | 45.0088 | 10 | 2 | 0 |
| 3 | feasible | -640 | -1485 | 45.0118 | 300 | 6 | 0 |
| 4 | feasible | -755 | -1495 | 45.1918 | 100 | 2 | 0 |
| 5 | feasible | -865 | -1485 | 45.0115 | 210 | 6 | 0 |

## Before and after

| Metric | Before | After |
|---|---:|---:|
| Hard violations | 0 | 0 |
| Soft penalty | 375 | 10 |
| Soft findings | 7 | 2 |
| Worst overload | 1 | 2 |

## Teaching loads

| Instructor | Target | Before | After | Delta |
|---|---:|---:|---:|---:|
| Bain, Leslie M. | 15 | 15 | 15 | +0 |
| Ballard, Kasey L. | 12 | 13 | 13 | +0 |
| Cox, Allie M. | 15 | 16 | 15 | -1 |
| Growns, Landon C. | 15 | 11 | 17 | +6 |
| Jordan, Scott M. | 12 | 12 | 12 | +0 |
| Jordan, Susan M. | 15 | 14 | 15 | +1 |
| King, Jamie L. | 15 | 15 | 15 | +0 |
| Limperis, Thomas G. | 12 | 13 | 13 | +0 |
| Overduin, Matthew D. | 12 | 9 | 12 | +3 |
| Staff | n/a | 23 | 17 | -6 |
| Staff 2 | n/a | 6 | 6 | +0 |
| Staff 3 | n/a | 6 | 0 | -6 |
| Taylor, Teresa L. | 15 | 15 | 15 | +0 |
| Winn, Janet L. | 15 | 15 | 15 | +0 |
| Xiao, Xinli | 12 | 10 | 13 | +3 |
| Yousuf, Marium | 15 | 15 | 15 | +0 |

## Changes from baseline

- **MATH 1914-001** instructor: `Cox, Allie M.` -> `Jordan, Susan M.`
- **MATH 2934-002** room: `Corley 101` -> `Corley 267`
- **MATH 4123-001** instructor: `Staff` -> `Limperis, Thomas G.`
- **MATH 4123-H01** instructor: `Staff` -> `Limperis, Thomas G.`
- **MATH 0903-001** instructor: `Staff 2` -> `Growns, Landon C.`
- **MATH 1113-001** instructor: `Staff 2` -> `Growns, Landon C.`
- **MATH 0803-004** instructor: `Staff 3` -> `Staff 2`
- **MATH 1003-004** instructor: `Staff 3` -> `Staff 2`
- **MATH 1203-TC1** instructor: `Bain, Leslie M.` -> `Cox, Allie M.`
- **MATH 2703-001** instructor: `Jordan, Susan M.` -> `Overduin, Matthew D.`
- **MATH 2703-002** instructor: `Limperis, Thomas G.` -> `Jordan, Susan M.`
- **MATH 2703-002** room: `Rothwell 206` -> `Corley 101`
- **MATH 2703-TC1** instructor: `Jordan, Susan M.` -> `Limperis, Thomas G.`
- **MATH 3243-002** instructor: `Limperis, Thomas G.` -> `Xiao, Xinli`
- **MATH 3243-002** time: `MWF 9:00am` -> `MWF 2:00pm`
- **MATH 4971-001** time: `T 11:00am` -> `TR 8:00am`
- **STAT 2163-004** instructor: `Staff` -> `Bain, Leslie M.`
- **STAT 2163-004** room: `` -> `Corley 104`

## Remaining hard violations

- none

## Remaining soft findings

- [disliked_time] (5) MATH 0803-001: falls in a disliked time (Prefers MWF only)
- [disliked_time] (5) MATH 1113-002: falls in a disliked time (Prefers MWF only)
