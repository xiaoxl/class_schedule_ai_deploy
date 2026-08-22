# Class Schedule

面向学期排课的离线流水线：清洗 CSV/XLSX，构造原子课程，应用学期变更和
教师偏好，使用 OR-Tools CP-SAT 求解，再输出不可覆盖、可审计、便于手调的
`out/<term>/<version>/` 版本目录。

## 快速开始

```powershell
uv sync

uv run class-schedule --config config clean 27S `
  "inputs/27S/Course Schedule Report.csv"

uv run class-schedule --config config draft 27S `
  work/27S/normalized/sections.csv inputs/27S/changes.toml

uv run class-schedule --config config solve 27S `
  --input work/27S/draft/starting.csv --attempts 5 --seconds 45
```

输出示例：

```text
out/27S/ver4/
  27S_ver4.csv
  report.md
  attempts.csv
  changes.csv
  overrides.toml
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

旧的网络界面代码仍保留，但当前生产入口是 `class-schedule` CLI；本轮架构
和文档不以 Web UI 为交付目标。
