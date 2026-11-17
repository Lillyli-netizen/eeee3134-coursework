# Part II — Technical Report (draft)

LLM-based car-following control compared with IDM in a bottleneck simulation

> Dataset: `results/fair_v3` — 4 experiments × 8 seeds × 3 controllers = 96 runs.
> `sim_version = 3.0-fair-sim`, `metrics_version = 3.0-metrics-v4`.
> Every result row also carries SHA-256 prefixes of the source files that produced it;
> full hashes and the exact commands are in `results/fair_v3/MANIFEST.md`.
> Personal Reflection (Section 6) is intentionally left blank — it is the author's
> own text. Conclusions (Section 7) summarise only what the data below support.

---

## 1. Task objective

The coursework asks for an LLM to be integrated into the existing car-following
framework and evaluated against a conventional model. The objective of this
report is narrower and more testable:

1. build a two-layer controller in which an LLM plans a *target speed* and a
   *time headway*, while the teacher's IDM executes the acceleration;
2. compare it with IDM under **identical demand**, so that any difference is
   attributable to the controller and not to a different arrival pattern;
3. report efficiency, safety and comfort with explicit, non-overlapping
   definitions, and state which conclusions the data do **not** support.

A rule-based planner (`Mock`) is used for the 96-run comparison so that the
full grid is cheap and deterministic. The real-model case is a separate,
small-scale experiment and is reported separately in §3.2.

---

## 2. Method

### 2.1 Architecture

![Controller architecture](figures/architecture.png)

*Figure 1. Planner/executor split, with the three stages that can change a
plan. Only the planner and executor stages are ours; the IDM acceleration rule
and the simulation loop are the teacher's original code.*

The planner is called on events (periodic re-check, approach to the
bottleneck, entering/leaving the zone, emergency leader) rather than every
step. Its JSON reply is validated (type, missing field, non-finite values) and
clamped by planner guardrails before it becomes the **cached plan**. The
executor then applies three further operations, each counted separately:

* **recovery guard** — past the zone end a stale slow plan is raised to the
  road limit (counted once per activation, not per step);
* **road-limit cap** — applied only when the cached plan is *above* the current
  road limit; a planner that recommends 2 m/s in a jam is doing its job and is
  **not** counted as being overruled;
* **headway ramp** — 0.5 s of headway per second, so a request for a longer gap
  is not applied as a step change.

The planner output, the guarded cached plan and the executed target are stored
as three distinct quantities, plus a 1 s execution trace for the tracked ego.

### 2.2 Fair comparison

* The arrival schedule is pre-generated per (experiment, seed) and shared by
  all controllers; it is hashed in every row.
* Bottleneck-influence flags and perception noise are deterministic functions
  of `(seed, vehicle id, step)` instead of a shared global stream, so one
  controller cannot shift another controller's random numbers.
* Delayed admission is recorded (vehicle, waiting time, blocking reason), not
  silently dropped.

### 2.3 Metric definitions

Efficiency has **two scopes**, reported side by side:

| Scope                               | Definition                                | Covers                                                                   |
| ----------------------------------- | ----------------------------------------- | ------------------------------------------------------------------------ |
| `mean_system_time_completed_s`      | exit − scheduled arrival                  | completed vehicles only                                                  |
| `mean_cumulative_system_time_all_s` | min(exit, `time_max`) − scheduled arrival | **all** scheduled vehicles, including never-admitted and incomplete ones |

The second is a finite-horizon truncated cumulative time: vehicles still on the
road at `time_max` and vehicles that never entered are both truncated at
`time_max`. It is therefore not a completed travel time and is only comparable
between controllers run with the same horizon.

Safety and comfort statistics use a **validity boundary**. The earlier of the
first body overlap and the first adjacent order crossing ends the interval, and
the pair statistics are recomputed from scratch on `t < valid_until_s`; speed,
jerk, hard-braking and stopping statistics are filtered with the same boundary.
`statistics_invalid` is the unified flag and `invalid_reason` records whether an
overlap or a crossing caused it. In this 96-run batch no run hit a boundary, so
every row is valid over the full 1000 s.

Low-TTC exposure is reported both as pair-time (vehicle-pairs × seconds) and as
a fraction of observed pair-samples, because the pair-time total also grows with
the number of pairs on the road. It is not the duration experienced by one
vehicle.

