# 手调、锁定和版本输出

## 覆盖文件

不要直接编辑 `starting.csv` 后失去修改来源。将人工决定写入独立 TOML：

```toml
term = "27S"
source_version = "ver10"

[[edits]]
course_id = "MATH 1113-F01"
instructor = "Taylor, Teresa L."
time_slot = "TR 9:30am"
building = "Corley"
room = "269"

[[locks]]
course_id = "MATH 1113-F01"
fields = ["instructor", "time", "building", "room"]

[[unassign]]
course_id = "STAT 2163-004"
placeholder = "Staff"
```

`term` 和 `source_version` 将配置绑定到一个明确的父版本。`final` 会在读取后
校验二者；把 `ver10` 的手调文件误用到 `ver9` 或其他学期时会立即失败，而不是
在错误的课表上继续求解。

`edits` 可设置 `instructor`、`time_slot`、`building`、`room` 的任意子集。
`locks.fields` 只接受 `instructor`、`time`、`building`、`room`。edit 改变当前
值，lock 决定求解器能否再次改变该值；只 edit 不 lock 表示“以此为起点，
仍允许优化”。`unassign` 等价于把教师 edit 为 `Staff`。

双行原子课程可加 `record = 0` 或 `record = 1`，下标为零起始。不写 record
表示对该原子课程的全部行操作。对 coreq 单独改一行时要确保组合仍合法；
覆盖层会重新运行类验证，非法编辑立即失败。

未锁定的 `Staff`、`Staff 2` 等属于自动占位池：冲突增加时系统会增加编号，
冲突消失时会自动合并。若确实要保留某个具体占位身份，需对该课程设置
`fields = ["instructor"]`；此时自动重着色关闭，以尊重人工锁定。

## 生成模板

每次正式发布 `verN` 时，系统都会自动生成：

```text
out/<term>/verN/overrides.toml
```

这是该版本专属、允许编辑的工作文件。默认是合法的 no-op 配置：所有
edit/lock 示例均被注释，不会意外修改课表。文件末尾列出源版本中的每个
原子课、零起始 record、实际 CSV course ID、教师、时间和教室，因此不需要
手写 course ID 或猜双行课程的 record 下标。

旧版本缺少模板时，才使用：

```powershell
uv run class-schedule --config config override-template 27S ver10
```

通用格式参考仍位于 `inputs/TEMPLATE/overrides.toml`。

## 刷新 final

例如编辑 `out/27S/ver10/overrides.toml`，取消所需 `[[edits]]`、`[[locks]]`
或 `[[unassign]]` 的注释并填写实际值，然后执行：

```powershell
uv run class-schedule --config config final 27S ver10 `
  --attempts 5 --seconds 45
```

`final` 自动完成以下工作：

1. 读取 `out/27S/ver10/27S_ver10.csv`；
2. 读取同目录的 `overrides.toml` 并校验 term/source_version；
3. 在完整 `Schedule` 上应用 edits，并把 locks 交给求解器；
4. 将完整结果原子写入或刷新 `out/27S/final/`；
5. 将 parent、输入/配置/override 哈希以及全部 CSV/Excel/report 产物写入 manifest。

`final` 不创建新的 `verN`。再次编辑同一个或另一个版本的内置 override 后运行，
`final` 会通过 staging + backup/rollback 刷新；失败时保留上一份完整 final。
`manifest.parent` 记录本次来源版本；自动生成的 `overrides.toml` 第一行也写明来源，
final 会原样保留该文件。空模板不能发布，
必须至少启用一项 edit/unassign 或 lock。

此契约只覆盖由当前严格分组代码生成、并能重新读成 `Schedule` 的版本。更早的
历史目录如果不满足当前原子课规则，会明确拒绝作为 final 来源，不做隐式修复。

同一能力可直接从 Python 调用：

```python
from class_schedule.schedule_run import publish_final

bundle = publish_final(
    "27S",
    "ver10",
    output_root="out",
    config_dir="config",
    attempts=5,
    time_limit_seconds=45,
)
print(bundle.output_dir, bundle.schedule_path, bundle.manifest_path)
```

底层 `solve --input ... --overrides ...` 仍可用于历史回填和特殊审计：

```powershell
uv run class-schedule --config config solve 27S `
  --input out/27S/ver3/27S_ver3.csv `
  --overrides out/27S/ver3/overrides.toml `
  --attempts 5 --seconds 45
```

正常人工后修订使用 `final`；`solve --overrides` 不会刷新 final。

`changes.csv` 不按父版本计算，而是累计比较该版本最开始使用的 start/change
baseline。每次生成 `verN` 时，系统把完整基线保存为同目录的 `baseline.csv`；
final 固定读取源 `verN/baseline.csv`，不读取以后可能被覆盖的
`out/<term>/starting.csv`。

累计变化不是把“start→ver”和“ver→final”两张表机械拼接，而是直接比较
`baseline Schedule` 与 `final Schedule`，所以会自动化简：同一字段的
`A→B` 加 `B→C` 只输出 `A→C`；`A→B` 后又改回 `A` 时不输出该字段。

例如 baseline、自动 ver 和手调 final 分别是：

| 阶段 | 时间 | 教室 |
|---|---|---|
| baseline | `MWF 9:00am` | `Corley 101` |
| ver10 | `MWF 10:00am` | `Corley 101` |
| final | `MWF 9:00am` | `Corley 102` |

