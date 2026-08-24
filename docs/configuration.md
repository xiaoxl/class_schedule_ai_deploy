# 配置格式

所有主配置都使用 TOML。四个必需配置和可选的硬约束配置都由 Pydantic 严格校验：未知键、重复
人员、重复房间、非法课程号、非法星期、越界权重都会直接报错。

## 文件定位和优先级

推荐布局：

```text
config/
  catalog/
    persons.toml
    locations.toml
  terms/
    27S/
      preferences.toml
      timeslot.toml
      constraints.toml
inputs/
  27S/
    changes.toml

out/
  27S/
    ver10/
      overrides.toml
```

为兼容现有项目，缺少推荐路径时逐文件回退到
`config/persons.toml`、`preferences.toml`、`timeslot.toml`、
`locations.toml`。`constraints.toml` 是可选文件；优先读取
`config/terms/<term>/constraints.toml`，再回退到 `config/constraints.toml`。
新学期应优先建立 `config/terms/<term>/`，避免覆盖旧学期设置。求解清单会记录
实际读取的全部配置路径及哈希。

## persons.toml

这是跨学期事实：正式姓名、合同负载、可授课程、导入别名。

```toml
[[persons]]
name = "Jordan, Susan M."
max_load = 15
aliases = [
  { short = "Jordan", subject = "MATH" },
  "S. Jordan",
]
courses = ["MATH 1003", "MATH 1113", "MATH 1914"]
```

- `name` 全局唯一，preferences 和 changes 中用这个正式名。
- `max_load` 必须大于 0，是目标负载，不只是上限。
- `courses` 格式严格为 `SUBJECT NUMBER`，不可带 section，不可重复。
- 字符串 alias 对所有学科生效；带 `subject` 的 alias 只在该学科解析。
- 两个人的 alias 作用域不得重叠，alias 也不得冒充另一人的正式名。

## locations.toml

```toml
[[rooms]]
name = "Corley 101"
location = "Corley"
available = true
```

`name` 必须以 `location` 开头且全局唯一。`available = false` 的房间不生成
新候选。加载后领域对象分成 `building = "Corley"` 和 `room = "101"`。

## timeslot.toml

```toml
[[calendar.meeting_patterns]]
days = ["MWF"]
duration_minutes = 50
starts = ["08:00", "09:00", "10:00"]
roles = ["normal", "hybrid_physical", "cross_listing", "coreq"]

[[calendar.meeting_patterns]]
days = ["MW"]
duration_minutes = 50
starts = ["12:00"]
roles = ["coreq_supplement"]
```

`roles` 描述当前 CSV 记录在分组后原子课中的结构角色：

| 值 | 用途 |
|---|---|
| `normal` | 单行普通原子课 |
| `hybrid_physical` | HybridClass 的实体记录 |
| `cross_listing` | CrossListingClass 的记录 |
| `coreq` | CoreqClass 中有学分的记录 |
| `coreq_supplement` | CoreqClass 中学分严格低于另一行的辅助记录 |
| `four_credit_primary` | FourCreditClass 的 MWF 主记录 |
| `four_credit_partial` | FourCreditClass 的 T/R 补充记录 |

`courses` 是可选的当前记录课程白名单；`atomic_courses` 是可选的原子课完整课程集合，
采用集合精确匹配。两者为空表示不限制课程。上面的 MW 规则不使用课程 selector：
通用匹配器只要求当前记录是 coreq 中学分较低的辅助记录，因此对任何具有相同结构的新 coreq
都生效。只有真正按课程命名的例外才需要 `courses` 或 `atomic_courses`。
两个课程 selector 都使用严格的 `SUBJECT NUMBER` 格式，不可重复；两者同时出现时，
`courses` 必须是 `atomic_courses` 的子集，否则加载配置时直接报错。

同一课程只要存在至少一条显式 `courses` pattern，这些显式 pattern 就构成该课程完整的
候选时间域，并优先于所有通用 pattern；其中的 `duration_minutes` 也作为规范时长。因此旧输入
记录的时长可以在求解候选中被配置规范化，而不需要在学期 `changes.toml` 里取消再新增课程。

