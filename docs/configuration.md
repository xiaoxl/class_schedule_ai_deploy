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
- 当前 `preferred_times`、`preferred_locations`、`preferred_courses` 仅记录
  信息，不计分。需要实际影响求解时必须写 `direction = "prefer"` 的 rule。
- `disliked_*` 会计分。
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

该文件属于一次求解请求，格式详见 [手调与版本](manual-adjustments.md)。