---

## 3. Results

### 3.1 Rule-based experiments (96 runs)

All numbers are means over 8 seeds; the same demand is used for all three
controllers within a seed.

#### Efficiency and demand

| Exp | Controller  | Entered / demand | Waiting | Throughput veh/h | Travel (completed) s | System (completed) s | Cumulative all-demand s |
| --- | ----------- | ---------------- | ------- | ---------------- | -------------------- | -------------------- | ----------------------- |
| 1   | IDM         | 589 / 589        | 0       | 1679             | 259.0 ± 0.8          | 259.0 ± 0.8          | 226.7 ± 0.6             |
| 1   | Mock        | 589 / 589        | 0       | 1651             | 271.2 ± 4.3          | 271.3 ± 4.2          | 235.6 ± 3.0             |
| 1   | Mock no-ant | 589 / 589        | 0       | 1672             | 262.4 ± 2.2          | 262.4 ± 2.2          | 229.2 ± 1.6             |
| 2   | IDM         | 664 / 670        | 7       | 1679             | 305.8 ± 4.0          | 308.2 ± 5.2          | 261.5 ± 3.6             |
| 2   | Mock        | 576 / 670        | 95      | 1642             | 266.1 ± 4.5          | 319.6 ± 4.7          | 269.3 ± 3.2             |
| 2   | Mock no-ant | 576 / 670        | 95      | 1654             | 258.1 ± 2.3          | 312.0 ± 3.9          | 264.2 ± 2.9             |
| 3   | IDM         | 589 / 589        | 0       | 454              | 529.5 ± 2.8          | 529.5 ± 2.8          | 422.2 ± 0.8             |
| 3   | Mock        | 589 / 589        | 0       | 443              | 539.1 ± 2.5          | 539.1 ± 2.5          | 425.6 ± 0.5             |
| 3   | Mock no-ant | 589 / 589        | 0       | 454              | 529.6 ± 2.8          | 529.6 ± 2.8          | 422.2 ± 0.8             |
| 4   | IDM         | 665 / 672        | 8       | 454              | 540.4 ± 3.8          | 541.8 ± 4.3          | 432.7 ± 2.9             |
| 4   | Mock        | 576 / 672        | 96      | 443              | 541.1 ± 2.5          | 551.1 ± 3.0          | 435.6 ± 2.9             |
| 4   | Mock no-ant | 576 / 672        | 96      | 454              | 531.5 ± 2.9          | 541.9 ± 4.3          | 432.7 ± 2.9             |

What the table supports:

* On the demand-wide scope the planner is slower in every experiment
  (+2.9 to +8.9 s, 8/8 seeds), and exit throughput is 1.7 %, 2.2 %, 2.4 %,
  2.4 % lower in experiments 1–4.
* In experiment 2 the completed-vehicle travel time is genuinely shorter
  (−39.7 s, 8/8 seeds), but that subset excludes the vehicles that never
  entered. The paired system time for the *same* vehicles is +11.4 s (8/8
  seeds slower), and the demand-wide cumulative time is +7.8 s.
* Experiment 2 admits on average about 88 fewer vehicles per run (664 vs 576).
  The 95 figure is the number of scheduled vehicles that never enter under the
  planner; it is **not** the drop relative to IDM.

#### Safety and comfort

