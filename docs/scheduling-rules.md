# 排课规则

## 原子课程分组

一行先解析为 `Section`；整表再按以下优先级组成一个或两个 Section 的
原子课程。求解器以原子课程为边界，负载计数一次，内部两行不互相报
double-booking。

1. `FourCreditClass`：同一课程/section 的两行，一行 `MWF`、一行 `T` 或
   `R`，同一教师。构造允许两个开始时间相差超过 90 分钟，以便旧输入仍能进入调整；
   此时对象的 `schedule_issues` 会记录 `four_credit_time_gap` 信息。求解候选配对使用
   `is_valid_schedule()`，只允许开始时间差不超过 90 分钟，最终评估把未修复的信息报告
   为硬违规。
2. `HybridClass`：section 以 `M` 或 `F` 开头，并有一条实际时间和 room 完整的
   物理会议。导入可以只有这条物理行，也可以同时带有旧的无物理会议 companion；
   构造原子课时统一以物理行为权威，自动生成或重建 ONLINE companion。只有 room
   一有一无但两行都有物理时间时不成立，也不会借此掩盖漏填 room。
3. `CrossListingClass`：不同课程共享非空 `Cross-List`；内置已知课程对
   `MATH 5173`/`STAT 4173` 且 section 相同；或同课程普通/honors section
   （如 `001`/`H01`）共享教师、时间和 room。
4. `CoreqClass`：代码白名单中的课程对、相同 section/教师。两行均无物理会议
   时合法；否则必须是在至少一个共同上课日中前后相接不超过 15 分钟且
   building/room 完全相同，或上课日完全不相交且开始时间相差不超过 30 分钟。
5. 其余每行是 `NormalClass`。

`HybridClass.physical_section` 唯一决定该原子课的时间、building、room 和教师。
扁平化为 CSV/XLSX 时，ONLINE 行由物理行重新生成：课程身份和教师随物理行，时间为
`ONLINE`，building/room 为空。硬约束以整个 Hybrid 原子课为单位，只对这条物理权威
记录判断一次，因此 ONLINE companion 不会被误报为 `not Corley`。

同一课程优先于 cross-list，cross-list 优先于 coreq。以 `P`、`ET`、`A`
开头的 section 在进入分组前删除。显式 cross-list 的输入两行可以暂时
不共享会议；求解器的组合约束要求输出必须共享教师、时间、时长和教室。
`MATH 5173`/`STAT 4173` 是 `CrossListingClass.COURSE_PAIRS` 中的固定领域
规则，不依赖源文件标记或配置文件，也不会向输出伪造 Cross-List 值。旧版本
中遗留的 `configured:` 合成标记会在导入时清空，再按此内置规则分组。

`MATH 1110` 的学分覆盖也在原子结构构造时完成：无论输入 Credits 是空值还是其他
数值，`Section` 都规范为 2 学分。负载统计和求解器只读取构造后的原子课学分，
不再各自识别课程号或重复覆盖。

教学负载必须通过 `schedule_model.teaching_loads()` 基于原子课程统计，不能
按 CSV 行相加。普通双行课、hybrid、cross-list 都只计一次；coreq 覆盖
`credit_hours`，按两门不同课程的学分合计。草案放置、软规则报告和版本报告
共享这一实现；CP-SAT 负载模型同样只在每个原子课程的 primary section 上
建立一次负载变量。

`schedule_model.evaluate_schedule()` 是统一统计入口，返回原子课数、展开行数、
`teaching_loads()` 结果、hard violations、soft penalty 和 soft findings。
CLI validate、求解尝试评估、版本报告和 Web API 都使用这组领域统计；不得在
调用端另写一套按行统计。

## 候选如何产生

每个 Section 的候选是 `(instructor, time, building, room)`：

- 教师来自 persons 中 `courses` 包含该 `SUBJECT NUMBER` 的人员；当前教师
  始终加入，防止历史表因缺配置而无候选。
- ONLINE/TBA/空时间不改时间和教室，只可改教师。
- 物理课按与原时长及通用 selector 匹配的 meeting pattern 生成时间，再和
  `available` rooms 做笛卡尔积。selector 由结构 `roles`、当前记录 `courses`
  和完整原子课集合 `atomic_courses` 组成；Python 匹配器不包含具体课程号。
  如果某课程存在显式 `courses` pattern，这些 pattern 会取代通用时间域，并以其
  `duration_minutes` 规范化旧输入时长。
- `changes.toml` 中新增的物理 section 在 initial 阶段必须精确匹配其原子类型可用的
  meeting pattern（days、duration、start）；不合法时在写出 `initial.csv` 前直接失败。
- 单行课程每位教师最多保留成本最低的 40 个候选；双行课程每位教师最多
  10 个，减少组合爆炸。
