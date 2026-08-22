# 排课系统架构与操作入口

本项目当前的主流程是离线、可复现的学期排课流水线。网络界面不是当前
交付边界。

```text
原始 CSV/XLSX
  -> clean: 固定字段、拒绝坏行、保存源文件哈希
  -> draft: 上学期滚动、停开课、离职、新聘教师初排
  -> atomic grouping: 将 1/2 行识别为一个不可拆的教学单元
  -> solve: 读取人员、房间、日历、偏好、手调锁定并运行 CP-SAT
  -> validate/diff: 检查冲突并比较版本
  -> out/<term>/<version>/: CSV、报告、变更、尝试记录、清单
```

## 目录职责

| 目录 | 职责 | 是否手工编辑 |
|---|---|---|
| `inputs/<term>/` | 原始导出和该学期 `changes.toml` | 是 |
| `work/<term>/normalized/` | 清洗中间产物 | 否 |
| `work/<term>/draft/` | 可求解的起始排课 | 通常否 |
| `config/catalog/` | 推荐位置：跨学期人员与房间事实 | 是 |
| `config/terms/<term>/` | 推荐位置：学期偏好与时间表 | 是 |
| `config/*.toml` | 旧平铺布局，仍作为兼容回退 | 是 |
| `out/<term>/<version>/` | 不覆盖的发布结果 | 只编辑其中的覆盖文件副本作参考 |
| `src/class_schedule/` | 与学期无关的代码 | 开发时 |

配置解析按文件逐个回退，因此可以渐进迁移：`persons.toml` 和
`locations.toml` 优先从 `config/catalog/` 读取；`preferences.toml` 和
`timeslot.toml` 优先从 `config/terms/<term>/` 读取；缺少时才读取
`config/` 根目录同名文件。

## 标准命令

`--config` 是全局参数，放在子命令前面。

```powershell
uv sync

uv run class-schedule --config config clean 27S `
  "inputs/27S/Course Schedule Report.csv"

uv run class-schedule --config config draft 27S `
  work/27S/normalized/sections.csv inputs/27S/changes.toml

uv run class-schedule --config config solve 27S `
  --input work/27S/draft/starting.csv --attempts 5 --seconds 45

uv run class-schedule --config config validate 27S out/27S/ver4/27S_ver4.csv

uv run class-schedule --config config diff 27S `
  out/27S/ver3/27S_ver3.csv out/27S/ver4/27S_ver4.csv `
  --output out/27S/ver4/diff-from-ver3.csv
```

`clean` 默认输出到 `work/<term>/normalized/`，`draft` 默认输出到
`work/<term>/draft/`，`solve` 默认写入下一个不存在的
`out/<term>/verN/`。任何已有版本目录都不会被覆盖。

## 代码依赖关系

| 模块 | 只负责什么 | 依赖的规则/数据 |
|---|---|---|
| `record_utils.py` | 列名、空值、日期时间的基础规范化 | 无配置 |
| `data_cleaning.py` | 行级清洗、拒绝表、清洗清单 | 可选 `persons.toml` 别名 |
| `class_model.py` | `Section` 和 1/2 行原子课程类型 | 固定代码规则 |
| `schedule_model.py` | 整表分组、编辑、冲突与软偏好报告 | persons/preferences 对象 |
| `term_builder.py` | 上学期向新学期滚动 | `changes.toml` |
| `starting_template.py` | 新聘教师预放置、Staff 分色 | `persons.toml` |
| `solver/config.py` | 四类配置解析、交叉引用校验、哈希 | TOML 文件 |
| `solver/candidates.py` | 教师/时间/房间候选与候选成本 | 全部 SolverConfig、locks |
| `solver/constraints.py` | CP-SAT 的组合、冲突、负载约束 | 候选、偏好 |
| `solver/engine.py` | 建模、求解、随机种子、结果状态 | candidates/constraints |
| `overrides.py` | 手调值和字段锁 | `overrides.toml` |
| `schedule_run.py` | 多次求解、选优、原子发布版本 | 以上全部 |

详细说明见 [数据清洗](data-cleaning.md)、[配置格式](configuration.md)、
[排课规则](scheduling-rules.md)、[手调与版本](manual-adjustments.md) 和
[开课需求分析](demand-analysis.md)。