| Exp | Controller  | min TTC s | TTC<3 s pair-time s | fraction of pairs | HB events | HB total s | HB in entry zone | Stop events | Stop total s | mean abs jerk |
| --- | ----------- | --------- | ------------------- | ----------------- | --------- | ---------- | ---------------- | ----------- | ------------ | ------------- |
| 1   | IDM         | 2.2       | 292.7               | 0.00221           | 5         | 6.5        | 0                | 11          | 19.6         | 2.77          |
| 1   | Mock        | 2.6       | 10.2                | 0.00007           | 3         | 0.3        | 0                | 64          | 251.6        | 2.81          |
| 1   | Mock no-ant | 2.3       | 39.4                | 0.00029           | 5         | 6.4        | 0                | 0           | 0.0          | 2.79          |
| 2   | IDM         | 1.8       | 1069.8              | 0.00622           | 626       | 169.8      | 621              | 899         | 7660.5       | 3.11          |
| 2   | Mock        | 2.7       | 7.5                 | 0.00006           | 638       | 593.5      | 635              | 38          | 210.2        | 2.70          |
| 2   | Mock no-ant | 2.3       | 41.3                | 0.00032           | 640       | 599.6      | 635              | 0           | 0.0          | 2.67          |
| 3   | IDM         | 2.0       | 4563.5              | 0.01842           | 5         | 6.5        | 0                | 4534        | 18648.0      | 2.08          |
| 3   | Mock        | 2.3       | 98.5                | 0.00039           | 3         | 0.3        | 0                | 3157        | 18753.9      | 2.09          |
| 3   | Mock no-ant | 2.2       | 127.0               | 0.00051           | 5         | 6.4        | 0                | 3228        | 16475.9      | 2.10          |
| 4   | IDM         | 1.9       | 5454.4              | 0.01899           | 632       | 173.7      | 627              | 5952        | 31612.0      | 2.25          |
| 4   | Mock        | 2.4       | 63.2                | 0.00026           | 636       | 589.4      | 633              | 2900        | 16118.5      | 2.10          |
| 4   | Mock no-ant | 2.3       | 99.7                | 0.00041           | 638       | 595.6      | 633              | 2928        | 14517.1      | 2.10          |

The safety picture is mixed, and it is reported item by item:

* **Minimum TTC** is higher for the planner in all four experiments
  (2.6/2.7/2.3/2.4 vs 2.2/1.8/2.0/1.9 s).
* **Low-TTC exposure** falls in all four experiments (292.7 → 10.2,
  1069.8 → 7.5, 4563.5 → 98.5, 5454.4 → 63.2 pair-seconds), a 96–99 % drop.
* **Hard-braking event counts are essentially equal** (5/3/5, 626/638/640,
  5/3/5, 632/636/638), so this metric does *not* separate the controllers.
* **Hard-braking duration is much larger for the planner** in experiments 2 and
  4 (593.5 s and 589.4 s vs 169.8 s and 173.7 s) despite similar event counts:
  the events are longer, not more frequent.
* **Stopping behaviour changes in both directions.** Event counts fall in
  experiments 2, 3 and 4 (899→38, 4 534→3 157, 5 952→2 900) but rise in
  experiment 1 (11→64). The total stopped duration falls sharply in experiment 2
  (7 660 → 210 s) and experiment 4 (31 612 → 16 118 s), but stays essentially
  unchanged in experiment 3 (18 648 → 18 754 s).
* **Jerk** is slightly lower in experiments 2 and 4 and essentially unchanged in
  1 and 3.

No single sentence such as "the LLM improves safety" or "the LLM is more
comfortable" is supported by all of these columns. The defensible statement is
that the planner keeps larger minimum TTC and much less low-TTC exposure (96–99 %
lower in experiments 2–4), at the cost of longer braking events and 1.7–2.4 %
lower exit throughput.

#### Paired differences (same demand, per seed)

| Exp | Comparison        | Δ cumulative all-demand s | Δ completed travel s | Δ completed system s |
| --- | ----------------- | ------------------------- | -------------------- | -------------------- |
| 1   | Mock − IDM        | +8.9 (8/8)                | +12.2 (8/8)          | +12.2 (8/8)          |
| 1   | Mock no-ant − IDM | +2.5 (8/8)                | +3.4 (8/8)           | +3.4 (8/8)           |
| 2   | Mock − IDM        | +7.8 (8/8)                | −39.7 (0/8)          | +11.4 (8/8)          |
| 2   | Mock no-ant − IDM | +2.6 (8/8)                | −47.6 (0/8)          | +3.8 (8/8)           |
| 3   | Mock − IDM        | +3.4 (8/8)                | +9.6 (8/8)           | +9.6 (8/8)           |
| 3   | Mock no-ant − IDM | +0.0 (1/8)                | +0.1 (6/8)           | +0.1 (6/8)           |
| 4   | Mock − IDM        | +2.9 (8/8)                | +0.8 (5/8)           | +9.4 (8/8)           |
| 4   | Mock no-ant − IDM | +0.1 (4/8)                | −8.8 (0/8)           | +0.1 (6/8)           |

#### Time-space diagrams

![Experiment 2, IDM](figures/exp2_idm_seed1_readable.png)
![Experiment 2, Mock planner](figures/exp2_llm_mock_seed1_readable.png)

