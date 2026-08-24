# 数据清洗

## 输入

生产流程的第一步是 `initialize`；它先调用同一套 `clean` 能力，再发布 change 前
`draft.csv` 以及原输入的教师和教室周课表。`initialize`/`clean` 接受 `.csv`、`.xlsx`。旧二进制 `.xls` 不在依赖范围内，应先另存
为 `.xlsx`。空行被删除；每个非空数据行单独
解析，所以一行错误不会阻止其他行输出。

必需语义字段是 `Subject`、`Number`、`Section`。物理上课记录还必须能
得到时间和时长：

- 时间可写成 `Time Slot = "MWF 9:00am"`，或 `Days` + `Start`；
- 时长可写 `Duration`，或由 `Start` + `End` 计算；
- `ONLINE`、`TBA` 和空白时间不要求 `Duration`。

代码识别的主要别名如下。未知列不会参与排课，但拒绝行中会保留，方便
追查源数据。

| 规范列 | 接受的常见源列 |
|---|---|
| `Time Slot` | `TimeSlot`, `time_slot` |
| `Days` | `Meeting Days`, `Meeting_Days` |
| `Start` | `Beginning Time` |
| `End` | `Ending Time` |
| `Duration` | `Duration Minutes`, `duration_minutes` |
| `Instructor` | `Instructor Name` |
| `Type` | `Schedule Type` |
| `Title` | `Catalog Title`, `Section Title` |
| `Credits` | `Course Credit Hours` |
| `Cross-List` | `Cross List`, `XL Group Code`，也忽略大小写和空格/连字符/下划线差异 |

ATU `Course Schedule Report` 的 `Meeting_Times` 可写成
`9:30 am-10:50 am`，清洗器会拆成 `Start`/`End`。`none`、`nan`、`nat`、
`unassigned` 均按空值处理。

## 输出格式

```powershell
uv run class-schedule --config config initialize 27S `
  "inputs/27S/Course Schedule Report.csv"
```

默认生成：

```text
work/27S/normalized/
  sections.csv
  rejected_rows.csv
  validation.md
  source_manifest.json

work/27S/draft/
  draft.csv
```

同时在原输入所在文件夹生成：

```text
inputs/27S/
  Course Schedule Report.csv
  Course Schedule Report_instructor.xlsx
  Course Schedule Report_room.xlsx
```

`draft.csv` 和两本 Excel 直接来自该原输入经规范化、人员别名解析和原子分组后的
同一个 `Schedule`。
此时尚未读取 `changes.toml`，也没有新员工预放置、preference、override 或 solver
变动，因此它们是 change 前输入的周课表变形。存在拒绝行或 grouping warning 时，
清洗审计包仍会写出，但不会发布可能不完整的 draft 和两本 Excel。`clean` 子命令保留为只需
清洗审计包、不需要输入视图时的底层入口。

`sections.csv` 的列和顺序固定：

| 列 | 格式和含义 |
|---|---|
| `Subject` | 大写，如 `MATH` |
| `Number` | 文本，如 `0803`，不要转成数字 |
| `Section` | 文本，如 `001`, `F01`, `TC1` |
| `Type` | 可选的教学类型 |
| `Title` | 可选课程名 |
| `Credits` | 可选小数；缺少时业务模型可按课程号末位推断，`1110` 特例为 2 |
| `Instructor` | 原名或经 `persons.toml` 别名解析后的正式名 |
| `Delivery Mode` | `in_person`, `online`, `arranged` |
| `Scheduling Status` | `scheduled`, `tba`, `unscheduled` |
| `Time Slot` | `MWF 9:00am`、`TR 9:30am`、`ONLINE`、`TBA` 或空 |
| `Duration` | 分钟，物理课必须为正数 |
| `Days` | `M T W R F` 的组合；星期四用 `R` |
| `Start`, `End` | ISO 时间，如 `09:00:00` |
| `Building`, `Room` | 分列保存；`Unassigned` 清为空 |
| `Cross-List` | 显式跨列组编号 |
| `CRN` | 注册记录连接键，排课本身不使用，需求分析使用 |
| `Seats Available` | 从 `Seats Available`/`Seats_Avail`/`Seats Avail` 保留 |
| `Source Row` | 原表行号；首条数据为 2，因为第 1 行是表头 |

三种无物理时间状态不会再被混为一个字符串：`ONLINE` 是在线且已安排；
`TBA` 是 arranged/tba；空时间是 arranged/unscheduled。领域模型中的
`Section.is_online` 是兼容名称，实际表示这三种“无物理会议”记录；排冲突时都不
产生时间冲突。

`MATH 5173`/`STAT 4173` 是代码内置的 cross-list 特例。清洗器保持源文件的
`Cross-List` 为空；构造 `Schedule` 时，只要二者 section 相同，就自动组成
`CrossListingClass`。不需要配置，也不会向清洗结果写入人工标记。

Hybrid 的无 room 行必须同时没有物理会议时间（`ONLINE`、`TBA` 或空时间）；
物理行必须有 room。两个都有物理时间但其中一个漏填 room 会作为原子分组错误，
不会被当成 Hybrid 掩盖数据问题。

## 错误和警告

- 行级解析失败写入 `rejected_rows.csv`，附 `Source Row` 和 `Error`。
- 行都能解析但无法组成合法原子课程时，写入 `validation.md` 的 grouping warning。
- 以 `P`、`ET`、`A` 开头的 concurrent section 会保留在清洗 CSV 中，
  但在构造 `Schedule` 时统一忽略；报告会给出数量。
- `source_manifest.json` 保存源路径、SHA-256、行数和规范列版本。
- 有拒绝行或 grouping warning 时命令退出码为 1，但审计文件仍完整生成。

进入 `initial` 前，应保证 `rejected_rows.csv` 为空且
`validation.md` 没有 grouping warning。

## 进入排课对象

清洗完成后的 `sections.csv` 仍是审计和交换格式，不是后续规则直接操作的
对象。磁盘入口的完整职责和禁止事项见[架构文档的 `schedule_io.py` 文件边界](index.md#schedule_iopy-文件边界)。
`draft`、`initial`、`solve`、`validate` 和 `diff` 都先调用：

```python
schedule = read_schedule(
    path,
    persons=config.persons,
)
```

返回值是已经完成原子分组的 `Schedule`。此后统计、调课和求解不得直接遍历
CSV/DataFrame 行。输出 CSV 是 `Schedule.to_dataframe()` 的展开表示，因此
cross-list 等双行原子课会重新出现两行，但教学负载仍按原子对象只算一次。

## draft 到 initial

`draft.csv` 严格是 change 前快照，不读取 `changes.toml`。随后执行：

```powershell
uv run class-schedule --config config initial 27S `
  work/27S/draft/draft.csv inputs/27S/changes.toml
```

得到 `work/27S/initial/initial.csv`、`initial_noadding.csv`、教师/教室 Excel 和
`manifest.json`。manifest 固定记录 draft、changes 和 initial 的 SHA-256；正常
solve 会验证这些哈希，因此修改 changes 后必须重建 initial。
