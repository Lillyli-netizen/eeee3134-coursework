# Part II 修正清单 v4（Codex 第三轮复审收尾）

> 日期：2026-11-08
> 代码：`sim_version = 3.0-fair-sim`，`metrics_version = 3.0-metrics-v4`
> 数据：`results/fair_v3`（4 实验 × 8 seeds × 3 控制器 = 96 场，全部重跑）
> 范围：只做修正与验证，未新增第二模型、未做全车队真实 API、未扩展消融。

---

## 0. 先给结论

| Codex 要求                  | 状态         | 落点                                                                             |
| --------------------------- | ------------ | -------------------------------------------------------------------------------- |
| 一、换序后的统计截断        | 已修         | `metrics.py` 统一边界 + 新测试 `test_crossing_truncation_keeps_pre_crossing_gap` |
| 二、模型输出/执行器覆盖计数 | 已修         | `vehicle_llm.py` 三阶段分离计数 + 1 s ego 执行轨迹                               |
| 三、版本与结果来源          | 已查明并重跑 | 96 场重跑为 `fair_v3`，逐行写入 sim/metrics 版本与源码哈希                       |
| 四、报告矛盾与错误          | 8 条全部改   | `Part2_Report_Technical.md`                                                      |
| 五、真实 Qwen 小规模案例    | 已执行       | 单车 id60，4 场景 × 2 seeds，189 次调用，4 次超时                                |
| 六、报告技术部分组装        | 已组装       | 架构图 + 精简表 + 时空图 + 复现命令                                              |

验证：`python test_fixes.py` 共 **15 项全部通过**；`fair_v3` 与 `fair_v2` 在 12 个关键字段上 **96/96 行完全一致**（0 处差异）。

---

## 1. 换序后的统计截断

### 1.1 问题

旧实现只在 `first_overlap_step` 存在时才用 `stop_step` 重扫。纯顺序交叉（车身不重叠）虽然写入了 `valid_until_s`，但 `scan` 仍是完整扫描结果，交叉之后的样本继续进入 min gap、TTC、曝露与舒适统计；`overlap_invalid` 也仍是 `false`。

### 1.2 修改

1. 完整扫描一次，同时取 `first_overlap_step` 与 `first_crossing_step`；
2. `boundary_step = min(两者)`，**只要存在任一**，就用 `stop_step=boundary_step` 重新扫描；
3. 所有 pair 统计（min gap、TTC p01/p05、低 TTC 曝露、pair_samples）、以及速度/jerk/急刹/停止统计，全部在重扫结果或 `t < valid_until_s` 上计算；
4. 统一标记：`statistics_invalid`（任一边界命中即为 true）、`invalid_reason`（`overlap` / `order_crossing`）；`overlap_invalid` 保留其窄义"车身确实重叠"；
5. `per_vehicle` 增加 `stats_valid_until_s`，逐车标明有效范围。

### 1.3 新增回归案例（不是只断言标记）

几何：两车换序前间距 `130 - 100 - 5 = 25 m`；换序步 `141 - 135 - 5 = 1 m`；换序后放一个 −8 m/s² 的急刹样本。

断言与实测：

| 断言                                    | 结果                          |
| --------------------------------------- | ----------------------------- |
| `first_order_crossing_time_s`           | 0.2 ✓                         |
| `valid_until_s`                         | 0.2 ✓                         |
| `statistics_invalid` / `invalid_reason` | true / `order_crossing` ✓     |
| `overlap_invalid`                       | false ✓                       |
| `pair_samples`                          | **2**（只含换序前两步）✓      |
| `min_gap_m`                             | **25.0 m**（不是 1 m）✓       |
| `hard_brake_events`                     | 0（换序后的 −8 m/s² 未计入）✓ |
| `mean_abs_jerk_mps3`                    | 0.0（同样未计入）✓            |

96 场正式数据：`valid_until_s` 全为 1000 s，`statistics_invalid` 全为 false，`invalid_reason` 全为 null —— 本批没有触发边界，结论不受截断影响。

---

## 2. 模型输出与执行器覆盖的计数

### 2.1 问题

旧口径用 `effective_limit < current_speed_limit` 判断"执行器覆盖"，含义是"有效限速低于道路限速"，因此：

- 模型正常建议低速（如拥堵中 2 m/s）会被误计为执行器覆盖；
- 恢复护栏把 2 提升到 30（`effective_limit` 等于道路限速）完全不会被计数。

### 2.2 修改

`vehicle_llm.py` 分三个层次记录，互不混算：