*Figure 2 (top: IDM, bottom: Mock planner), experiment 2, seed 1, 1000 s. One
vehicle line in every five is drawn so that individual trajectories stay
readable; both panels come from the same code version as the tables.*

The congested band reaches the entrance in the IDM panel and stops earlier in
the Mock panel. This visual difference must be read together with the demand
column above: the planner admits about 88 fewer vehicles, so part of the
"cleaner" appearance is simply fewer vehicles on the road, not better control.
The dashed line is the teacher's reference wave speed, not a measured value.

### 3.2 Real-model case — one real ego, 4 experiments × 2 seeds

A single vehicle (id 60) is driven by the real model, every other vehicle stays
on IDM. Runs use the same pre-generated arrival schedule as §3.1 — the schedule
hash matches in all eight pairs — so the only difference between the two rows of
a pair is the controller of vehicle 60.

Model `qwen-flash` (DashScope OpenAI-compatible endpoint, temperature 0.2),
prompt `v2-tuned-2026-11`, unchanged from §2.1. Budget was capped at 250 calls
and the driver aborts on exceeding it; the grid used **189 calls**.

![Ego travel time, real Qwen vs IDM](figures/qwen_real_ego.png)

*Figure 3. Vehicle 60 travel time, real model vs IDM under identical demand.
Right: Qwen minus IDM, positive = the model is slower.*

| Exp | Seed | Calls | Ego travel IDM / Qwen (s) | Δ (s)  | Ego HB events | Fleet min TTC IDM / Qwen (s) | Entered IDM / Qwen | Recovery guard | Headway ramp steps |
| --- | ---- | ----- | ------------------------- | ------ | ------------- | ---------------------------- | ------------------ | -------------- | ------------------ |
| 1   | 1    | 15    | 299.4 / 301.7             | +2.3   | 0 / 0         | 2.32 / 2.11                  | 589 / 589          | 1              | 14                 |
| 1   | 2    | 15    | 296.9 / 299.4             | +2.5   | 0 / 0         | 2.27 / 1.98                  | 589 / 589          | 1              | 12                 |
| 2   | 1    | 16    | 313.4 / 315.6             | +2.2   | 2 / 2         | 1.47 / 0.76                  | 665 / 665          | 1              | 20                 |
| 2   | 2    | 15    | 309.8 / 312.4             | +2.6   | 1 / 1         | 2.28 / 2.28                  | 663 / 663          | 1              | 12                 |
| 3   | 1    | 34    | 520.0 / 583.0             | +63.0  | 0 / 0         | 1.99 / 1.91                  | 589 / 589          | 0              | 23                 |
| 3   | 2    | 29    | 511.7 / 516.3             | +4.6   | 0 / 0         | 1.96 / 1.96                  | 589 / 589          | 0              | 22                 |
| 4   | 1    | 35    | 530.0 / 632.3             | +102.3 | 0 / 0         | 1.42 / 1.05                  | 666 / 665          | 0              | 28                 |
| 4   | 2    | 30    | 521.9 / 552.3             | +30.4  | 0 / 0         | 1.91 / 1.98                  | 664 / 663          | 1              | 19                 |

What the run supports, item by item:

* **Call volume came out at or below the offline estimate.** The estimate was
  16/16/38/38 calls per run; the real counts are 15/15/16/15 in experiments 1–2
  and 34/29/35/30 in experiments 3–4 — below the estimate in seven runs and equal
  in one, never above. The estimate therefore remains a usable *budget*, but the
  per-run distribution differs because the model's own plan changes the trigger
  sequence; it is a planning figure, not a prediction.
* **The single-vehicle effect is small in experiments 1–2 and large in 3–4.**
  These are same-vehicle paired differences (vehicle 60 with the model minus
  vehicle 60 with IDM, same run, same demand), not a difference between two
  group averages. Per run: +2.3, +2.5, +2.2, +2.6, +63.0, +4.6, +102.3, +30.4 s.
  The mean is +26.2 s, the median is +3.6 s. Both are reported because they
  answer different questions: the median says a *typical* run cost the ego only
  a few seconds, while the mean is pulled up by the two long-bottleneck runs
  where the ego lost over a minute. Neither statistic alone is the summary.
