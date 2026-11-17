# Car-Following Simulation — Teaching Version

This directory contains a readable, corrected car-following simulation for
teaching IDM, traffic bottlenecks, and stop-and-go traffic.

## Program structure

The simulation follows the same sequence at every time step:

```text
Generate vehicle
    -> check road conditions
    -> calculate every vehicle's acceleration
    -> update every vehicle's speed and position
    -> record the results
```

| File                 | Purpose                                              |
| -------------------- | ---------------------------------------------------- |
| `config.py`          | Road, IDM, bottleneck, and experiment parameters     |
| `vehicle.py`         | Shared vehicle state and motion update               |
| `vehicle_idm.py`     | IDM acceleration calculation                         |
| `simulator.py`       | The five-step simulation loop                        |
| `plotting.py`        | Speed-colored time-space diagram                     |
| `vehicle_knn.py`     | Empty extension point for a future KNN policy        |
| `vehicle_llm.py`     | Empty extension point for a future LLM policy        |
| `test_simulation.py` | Optional correctness tests; not part of a normal run |

## Run

From the repository root:

```bash
.venv/bin/python car-following-simulation/main.py --experiment 1
```

The default duration is defined only once, as `DEFAULT_TIME_MAX` in
`config.py`. Override it for one run with:

```bash
.venv/bin/python car-following-simulation/main.py \
  --experiment 1 --time-max 500
```

Save the plot without opening a window:

```bash
.venv/bin/python car-following-simulation/main.py \
  --experiment 1 \
  --output car-following-simulation/results/experiment-1.png \
  --no-show
```

## Experiments

| Experiment | Arrival process        | Bottleneck duration    |
| ---------- | ---------------------- | ---------------------- |
| 1          | Fixed arrival interval | 100–300 seconds        |
| 2          | Random interval        | 100–300 seconds        |
| 3          | Fixed arrival interval | 100 seconds to the end |
| 4          | Random interval        | 100 seconds to the end |

The temporary low-speed region is configured relative to the road end in
`config.py`. It is a simple single-lane representation of a temporary highway
bottleneck; it does not model an actual lane drop or lane-changing behavior.

A vehicle is affected only if it enters the low-speed region after the
bottleneck has started and before it ends. A vehicle that entered the region
before the start time continues through without adopting the bottleneck speed.

## Important correction

The original program updated speed first and then used the updated speed in a
second kinematic formula for position. This version updates speed and position
together using the average of the old and new speeds:

```text
new speed = old speed + acceleration x time step
distance  = (old speed + new speed) / 2 x time step
```

All accelerations are calculated before any vehicle moves, so every vehicle
uses the same pre-update traffic state.

## Optional tests

```bash
cd car-following-simulation
../.venv/bin/python -m unittest -v test_simulation.py
```

The tests are separate from the teaching workflow and do not run when
`main.py` is executed.

---

# LLM extension (coursework Part II) — `llm_car_following`

This copy extends the teaching framework with LLM-based car-following
control. Everything below the line is our addition; everything above it is
the teacher's original README.

## Requirements

```bash
pip install -r requirements.txt   # matplotlib, numpy — that is all
```

The LLM clients use only the Python standard library (`urllib`), so no SDK
install is needed. Real-API runs additionally need:

```powershell
$env:DASHSCOPE_API_KEY = "sk-..."   # never hard-coded; env var only
$env:LLM_BASE_URL = "https://dashscope.aliyuncs.com/compatible-mode/v1"
```

## Run

Offline comparison (no API cost), 4 experiments x 8 seeds x 3 controllers:

```bash
python run_comparison.py --experiment 1 2 3 4 --seed 1 2 3 4 5 6 7 8 \
  --modes idm llm_mock llm_mock_noant \
  --output-dir results/fair_v1 --json-output results/fair_v1/metrics.json
```

Single real-LLM vehicle (ego = id 60) inside IDM traffic:

```bash
python run_comparison.py --experiment 1 --seed 1 --modes llm_qwen \
  --llm-ego-id 60 --output-dir results/qwen_check
```

Verification of the fair-comparison fixes (offline, < 1 min):

```bash
python test_fixes.py
```

## What changed relative to the teacher's framework

Teacher-original files, untouched: `config.py`, `main.py` (only a
`vehicle_class` argument added), `vehicle_knn.py`, `plotting.py` (only
optional stride/line-width arguments added), `test_simulation.py`.

Modified teacher files (behaviour-compatible, reasons documented in code):

