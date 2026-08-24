# 排课系统架构与操作入口

本项目当前的主流程是离线、可复现的学期排课流水线。网络界面不是当前
交付边界。

```text
原始 CSV/XLSX
  -> read_table(): 只负责文件格式和文本类型
  -> initialize: clean + 发布 change 前的 instructor/room 输入视图
  -> clean: 固定字段、拒绝坏行、保存源文件哈希
  -> normalized sections.csv
  -> read_schedule(): 构造 Section，再分组为 Schedule[原子课程]
  -> draft/override: 只修改 Schedule 对象
  -> evaluate_schedule(): 行数、原子课数、负载、hard、soft
  -> solve: 从 Schedule 建立 CP-SAT，返回新的 Schedule
  -> evaluate/diff/export
  -> out/<term>/verN/: 不覆盖快照 + baseline + 可编辑 override 模板
  -> 编辑 verN/overrides.toml
  -> final: 从 verN 应用 edit/lock 并重新求解
  -> out/<term>/final/: 可反复刷新的最终 CSV/Excel/报告/清单
```

## 唯一数据主线

`DataFrame` 只是文件边界，不是排课业务模型。`schedule_io.read_schedule()`
统一执行 `CSV/XLSX -> DataFrame(dtype=str) -> Schedule.from_dataframe()`；后者
规范每行并构造 `Section`，再按固定优先级组合为 `NormalClass`、
`FourCreditClass`、`HybridClass`、`CrossListingClass` 或 `CoreqClass`。从函数
返回开始，业务代码只能处理 `Schedule`/`Class`/`Section`，不能按 CSV 行重新
推断学分、冲突或课程关系。

### `schedule_io.py` 文件边界

`schedule_io.py` 是排课 CSV/XLSX 的唯一磁盘表格入口，集中保证：

- 只接受 `.csv` 和 `.xlsx`，其他格式立即报错；
- 全部字段用 `dtype=str` 读取，保留 `0803`、`001` 等前导零；
- 构造业务对象前删除全空行；
- 把 `persons.toml` 人员对象交给分组层统一解析教师别名；
- 调用唯一的 `Schedule.from_dataframe()`，完成 `Section` 构造和所有原子课分组；
- 返回已经分组完成的 `Schedule`，不向业务层返回原始 CSV 行。

cross-list 也在原子分组阶段统一识别，但不是向 DataFrame“注入标记”。显式
`Cross-List` 按源值分组；`MATH 5173`/`STAT 4173` 由
`CrossListingClass.COURSE_PAIRS` 按相同 section 自动识别，输入和输出的
`Cross-List` 都可以保持空白。

CLI 的 `initialize`、`draft`、`solve`、`validate`、`diff`，版本发布和 starting template
都通过 `read_schedule()` 取得对象；term builder 只接收已经分组的 `Schedule`。
负载统计、偏好评估、
冲突检查、人工调整和 solver 不得依赖 `pandas`，也不得自行读取排课文件。

Excel 周课表不另建数据模型。报表实现集中在
`Schedule.to_instructor_excel()` 和 `Schedule.to_room_excel()`：Web 下载和
`schedule_run` 的版本发布都调用这两个方法。教师/教室分组、原子课同行合并、
冲突标红及 `ONLINE`/`TBA` 展示规则只在这一处实现。

离线流程中只有两个模块会在分组之外保留表格级数据：`clean` 要保存拒绝行、
源行号和 CRN 等审计字段；开课需求分析要用 CRN 连接 Cube 人数。两者在涉及“课程数/原子课”时仍
调用同一个 `Schedule.from_dataframe()` 分组器，不复制原子课程规则。

Web 上传不落盘：它从请求字节以 `dtype=str` 构造短生命周期 DataFrame，删除全空行后
立即调用同一 `Schedule.from_dataframe()`。这不是第二个磁盘入口，后续 Web 统计、求解和
Excel 输出同样只处理 `Schedule`。

核心不变量：

1. 一个磁盘排课文件每次进入业务层都必须经过 `read_schedule()`；
2. 所有教学负载由 `teaching_loads(Schedule)` 计算，不能按输出行求和；
3. 所有确定性检查由 `evaluate_schedule(Schedule, ...)` 汇总；
4. draft、人工 edit/lock、Staff 重着色和 solver 的输入输出都是 `Schedule`；
5. 只有发布或中间审计时才用 `Schedule.to_dataframe()` 展开回 CSV；再次读入时
   必须重新经过原子分组。

## 目录职责

| 目录 | 职责 | 是否手工编辑 |
|---|---|---|
| `inputs/<term>/` | 原始导出、change 前自动 Excel 视图和学期滚动 `changes.toml` | 原始文件和 changes 是；自动 Excel 否 |
| `work/<term>/normalized/` | 清洗中间产物 | 否 |
| `work/<term>/draft/` | 可求解的起始排课 | 通常否 |
| `config/catalog/` | 推荐位置：跨学期人员与房间事实 | 是 |
| `config/terms/<term>/` | 推荐位置：学期偏好与时间表 | 是 |
| `config/*.toml` | 旧平铺布局，仍作为兼容回退 | 是 |
| `out/<term>/verN/` | 不覆盖的求解快照；内含 final 手调模板 | 只编辑 `overrides.toml` |
| `out/<term>/final/` | 从指定 ver 手调后反复刷新的最终发布 | 否 |
| `src/class_schedule/` | 与学期无关的代码 | 开发时 |