`days` 必须是非空数组，数组的每个字符串只能由 `MTWRF` 组成。每个数组元素是一个
可选的完整 meeting pattern：`days = ["M", "W", "F"]` 表示可从三个单日模式中
选择，`days = ["MWF"]` 表示一个每周 M/W/F 都上课的模式，两者含义不同。loader 会
把数组展开成独立运行时候选。`duration_minutes > 0`，`starts` 不可为空。
`timeslot.toml` 只包含允许生成的 meeting pattern，不存禁止时段。
`changes.toml` 新增的物理 section 也使用这里的 pattern 做严格校验；
例如标准 MWF 50 分钟课不能写成 `11:50`。Friday `12:00-12:50` 的禁止时段
使用 `constraints.toml` 负规则表达。`MATH 0803`/`MATH 1003` 和
`MATH 0903`/`MATH 1113` 两类 coreq 都只能使用 standard pattern；coreq 中学分较低的
辅助记录可以使用 `MW 12:00pm`。在当前数据中，这对应 `MATH 1110` 记录，但规则本身
不识别这个课程号。

一次只上一天的课可把相同 duration/starts/selectors 的日期合并到一个数组元素列表；
`days = ["MTWRF"]` 表示每周五天都上课，不表示“从五天中任选一天”。当前
`MATH 4971` 是每周一次的 seminar，因此配置用 `days = ["M", "W", "F"]` 表示
三个 50 分钟单日选项，用 `days = ["T", "R"]` 表示两个 80 分钟单日选项，并使用标准
TR 网格；显式课程 pattern 的优先级避免错误生成通用 MWF/TR 候选。Friday
`12:00-12:50` 仍由 constraint 负规则统一禁止。

## preferences.toml

这是学期数据，不是人员合同事实。

```toml
staff_count_weight = 100

# Xiao, Xinli
[[instructors]]
name = "Xiao, Xinli"
allow_overload = false
allow_back_to_back = true
max_back_to_back = 3

[[rules]]
name = "Xiao, Xinli"
time = "09:00-13:00"
weight = 50

[[rules]]
name = "Xiao, Xinli"
course = "MATH 2934"
weight = -50

[[rules]]
name = "Xiao, Xinli"
course = "STAT 3113"
room = "Corley 101"
weight = 50

[[rules]]
name = "Xiao, Xinli"
section_prefix = "TC"
weight = 20

```

- `staff_count_weight` 是每个实际使用的 `Staff`/`Staff N` 身份的全局成本，范围
  `0-100`。值越高，求解器越愿意调整时间来合并 Staff；硬冲突仍可迫使它增加身份。
- `[[instructors]]` 是人员 profile，只存 `allow_overload` 和连排参数；`name`
  必须存在于 persons。
- `allow_overload` 只改变超载软惩罚，不解除求解器绝对负载上界。
- `allow_back_to_back = false` 对每个相邻连续课惩罚；为 true 且设置
  `max_back_to_back = N` 时，从同日连续第 `N+1` 门开始逐门惩罚。
- 每条 `[[rules]]` 都是独立字典。`name` 决定教师作用域；同一人的规则可以连续放在
  `# Name` 注释下便于阅读，但注释没有任何配置意义。
- 每条规则直接使用 `course`、`section`、`section_prefix`、`room`、`time`
  selector。`weight` 必填、不可为 0，范围为 `-100` 到 `100`：正数表示喜欢，命中时
  从候选成本减去该值；负数表示排斥，命中时把绝对值加入成本。同一候选命中多条
  规则时累加。
- 正权重规则未命中不是违规；负权重规则命中会写入软问题报告。
- selector 内的 `course`、`section`、`section_prefix`、`room`、`time`
  是可选匹配条件，同一字典内按 AND 组合。selector 至少需要一个条件，`section`
  必须与 `course` 同时出现。
- `room` 可写单个字符串，也可写候选数组，例如
  `room = ["Corley 103", "Corley 104", "Rothwell 221"]`。命中数组中
  任意一个房间即满足该 selector，一条规则最多计算一次 `weight`。
- `time = "8-12"` 是所有工作日的简写，等价于
  `time = { days = ["M", "T", "W", "R", "F"], between = ["08:00", "12:00"] }`。
  需要限定 MWF/TR 或记录 `reason` 时使用完整字典。
- `section_prefix` 是不绑定课程的大小写无关前缀匹配，例如 `"TC"` 匹配
  `TC1`、`TC2`；不可与精确的 `section` 同时出现。
- 本项目以 `TC` section 编码表示网课。喜欢网课写 `section_prefix = "TC"` 和正权重，
  排斥网课写同一 selector 和负权重。不要用 TBA 或无时间记录推断网课，因为原始输入中的
  `F01`、普通 `001`、高中段等记录也可能是 TBA。
