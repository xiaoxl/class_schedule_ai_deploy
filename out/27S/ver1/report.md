# 27S ver1 solve report

Validated solver input: `work/27S/initial/initial.csv` (57 atomic classes, 79 rows)

Initial baseline: `work/27S/initial/initial.csv` (57 atomic classes, 79 rows)

Term changes snapshot: `inputs/27S/changes.toml`; cancelled-course validation passed

Configuration version: `f1d7cf69b459`

Ran 3 independent attempt(s), each with a 20s CP-SAT budget. Selected attempt 1 by lowest worst instructor overload, then lowest solver objective, then lowest reported soft penalty.

## Selected result

- Solver status: feasible
- Solver objective: -860
- Best objective bound: -1340
- Solve time: 20.0067 seconds
- Candidate assignments: 5972
- Hard violations: 0
- Soft penalty: 210 (6 findings)
- Worst instructor overload: 6 credit hours
- Remaining placeholder identities: Staff, Staff 2

## Attempt comparison

| Attempt | Status | Objective | Bound | Seconds | Soft | Worst overload | Hard |
|---:|---|---:|---:|---:|---:|---:|---:|
| 1 | feasible | -860 | -1340 | 20.0067 | 210 | 6 | 0 |
| 2 | feasible | -800 | -1565 | 20.0221 | 300 | 6 | 0 |
| 3 | feasible | -495 | -1500 | 20.0066 | 340 | 6 | 0 |

## Before and after

| Metric | Before | After |
|---|---:|---:|
| Hard violations | 2 | 0 |
| Soft penalty | 475 | 210 |
| Soft findings | 10 | 6 |
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
| Limperis, Thomas G. | 12 | 10 | 14 | +4 |
| Overduin, Matthew D. | 12 | 9 | 12 | +3 |
| Staff | n/a | 23 | 15 | -8 |
| Staff 2 | n/a | 6 | 4 | -2 |
| Staff 3 | n/a | 6 | 0 | -6 |
| Taylor, Teresa L. | 15 | 15 | 15 | +0 |
| Winn, Janet L. | 15 | 15 | 15 | +0 |
| Xiao, Xinli | 12 | 10 | 14 | +4 |
| Yousuf, Marium | 15 | 15 | 7 | -8 |

## Simplified changes from initial

- **MATH 1914-001** room: `Corley 101` -> `Corley 268`
- **MATH 1914-003** room: `Corley 268` -> `Corley 104`
- **MATH 2914-002** time: `MWF 1:00pm` -> `MWF 11:00am`
- **MATH 2914-003** instructor: `Yousuf, Marium` -> `Jordan, Susan M.`
- **MATH 2924-002** instructor: `Yousuf, Marium` -> `Xiao, Xinli`
- **MATH 2924-002** time: `MWF 12:00pm` -> `MWF 8:00am`
- **MATH 2934-001** instructor: `Staff` -> `Staff 2`
- **MATH 2934-002** instructor: `Staff` -> `Limperis, Thomas G.`
- **MATH 2934-002** room: `Corley 101` -> `Corley 102`
- **MATH 2934-002** room: `Corley 101` -> `Corley 268`
- **MATH 4123-001** instructor: `Staff` -> `Limperis, Thomas G.`
- **MATH 4123-001** time: `MWF 8:00am` -> `MWF 1:00pm`
- **MATH 4123-H01** instructor: `Staff` -> `Limperis, Thomas G.`
- **MATH 4123-H01** time: `MWF 8:00am` -> `MWF 1:00pm`
- **MATH 0903-001** instructor: `Staff 3` -> `Winn, Janet L.`
- **MATH 1113-001** instructor: `Staff 3` -> `Winn, Janet L.`
- **MATH 0903-002** instructor: `Winn, Janet L.` -> `Growns, Landon C.`
- **MATH 1113-002** instructor: `Winn, Janet L.` -> `Growns, Landon C.`
- **MATH 0803-004** instructor: `Staff 2` -> `Staff`
- **MATH 1003-004** instructor: `Staff 2` -> `Staff`
- **MATH 1003-005** room: `Corley 104` -> `Rothwell 312`
- **MATH 1113-006** time: `TR 9:30am` -> `TR 2:30pm`
- **MATH 1113-006** room: `Corley 104` -> `Corley 102`
- **MATH 2033-001** time: `MWF 10:00am` -> `MWF 8:00am`
- **MATH 2703-002** instructor: `Limperis, Thomas G.` -> `Jordan, Susan M.`
- **MATH 2703-002** room: `Rothwell 206` -> `Corley 101`
- **MATH 2703-TC1** instructor: `Jordan, Susan M.` -> `Overduin, Matthew D.`
- **MATH 4971-001** room: `Corley 101` -> `Rothwell 221`
- **STAT 3153-002** room: `Corley 102` -> `Corley 269`
- **MATH 1003-007** instructor: `Staff` -> `Jordan, Susan M.`
- **MATH 1003-007** room: `` -> `Corley 101`

## Remaining hard violations

- none

## Remaining soft findings

- [overload] (100) Jordan, Susan M.: 21 credit hours exceeds max_load 15
- [under_load] (90) Yousuf, Marium: 7 credit hours is under max_load 15
- [disliked_time] (5) MATH 1914-001: falls in a disliked time (Prefers no early classes)
- [disliked_time] (5) MATH 0803-001: falls in a disliked time (Prefers MWF only)
- [disliked_time] (5) MATH 0903-001: falls in a disliked time (Prefers MWF only)
- [disliked_time] (5) MATH 2033-001: falls in a disliked time (No 8am classes on MWF)