* **No overlap occurred, but the margin narrowed.** Minimum TTC of the fleet is
  essentially unchanged in three runs, but in experiment 2 seed 1 it drops from
  1.47 s to 0.76 s and in experiment 4 seed 1 from 1.42 s to 1.05 s. "No
  collision" is not "safer"; on these two runs the real model left less margin
  than the IDM it replaced.
* **The model mostly saturated rather than modulated.** Requested speeds span
  1.0–30.0 m/s with headways 1.0–1.8 s: it followed the zone limit inside the
  bottleneck and the road limit outside, and used the headway dimension to
  modulate. Its rationale strings are short and consistent
  (e.g. "Before slow zone, maintain speed limit").
* **The three-stage counters show where the executor disagreed with the plan.**
  Planner guardrail corrections were 0 and road-limit cap steps were 0 in all
  runs — the model never asked for more than the road limit. The recovery guard
  fired once in five of the eight runs (a stale slow plan raised to the limit
  after the zone end), and the headway ramp absorbed 12–28 steps per run. So in
  this sample the executor's influence came from the ramp and the recovery
  guard, not from clamping the model.
* **Prompt compliance has one visible exception.** The prompt asks for 1.0–1.6 s
  headway, but one request was 1.80 s. The hard guardrail bound is [0.8, 2.0],
  so it passed uncorrected. The range in the prompt is advisory; only the hard
  bound is enforced, and the report should not claim otherwise.

Failures and cost, stated plainly:

* **4 of 189 calls failed (2.1 %)**, all as 10 s client timeouts
  (`status: invalid`, `raw: None`), one per seed-2 run. Fail-operational
  behaviour kept the last cached plan and the simulation continued; no run was
  aborted and no call was retried. The failed requests are logged with their
  observation, so they can be inspected rather than inferred.
* Mean round-trip latency, recomputed from the 189 raw decision-log entries:
  **0.61 s over the 185 successful calls** (113.8 s of blocking), plus the four
  10 s timeout waits = **153.8 s of blocking in total, 0.81 s per call when the
  failure waits are included**. The earlier run-log figure (113.7 s, 0.60 s)
  covers successful calls only, because `total_latency` is accumulated after a
  successful response. The client is synchronous: the Python process waits, but
  **simulation time does not advance during a call**. Every number above
  therefore describes a zero-latency planner. Real communication delay, message
  loss under load and the feasibility of a sub-second round trip inside a 0.1 s
  control step are **not** tested, and a deployed version would need an
  asynchronous planner.

Scope limits: a single ego in an otherwise IDM fleet measures that vehicle's own
trajectory and its local interaction with its leader and follower. It does not
measure what happens when many vehicles are planned by the model at once, and it
is not evidence about network-level throughput. One model, one prompt, one
temperature were used; no prompt search was performed, because the brief asks
for a small verified case rather than a tuned contest entry.

### 3.3 Entry backlog: observation only

In experiment 2, seed 1, over the first 100 s (before the bottleneck starts),
the three controllers face the same 72 scheduled arrivals:

| Controller  | Entered | Waiting | Mean entry delay s | Admission failures | Failures while bottleneck active |
| ----------- | ------- | ------- | ------------------ | ------------------ | -------------------------------- |
| IDM         | 69      | 3       | 0.97               | 513                | 0                                |
| Mock        | 61      | 11      | 4.26               | 829                | 0                                |
| Mock no-ant | 61      | 11      | 4.26               | 829                | 0                                |

The blocking vehicle at those attempts sat at 22.4 m (IDM) and 21.4 m (Mock)
with 26.44 and 24.21 m/s and requested headways of 1.00 s and 1.24 s
respectively. The leading vehicle has not reached the bottleneck (about
3000 m at 100 s), and no admission failure occurred while the bottleneck was
active, so **queue spill-back from the bottleneck cannot explain the admission
backlog in this window**. What the data show is that the planner's larger
headway request is associated with slower blocking vehicles and longer entry
delays; the causal chain was not isolated and is not claimed.

---

## 4. Challenges and how they were resolved

**4.1 A headline result that turned out to be an artefact.**
An earlier version reported "+9.5 % throughput" for the planner in experiment 2.
The two controllers were not facing the same number of vehicles: the planner
left 95 scheduled vehicles outside the entrance while IDM left 7. With fewer
cars on the road the remaining ones travel faster, so the comparison measured
demand, not control. The claim was withdrawn, the entrance accounting was added
(`entered`, `waiting_at_end`, `entry_delay`), and every later comparison uses
shared demand plus paired, per-seed differences.

