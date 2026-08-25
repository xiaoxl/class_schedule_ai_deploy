# 27S final solve report

Validated solver input: `out/27S/ver16/27S_ver16.csv` (57 atomic classes, 79 rows)

Initial baseline: `out/27S/ver16/baseline.csv` (57 atomic classes, 79 rows)

Term changes snapshot: `out/27S/ver16/applied_changes.toml`; cancelled-course validation passed

Configuration version: `fbd2b0f19eb7`

Ran 1 independent attempt(s), each with a 45s CP-SAT budget and 8 search worker(s). Selected attempt 1 by lowest worst instructor overload, then lowest solver objective, then lowest reported soft penalty.

## Selected result

- Solver status: optimal
- Solver objective: -1465
- Best objective bound: -1465
- Solve time: 2.02884 seconds
- Candidate assignments: 5496
- CP-SAT search workers: 8
- Hard violations: 0
- Soft penalty: 10 (2 findings)
- Worst instructor overload: 0 credit hours
- Remaining placeholder identities: Staff

## Attempt comparison

| Attempt | Status | Objective | Bound | Seconds | Soft | Worst overload | Hard |
|---:|---|---:|---:|---:|---:|---:|---:|
| 1 | optimal | -1465 | -1465 | 2.02884 | 10 | 0 | 0 |

## Before and after

| Metric | Before | After |
|---|---:|---:|
| Hard violations | 3 | 0 |
| Soft penalty | 460 | 10 |
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
| Limperis, Thomas G. | 12 | 10 | 14 | +4 |
| Overduin, Matthew D. | 12 | 9 | 13 | +4 |
| Staff | n/a | 23 | 15 | -8 |
| Staff 2 | n/a | 6 | 0 | -6 |
| Staff 3 | n/a | 6 | 0 | -6 |
| Taylor, Teresa L. | 15 | 15 | 15 | +0 |
| Winn, Janet L. | 15 | 15 | 15 | +0 |
| Xiao, Xinli | 12 | 10 | 13 | +3 |
| Yousuf, Marium | 15 | 15 | 17 | +2 |

## Simplified changes from initial

- **MATH 1914-001** instructor: `Cox, Allie M.` -> `Jordan, Susan M.`
- **MATH 1914-001** time: `MWF 8:00am` -> `MWF 10:00am`
- **MATH 1914-003** room: `Corley 102` -> `Corley 104`
- **MATH 2914-003** instructor: `Yousuf, Marium` -> `Jordan, Susan M.`
- **MATH 2924-002** time: `MWF 12:00pm` -> `MWF 2:00pm`
- **MATH 2934-001** instructor: `Staff` -> `Limperis, Thomas G.`
- **MATH 2934-001** time: `MWF 10:00am` -> `MWF 11:00am`
- **MATH 2934-002** instructor: `Staff` -> `Overduin, Matthew D.`
- **MATH 4123-001** instructor: `Staff` -> `Limperis, Thomas G.`
- **MATH 4123-001** time: `MWF 8:00am` -> `MWF 9:00am`
- **MATH 4123-001** room: `Corley 268` -> `Rothwell 212`
- **MATH 4123-H01** instructor: `Staff` -> `Limperis, Thomas G.`
- **MATH 4123-H01** time: `MWF 8:00am` -> `MWF 9:00am`
- **MATH 4123-H01** room: `Corley 268` -> `Rothwell 212`
- **MATH 0903-001** instructor: `Staff 3` -> `Growns, Landon C.`
- **MATH 1113-001** instructor: `Staff 3` -> `Growns, Landon C.`
- **MATH 0903-002** time: `MWF 8:00am` -> `MWF 2:00pm`
- **MATH 1113-002** time: `TR 8:00am` -> `TR 2:30pm`
- **MATH 1110-003** time: `MW 2:00pm` -> `TR 1:00pm`
- **MATH 0803-004** instructor: `Staff 2` -> `Staff`
- **MATH 1003-004** instructor: `Staff 2` -> `Staff`
- **MATH 1113-006** room: `Corley 104` -> `Corley 102`
- **MATH 1203-TC1** instructor: `Bain, Leslie M.` -> `Cox, Allie M.`
- **MATH 2703-001** instructor: `Jordan, Susan M.` -> `Yousuf, Marium`
- **MATH 2703-001** time: `MWF 10:00am` -> `MWF 9:00am`
- **MATH 2703-001** room: `Corley 101` -> `Corley 268`
- **MATH 2703-TC1** instructor: `Jordan, Susan M.` -> `Yousuf, Marium`
- **MATH 3243-002** instructor: `Limperis, Thomas G.` -> `Xiao, Xinli`
- **MATH 3243-002** time: `MWF 9:00am` -> `MWF 1:00pm`
- **STAT 2163-004** instructor: `Staff` -> `Bain, Leslie M.`
- **STAT 2163-004** room: `` -> `Rothwell 221`

## Remaining hard violations

- none

## Remaining soft findings

- [custom_rule] (5) MATH 0803-001: matches a custom dislike rule (weight 5)
- [custom_rule] (5) MATH 1113-002: matches a custom dislike rule (weight 5)
