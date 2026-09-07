# 27Sv2 ver1 solve report

Validated solver input: `work/27Sv2/initial/initial.csv` (56 atomic classes, 78 rows)

Initial baseline: `work/27Sv2/initial/initial.csv` (56 atomic classes, 78 rows)

Reconciliation snapshot: `work/27Sv2/initial/reconciliation.toml`

Configuration version: `a06f55105fa7`

Ran 1 independent attempt(s), each with a 45s CP-SAT budget and 8 search worker(s). Selected attempt 1 by lowest worst instructor overload, then lowest solver objective, then lowest reported soft penalty.

## Selected result

- Solver status: optimal
- Solver objective: -4065
- Best objective bound: -4065
- Solve time: 19.8499 seconds
- Candidate assignments: 8266
- CP-SAT search workers: 8
- Hard violations: 0
- Soft penalty: 35 (2 findings)
- Worst instructor overload: 0 credit hours
- Remaining placeholder identities: new_instructor

## Attempt comparison

| Attempt | Status | Objective | Bound | Seconds | Soft | Worst overload | Hard |
|---:|---|---:|---:|---:|---:|---:|---:|
| 1 | optimal | -4065 | -4065 | 19.8499 | 35 | 0 | 0 |

## Before and after

| Metric | Before | After |
|---|---:|---:|
| Hard violations | 20 | 0 |
| Soft penalty | 1050 | 35 |
| Soft findings | 13 | 2 |
| Worst overload | 0 | 0 |

## Teaching loads

| Instructor | Target | Before | After | Delta |
|---|---:|---:|---:|---:|
| Bain, Leslie M. | 15 | 12 | 15 | +3 |
| Ballard, Kasey L. | 12 | 13 | 12 | -1 |
| Cox, Allie M. | 15 | 16 | 17 | +1 |
| Growns, Landon C. | 15 | 11 | 17 | +6 |
| Jordan, Scott M. | 12 | 12 | 12 | +0 |
| Jordan, Susan M. | 15 | 14 | 15 | +1 |
| King, Jamie L. | 15 | 15 | 15 | +0 |
| Limperis, Thomas G. | 12 | 14 | 14 | +0 |
| Overduin, Matthew D. | 12 | 9 | 13 | +4 |
| Taylor, Teresa L. | 15 | 15 | 15 | +0 |
| Winn, Janet L. | 15 | 15 | 15 | +0 |
| Xiao, Xinli | 12 | 10 | 13 | +3 |
| Yousuf, Marium | 15 | 0 | 17 | +17 |
| new_instructor | 15 | 31 | 12 | -19 |
| new_professor | n/a | 15 | 0 | -15 |

## Simplified changes from initial

