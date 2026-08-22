# 排课规则

## 原子课程分组

一行先解析为 `Section`；整表再按以下优先级组成一个或两个 Section 的
原子课程。求解器以原子课程为边界，负载计数一次，内部两行不互相报
double-booking。

1. `FourCreditClass`：同一课程/section 的两行，一行 `MWF`、一行 `T` 或
   `R`，同一教师。
2. `HybridClass`：同一课程/section，section 以 `M` 或 `F` 开头，一行有
   room、一行无 room。
3. `CrossListingClass`：不同课程共享非空 `Cross-List`；或同课程普通/
   honors section（如 `001`/`H01`）共享教师、时间和 room。
4. `CoreqClass`：代码白名单中的课程对、相同 section/教师，并符合物理
   back-to-back 或全在线 TC 配对规则。
5. 其余每行是 `NormalClass`。

同一课程优先于 cross-list，cross-list 优先于 coreq。以 `P`、`ET`、`A`
开头的 section 在进入分组前删除。显式 cross-list 的输入两行可以暂时
不共享会议；求解器的组合约束要求输出必须共享教师、时间、时长和教室。

## 候选如何产生

每个 Section 的候选是 `(instructor, time, building, room)`：

- 教师来自 persons 中 `courses` 包含该 `SUBJECT NUMBER` 的人员；当前教师
  始终加入，防止历史表因缺配置而无候选。
- ONLINE/TBA/空时间不改时间和教室，只可改教师。
- 物理课按与原时长、原子类型匹配的 meeting pattern 生成时间，再和
  `available` rooms 做笛卡尔积。
- blackout 相交的新增时间候选被排除。
- 单行课程每位教师最多保留成本最低的 40 个候选；双行课程每位教师最多
  10 个，减少组合爆炸。
- 当前原始候选总会补回，即使它不在 room 列表、meeting pattern 中，或
  落在 blackout。这是兼容历史排课的逃生口，因此这些配置不是对输入现状
  的绝对禁止。如需绝对固定/禁止，应先修数据并使用 lock，且最终 validate。

手调 lock 在候选生成最后过滤：锁了某字段就只保留与手调后当前值一致的
候选。若全部候选被过滤，求解直接报 `No legal candidates`。

## 硬约束

求解模型必须满足：

- 每个 Section 恰选一个候选；
- 不同原子课程不能在同一 room 的重叠时间出现；
- 同一教师不能在重叠时间教不同原子课程；
- 双行原子课程保持同一教师及各自类型的合法组合；cross-list 输出共享
  meeting；
- 已设置的 lock 字段不得变化；
- 对 persons 中出现且获得课程的教师，求解负载不超过
  `max_load + 6` 学分。

`check_conflicts()` 对任意已生成/导入排课只报告两种硬冲突：room overlap
和 instructor overlap。原子类型合法性在对象构造时检查；`max_load + 6`
是求解器内部上界，不会把外部导入表标成 hard violation。因此发布前必须
同时看导入/分组是否成功、solver status 和 validate 报告，不能只看一个数。

## 软目标和成本

求解器最小化总成本：

| 项目 | 成本 |
|---|---:|
| 更换教师 | 10 |
| 更换时间 | 5 |
| 更换 building/room 组合 | 5 |
| disliked time/location/course | 每项 5 |
| prefers online 但安排物理课 | 5 |
| 不允许 back-to-back，或超过连续课上限 | 每处 10 |
| 低于 `max_load` | 每位教师 90 |
| 超过 `max_load + 2` 且 `allow_overload=true` | 10 |
| 超过 `max_load + 2` 且 `allow_overload=false` | 100 |
| allow overload 且超过 `max_load + 4` | 额外 50 |
| 自定义 dislike rule | `+weight` |
| 自定义 prefer rule | `-weight` |

`max_load` 是目标：不足和过量都是软目标；只有上节所述 `+6` 是模型硬上界。
偏好报告只列“违反项”，因此已满足的 prefer 奖励不会出现在 reported soft
penalty 中，但会出现在 solver objective 中。

同一学期多次独立求解按以下顺序选优：最低 worst overload、最低 solver
objective、最低 reported soft penalty。每次使用独立随机种子，种子写入
manifest，时间预算按每次 attempt 单独计算。

## 求解状态

- `optimal`：在时间内证明当前候选空间的最优解。
- `feasible`：找到合法解，但未证明最优。
- `timeout`：时间内连合法解都没有找到，该 attempt 失败。
- `infeasible`：候选模型被证明无解，整次运行失败。

求解成功不等于业务上无遗留问题。结果报告还应确认 hard violations 为 0、
Staff 占位人员是否清零、负载和 soft findings 是否可接受。