| 层次                 | 字段                                                             | 定义                                                                   |
| -------------------- | ---------------------------------------------------------------- | ---------------------------------------------------------------------- |
| 模型解析输出         | `requested_target_speed` / `requested_time_headway`（决策日志）  | 模型 JSON 的原始值                                                     |
| 护栏处理后的缓存计划 | `llm_target_speed` / `llm_time_headway`；`guardrail_corrections` | 校验 + clamp 后的值；每次 clamp 计 1                                   |
| 执行器实际使用       | `executor_target_speed` / `executor_target_headway`（每步）      | 真正交给 IDM 的目标                                                    |
| 修改原因 1           | `recovery_guard_activations`                                     | 缓存计划低于新限速且已过瓶颈末端，被抬高时计 1（每次激活，不按步重复） |
| 修改原因 2           | `road_limit_cap_steps`                                           | **仅当缓存计划高于道路限速**时按步计数                                 |
| 修改原因 3           | `headway_ramp_steps`                                             | 时距仍在 0.2 s/s 爬坡时按步计数                                        |
| 停车意图             | `stop_intent_steps`                                              | 目标速度 ≤ 0 的显式停车分支                                            |

另外：记录 `model_name` 与 `prompt_version`；ego 每秒写一条执行轨迹（`execution_trace`，上限 2000 条，含缓存计划、执行目标、三种修改原因标记、停车意图、加速度、当时已发生的决策次数），并随运行落盘为 `*_execution.json`。

### 2.3 断言（`test_guardrail_vs_executor_counted`）

| 场景                           | 期望                                                                          | 结果 |
| ------------------------------ | ----------------------------------------------------------------------------- | ---- |
| 请求 100 m/s / 5 s             | 护栏修正 1 次；缓存 = 30 m/s、2.0 s                                           | ✓    |
| 连续 5 步执行                  | `road_limit_cap_steps == 0`（缓存等于限速，不算覆盖）                         | ✓    |
| 模型请求 2 m/s（拥堵正常建议） | **不计数为覆盖**，`executor_target_speed == 2.0`，`road_limit_cap_steps == 0` | ✓    |
| 缓存 30、道路限速 10           | `road_limit_cap_steps == 1`，执行目标 10                                      | ✓    |
| 过瓶颈末端，缓存 2、限速 30    | `recovery_guard_activations == 1`，执行目标 30；再走一步仍为 1                | ✓    |
| 模型名 / prompt 版本           | `test-model` / `test-v1`                                                      | ✓    |

---

## 3. 版本与结果来源

### 3.1 查明的结论

`fair_v2` 的 96 行写的是 `2.0-fair-metrics`，而工作树常量当时已是 `2.1-metrics-v3`。核对后确认属于**批次执行时版本常量未同步（元数据遗漏）**，不是"用旧轨迹重算指标"：当时批跑的 `metrics.py` 已包含 v3 的全部字段（`hard_brake_total_duration_s`、`mean_cumulative_system_time_all_s`、`low_ttc_fraction_of_pair_samples` 等），只是常量字符串停在 2.0。

### 3.2 处理方式（不是改标签）

- 拆分 `sim_version` 与 `metrics_version` 两个独立常量；
- **所有 96 场全部重跑**为 `results/fair_v3`；
- 每一行写入 `sim_version`、`metrics_version`、`source_hashes`（10 个源文件的 SHA-256 前 16 位）；
- 重跑结果与 `fair_v2` 在 12 个关键字段上逐行比对：**96 行 0 差异**。这同时证明两件事：旧行确实来自同一模拟与指标定义（标签遗漏），以及当前改动（截断、计数）没有改变任何无边界场景的数值。

### 3.3 来源清单

| 项                                   | 值                            |
| ------------------------------------ | ----------------------------- |
| sim_version                          | `3.0-fair-sim`                |
| metrics_version                      | `3.0-metrics-v4`              |
| 数据行数                             | 96（4 × 8 × 3）               |
| `metrics.py` sha256 前缀             | `7d025750fed1fa9d`            |
| `simulator.py`                       | `478cb435a8837eb9`            |
| `vehicle_llm.py`                     | `1fd110316f069a68`            |
| `run_comparison.py`                  | `353ed68939a4f106`            |
| 完整 18 个文件哈希 / 环境版本 / 命令 | `results/fair_v3/MANIFEST.md` |
| 结果文件哈希与行数                   | 同上                          |

环境：Python 3.12.7、numpy 1.26.4、matplotlib 3.9.2。

---

## 4. 报告中的矛盾与错误（8 条）

