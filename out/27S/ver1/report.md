# 27S ver1 solve report

Input: `out/27S/starting.csv` (59 classes)

Ran 5/5 feasible independent solves (each 45s CP-SAT budget) and kept the one with the lowest worst-case per-instructor overload, tie-broken by total soft penalty -- the raw penalty score alone can hide a schedule that dumps an unrealistic load onto one instructor, since overload penalty is flat past a threshold rather than scaled by magnitude.

## Before solve

- Hard violations: 0
- Soft penalty: 575.0 (9 findings)
- Worst per-instructor overload: 5.0 credit hours

## After solve (best of the attempts)

- Hard violations: 0
- Soft penalty: 110.0 (3 findings)
- Worst per-instructor overload: 3.0 credit hours

## Teaching load, before vs after

| Instructor | max_load | before | after |
|---|---:|---:|---:|
| Bain, Leslie M. | 15 | 15 | 15 |
| Ballard, Kasey L. | 12 | 13 | 13 |
| Cox, Allie M. | 15 | 16 | 15 |
| Growns, Landon C. | 15 | 11 | 15 |
| Jordan, Scott M. | 12 | 15 | 15 |
| Jordan, Susan M. | 15 | 14 | 15 |
| King, Jamie L. | 15 | 15 | 15 |
| Limperis, Thomas G. | 12 | 17 | 13 |
| Overduin, Matthew D. | 12 | 9 | 12 |
| Staff | — | 23 | 16 |
| Staff 2 | — | 6 | 6 |
| Taylor, Teresa L. | 15 | 15 | 15 |
| Winn, Janet L. | 15 | 15 | 15 |
| Xiao, Xinli | 12 | 10 | 14 |
| Yousuf, Marium | 15 | 17 | 17 |

## Changes made by solver

- **MATH 1113-F01** room: `Corley 269` -> `Ross Pendergraft Library 220`
- **MATH 1914-001** time: `MWF 8:00am` -> `MWF 10:00am`
- **MATH 2914-003** instructor: `Yousuf, Marium` -> `Jordan, Susan M.`
- **MATH 2914-003** instructor: `Yousuf, Marium` -> `Jordan, Susan M.`
- **MATH 2924-002** instructor: `Limperis, Thomas G.` -> `Yousuf, Marium`
- **MATH 2924-002** time: `MWF 12:00pm` -> `MWF 8:00am`
- **MATH 2924-002** instructor: `Limperis, Thomas G.` -> `Yousuf, Marium`
- **MATH 2934-002** instructor: `Staff` -> `Xiao, Xinli`
- **MATH 2934-002** time: `MWF 11:00am` -> `MWF 8:00am`
- **MATH 2934-002** instructor: `Staff` -> `Xiao, Xinli`
- **MATH 3203-001** instructor: `Staff` -> `Overduin, Matthew D.`
- **MATH 3203-H01** instructor: `Staff` -> `Overduin, Matthew D.`
- **MATH 1003-002** time: `MWF 10:00am` -> `MWF 8:00am`
- **MATH 1110-003** instructor: `Growns, Landon C.` -> `Cox, Allie M.`
- **MATH 1113-003** instructor: `Growns, Landon C.` -> `Cox, Allie M.`
- **MATH 2223-001** instructor: `Cox, Allie M.` -> `Growns, Landon C.`
- **MATH 2223-003** instructor: `Cox, Allie M.` -> `Growns, Landon C.`
- **MATH 2243-001** instructor: `Overduin, Matthew D.` -> `Growns, Landon C.`
- **MATH 2703-001** instructor: `Jordan, Susan M.` -> `Limperis, Thomas G.`
- **MATH 2703-001** time: `MWF 10:00am` -> `MWF 11:00am`
- **MATH 3243-002** instructor: `Limperis, Thomas G.` -> `Overduin, Matthew D.`

## Remaining hard violations

- none

## Remaining soft findings

- [overload] (100) Jordan, Scott M.: Jordan, Scott M.: 15 credit hours exceeds max_load 12
- [disliked_time] (5) Winn, Janet L.: MATH 0803-001: falls in a disliked time (Prefers MWF only)
- [disliked_time] (5) Winn, Janet L.: MATH 1113-002: falls in a disliked time (Prefers MWF only)
