# 配置格式

所有主配置都使用 TOML。四个求解配置由 Pydantic 严格校验：未知键、重复
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
`locations.toml`。新学期应优先建立 `config/terms/<term>/`，避免覆盖旧学期
偏好。求解清单会记录实际读取的四个路径及哈希。

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
types = ["standard"]

[[calendar.blackouts]]
days = ["F"]
between = ["12:00", "13:00"]
reason = "department meeting"
```

`types` 只能是：

| 值 | 用途 |
|---|---|
| `standard` | 普通课，以及四学分课的 MWF 部分 |
| `four_credit_partial` | 四学分课的单日补充会议 |
| `coreq_short` | `MATH 1113`/`MATH 1110` 特殊短配对 |

`days` 只能由 `MTWRF` 组成，`duration_minutes > 0`，`starts` 不可为空。
blackout 与候选相交时该候选不生成。

## preferences.toml

这是学期数据，不是人员合同事实。

```toml
[[instructors]]
name = "Xiao, Xinli"
allow_overload = false
allow_back_to_back = true
max_back_to_back = 3
prefers_online = false
preferred_times = []
disliked_times = [
  { days = ["M", "W", "F"], between = ["08:00", "09:00"], reason = "no early MWF" },
]
preferred_locations = []
disliked_locations = ["Rothwell"]
preferred_courses = []
disliked_courses = ["MATH 2934"]

  [[instructors.rules]]
  course = "STAT 3113"
  room = "Corley 101"
  direction = "prefer"
  weight = 50

[[rules]]
course = "MATH 1113"
section = "F01"
room = "Corley 269"
direction = "prefer"
weight = 100
```

- `name` 必须存在于 persons。
- `allow_overload` 只改变超载软惩罚，不解除求解器绝对负载上界。
- `allow_back_to_back = false` 对每个相邻连续课惩罚；为 true 且设置
  `max_back_to_back = N` 时，从同日连续第 `N+1` 门开始逐门惩罚。
- `prefers_online = true` 会惩罚其每个物理课候选。
- `preferred_times`、`preferred_locations`、`preferred_courses` 匹配候选时各奖励
  5 分（目标成本减 5）；未匹配不会作为违规写入报告。
- `disliked_times`、`disliked_locations`、`disliked_courses` 匹配候选时各惩罚 5 分。
- rule 的 `course`、`section`、`room`、`time` 都是可选匹配条件；条件之间
  是 AND。`section` 必须与 `course` 同时出现。
- 顶层 `[[rules]]` 对所有教师生效；嵌套 `[[instructors.rules]]` 只对该教师。
- `direction` 只能是 `prefer` 或 `dislike`，`weight` 范围 0 到 100。
- prefer 以负成本奖励匹配候选；dislike 以正成本惩罚匹配候选。

## changes.toml

`inputs/<term>/changes.toml` 用于从上学期排课生成草案。

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

`departures` 将其原课程改给 `Staff`，不删除课程；`new_hires` 只触发草案
预放置，人员本身仍必须先写入 persons；新课空教师也填为 `Staff`。双行
原子课程要写两份 `[[new_courses]]`。

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