- **MATH 1113-F01** instructor: `new_instructor` -> `Ballard, Kasey L.`
- **MATH 1914-001** time: `MWF 8:00am` -> `MWF 1:00pm`
- **MATH 1914-001** room: `Corley 101` -> `Corley 104`
- **MATH 1914-001** time: `T 9:30am` -> `T 2:30pm`
- **MATH 1914-003** instructor: `Ballard, Kasey L.` -> `Cox, Allie M.`
- **MATH 1914-003** room: `Corley 102` -> `Corley 104`
- **MATH 1914-003** room: `Corley 268` -> `Corley 104`
- **MATH 2914-001** time: `MWF 9:00am` -> `MWF 11:00am`
- **MATH 2914-003** instructor: `new_instructor` -> `Jordan, Susan M.`
- **MATH 2914-003** time: `MWF 2:00pm` -> `MWF 10:00am`
- **MATH 2914-003** time: `R 2:30pm` -> `R 11:00am`
- **MATH 2924-001** instructor: `new_professor` -> `Yousuf, Marium`
- **MATH 2924-001** time: `MWF 1:00pm` -> `MWF 11:00am`
- **MATH 2924-001** room: `Corley 102` -> `Corley 267`
- **MATH 2924-001** time: `R 1:00pm` -> `T 9:30am`
- **MATH 2924-002** time: `MWF 12:00pm` -> `MWF 2:00pm`
- **MATH 2924-003** instructor: `Limperis, Thomas G.` -> `Yousuf, Marium`
- **MATH 2924-003** room: `Rothwell 306` -> `Corley 267`
- **MATH 2924-003** room: `Rothwell 206` -> `Corley 267`
- **MATH 2934-001** instructor: `new_professor` -> `Limperis, Thomas G.`
- **MATH 2934-001** time: `T 9:30am` -> `R 1:00pm`
- **MATH 2934-001** time: `MWF 10:00am` -> `MWF 1:00pm`
- **MATH 2934-002** instructor: `new_professor` -> `Overduin, Matthew D.`
- **MATH 2934-002** room: `Corley 101` -> `Corley 269`
- **MATH 2934-002** time: `R 11:00am` -> `T 9:30am`
- **MATH 4123-001** instructor: `new_professor` -> `Limperis, Thomas G.`
- **MATH 4123-001** time: `MWF 8:00am` -> `MWF 9:00am`
- **MATH 4123-001** room: `Corley 101` -> `Rothwell 212`
- **MATH 4123-H01** instructor: `new_professor` -> `Limperis, Thomas G.`
- **MATH 4123-H01** time: `MWF 8:00am` -> `MWF 9:00am`
- **MATH 4123-H01** room: `Corley 101` -> `Rothwell 212`
- **MATH 1003-001** room: `Corley 103` -> `Ross Pendergraft Library 332`
- **MATH 0803-002** instructor: `Growns, Landon C.` -> `King, Jamie L.`
- **MATH 0803-002** room: `Ross Pendergraft Library 331` -> `Corley 103`
- **MATH 1003-002** instructor: `Growns, Landon C.` -> `King, Jamie L.`
- **MATH 1003-002** room: `Ross Pendergraft Library 331` -> `Corley 103`
- **MATH 0803-003** instructor: `Ballard, Kasey L.` -> `Winn, Janet L.`
- **MATH 1003-003** instructor: `Ballard, Kasey L.` -> `Winn, Janet L.`
- **MATH 0903-002** instructor: `Winn, Janet L.` -> `Growns, Landon C.`
- **MATH 1113-002** instructor: `Winn, Janet L.` -> `Growns, Landon C.`
- **MATH 0903-TC1** instructor: `new_instructor` -> `Bain, Leslie M.`
- **MATH 1113-TC1** instructor: `new_instructor` -> `Bain, Leslie M.`
- **MATH 1110-003** time: `MW 2:00pm` -> `TR 11:00am`
- **MATH 1113-003** time: `MWF 1:00pm` -> `MWF 11:00am`
- **MATH 1003-005** room: `Corley 104` -> `Rothwell 312`
- **MATH 1003-006** instructor: `King, Jamie L.` -> `Ballard, Kasey L.`
- **MATH 1003-TC2** instructor: `King, Jamie L.` -> `Ballard, Kasey L.`
- **MATH 1113-006** instructor: `Taylor, Teresa L.` -> `Yousuf, Marium`
- **MATH 1113-006** time: `TR 9:30am` -> `TR 2:30pm`
- **MATH 1113-006** room: `Corley 104` -> `Corley 267`
- **MATH 1113-TC2** instructor: `Ballard, Kasey L.` -> `Taylor, Teresa L.`
- **MATH 1203-TC1** instructor: `Bain, Leslie M.` -> `Growns, Landon C.`
- **MATH 2223-003** time: `MWF 10:00am` -> `MWF 2:00pm`
- **MATH 2223-003** room: `Corley 103` -> `Corley 104`
- **MATH 2223-TC1** instructor: `Cox, Allie M.` -> `Ballard, Kasey L.`
- **MATH 2243-001** room: `Corley 104` -> `Corley 102`
- **MATH 2243-002** time: `TR 9:30am` -> `TR 2:30pm`
- **MATH 2243-002** room: `Ross Pendergraft Library 220` -> `Corley 269`
- **MATH 2703-001** time: `MWF 10:00am` -> `MWF 2:00pm`
- **MATH 2703-TC1** instructor: `Jordan, Susan M.` -> `Yousuf, Marium`
- **MATH 3243-001** time: `MWF 10:00am` -> `MWF 1:00pm`
- **MATH 3243-002** instructor: `Limperis, Thomas G.` -> `Xiao, Xinli`
- **MATH 3243-002** time: `MWF 9:00am` -> `MWF 2:00pm`
- **STAT 2163-001** instructor: `King, Jamie L.` -> `Bain, Leslie M.`
- **STAT 2163-TC1** instructor: `Bain, Leslie M.` -> `King, Jamie L.`
- **MATH 1003-007** instructor: `new_instructor` -> `Growns, Landon C.`
- **MATH 1003-007** room: `Corley 103` -> `Rothwell 212`
- **STAT 2163-004** instructor: `new_instructor` -> `Yousuf, Marium`
- **STAT 2163-004** time: `MWF 1:00pm` -> `MWF 9:00am`
- **STAT 2163-004** room: `Corley 268` -> `Corley 267`

## Remaining hard violations

- none

## Remaining soft findings

- [custom_rule] (5) MATH 0803-001: matches a custom dislike rule (weight 5)
- [custom_rule] (30) MATH 1113-006: matches a custom dislike rule (weight 30)
