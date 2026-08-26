# 27S ver17 solve report

Validated solver input: `work/27S/initial-reconciled/initial.csv` (57 atomic classes, 79 rows)

Initial baseline: `work/27S/initial-reconciled/initial.csv` (57 atomic classes, 79 rows)

Reconciliation snapshot: `work/27S/initial-reconciled/reconciliation.toml`

Configuration version: `a2a787977c32`

Ran 1 independent attempt(s), each with a 45s CP-SAT budget and 8 search worker(s). Selected attempt 1 by lowest worst instructor overload, then lowest solver objective, then lowest reported soft penalty.

## Selected result

- Solver status: optimal
- Solver objective: -1175
- Best objective bound: -1175
- Solve time: 15.6665 seconds
- Candidate assignments: 12826
- CP-SAT search workers: 8
- Hard violations: 0
- Soft penalty: 10 (2 findings)
- Worst instructor overload: 0 credit hours
- Remaining placeholder identities: new_instructor

## Attempt comparison

| Attempt | Status | Objective | Bound | Seconds | Soft | Worst overload | Hard |
|---:|---|---:|---:|---:|---:|---:|---:|
| 1 | optimal | -1175 | -1175 | 15.6665 | 10 | 0 | 0 |

## Before and after

| Metric | Before | After |
|---|---:|---:|
| Hard violations | 18 | 0 |
| Soft penalty | 850 | 10 |
| Soft findings | 10 | 2 |
| Worst overload | 0 | 0 |

## Teaching loads

| Instructor | Target | Before | After | Delta |
|---|---:|---:|---:|---:|
| Bain, Leslie M. | 15 | 15 | 15 | +0 |
| Ballard, Kasey L. | 12 | 13 | 13 | +0 |
| Cox, Allie M. | 15 | 16 | 15 | -1 |
| Growns, Landon C. | 15 | 11 | 17 | +6 |
| Jordan, Scott M. | 12 | 12 | 12 | +0 |
| Jordan, Susan M. | 15 | 14 | 16 | +2 |
| King, Jamie L. | 15 | 15 | 15 | +0 |
| Limperis, Thomas G. | 12 | 14 | 14 | +0 |
| Overduin, Matthew D. | 12 | 9 | 13 | +4 |
| Taylor, Teresa L. | 15 | 15 | 15 | +0 |
| Winn, Janet L. | 15 | 15 | 15 | +0 |
| Xiao, Xinli | 12 | 10 | 13 | +3 |
| Yousuf, Marium | 15 | 0 | 17 | +17 |
| new_instructor | n/a | 24 | 15 | -9 |
| new_instructor 2 | n/a | 13 | 0 | -13 |
| new_instructor 3 | n/a | 3 | 0 | -3 |
| new_instructor 4 | n/a | 6 | 0 | -6 |

## Simplified changes from initial

- **MATH 1914-001** instructor: `Cox, Allie M.` -> `Jordan, Susan M.`
- **MATH 1914-001** time: `MWF 8:00am` -> `MWF 10:00am`
- **MATH 2914-003** instructor: `new_instructor` -> `Jordan, Susan M.`
- **MATH 2924-001** instructor: `new_instructor` -> `Yousuf, Marium`
- **MATH 2924-002** time: `MWF 12:00pm` -> `MWF 1:00pm`
- **MATH 2934-001** instructor: `new_instructor 2` -> `Yousuf, Marium`
- **MATH 2934-002** instructor: `new_instructor` -> `Overduin, Matthew D.`
- **MATH 2934-002** room: `Corley 101` -> `Corley 268`
- **MATH 4123-001** instructor: `new_instructor` -> `Limperis, Thomas G.`
- **MATH 4123-001** time: `MWF 8:00am` -> `MWF 9:00am`
- **MATH 4123-001** room: `Corley 101` -> `Rothwell 312`
- **MATH 4123-H01** instructor: `new_instructor` -> `Limperis, Thomas G.`
- **MATH 4123-H01** time: `MWF 8:00am` -> `MWF 9:00am`
- **MATH 4123-H01** room: `Corley 101` -> `Rothwell 312`
- **MATH 0803-004** instructor: `new_instructor 4` -> `new_instructor`
- **MATH 0803-004** room: `Corley 101` -> `Corley 269`
- **MATH 1003-004** instructor: `new_instructor 4` -> `new_instructor`
- **MATH 1003-004** room: `Corley 101` -> `Corley 269`
- **MATH 0903-001** instructor: `new_instructor 2` -> `Growns, Landon C.`
- **MATH 1113-001** instructor: `new_instructor 2` -> `Growns, Landon C.`
- **MATH 0903-002** time: `MWF 8:00am` -> `MWF 2:00pm`
- **MATH 1113-002** time: `TR 8:00am` -> `TR 2:30pm`
- **MATH 1113-TC2** instructor: `Ballard, Kasey L.` -> `Cox, Allie M.`
- **MATH 2703-001** instructor: `Jordan, Susan M.` -> `Yousuf, Marium`
- **MATH 2703-001** time: `MWF 10:00am` -> `MWF 11:00am`
- **MATH 2703-TC1** instructor: `Jordan, Susan M.` -> `Yousuf, Marium`
- **MATH 3243-002** instructor: `Limperis, Thomas G.` -> `Xiao, Xinli`
- **MATH 3243-002** time: `MWF 9:00am` -> `MWF 1:00pm`
- **STAT 2163-TC2** instructor: `Bain, Leslie M.` -> `Yousuf, Marium`
- **MATH 1003-007** instructor: `new_instructor 3` -> `Ballard, Kasey L.`
- **STAT 2163-004** instructor: `new_instructor 2` -> `Bain, Leslie M.`
- **STAT 2163-004** room: `Corley 101` -> `Rothwell 221`

## Remaining hard violations

- none

## Remaining soft findings

- [custom_rule] (5) MATH 0803-001: matches a custom dislike rule (weight 5)
- [custom_rule] (5) MATH 1113-002: matches a custom dislike rule (weight 5)