- 当前原始候选通常会补回，即使它不在 room 列表，以兼容历史排课。但 constraint
  负规则是绝对禁止条件，当前候选也不能绕过；meeting pattern 对已经配置的同类时间族
  同样严格：如果相同
  `days + duration` 已有可用 pattern，当前 start 也必须出现在其 `starts` 中。
  例如 MWF 50 分钟族不保留 `MWF 11:50am`，Friday noon 负硬规则也会排除
  `MWF 12:00pm`。等学分 coreq 的记录不能使用 MW noon；coreq 中学分较低的辅助记录
  可以使用 `MW 12:00pm`。当前数据中该记录是 `MATH 1110`，但代码和该时间模式
  都不依赖课程号。生产配置存在 meeting patterns 时不再隐式保留未配置
  的历史时间；特殊 seminar 必须用独立 pattern 明确列出。如需固定合法当前值，
  应使用 lock，且最终 validate。

`MATH 4971` 的旧模板记录是 80 分钟，但不在学期 `changes.toml` 中增加 timeslot 或替换课程。
通用 `timeslot.toml` 用两条配置开放单日候选：`days = ["M", "W", "F"]` 的每个
选项为 50 分钟，`days = ["T", "R"]` 的每个选项为 80 分钟；这表示“每周从任一
合法工作日选一天”，不是 `days = ["MTWRF"]` 的“每周五天都上课”。
显式 `courses` pattern 优先于通用 MWF/TR pattern，所以求解候选统一为合法的单日课，
不会变成每周两次或三次。Friday noon 负硬规则仍对它生效。

手调 lock 在候选生成最后过滤：锁了某字段就只保留与手调后当前值一致的
候选。若全部候选被过滤，求解直接报 `No legal candidates`。

`Staff` 是一个可伸缩的占位教师池。求解前会对所有 `Staff`/`Staff N` 课程建立
时间冲突图并贪心着色，生成足够的候选身份。模型随后按实际启用的不同 Staff
身份计全局成本，并在没有 Staff instructor lock 时强制连续编号：使用 `Staff 2`
就必须同时使用 `Staff`。因此时间冲突严重时可以增加身份，能够通过调时合并时
则倾向于使用更少身份。求解后保留模型选择，不再用一次独立贪心着色覆盖结果。
若 Staff instructor 被 lock，则保留人工指定身份，不施加连续编号约束。

## 硬约束

求解模型必须满足：

- 每个 Section 恰选一个候选；
- 不同原子课程不能在同一 room 的重叠时间出现；
- 同一教师不能在重叠时间教不同原子课程；
- 双行原子课程保持同一教师及各自类型的合法组合；cross-list 输出共享
  meeting；
- 已设置的 lock 字段不得变化；
- `constraints.toml` 中每条 `[[rules]]` 的 name/物理 room/time 必须满足；
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
| 每个实际启用的 `Staff`/`Staff N` 身份 | `+staff_count_weight` |
| 留给 `Staff`/`Staff N` 的每学分 | `+staff_credit_weight` |
| 正权重 rule 匹配 | `-weight` |
| 负权重 rule 匹配 | `+abs(weight)` |
| 不允许 back-to-back，或超过连续课上限 | 每处 10 |
| 低于 `max_load` | 每缺少 1 学分 30 |
| 超过 `max_load + 2` 且 `allow_overload=true` | 每超出 1 学分 10 |
| 超过 `max_load + 2` 且 `allow_overload=false` | 每超出 1 学分 100 |
| allow overload 且超过 `max_load + 4` | 额外 50 |
所有偏好都写成扁平 `[[rules]]` 字典并显式携带 `weight`，范围为 `-100` 到 `100`
且不可为 0；
同一候选匹配多个条目时逐项相加。每条规则自己的 `name` 决定教师作用域，
省略 `name` 才是全局规则；`# Name` 注释只用于排版。规则直接使用无方向前缀的
`course`、`section`、`section_prefix`、`room`、`time` selector；正负
方向只由 signed `weight` 决定。

网课偏好统一通过 `section_prefix = "TC"` 表达；正权重表示喜欢 TC 网课，负权重表示
排斥 TC 网课。不能用 TBA/无物理时间作为网课 selector，因为其他类型的 section 也可能
没有固定时间。

`max_load` 是目标：不足和过量都是软目标；只有上节所述 `+6` 是模型硬上界。
偏好报告只列“违反项”，因此已满足的 prefer 奖励不会出现在 reported soft
penalty 中，但会出现在 solver objective 中。

同一学期多次独立求解按以下顺序选优：最低 worst overload、最低 solver
objective、最低 reported soft penalty。每次使用独立随机种子，种子写入
manifest，时间预算按每次 attempt 单独计算。

CP-SAT 默认使用 8 个并行 search workers；CLI 可用 `--workers N` 调整。需要严格复现
单线程搜索路径时使用 `--workers 1`。某次 attempt 已返回 `optimal` 且通过硬规则复核后，
后续 attempt 不再运行；`manifest.json` 同时记录请求次数与实际运行次数。

## 求解状态

- `optimal`：在时间内证明当前候选空间的最优解。
- `feasible`：找到合法解，但未证明最优。
- `timeout`：时间内连合法解都没有找到，该 attempt 失败。
- `infeasible`：候选模型被证明无解，整次运行失败。

求解成功不等于业务上无遗留问题。结果报告还应确认 hard violations 为 0、
Staff 占位人员是否清零、负载和 soft findings 是否可接受。
