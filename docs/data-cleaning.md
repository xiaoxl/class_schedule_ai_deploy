# 数据清洗

## 输入

`clean` 接受 `.csv`、`.xlsx`。旧二进制 `.xls` 不在依赖范围内，应先另存
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
uv run class-schedule --config config clean 27S `
  "inputs/27S/Course Schedule Report.csv"
```

默认生成：

```text
work/27S/normalized/
  sections.csv
  rejected_rows.csv
  validation.md
  source_manifest.json
```

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
`TBA` 是 arranged/tba；空时间是 arranged/unscheduled。当前旧领域 API 的
`Section.is_online` 为兼容仍把这三种都视作“无物理会议”，排冲突时都不
产生时间冲突。

## 错误和警告

- 行级解析失败写入 `rejected_rows.csv`，附 `Source Row` 和 `Error`。
- 行都能解析但无法组成合法原子课程时，写入 `validation.md` 的 grouping warning。
- 以 `P`、`ET`、`A` 开头的 concurrent section 会保留在清洗 CSV 中，
  但在构造 `Schedule` 时统一忽略；报告会给出数量。
- `source_manifest.json` 保存源路径、SHA-256、行数和规范列版本。
- 有拒绝行或 grouping warning 时命令退出码为 1，但审计文件仍完整生成。

进入 `draft` 或 `solve` 前，应保证 `rejected_rows.csv` 为空且
`validation.md` 没有 grouping warning。