| #   | 旧表述                                                           | 问题                                                  | 新表述                                                                                                         |
| --- | ---------------------------------------------------------------- | ----------------------------------------------------- | -------------------------------------------------------------------------------------------------------------- |
| 1   | "时距变长 → 瓶颈流率下降 → 排队倒灌入口"                         | 与入口诊断矛盾（100 s 内瓶颈未激活、最前车约 3000 m） | 删除因果；只写"时距请求与更慢的阻挡车、更长入场延迟同时出现，因果未隔离"                                       |
| 2   | "95 fewer vehicles（576 vs 664）"                                | 把"95 辆从未入场"当成"比 IDM 少入场 95 辆"            | "平均少入场约 88 辆（664 vs 576）；95 是规划器下从未入场的计划车辆数（IDM 为 7）"                              |
| 3   | 出口流量下降 0.4–2.2%                                            | 区间算错                                              | 1.7% / 2.2% / 2.4% / 2.4%（实验 1–4）                                                                          |
| 4   | "入口区急刹是完全独立于控制器的环境效应"                         | 仅因起点集中在入口                                    | "三种控制器计数接近（621/635/635），与共享入口机制一致；但该机制未被单独隔离，不作独立性结论"                  |
| 5   | 用 Mock 调用次数估算全车队真实 API 耗时（约 97 800 次 / 17.7 h） | 论证无效（Mock 决策不能外推真实模型触发）             | 删除；只保留单 ego 的 16/16/38/38 与 216 次估算                                                                |
| 6   | "安全/舒适整体提升"                                              | 逐项方向不一致                                        | 逐项列出：min TTC 升、低 TTC 曝露降、急刹事件数持平、急刹时长升 3.5 倍、停止时长实验 3 基本不变、jerk 基本不变 |
| 7   | "IDM 保证安全"                                                   | 未验证                                                | "96 场未出现车身重叠，这是观测，不是证明"                                                                      |
| 8   | 多处"已完成"无文件对应                                           | 无法核验                                              | 报告 §5 增加"主张 → 文件/命令"对照表                                                                           |

另外：`README.md` 删除"Mock 是 LLM 性能上界"，改为"规则规划器，与真实 LLM 决策质量无包含关系"；明确同步 API 只暂停进程、不推进仿真时间。

---

## 5. 真实 Qwen 小规模案例

**状态：已执行。** 单车 id60 使用真实模型，其余车辆 IDM，需求表与规则实验逐场相同（`arrival_schedule_hash` 8/8 一致）。

配置与用量：

- 模型 `qwen-flash`，prompt `v2-tuned-2026-11`，temperature 0.2；
- 驱动脚本 `run_qwen_real.py`，硬预算 250 次，超预算即 `SystemExit(3)` 中止，不重试；
- 实际 **189 次调用，4 次失败（2.1%）**，全部为 10 s 客户端超时（`status: invalid`, `raw: None`），
  由 fail-operational 保留上一份缓存计划，仿真未中断、未重试；
- 延迟按两个口径报告（由 189 条决策日志重算，不重跑 API）：成功 185 次、平均 **0.61 s**、
  累计 113.8 s；失败 4 次、各 10.0 s；**含失败等待合计 153.8 s、平均 0.81 s**。
  原始日志全部保留在 `results/qwen_real/exp*/…_v60_decisions.json`，未改动；
- 失败原因按现有证据措辞：4 次失败均为 10 s 客户端超时（`status: invalid`、`raw: None`、
  `latency_s: 10.0`）。代码已改为在失败条目中记录异常类型（`exception` 字段，
  如 `TimeoutError`），今后失败可直接按类型区分；
- 密钥仅从 `DASHSCOPE_API_KEY` 读取，不写入代码、日志或提交包（已用 `sk-…` 正则全量扫描确认无泄漏）。

结果（ego id60，同需求 IDM 对照）：

| 场景 | seed | 调用 | ego 旅行 IDM / Qwen (s) | Δ (s) | 车队最小 TTC IDM / Qwen (s) | 恢复护栏 | 时距渐变步 |
|---|---|---|---|---|---|---|---|
| 1 | 1 | 15 | 299.4 / 301.7 | +2.3 | 2.32 / 2.11 | 1 | 14 |
| 1 | 2 | 15 | 296.9 / 299.4 | +2.5 | 2.27 / 1.98 | 1 | 12 |
| 2 | 1 | 16 | 313.4 / 315.6 | +2.2 | 1.47 / 0.76 | 1 | 20 |
| 2 | 2 | 15 | 309.8 / 312.4 | +2.6 | 2.28 / 2.28 | 1 | 12 |
| 3 | 1 | 34 | 520.0 / 583.0 | +63.0 | 1.99 / 1.91 | 0 | 23 |
| 3 | 2 | 29 | 511.7 / 516.3 | +4.6 | 1.96 / 1.96 | 0 | 22 |
| 4 | 1 | 35 | 530.0 / 632.3 | +102.3 | 1.42 / 1.05 | 0 | 28 |
| 4 | 2 | 30 | 521.9 / 552.3 | +30.4 | 1.91 / 1.98 | 1 | 19 |