- 省略 `name` 的规则是全局规则。填写 `name` 时必须存在同名 `[[instructors]]` profile；
  不能依靠附近注释推断姓名。

## constraints.toml

这是学期级硬约束，不是偏好。需要保证某门课必须由指定教师承担或使用指定物理
教室时写：

```toml
[[rules]]
direction = "+"
course = "MATH 4123"
name = "Limperis, Thomas G."

[[rules]]
direction = "+"
course = "MATH 1113"
section = "006"
name = "Taylor, Teresa L."

[[rules]]
direction = "+"
course = "MATH 1113"
section = "F01"
room = "Corley 269"

# 同一条规则可以同时要求教师和教室
[[rules]]
direction = "+"
course = "STAT 2163"
section = "001"
name = "Bain, Leslie M."
room = ["Corley 103", "Corley 104"]

# 全局禁止 Friday 12:00-12:50
[[rules]]
direction = "-"
time = { days = ["F"], between = ["12:00", "12:50"] }
```

- `constraints.toml` 和 `preferences.toml` 都使用 `[[rules]]`，并共享
  `name`、`course`、`section`、`section_prefix`、`room`、`time` 字段。
- preference rule 必须写 signed `weight`，命中后进入软目标；constraint rule 不写
  `weight`，必须写 `direction = "+"` 或 `direction = "-"`。
- `direction = "+"` 表示受规则作用的候选必须匹配全部 `name/room/time` 条件；
  `direction = "-"` 表示禁止同时匹配全部这些条件的候选。因此负规则可以禁止单一值，
  也可以禁止特定教师、房间、时间的组合。
- `course` 使用严格的 `SUBJECT NUMBER` 格式；省略 `section` 时匹配该课程的
  全部 section，填写时只匹配该 section。
- `name` 在硬规则中表示必须使用的教师；该名称必须存在于 `persons.toml`，且其
  `courses` 必须包含规则中的课程。
- `course`、`section`、`section_prefix` 决定规则作用于哪些 section；`name`、`room`、
  `time` 是这些 section 的候选必须满足的值。
- 同一 selector 可以在一条规则中同时要求教师、教室和时间，也可以写成多条规则；
  所有匹配的硬规则都会累计执行。
- 一条省略 `section` 的课程规则和一条指定 `section` 的规则可以同时命中；两条都必须
  满足，不存在后者覆盖前者的隐式行为。互相矛盾的教师要求在加载配置时直接报错。
- `room` 可写一个字符串或字符串数组。求解器只生成命中指定位置的物理会议候选；
  Hybrid 的时间和位置由 `physical_section` 唯一决定，整项硬规则也只用这条物理权威
  记录判断一次。ONLINE companion 是导出表示，不是另一个待分配教室的会议。位置必须
  存在于 `locations.toml`。
- 求解器只生成满足规则的候选；`validate` 和最终报告把不满足的正/负规则分别报告为
  `constraint_positive`、`constraint_negative` 硬违规。
- `weight = 100` 或 `weight = -100` 仍然只是软偏好。“必须由某位教师承担”只写在
  学期 `constraints.toml` 的 `[[rules]]` 中，不在 preference 或 Python 代码中重复。
  其他“必须”或“禁止”的教师/教室分配也不能只依靠 preference rule。

## changes.toml

`inputs/<term>/changes.toml` 用于把清洗后的 change 前 draft 变成 initial。

```toml
departures = ["Old, Instructor"]
new_hires = ["New, Instructor"]

[[cancel_courses]]
subject = "MATH"
number = "2243"
# section = "001"  # 省略则取消该课程全部 section

[[new_courses]]
Subject = "STAT"
Number = "2163"
Section = "004"
Credits = 3
Instructor = ""
"Time Slot" = "MWF 2:00pm"
Duration = 50
Building = ""
Room = ""
```

`departures` 将其原课程改给 `Staff`，不删除课程；`new_hires` 只触发 initial
预放置，人员本身仍必须先写入 persons；新课空教师也填为 `Staff`。双行
原子课程要写两份 `[[new_courses]]`。