配置解析按文件逐个回退，因此可以渐进迁移：`persons.toml` 和
`locations.toml` 优先从 `config/catalog/` 读取；`preferences.toml` 和
`timeslot.toml` 优先从 `config/terms/<term>/` 读取；缺少时才读取
`config/` 根目录同名文件。

## 标准命令

`--config` 是全局参数，放在子命令前面。

```powershell
uv sync

uv run class-schedule --config config initialize 27S `
  "inputs/27S/Course Schedule Report.csv"

uv run class-schedule --config config draft 27S `
  work/27S/normalized/sections.csv inputs/27S/changes.toml

uv run class-schedule --config config solve 27S `
  --input work/27S/draft/starting.csv `
  --baseline work/27S/draft/starting.csv --attempts 5 --seconds 45

uv run class-schedule --config config final 27S ver10 `
  --attempts 5 --seconds 45

uv run class-schedule --config config validate 27S out/27S/ver10/27S_ver10.csv

uv run class-schedule --config config diff 27S `
  out/27S/ver9/27S_ver9.csv out/27S/ver10/27S_ver10.csv `
  --output work/27S/diff-ver9-ver10.csv
```

`initialize` 和底层 `clean` 默认输出到 `work/<term>/normalized/`；`initialize`
还会把 `<输入stem>_instructor.xlsx`、`<输入stem>_room.xlsx` 写在原输入文件旁边。
这两本工作簿只由原输入清洗并分组后的 `Schedule` 生成，函数接口不接受
`changes.toml`、preferences、overrides 或 solver 结果，因而严格表示 change 前快照。
`draft` 默认输出到
`work/<term>/draft/`，`solve` 默认写入下一个不存在的
`out/<term>/verN/`：扫描所有名称严格为 `ver数字` 的目录，然后使用
`max(N) + 1`。归档目录如 `ver4_validation` 不参与编号。任何已有版本目录
都不会被覆盖；`--version` 只用于明确的历史回填，正常运行不要填写。
每个新 `verN` 都自动带有可编辑的 `overrides.toml` 和 course/record 对照表；
`final` 从指定父版本读取该文件、应用 edit/lock，并原子刷新
`out/<term>/final/`，不会增加版本号。

## ver 与 final

`verN` 和 `final` 是两个不同的发布通道：

| 属性 | `verN` | `final` |
|---|---|---|
| 目的 | 保存一次自动求解快照 | 保存人工决定后的当前最终版本 |
| 是否覆盖 | 否；自动追加下一号 | 是；每次原子刷新同一目录 |
| 输入 | starting/draft 或显式 input | 指定 `verN` 的 CSV 和内置 overrides |
| parent | 从 input 推断或显式指定 | 必须是命令选择的源 `verN` |
| overrides.toml | 可编辑工作文件，不计入 immutable files 哈希 | 本次实际使用配置的只读副本 |
| applied_overrides.toml | 生成该 ver 时实际使用的配置 | 与本次 final 实际配置一致 |
| baseline.csv | 该 ver 的最初 change baseline 快照 | 从父 ver 继承的同一逻辑基线 |
| changes.csv | baseline 到 ver 的直接化简 diff | baseline 到 final 的直接化简 diff |

final 的累计变化不是连接两张 CSV。系统保留父 ver 的 `baseline.csv`，然后直接
调用领域层 diff 比较 `baseline Schedule` 与 `final Schedule`。因此同一字段
`A→B→C` 只留下 `A→C`，`A→B→A` 完全消失；新增后又删除且首尾都不存在的课程
也不会留下中间噪声。

`out/<term>/starting.csv` 以后即使被新流程覆盖，也不会改变已有 ver/final 的
累计变化基线。final 缺少父 ver 的 `baseline.csv` 时明确失败，不退回当前
starting，也不猜测旧版本数据。

## 代码依赖关系

| 模块 | 只负责什么 | 依赖的规则/数据 |
|---|---|---|
| `record_utils.py` | 列名、空值、日期时间的基础规范化 | 无配置 |
| `data_cleaning.py` | 行级清洗、拒绝表、清洗清单 | 可选 `persons.toml` 别名 |
| `class_model.py` | `Section` 和 1/2 行原子课程类型 | 固定代码规则 |
| `schedule_io.py` | CSV/XLSX 到原子 `Schedule` 的唯一磁盘入口 | persons 别名 |
| `schedule_model.py` | 整表分组、编辑、负载和统一评估 | persons/preferences 对象 |
| `term_builder.py` | 上学期向新学期滚动 | `changes.toml` |
| `starting_template.py` | 新聘教师预放置、Staff 分色 | `persons.toml` |
| `solver/config.py` | 四类配置解析、交叉引用校验、哈希 | TOML 文件 |
| `solver/candidates.py` | 教师/时间/房间候选与候选成本 | 全部 SolverConfig、locks |
| `solver/constraints.py` | CP-SAT 的组合、冲突、负载约束 | 候选、偏好 |
| `solver/engine.py` | 建模、求解、随机种子、结果状态 | candidates/constraints |
| `overrides.py` | 手调值、字段锁、term/source_version 校验和模板内容 | `overrides.toml` |
| `schedule_run.py` | 多次求解、baseline 快照、final API、选优和原子发布 | 以上全部 |

详细说明见 [数据清洗](data-cleaning.md)、[配置格式](configuration.md)、
[排课规则](scheduling-rules.md)、[手调与版本](manual-adjustments.md) 和
[开课需求分析](demand-analysis.md)。
