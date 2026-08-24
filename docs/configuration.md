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
days = "MWF"
duration_minutes = 50
starts = ["08:00", "09:00", "10:00"]
roles = ["normal", "hybrid_physical", "cross_listing", "coreq"]

[[calendar.meeting_patterns]]
days = "MW"
duration_minutes = 50
starts = ["12:00"]
roles = ["coreq_supplement"]

[[calendar.blackouts]]
days = ["F"]
between = ["12:00", "12:50"]
reason = "department meeting"
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

`days` 只能由 `MTWRF` 组成，`duration_minutes > 0`，`starts` 不可为空。
blackout 与候选相交时该候选不生成。
`changes.toml` 新增的物理 section 也使用这里的 pattern 和 blackout 做严格校验；
例如标准 MWF 50 分钟课不能写成 `11:50`，Friday `12:00-12:50` blackout
也绝对禁止 `MWF 12:00pm`。`MATH 0803`/`MATH 1003` 和
`MATH 0903`/`MATH 1113` 两类 coreq 都只能使用 standard pattern；coreq 中学分较低的
辅助记录可以使用 `MW 12:00pm`。在当前数据中，这对应 `MATH 1110` 记录，但规则本身
不识别这个课程号。

## preferences.toml

这是学期数据，不是人员合同事实。

```toml
# Xiao, Xinli
[[instructors]]
name = "Xiao, Xinli"
allow_overload = false
allow_back_to_back = true
max_back_to_back = 3
prefers_online = { weight = 20 }

[[rules]]
name = "Xiao, Xinli"
preferred_time = "09:00-13:00"
weight = 50

[[rules]]
name = "Xiao, Xinli"
disliked_course = "MATH 2934"
weight = 50

[[rules]]
name = "Xiao, Xinli"
preferred_course = "STAT 3113"
preferred_room = "Corley 101"
weight = 50

[[rules]]
name = "Xiao, Xinli"
disliked_section_prefix = "TC"
weight = 10

# Global: no name means the rule applies regardless of instructor.
[[rules]]
preferred_course = "MATH 1113"
preferred_section = "F01"
preferred_room = "Corley 269"
weight = 100
```

- `[[instructors]]` 是人员 profile，只存 `allow_overload`、连排参数和
  `prefers_online`；`name` 必须存在于 persons。
- `allow_overload` 只改变超载软惩罚，不解除求解器绝对负载上界。
- `allow_back_to_back = false` 对每个相邻连续课惩罚；为 true 且设置
  `max_back_to_back = N` 时，从同日连续第 `N+1` 门开始逐门惩罚。
- `prefers_online = { weight = N }` 会对其每个物理课候选增加 `N` 分成本；省略表示
  没有在线偏好。
- 每条 `[[rules]]` 都是独立字典。`name` 决定教师作用域；同一人的规则可以连续放在
  `# Name` 注释下便于阅读，但注释没有任何配置意义。
- 每条规则必须选择一个方向：全部使用 `preferred_*` 字段，或全部使用 `disliked_*`
  字段，不可混用。`weight` 必填且范围为 `0-100`。匹配 preferred 规则时从候选成本
  减去 `weight`，匹配 disliked 规则时增加 `weight`；同一候选命中多条规则时累加。
- prefer 未命中不是违规；dislike 命中会写入软问题报告。
- selector 内的 `course`、`section`、`section_prefix`、`room`、`time` 是可选匹配条件，
  同一字典内按 AND 组合。selector 至少需要一个条件，`section` 必须与 `course` 同时出现。
- `preferred_time = "8-12"`（或 `disliked_time`）是所有工作日的简写，等价于
  `preferred_time = { days = ["M", "T", "W", "R", "F"], between = ["08:00", "12:00"] }`。
  需要限定 MWF/TR 或记录 `reason` 时使用完整字典。
- `section_prefix` 是不绑定课程的大小写无关前缀匹配，例如 `"TC"` 匹配
  `TC1`、`TC2`；不可与精确的 `section` 同时出现。
- 省略 `name` 的规则是全局规则。填写 `name` 时必须存在同名 `[[instructors]]` profile；
  不能依靠附近注释推断姓名。

## constraints.toml

这是学期级硬约束，不是偏好。需要保证某门课必须由指定教师承担时写：

```toml
[[required_instructors]]
course = "MATH 4123"
instructor = "Limperis, Thomas G."

[[required_instructors]]
course = "MATH 1113"
section = "006"
instructor = "Taylor, Teresa L."
```

- `course` 使用严格的 `SUBJECT NUMBER` 格式；省略 `section` 时匹配该课程的
  全部 section，填写时只匹配该 section。
- `instructor` 必须存在于 `persons.toml`，且其 `courses` 必须包含该课程。
- 同一个 `(course, section)` 不得重复。
- 求解器只为匹配课程生成该教师的候选；`validate` 和最终报告也会把不匹配结果
  报告为 `required_instructor` 硬违规。
- `weight = 100` 仍然只是软偏好。凡是“必须”或“禁止”的教师分配，不应写成
  `preferences.toml` 的 preferred/disliked rule。

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
同时作用于原子课全部记录。多个 edit 按文件顺序执行，每一步都会重新运行原子
课类型验证，因此不能用一个暂时非法的中间状态等待后续 edit 修复；双行课程要
整体修改时优先省略 record。

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
