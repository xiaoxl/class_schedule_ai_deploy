# 开课需求分析

`class_schedule.section_demand` 将 schedule export 和 Cube1 人数表按 CRN
连接，判断下一学期是否值得增加 section。它是 draft 之前的辅助决策，不
直接修改排课。

```powershell
uv run python -m class_schedule.section_demand `
  "inputs/27S/Course Schedule Report.csv" inputs/27S/Cube1.xlsx `
  -o work/27S/demand.csv
```

schedule 侧需要 `Subject`、`Number`、`Section`、`CRN`、`Seats_Avail`，
并需要足够的时间/时长字段让 `Schedule` 完成原子分组。清洗后的
`sections.csv` 使用 `Seats Available`，原始报表通常使用 `Seats_Avail`；
命令同时接受两种名称。

`Seats_Avail` 原值为 `seats_available / max_enrolled / room_capacity`，算法
使用第三项 room capacity。在线/TBA 无实际 room capacity 时按 30 计算。

Cube1 XLSX 不是普通表：程序寻找首列恰为 `CRN` 的行作为表头，跳过下一行
子表头，从后续纯数字 CRN 行读取 `Course Start Date Headcount` 和
`Final Headcount`，遇到非 CRN 行停止。规划使用开学人数，不使用期末人数。

原子分组与排课一致，但汇总桶有以下含义：coreq 独立成
`MATH 0803 / MATH 1003`；hybrid 独立标记；honors cross-list 并入普通课程；
同一 CRN 只计一次。`P`、`ET`、`A` 开头的 concurrent section 被忽略。

推荐公式为：

```text
avg_capacity_per_section = total_capacity / section_count
projected_avg_enrollment = total_enrollment / (section_count + 1)
needs_new_section = projected_avg_enrollment > 0.5 * avg_capacity_per_section
```

缺少 Cube1 匹配的 CRN 不按零人数静默处理，而会从 enrollment total 排除并
列在警告中。将确认的新 section 手工写入 `inputs/<term>/changes.toml`，再
进入 draft 流程。