| File             | Change                                                                                                                                                                | Reason                                                                                               |
| ---------------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ---------------------------------------------------------------------------------------------------- |
| `vehicle.py`     | Bottleneck-influence flag now drawn from a deterministic per-vehicle hash instead of the global random stream; bookkeeping fields (`scheduled_arrival`, `entry_time`) | Fair comparison: every strategy must face the same assignment                                        |
| `vehicle_idm.py` | Perception noise is now a deterministic function of (seed, vehicle id, step)                                                                                          | Same noise for every strategy; the global stream made runs incomparable                              |
| `simulator.py`   | Arrival schedule pre-generated once per (experiment, seed); entry deferral logged with waiting time; **kinematic entry condition (our addition)**                     | Common demand; delayed demand is recorded, not dropped; spawned cars must be physically able to stop |
| `vehicle_llm.py` | Was an empty stub; now the two-layer LLM vehicle                                                                                                                      | Coursework task                                                                                      |

**Provenance of the two entry conditions (verified by diff, not assumed).**
`simulator.py` gates entry with two checks. The first is the teacher's
original spacing rule (`vehicle_length + idm_minimum_spacing +
initial_speed * idm_time_headway`). The second, the kinematic stopping-
distance rule, is **our addition**; it does not exist in
`teaching_artificial_intelligence/car-following-simulation/simulator.py`.
It is applied identically to every controller, but it must not be described
as part of the original framework.

New files: `llm_client.py` (mock / qwen / qwen_accel / mock_noant),
`vehicle_llm_direct.py` (single-layer ablation), `noise.py`,
`metrics.py`, `run_comparison.py`, `test_fixes.py`, `diagnose_entry.py`.

## Metric names (v3)

* `mean_system_time_completed_s` — scheduled arrival → exit, **completed
  vehicles only**. Not demand-wide; vehicles that never entered are absent.
* `mean_cumulative_system_time_all_s` — finite-horizon cumulative time over
  **all scheduled demand**: `(exit_time or time_max) - scheduled_arrival`,
  including never-admitted and incomplete vehicles. Truncated by
  `time_max`, so it is not a completed travel time.
* `min_ttc_s` / `ttc_p05_s` / `low_ttc_exposure_s` — pair-time exposure;
  `low_ttc_fraction_of_pair_samples` normalises it by observed pair-samples.
* `valid_until_s` — all pair, speed and comfort statistics are computed for
  `t < valid_until_s` only. The boundary is the EARLIER of the first body
  overlap and the first adjacent order crossing, and the statistics are
  recomputed on the truncated interval.
* `statistics_invalid` / `invalid_reason` — unified flag and cause
  (`overlap` / `order_crossing`). `overlap_invalid` is kept with its narrow
  meaning "bodies actually overlapped".
* `admission_block_*` — which rule deferred entry and where the blocking
  vehicle was; evidence, not a causal attribution.
* `llm_guardrail_corrections` / `llm_recovery_guard_activations` /
  `llm_road_limit_cap_steps` / `llm_headway_ramp_steps` — model output,
  guarded cached plan and executed plan are counted separately. A planner
  that recommends a low speed is **not** counted as an executor override.

## Provenance

Each result row carries `sim_version`, `metrics_version` and
`source_hashes` (SHA-256 prefixes of every file that can change a result).
`results/fair_v3/MANIFEST.md` lists the full hashes, environment versions
and the exact commands. Do not mix rows from different version stamps.

## Known limitations (reported, not hidden)

* **API latency is wall-clock only.** `QwenLLMClient` calls the API
  synchronously: the Python process blocks, but simulation time does not
  advance during the call. Results therefore assume a *zero-latency*
  planner and do **not** validate communication delay or real-time control.
* **The real-model case is small.** One ego (id 60) was driven by
  `qwen-flash` (prompt `v2-tuned-2026-11`) in 4 experiments × 2 seeds, 189
  calls, all other vehicles on IDM. 4 calls timed out (2.1 %) and were handled
  by fail-operational caching. It is not a fleet-wide LLM experiment, and the
  earlier 16/16/38/38 estimate is superseded by measured counts
  (15/15/16/15 and 34/29/35/30).
* The `-16 km/h` line in the time-space diagram is the teacher's *reference
  line* for the expected congestion wave speed, not a value we measured.
* Mock results describe a deterministic rule-based planner. They say
  nothing about the decision quality of a real LLM and are **not** an
  upper bound on it: the mock's closed-form responses can be better or
  worse than real model output.
* IDM is **not** proven collision-free. It did not produce body overlap in
  these runs; that is an observation over 96 runs, not a guarantee.