`initial` 命令一次性应用全部学期变动，并在 `work/<term>/initial/manifest.json`
记录 draft、changes 和 initial 的哈希。修改 `cancel_courses`、`departures`、
`new_hires` 或 `new_courses` 后都必须重建 initial，并从新的 initial 开始一条
新的 ver 链。solve 只验证取消课程已经不在输入中，不会在求解阶段偷偷增删课程；
否则直接失败并提示重建 initial。每个 ver 保存 initial 使用的
`applied_changes.toml` 快照。
`validate` 读取同一默认文件但不会改写 Schedule；若输入仍含取消课程，会报告
`HARD [cancelled_course]` 并返回非零状态。

## overrides.toml

每个由当前代码发布的 `out/<term>/verN/` 都自动包含一个绑定该版本的
`overrides.toml`。这是唯一允许在版本目录中人工编辑的文件；用于从该 ver
生成或刷新 `out/<term>/final/`。

完整示例：

```toml
term = "27S"
source_version = "ver10"

[[edits]]
course_id = "MATH 1113-F01"
record = 1
instructor = "Taylor, Teresa L."
time_slot = "TR 9:30am"
building = "Corley"
room = "269"

[[locks]]
course_id = "MATH 1113-F01"
record = 1
fields = ["instructor", "time", "building", "room"]

[[unassign]]
course_id = "STAT 2163-004"
placeholder = "Staff"
```

### 顶层字段

| 字段 | 类型 | 规则 |
|---|---|---|
| `term` | string | 生成模板时写入学期；final 必须与命令中的 term 相同 |
| `source_version` | string | 严格为 `ver数字`；final 必须与选定父版本相同 |
| `[[edits]]` | table array | 修改源 ver 的字段值 |
| `[[locks]]` | table array | 限制求解器不得再改指定字段 |
| `[[unassign]]` | table array | 把教师改成 Staff 类占位身份 |

解析器拒绝所有未知顶层键。通用 `solve --overrides` 允许省略 term/version，
但版本内自动生成的模板始终包含二者；final 工作流不要删除。

### edits

| 字段 | 是否必填 | 规则 |
|---|---|---|
| `course_id` | 是 | 精确格式 `SUBJECT NUMBER-SECTION`，必须存在于源 Schedule |
| `record` | 否 | 零起始非负整数；只操作双行原子课中的指定 CSV 记录 |
| `instructor` | 否 | string；使用 persons 中的正式姓名或 Staff 占位身份 |
| `time_slot` | 否 | string，例如 `MWF 9:00am`、`ONLINE`、`TBA` 或空字符串 |
| `building` | 否 | string；允许 `""` 清空 |
| `room` | 否 | string；允许 `""` 清空 |

每个 edit 至少设置一个可修改字段；字段值必须是字符串。省略 `record` 时，edit
通常同时作用于原子课全部记录。Hybrid 是例外：时间和教室默认修改唯一的物理行，
ONLINE companion 自动重建；教师仍同步整个原子课。多个 edit 按文件顺序执行，
每一步都会重新运行原子课类型验证，因此不能用一个暂时非法的中间状态等待后续
edit 修复；其他双行课程要整体修改时优先省略 record。

edit 只改变求解起点，不自动锁定。没有对应 lock 时，求解器可以再次改变这个
值。设置为空字符串是明确清空，不等于省略字段。

### locks

`fields` 必须是非空 string array，只接受：

| 值 | 锁定内容 |
|---|---|
| `instructor` | 教师或具体 Staff 身份 |
| `time` | 完整 `time_slot` |
| `building` | building |
| `room` | room |

lock 可以与 edit 配对，也可以单独使用：单独 lock 表示冻结源 ver 的现值。
省略 record 时锁定原子课全部记录；指定 record 时只锁对应记录。多个 lock 的
fields 会合并。锁定后如果候选生成找不到完全匹配的候选，求解以
`No legal candidates` 失败，不会偷偷放松锁。

### unassign

`course_id` 必填，`record` 规则与 edit 相同，`placeholder` 默认为 `Staff`。
它等价于 instructor edit。未锁定时 Staff 池仍会自动增加、合并和重编号；若
必须保留具体 `Staff N`，还要增加 `fields = ["instructor"]` 的 lock。

### final 前置检查

- 空模板（没有启用 edit/unassign 且没有 lock）拒绝生成 final；
- term/source_version 不匹配立即失败；
- course ID 或 record 不存在立即失败；
- 非法时间格式、非法双行组合在进入求解前失败；
- final 只读取 `out/<term>/verN/overrides.toml`，不读取 inputs 中的同名文件。

模板末尾自动包含该版本所有原子课及 record 对照表。完整工作流、累计变化
化简和输出目录见 [手调与版本](manual-adjustments.md)。
