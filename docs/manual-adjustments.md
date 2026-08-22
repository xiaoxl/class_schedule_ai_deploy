# 手调、锁定和版本输出

## 覆盖文件

不要直接编辑 `starting.csv` 后失去修改来源。将人工决定写入独立 TOML：

```toml
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

`edits` 可设置 `instructor`、`time_slot`、`building`、`room` 的任意子集。
`locks.fields` 只接受 `instructor`、`time`、`building`、`room`。edit 改变当前
值，lock 决定求解器能否再次改变该值；只 edit 不 lock 表示“以此为起点，
仍允许优化”。`unassign` 等价于把教师 edit 为 `Staff`。

双行原子课程可加 `record = 0` 或 `record = 1`，下标为零起始。不写 record
表示对该原子课程的全部行操作。对 coreq 单独改一行时要确保组合仍合法；
覆盖层会重新运行类验证，非法编辑立即失败。

## 从上一版继续

```powershell
uv run class-schedule --config config solve 27S `
  --input out/27S/ver3/27S_ver3.csv `
  --overrides inputs/27S/overrides-ver4.toml `
  --parent ver3 --version ver4 --attempts 5 --seconds 45
```

`parent` 是审计关系，不会自动寻找或加载父版本；`--input` 必须明确指向要
继承的排课。目标 `out/27S/ver4/` 已存在时命令拒绝覆盖。

## 版本目录

每次 solve 原子写入：

```text
out/27S/ver4/
  27S_ver4.csv       最终排课，一行一个 Section
  report.md          指标、负载、变更、遗留问题
  attempts.csv       所有独立求解尝试的状态和指标
  changes.csv        相对 --input 的字段级变化
  overrides.toml     本次覆盖文件的精确副本；没有覆盖时写明为空
  manifest.json      输入、配置、覆盖、输出文件哈希和求解参数
```

manifest 包含 term/version/parent、UTC 创建时间、源文件 SHA-256、实际配置
路径与 SHA-256、配置聚合版本、覆盖哈希、选中 attempt、solver status、
objective、bound、random seed、时间预算、hard/soft/overload 指标以及所有
产物哈希。修改版本目录中的任一产物都会使 manifest 文件哈希不再匹配。

## 检查和比较

```powershell
uv run class-schedule --config config validate 27S out/27S/ver4/27S_ver4.csv

uv run class-schedule --config config diff 27S `
  out/27S/ver3/27S_ver3.csv out/27S/ver4/27S_ver4.csv `
  --output out/27S/ver4/diff-from-ver3.csv
```

`validate` 不修改排课；hard violation 非零时退出码为 1。`diff` 比较教师、
时间和完整 building/room，适合人工复核。正式采用一个版本前，至少检查：

1. 清洗无 rejected/grouping warning；
2. solver status 和 objective/bound；
3. hard violations 为 0；
4. `Staff`, `Staff 2` 等占位身份是否仍存在；
5. 教师 load、soft findings、`changes.csv`；
6. overrides 是否完整表达所有人工决定。