读法：

- 同车配对差（每场 Qwen − IDM）：+2.3, +2.5, +2.2, +2.6, +63.0, +4.6, +102.3, +30.4 s。
  均值 **+26.2 s**、中位数 **+3.6 s** 同时保留：中位数说明典型场次只慢几秒，
  均值被两个长瓶颈场景（+63.0、+102.3）拉高——两者回答不同问题，不只用中位数；
- 无车身重叠，但场景 2 seed1 最小 TTC 从 1.47 降到 0.76 s，场景 4 seed1 从 1.42 降到 1.05 s——
  "没撞"不等于"更安全"；
- 护栏修正 0 次、道路上限截断 0 步：模型从未要求超过限速；执行器的影响只来自时距渐变与恢复护栏；
- prompt 写 1.0–1.6 s 时距，实际有一次请求 1.80 s；硬边界是 [0.8, 2.0]，因此未计为修正——
  prompt 的区间是建议值，只有硬边界被强制执行；
- 调用量实测 15/15/16/15 与 34/29/35/30，对比方向：**全部不高于**离线估算 16/16/38/38
  （7 场低于、1 场持平）。估算仍是可用预算，但逐场分布不同——触发序列取决于模型自身决策；
- 同步调用期间仿真时间不前进，等价零延迟规划器；**真实通信延迟未验证**。

---

## 6. 精简结果表

完整三张表：`results/fair_v3/summary.md`（A 效率与需求 / B 安全与舒适 / C 逐 seed 配对差）。

效率（8 seeds 均值）：

| 实验 | 控制器 | 入场/需求 | 出口流量 | 完成旅行 | 完成系统 | 全部需求累计 |
| ---- | ------ | --------- | -------- | -------- | -------- | ------------ |
| 2    | IDM    | 664/670   | 1679     | 305.8    | 308.2    | 261.5        |
| 2    | Mock   | 576/670   | 1642     | 266.1    | 319.6    | 269.3        |
| 4    | IDM    | 665/672   | 454      | 540.4    | 541.8    | 432.7        |
| 4    | Mock   | 576/672   | 443      | 541.1    | 551.1    | 435.6        |

安全与舒适（实验 2）：

| 控制器 | min TTC | TTC<3 s 对·秒 | 占比    | 急刹事件 | 急刹总时长 | 停止总时长 |
| ------ | ------- | ------------- | ------- | -------- | ---------- | ---------- |
| IDM    | 1.8     | 1069.8        | 0.00622 | 626      | 169.8      | 7660.5     |
| Mock   | 2.7     | 7.5           | 0.00006 | 638      | 593.5      | 210.2      |

配对差（同需求、8 对）：实验 2 Mock−IDM 累计 **+7.8 s（8/8 更慢）**、配对旅行 **−39.7 s（0/8 更慢）**、配对系统 **+11.4 s（8/8 更慢）**。

---

## 7. 验证输出

`python test_fixes.py`（15 项，实际终端输出）：

```text
ok  common demand identical across modes (269 scheduled, 268 entered)
ok  noise deterministic (influence=True, n(60,1500)=-0.6456)
ok  stop target: v=10→0 in 5.1s, a0=-2.00 m/s^2
ok  validation rejects NaN/inf/missing/non-numeric/non-dict
ok  recovery guard lifts stale plan past zone end (persistent bottleneck)
ok  travel time: demand=177 entered=177 exited=6 incomplete=171 tt=273.3s
ok  ttc: min=2.35 p05=28.52 exposure<3s=124.7s
ok  idm ego60: scheduled=100.3s entered=100.30000000000001s travel=299.4s
ok  cumulative: demand=72 entered=61 waiting=11 cum=49.2s completed-only=None
ok  overlap truncation: overlap@0.2s (min_gap 3.5 m, post-overlap hard brake excluded); order crossing@0.2s also flagged
ok  crossing truncation: gap 25 m before / 1 m after, min_gap=25.0 m from 2 pre-crossing samples; post-crossing brake excluded
ok  ego execution trace (1 s sampling) and per-vehicle stats_valid_until_s recorded
ok  low-TTC normalised: <3s exposure=121.1s = 0.00409 of 296252 pair-samples
ok  admission evidence: demand=72 entered=61 waiting=11 blocks=829 (spacing=786, kinematic=43) front_pos~21.4m front_v~24.21m/s
ok  model/guardrail/executor split: clamp request 100->30.0; low plan 2 m/s executed without being counted as an override; road cap 30->10 counted; recovery 2->30 counted once

all targeted verification checks passed
```

