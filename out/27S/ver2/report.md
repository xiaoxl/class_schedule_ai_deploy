# 27S ver2 solve report

Input: `out/27S/starting.csv` (59 classes)

Ran 5/5 feasible independent solves (each 45s CP-SAT budget) and kept the one with the lowest worst-case per-instructor overload, tie-broken by total soft penalty -- the raw penalty score alone can hide a schedule that dumps an unrealistic load onto one instructor, since overload penalty is flat past a threshold rather than scaled by magnitude.

## Before solve

- Hard violations: 0
- Soft penalty: 575 (9 findings)
- Worst per-instructor overload: 5 credit hours

## After solve (best of the attempts)

- Hard violations: 0
- Soft penalty: 105 (2 findings)
- Worst per-instructor overload: 3 credit hours

## Teaching load, before vs after

| Instructor | max_load | before | after |
|---|---:|---:|---:|
| Bain, Leslie M. | 15 | 15 | 15 |
| Ballard, Kasey L. | 12 | 13 | 13 |
| Cox, Allie M. | 15 | 16 | 15 |
| Growns, Landon C. | 15 | 11 | 17 |
| Jordan, Scott M. | 12 | 15 | 15 |
| Jordan, Susan M. | 15 | 14 | 15 |
| King, Jamie L. | 15 | 15 | 15 |
| Limperis, Thomas G. | 12 | 17 | 14 |
| Overduin, Matthew D. | 12 | 9 | 12 |
| Staff | — | 23 | 14 |
| Staff 2 | — | 6 | 6 |
| Taylor, Teresa L. | 15 | 15 | 15 |
| Winn, Janet L. | 15 | 15 | 15 |
| Xiao, Xinli | 12 | 10 | 13 |
| Yousuf, Marium | 15 | 17 | 17 |

## Changes made by solver

- **MATH 1914-001** instructor: `Cox, Allie M.` -> `Jordan, Susan M.`
- **MATH 1914-001** instructor: `Cox, Allie M.` -> `Jordan, Susan M.`
- **MATH 2914-003** room: `Corley 101` -> `Corley 268`
- **MATH 3203-001** instructor: `Staff` -> `Overduin, Matthew D.`
- **MATH 3203-H01** instructor: `Staff` -> `Overduin, Matthew D.`
- **MATH 0903-002** instructor: `Winn, Janet L.` -> `Growns, Landon C.`
- **MATH 1113-002** instructor: `Winn, Janet L.` -> `Growns, Landon C.`
- **MATH 1003-006** instructor: `King, Jamie L.` -> `Winn, Janet L.`
- **MATH 1003-006** time: `MWF 9:00am` -> `MWF 8:00am`
- **MATH 2243-001** instructor: `Overduin, Matthew D.` -> `Cox, Allie M.`
- **MATH 2703-001** instructor: `Jordan, Susan M.` -> `Overduin, Matthew D.`
- **MATH 3243-002** instructor: `Limperis, Thomas G.` -> `Xiao, Xinli`
- **MATH 3243-002** time: `MWF 9:00am` -> `MWF 1:00pm`
- **MATH 1003-007** instructor: `Staff` -> `Winn, Janet L.`
- **MATH 1003-007** room: `` -> `Corley 267`
- **STAT 2163-004** instructor: `Staff` -> `King, Jamie L.`
- **STAT 2163-004** room: `` -> `Corley 268`

## Remaining hard violations

- none

## Remaining soft findings

- [overload] (100) Jordan, Scott M.: Jordan, Scott M.: 15 credit hours exceeds max_load 12
- [disliked_time] (5) Winn, Janet L.: MATH 0803-001: falls in a disliked time (Prefers MWF only)