**4.2 The efficiency metric covered only the winners.**
A mean over completed vehicles silently drops the vehicles that never entered.
The fix was to keep that column but rename it (`..._completed_s`) and add a
demand-wide truncated cumulative time over *all* scheduled vehicles, together
with the completed fraction, the never-admitted count and the incomplete count.
The two scopes now disagree in experiment 2, and that disagreement is itself
the finding.

**4.3 Sampling points were counted as events.**
An earlier "67 hard brakes" was 67 one-step samples: a single 1 s braking event
was counted ten times. Events are now contiguous segments and the report shows
event count, total duration and maximum duration separately. This is what
revealed that the planner has *similar* event counts but a much longer total
braking duration.

**4.4 The overlap guard only skipped points, it did not truncate.**
The first implementation ignored pairs while they overlapped and then resumed
statistics afterwards, so post-overlap data (where following no longer means
anything) re-entered min-gap and TTC. Statistics are now recomputed on
`t < valid_until_s`, where the boundary is the earlier of the first overlap and
the first adjacent order crossing, and both events are detected. A synthetic
case with a 25 m gap before the swap and a 1 m gap after it returns `min_gap =
25 m` with only the pre-crossing samples, which is the regression test for this
bug (`test_crossing_truncation_keeps_pre_crossing_gap`).

**4.5 Model output and executor action were conflated.**
The executor counter was originally "effective limit below the road limit",
which counted a correct low-speed recommendation as an override, while the
recovery guard raising 2 → 30 m/s was not counted at all. The three stages now
have separate counters (planner clamp, recovery guard, road-limit cap, headway
ramp), and the ego's executed target speed and headway are traced once per
second.

**4.6 Results carried a stale version label.**
The 96-run dataset was produced while the version constant still read
`2.0-fair-metrics`, although the metric definitions in the working tree were
newer. Rather than relabel the file, the whole grid was re-simulated with
`sim_version` and `metrics_version` recorded in every row plus SHA-256 prefixes
of all source files. The new rows reproduce the previous dataset on every
compared field (4 experiments × 24 rows, 0 mismatches), which shows the old rows
came from the same simulation and metric definitions and that the mismatch was a
stale label — not a silent recomputation.

**4.7 Entry-zone braking looked like a controller effect.**
Hard braking in experiments 2 and 4 is concentrated in the first 500 m and the
counts are nearly identical for all three controllers (621 / 635 / 635). That is
consistent with a mechanism in the shared entrance logic, but the mechanism was
not isolated experimentally, so the report states the observation and does not
attribute it to the environment being "independent of the controller".

**4.8 Safety cannot be summarised in one direction.**
Minimum TTC and low-TTC exposure improve, hard-braking duration worsens,
stopping duration is unchanged in one experiment, and jerk barely moves. The
report therefore describes each metric and refuses an overall safety or comfort
verdict. Likewise, IDM is not described as "proven safe": it produced no body
overlap in these 96 runs, which is an observation over this grid, not a
guarantee.

---

## 5. Deliverables and reproduction

Package layout (paths are relative to the package root):

```text
Part2_Report_Technical.md      this report
figures/                       architecture, time-space panels, real-Qwen ego chart
code/                          all source files, README, requirements
results/fair_v3/               exp1..exp4 metrics.json, summary.md/csv, MANIFEST.md
results/qwen_real/             real-model metrics.json, run log, per-run decisions
                               and execution traces for vehicle 60
sample_decisions/              pre-fix Qwen logs (history only, excluded from tables)
```

Run from `code/` after unzipping:

```bash
python test_fixes.py
python diagnose_entry.py
python run_comparison.py --experiment 2 --seed 1 --modes idm llm_mock llm_mock_noant \
  --ego-ids 60 --no-plots --json-output ../results/recheck/exp2/metrics.json
python summarize_results.py ../results/fair_v3
python analyze_paired.py ../results/fair_v3/exp2/metrics.json
python make_manifest.py ../results/fair_v3
python make_report_figures.py ../figures
python make_qwen_figure.py ../figures
python summarize_qwen_real.py
```

The real-model grid is re-run with the key in `DASHSCOPE_API_KEY` (never written
to disk). The driver aborts when the call budget is exceeded:

```bash
python run_qwen_real.py --experiments 1 --seeds 1 --budget 25          # pilot
python run_qwen_real.py --experiments 1 2 3 4 --seeds 1 2 --budget 250
```

Claim-to-evidence map (so that "done" means a file, not an assertion):

| Claim                               | Evidence                                                             |
| ----------------------------------- | -------------------------------------------------------------------- |
| 96 fair runs, shared demand         | `results/fair_v3/exp*/metrics.json`, `arrival_schedule_hash` per row |
| Efficiency: two scopes              | `results/fair_v3/summary.md`, tables A and C                         |
| Safety/comfort per metric           | `results/fair_v3/summary.md`, table B                                |
| Validity boundary works             | `python test_fixes.py` (15 checks)                                   |
| Provenance and environment          | `results/fair_v3/MANIFEST.md`                                        |
| Figures belong to this code version | source hashes in `results/fair_v3/MANIFEST.md`                       |
| Real-model runs happened             | `results/qwen_real/metrics.json` (8 rows, `llm_api_calls` 15–35)     |
| Real model output vs executor action | `results/qwen_real/exp*/…_v60_decisions.json`, `…_v60_execution.json` |
| Failures were handled, not hidden    | `qwen_run_log.json` (`total_api_failures = 4`), invalid entries kept  |

Dependencies: Python 3.12.7, numpy 1.26.4, matplotlib 3.9.2 (matplotlib and numpy
only; the LLM client uses the standard library).

---

## 6. Personal Reflection

*(Reserved for the author. Not written by the assistant.)*

---

## 7. Conclusions

1. **The two-layer design works mechanically.** The model plans a target speed
   and a headway on events; the IDM executes the acceleration; a failed call
   keeps the last plan instead of stalling the vehicle. This held over 189 real
   calls, including four 10 s timeouts.

2. **Under identical demand the planner does not improve the system.** On the
   demand-wide scope it is slower in all four experiments (+2.9 to +8.9 s, 8/8
   seeds), exit throughput is 1.7–2.4 % lower, and in experiment 2 it admits
   about 88 fewer vehicles per run. The shorter completed-vehicle travel time in
   experiment 2 is a selection effect: it is computed on the vehicles that
   entered, and the paired system time for the same vehicles is +11.4 s.

3. **Safety cannot be summarised in one direction.** Minimum TTC and low-TTC
   exposure improve consistently (96–99 % less exposure in experiments 2–4),
   hard-braking duration roughly triples in experiments 2 and 4, stopping
   duration is halved in experiment 2 and unchanged in experiment 3, and jerk
   barely moves. The defensible claim is "larger TTC margin and much less
   low-TTC exposure, at the cost of longer braking events and slightly lower
   throughput", not "safer" or "more comfortable".

4. **The real model behaves like a saturating rule, not a negotiator.** With
   vehicle 60 on `qwen-flash` and everything else on IDM, the paired cost on that
   vehicle is +2.2 to +102.3 s per run — median +3.6 s, mean +26.2 s, the mean
   pulled up by two long-bottleneck runs that cost over a minute each.
   The model tracked the zone limit and the road limit and used the headway
   dimension to modulate; it never requested more than the road limit, so the
   planner clamp and the road-limit cap never had to act, while the headway ramp
   and the recovery guard did. No overlap occurred, but the fleet's minimum TTC
   fell to 0.76 s in one run, below the IDM run it replaced.

5. **Most of the work went into the measurement, and that was the right call.**
   Three definitions changed the conclusions: demand-wide versus completed-only
   efficiency (an earlier "+9.5 % throughput" claim was withdrawn), record
   versus event counting (which exposed longer, not more frequent, braking), and
   the validity boundary (post-overlap data no longer leaks into min-gap and
   TTC). Provenance (version split plus per-row source hashes) is what made a
   stale label diagnosable instead of fatal.

6. **The scope of these conclusions is narrow, and deliberately so.** One
   control vehicle, one model, one prompt, one temperature, eight seeded runs, a
   synchronous client that does not advance simulation time. The results say
   nothing about fleet-wide LLM control, about real communication delay, or
   about whether a different prompt would do better. They do say that the
   architecture is implementable, measurable and honestly comparable with IDM —
   and that in this setting the conventional controller is still the better
   system-level choice.
