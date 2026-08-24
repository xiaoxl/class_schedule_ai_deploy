# Class Schedule

面向学期排课的离线流水线：清洗 CSV/XLSX，构造原子课程，应用学期变更和
教师偏好，使用 OR-Tools CP-SAT 求解，再输出不可覆盖、可审计、便于手调的
`out/<term>/verN/` 不可变版本目录，以及可重复刷新的 `out/<term>/final/` 发布目录。

## 快速开始

```powershell
uv sync

uv run class-schedule --config config initialize 27S `
  "inputs/27S/Course Schedule Report.csv"

uv run class-schedule --config config draft 27S `
  work/27S/normalized/sections.csv inputs/27S/changes.toml

uv run class-schedule --config config solve 27S `
  --input work/27S/draft/starting.csv `
  --baseline work/27S/draft/starting.csv --attempts 5 --seconds 45

# 编辑 out/27S/ver10/overrides.toml，启用 edit/lock 后刷新 final
uv run class-schedule --config config final 27S ver10
```

`initialize` 在清洗的同时，直接从尚未应用 `changes.toml` 的原输入排课生成
`inputs/27S/Course Schedule Report_instructor.xlsx` 和
`inputs/27S/Course Schedule Report_room.xlsx`。这两份表是输入快照视图，不是 draft
或 solver 结果。

`verN` 是不覆盖的自动求解快照；`final` 是从指定 ver 应用人工调整后可反复
刷新的发布目录。空 override 不会生成 final。final 的 `changes.csv` 始终直接
比较父 ver 保存的 `baseline.csv` 与最终 Schedule，因此中间变动会自动抵消或
合并，而不是把 ver 和手调的两张 changes 表直接拼接。

输出示例：

```text
out/27S/ver10/
  27S_ver10.csv
  27S_ver10_instructor.xlsx
  27S_ver10_room.xlsx
  report.md
  attempts.csv
  changes.csv              # 从最初 baseline 到当前结果的化简累计变动
  baseline.csv             # 该版本使用的 baseline 快照
  overrides.toml          # 可编辑，随后用于刷新 final
  applied_overrides.toml  # 生成本 ver 时实际使用的配置
  manifest.json
```

## 文档

- [架构和完整流程](docs/index.md)
- [如何清洗数据及规范格式](docs/data-cleaning.md)
- [所有配置文件格式](docs/configuration.md)
- [原子分组、硬规则、软规则和计分](docs/scheduling-rules.md)
- [人工编辑、字段锁定、版本输出和比较](docs/manual-adjustments.md)
- [开课需求分析](docs/demand-analysis.md)

## 测试

```powershell
uv run python -m unittest discover -s tests
```

`class-schedule` CLI 是离线生产入口。Web 界面仍是可部署的辅助入口，并与 CLI
共享同一套 `Schedule`、solver、校验和 Excel 导出实现。