final 的 `changes.csv` 只有：

```csv
Course ID,Field,Before,After
...,room,Corley 101,Corley 102
```

时间的 `9:00→10:00→9:00` 已抵消。类似地，教师 `A→B→C` 只保留
`A→C`。化简按 `(course identity, record, field)` 的最终首尾状态完成，不按
文本行顺序拼接，也不按 CSV 行重复统计双行原子课。

`changes.csv` 固定列为 `Course ID,Field,Before,After`，Field 只有：

| Field | 含义 |
|---|---|
| `status` | 课程记录相对 baseline 新增或删除 |
| `instructor` | 教师变化 |
| `time` | 完整 time slot 变化 |
| `room` | 完整 `Building Room` 变化；building 或 room 任一变化都归入此项 |

它不报告标题、CRN、容量等非求解字段变化；这些字段应在 clean/draft 输入阶段
审计，而不是通过 final 手调。`changes.csv` 的用途是描述最终排课状态相对
baseline 的可执行字段差异。

底层 solve 如果使用新的 start，应明确传入：

```powershell
uv run class-schedule --config config solve 27S `
  --input out/27S/ver6/27S_ver6.csv `
  --baseline work/27S/ver7/draft/starting.csv
```

manifest 同时记录 `input`、原始 `change_baseline` 的路径/哈希以及
`baseline.csv` 快照名。report 的 Before/After、Teaching loads 和 Simplified
Changes 均以该快照为 Before。

## 版本目录

每次 solve 原子写入：

```text
out/27S/ver10/
  27S_ver10.csv       最终排课，一行一个 Section
  27S_ver10_instructor.xlsx  按教师分 worksheet 的周课表
  27S_ver10_room.xlsx        按教室分 worksheet 的周课表
  report.md          指标、负载、变更、遗留问题
  attempts.csv       所有独立求解尝试的状态和指标
  changes.csv        相对 start/change baseline 的累计字段级变化
  baseline.csv       生成该版本时使用的完整 start/change baseline 快照
  overrides.toml     允许编辑的、绑定 ver10 的 final 手调工作文件
  applied_overrides.toml  生成 ver10 时实际使用的覆盖文件，不可编辑
  manifest.json      输入、配置、覆盖、输出文件哈希和求解参数
```

`out/27S/final/` 具有同样结构，主文件名为 `27S_final.csv`、
`27S_final_instructor.xlsx` 和 `27S_final_room.xlsx`。其中 `overrides.toml`
是本次从父版本读取的精确副本，而不是下一轮模板。

教师和教室 workbook 与主 CSV 来自同一个最终 `Schedule`，并在同一次 staging
发布中生成。教师文件包含所有有教师归属的记录，每位教师一个 worksheet；教室
文件排除 `ONLINE`/`TBA`/空时间记录，只为有实体教室的记录按完整
`Building Room` 建立 worksheet。两个文件都写入 `manifest.json` 的 `files`
哈希表，不是从发布后的 CSV 另行推断或手工维护。

manifest 包含 term/version/parent、UTC 创建时间、源文件 SHA-256、实际配置
路径与 SHA-256、实际应用覆盖哈希、选中 attempt、solver status、
objective、bound、random seed、时间预算、hard/soft/overload 指标以及所有
产物哈希。版本目录的 `overrides.toml` 是唯一明确允许修改、且不进入 immutable
files 哈希表的工作文件；其余产物以及 `applied_overrides.toml` 均不可编辑。

manifest schema v3 的关键字段：

| 字段 | 含义 |
|---|---|
| `term`, `version`, `parent` | 发布身份；final 的 version 是 `final`，parent 是源 ver |
| `input.path/sha256` | 本次求解实际读取的 ver/start CSV |
| `change_baseline.path/sha256` | 首次发布时原始 baseline 的来源和哈希 |
| `change_baseline.snapshot` | 当前目录内固定为 `baseline.csv` 的快照名 |
| `configuration.version/files` | 四个实际配置文件的聚合版本、路径与哈希 |
| `applied_overrides_sha256` | 本次实际应用配置的哈希 |
| `override_workspace` | override 路径、是否 mutable、绑定的 source version |
| `selected_attempt`, `solver`, `validation` | 选优结果、求解预算和最终检查指标 |
| `files` | 所有不可变输出文件名到 SHA-256 的映射 |

在 `verN` 中，mutable `overrides.toml` 故意不在 `files`；在 final 中它是本次
使用配置的发布副本，因此 `mutable=false` 并进入 `files`。两类目录中的
`applied_overrides.toml`、`baseline.csv`、CSV、Excel、report、attempts 和
changes 都进入 `files`。

## 检查和比较

```powershell
uv run class-schedule --config config validate 27S out/27S/ver10/27S_ver10.csv

uv run class-schedule --config config diff 27S `
  out/27S/ver9/27S_ver9.csv out/27S/ver10/27S_ver10.csv `
  --output work/27S/diff-ver9-ver10.csv
```

`validate` 不修改排课；hard violation 非零时退出码为 1。`diff` 比较教师、
时间和完整 building/room，适合人工复核。正式采用一个版本前，至少检查：

1. 清洗无 rejected/grouping warning；
2. solver status 和 objective/bound；
3. hard violations 为 0；
4. `Staff`, `Staff 2` 等占位身份是否仍存在；
5. 教师 load、soft findings、`changes.csv`；
6. overrides 是否完整表达所有人工决定。