重跑一致性（`fair_v2` vs `fair_v3`，12 字段 × 96 行）：

```text
exp 1 rows 24 mismatched 0
exp 2 rows 24 mismatched 0
exp 3 rows 24 mismatched 0
exp 4 rows 24 mismatched 0
```

`summarize_results.py` 输出首行：

```text
Provenance: sim_version `3.0-fair-sim`, metrics_version `3.0-metrics-v4`, 96 runs.
Runs truncated at a validity boundary: 0 of 96
```

---

## 8. 交付与复现

包内布局与命令见报告 §5。要点：

- 报告直接引用 `figures/` 下的架构图与两张时空图，均为当前代码版本生成（哈希见 MANIFEST）；
- 解压后 `cd code` 即可执行 `python test_fixes.py` 等命令，结果写到 `../results/`；
- `sample_decisions/` 为修复前、prompt v1 的历史日志，文件名带 `PRE_FIX_` 前缀，明确不与新指标混算。

---

## 9. 仍未完成 / 需你决定

1. **Personal Reflection**：按课程红线由你本人撰写，报告 §6 已留空；素材与大纲见
   `Part2_反思大纲与过程素材.md`。
2. **Conclusions**：已由本清单对应数据生成，写在报告 §7，可自行改写。
3. **真实模型仍有的边界**：仅一个 ego、一个模型、一个 prompt、一个温度、8 场；
   未做全车队真实 API，未验证真实通信延迟；如要扩展，需先确认预算与时间。
4. 提交格式与渠道（PDF / Moodle）课程说明未写明，需你确认。

---

## 10. 最终收尾验证记录（本轮新增）

四项修正 + 验证输出，全部离线完成，未再调用付费 API。

**① 延迟两口径（由 189 条原始决策日志重算，日志未改动）**

```text
Latency (from raw decision logs):
  success: n=185 total=113.8s mean=0.61s
  failed : n=4 total=40.0s mean=10.01s (all 10s client timeouts)
  ALL    : n=189 total=153.8s mean=0.81s
```

**② headway ramp 统一**：代码 `vehicle_llm.py` 为 0.5 s/s；报告 §2.1 与
`figures/architecture.png` 已由 0.2 改为 0.5（实验代码未动）。

**③ 预算异常穿透修复**：`QwenCallBudgetExceeded(BaseException)`，新增离线测试
`test_budget_abort_saves_partial_results`（stub 决策，不触网），输出：

```text
STOPPED: QWEN_CALL_BUDGET_EXCEEDED: 2 calls reached (budget 2). Stopping as instructed; no retry.
partial results saved to ...qwen_budget_test...
ok  budget abort: SystemExit(3), 2 calls counted, partial idm row saved
all targeted verification checks passed   (16 项)
```

**④ 路径统一与解压即跑**：文件包/评审包布局统一为 `code/` + `results/` + `figures/` + 根部文档；
`summarize_results.py`、`analyze_paired.py`、`summarize_qwen_real.py`、`make_qwen_figure.py`
均自动定位数据目录（`results/...` 或 `../results/...`）。解压文件包到临时目录后从 `code/` 直接运行：

```text
python summarize_qwen_real.py   -> data dir: ..\results\qwen_real（自动定位）
python summarize_results.py     -> 正常输出 fair_v3 summary
python analyze_paired.py        -> 24 rows, 8 seeds
python make_qwen_figure.py ..\figures -> written: ..\figures\qwen_real_ego.png
python test_fixes.py            -> all targeted verification checks passed（16 项）
```

**⑤ 对比方向与统计口径**：实测调用量全部不高于离线估算（7 场低于、1 场持平），
报告与清单中的方向性表述已更正；真实案例逐场配对差、均值 +26.2 s、中位数 +3.6 s 同时保留。

MANIFEST 已重新生成；`llm_client.py`、`vehicle_llm.py` 的当前哈希与行内前缀不一致属预期
（跑批后新增的异常类型记录与预算中止路径，不影响任何计划值与指标），MANIFEST 中有专门说明。
