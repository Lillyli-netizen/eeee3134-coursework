# Exploring LLM-Assisted Longitudinal Vehicle Control

## Coursework Part II — Technical report for student review

Student name: [complete]  
Student ID: [complete]  
Module: [confirm official module title and code]  
Date: 10 November 2026

**Document status.** This is an AI-assisted technical draft, prepared from the supplied simulation code, experiment files and decision logs. Sections 1–4 and the technical appendices are provided for review and editing. Section 5 is intentionally unwritten: the coursework requires personal reflection and conclusions to be written entirely by the student. Formatting and submission requirements should be checked against any later module announcement.

## 1. Introduction and objectives

This coursework investigates how a large language model (LLM) can participate in longitudinal vehicle control within an existing car-following simulator. Longitudinal control concerns acceleration and braking along the road; lane changes, steering and route choice are outside this project. The conventional baseline is the Intelligent Driver Model (IDM), which uses vehicle speed, distance to the leader and relative speed to calculate acceleration [1, 2].

The project implements a hierarchical controller. A planner proposes a target speed and desired time headway, while an IDM executor converts these quantities into acceleration at each simulation step. Two distinct forms of evidence are used: an actual Qwen-controlled vehicle within IDM traffic, and larger offline comparisons using explicitly programmed rule planners. The latter test the architecture and policy choices; their results are not measurements of LLM performance.

The technical investigation addresses three questions:

1. Can Qwen provide structured plans that are used in a closed simulation loop, including when individual requests fail?
2. How do the observed trajectories and efficiency, safety-proxy and comfort measures differ from an IDM baseline under common external demand?
3. Which implementation and measurement choices limit the interpretation of those differences?

The coursework is exploratory: a performance improvement over IDM is not assumed. The simulator provides a controlled setting for examining integration and measurement, rather than evidence of readiness for a real vehicle.

## 2. Methodology and implementation

### 2.1 Simulation environment and conventional baseline

The supplied implementation represents a single open road with a temporary low-speed region. Vehicles enter at the upstream boundary when admission conditions permit and leave at 5,000 m. A vehicle has a permanent leader reference in the no-overtaking setting. Accelerations are calculated for all active vehicles before any vehicle moves, avoiding dependence on the order of state updates.

| Setting | Value in the supplied code |
|---|---|
| Road and vehicle length | 5,000 m; 5 m |
| Time step and observation horizon | 0.1 s; 1,000 s |
| Normal desired speed; entry speed | 30 m/s; 30 m/s |
| Low-speed region | 4,500–4,700 m; desired speed 2 m/s for affected vehicles |
| Low-speed influence assignment | Deterministic per-vehicle draw with configured probability 0.7 |
| IDM minimum gap and baseline headway | 2 m; 1.0 s |
| Maximum acceleration; comfortable deceleration | 1.5 m/s²; 2.0 m/s² |
| Numerical maximum deceleration | 8.0 m/s² |
| Relative-speed perception-noise scale | 0.5 m/s |

*Table 1. Implementation parameters read directly from the supplied code; they are not calibrated values.*

The low-speed condition is applied only to influenced vehicles inside the region during its active period, subject to the code's entry-time condition. Thus, it is a simplified disturbance model, not a physical lane closure or a speed limit applied identically to every vehicle. Parameters describe this coursework implementation; they are not calibrated to a particular real road.

| Experiment | Scheduled arrival intervals | Low-speed period |
|---|---|---|
| E1 | Fixed, 1.7 s | 100–300 s |
| E2 | 1.0 s + exponential draw of mean 0.5 s | 100–300 s |
| E3 | Fixed, 1.7 s | 100–1,000 s |
| E4 | 1.0 s + exponential draw of mean 0.5 s | 100–1,000 s |

*Table 2. The four demand and disturbance scenarios.*

The implemented IDM follows the usual free-road and leader-interaction structure [2]. In compact notation, its unbounded acceleration is

\[a_{IDM}=a[1-(v/v_0)^\delta-(s^*/s)^2],\]

with desired dynamic gap

\[s^*=s_0+\max(0,vT+v\Delta v/(2\sqrt{ab})).\]

Here, s is the bumper-to-bumper gap and positive relative speed means closing on the leader. The coursework code adds perception noise to relative speed and bounds deceleration. It also clips speed at zero and uses the average of old and new speed to advance position. The underlying IDM equation is retained, but the implementation is not claimed to be an unchanged reproduction of a published model or a formally verified safety controller.

### 2.2 Planner, guardrails and executor

![Controller architecture](figures/architecture.png)

*Figure 1. Planner–executor architecture, redrawn for this report from the supplied code. The original simulator is extended with common-demand bookkeeping, deterministic noise and admission checks; the figure does not imply that these extensions belong to the original teaching framework.*

The planner observes speed, current desired-speed limit, leader gap and relative speed, low-speed-region activity, and distances to the region's start and end. Distances and speeds are supplied explicitly in metres and metres per second. A valid reply contains `target_speed`, `time_headway` and a short explanatory `reason`.

Three control modes are distinguished:

| Mode | Planner | Role in the investigation |
|---|---|---|
| IDM | None | Conventional baseline |
| Mock / Mock no-ant | Deterministic hand-written policies | Offline architecture and policy comparison |
| Qwen + IDM | Actual `qwen-flash` requests | Small-scale real-model closed-loop cases |

*Table 3. The three control modes.*

The Mock planner reduces its target speed on approaching an active low-speed region within 300 m, using a linear ramp. Both Mock variants request headway 1.3 s when closing sufficiently quickly on a nearby leader and 1.0 s otherwise. The no-anticipation variant removes the approach-speed ramp. The realised traffic states subsequently differ, so the same headway rule need not produce identical headway histories across variants.

Replies are checked for the expected structure, numerical convertibility and finite values. Accepted targets are bounded by the current road condition, and accepted headways by [0.8, 2.0] s. An invalid request leaves the previous cached plan in place. An explicit zero-speed target uses a stopping branch rather than dividing by zero in IDM.

The executor applies the road-speed cap, increases headway gradually at **0.5 s of headway per second**, and restores a stale low-speed target once the vehicle has passed the region end. Requested model values, guarded plan values and executor values have separate logs or counters. A 1 s sampled execution trace complements the per-call decisions; this trace cannot reconstruct every 0.1 s override event, so aggregate counters remain necessary.

Mock calls have a minimum interval of 2 s and periodic refresh of 15 s, with 300 m notice distance. Real-Qwen cases use 10 s, 60 s and 500 m respectively. Zone transitions and close/fast-closing leaders can also trigger a call, subject to the minimum interval. These differences preclude treating Mock and Qwen as interchangeable implementations of one measured policy.

### 2.3 Common demand, admission and reproducibility

Arrival schedules are generated before the simulation using a dedicated random stream. Within each experiment and seed, all modes use the same schedule. Bottleneck influence and perception noise are keyed to seed, vehicle ID and simulation step rather than a shared sequence of random draws. Schedule hashes and source-file hashes are included in result rows.

When admission is blocked, demand remains in an off-road FIFO queue. The code checks both an entrance-spacing condition and an added stopping-distance condition based on entry speed and leader speed. The latter is a project extension, applied to all controllers. Its simplified assumptions and the fixed high entry speed can materially affect braking near the boundary; common implementation alone does not make that effect independent of the policy.

The offline grid contains four experiments, eight seeds and three controllers: 96 runs. The real-model study contains eight Qwen cases and eight paired IDM baselines, using seeds 1 and 2. Only vehicle 60 is model-controlled. Qwen uses temperature 0.2 and prompt version `v2-tuned-2026-11`. The API is called synchronously: simulation time pauses while Python waits for a response. These cases therefore test an idealised zero-simulation-latency planner, not real-time deployment.

### 2.4 Evaluation measures and valid scope

For vehicle i, let A_i denote scheduled arrival, E_i actual entry and X_i exit. Completed travel time is X_i − E_i; completed system time is X_i − A_i. Neither mean includes vehicles that have not exited. Both are reported with entry, completion and waiting counts.

To include all demand within a common horizon H, define

\[\bar C_H=\frac{1}{N}\sum_{i=1}^{N}(\min(X_i,H)-A_i),\]

where an uncompleted or never-admitted vehicle has its endpoint set to H. This is mean time accumulated within the observation window, not mean completed journey time or delay relative to free flow. It accounts for off-road waiting, but does not reveal how long the residual queue would take to clear after H. The denominator and horizon must match within a comparison.

Exit throughput is the number of exits divided by 1,000 s and converted to vehicles/hour. It is a finite-window output rate, not a calibrated capacity estimate. Safety proxies include minimum gap and time-to-collision (TTC). For a closing pair with positive gap, TTC = gap / closing speed; non-closing samples receive a large sentinel in the code. Minimum TTC does not itself establish collision probability or overall safety.

Low-TTC exposure sums vehicle-pair time below 3 s and 1.5 s; normalised exposure divides qualifying pair-samples by all observed pair-samples. Hard braking means acceleration at or below −6 m/s², stopping means speed below 0.1 m/s, and an event is a contiguous segment of qualifying samples. Durations are fleet sums, not one vehicle's elapsed time. Events are assigned to the entry zone if they start below 500 m. Mean absolute jerk measures changes in acceleration per second.

At the first detected overlap or adjacent order crossing, pair statistics and comfort samples are truncated to the preceding interval and the run is flagged. The current formal datasets contain no flagged cases. Invalid-run efficiency figures would still require separate treatment; the existence of a flag does not make post-failure travel times physically meaningful.

## 3. Experiments, results and technical discussion

### 3.1 Real Qwen: vehicle 60 within IDM traffic

The eight cases used 189 logged calls, with four invalid returns and no retries recorded in the supplied decision logs. Each paired baseline uses the same demand schedule. The model-generated plans are coupled to traffic through the executor; these are simulation closed-loop cases, not detached questions answered without vehicle feedback.

| Case | Calls | IDM travel (s) | Qwen travel (s) | Difference (s) | Fleet min TTC: IDM / Qwen (s) |
|---|---|---|---|---|---|
| E1 S1 | 15 | 299.4 | 301.7 | +2.3 | 2.32 / 2.11 |
| E1 S2 | 15 | 296.9 | 299.4 | +2.5 | 2.27 / 1.98 |
| E2 S1 | 16 | 313.4 | 315.6 | +2.2 | 1.47 / 0.76 |
| E2 S2 | 15 | 309.8 | 312.4 | +2.6 | 2.28 / 2.28 |
| E3 S1 | 34 | 520.0 | 583.0 | +63.0 | 1.99 / 1.91 |
| E3 S2 | 29 | 511.7 | 516.3 | +4.6 | 1.96 / 1.96 |
| E4 S1 | 35 | 530.0 | 632.3 | +102.3 | 1.42 / 1.05 |
| E4 S2 | 30 | 521.9 | 552.3 | +30.4 | 1.91 / 1.98 |

*Table 4. Absolute travel times are taken directly from `evidence/qwen_real/metrics.json`, `per_vehicle["60"].travel_time_s` (entry-to-exit duration, not the absolute exit timestamp). Differences are Qwen minus IDM. Fleet minimum TTC is a run-level minimum over observed pairs; E4 S1 is 1.05 s in the Qwen case. The 0.76 s E2 S1 event is identified below and does not involve vehicle 60.*

![Qwen ego travel comparison](figures/qwen_real_ego.png)

*Figure 2. The eight paired ego travel times and their differences, generated from the supplied real-model metrics. Rounded bar annotations supplement the more precise values in Table 4.*

All eight ego differences are positive. The mean is +26.2 s, the median +3.6 s and the largest +102.3 s. Reporting all three prevents the two large long-bottleneck penalties from being hidden by the median. Pooling eight different cases is descriptive only: two seeds per scenario and one sampled model trajectory per case do not support a general population claim about Qwen.

No body overlap or order crossing is flagged. The Qwen-case fleet minimum TTC is 1.05 s in E4 S1 and 0.76 s in E2 S1. Offline replay now locates the latter at t = 996.9 s near x = 54 m: IDM-controlled vehicle 665 approaches the stationary entrance-queue vehicle 664 at about 6.0 m/s with a 4.6 m gap. This is a low-speed entrance-queue joining event, not an event involving the Qwen-controlled ego; vehicle 60 has a minimum leader-pair TTC of approximately 2.83 s in E2 S1. The 0.76 s value remains a fleet-level observation in that combined-system run, but does not demonstrate an ego near-collision or isolate an effect caused by Qwen.

All accepted requests remained inside hard guardrail bounds: the recorded clamp count and road-limit cap count are zero. Recovery was activated once in five cases, while headway ramping occurred for 12–28 steps per case. Thus, the resulting trajectories belong to the **combined Qwen–executor system**, not to an unconstrained model. One requested headway of 1.8 s exceeds the prompt's advisory 1.0–1.6 s range but remains within the implemented hard bounds. Prompt instructions and enforced limits are different mechanisms.

For example, the first E4 S1 decision at simulation time 90.1 s observes speed 30 m/s, a 42.3 m gap and an inactive bottleneck. It requests 30 m/s and 1.4 s headway. This shows a structured plan, but the accompanying reason is not proof of a faithful internal reasoning process. Later outcomes must be assessed from state and execution records.

Across the 189 per-call log entries, observed call duration totals approximately **153.8 s**, or **0.81 s per attempt**. The 185 successful calls contribute about 113.8 s (0.61 s each); four failures contribute about 40.0 s. Each failure took approximately 10 s, consistent with the configured timeout, but the historical records do not preserve the original exception type. The earlier client summary of 113.7 s excludes failed-call waits and must not be called total blocking time. These are request durations, not monetary cost or entire experiment runtime.

### 3.2 Real-model time–space comparison and entrance event

![Highlighted vehicle 60 in E4 S1](supplement_20261110/fig_ego_highlight_E4S1.png)

*Figure 3. Offline reconstruction of E4 S1 using the stored Qwen decisions and the supplied fixed-code snapshot; no new API calls. Left: IDM baseline, vehicle 60 travel time 530.0 s. Right: Qwen–IDM case, 632.3 s. Vehicle 60 is highlighted in black; sampled background trajectories are coloured by speed. Axes and colour scale are shared. See `supplement_20261110/回放验证记录.md` and the independent replay audit for fidelity checks.*

A trajectory's slope represents speed; a nearly horizontal section indicates little progress. The explicitly highlighted ego removes the ambiguity in the earlier stride-selected panels. E4 S1 is shown because it has the largest ego travel-time penalty, not because it represents every case. The paired difference is +102.3 s. These are reconstructed trajectories from the stored decisions, rather than a new stochastic model run.

![E2 S1 entrance-queue minimum TTC event](supplement_20261110/fig_ttc_event_E2S1.png)

*Figure 4. Offline replay localisation of the 0.76 s fleet-minimum TTC event in E2 S1. Vehicle 665 joins the entrance queue behind vehicle 664 at t = 996.9 s, near x = 54 m. At the minimum, the gap is approximately 4.6 m, follower speed 6.0 m/s and leader speed 0.0 m/s. Neither vehicle is ego 60. The displayed TTC curve is capped at 15 s for readability.*

The local view separates this entrance-boundary interaction from the Qwen ego trajectory. It also illustrates why an extreme fleet statistic must be traced to its vehicle pair and location before being interpreted. This evidence identifies the event but does not establish that its occurrence is independent of upstream control effects. No collision-probability claim follows from the TTC value alone.

### 3.3 Offline rule-planner comparison

The larger experiment grid separates systematic policy comparison from the small real-model study. Values below are arithmetic means over eight seeds. Fractional vehicle counts therefore represent averages, not partial vehicles. Full per-run records and additional metrics are supplied in the evidence directory.

| Exp. | Mode | Entered | Exited | Still outside | Mean accumulated all-demand time (s) |
|---|---|---|---|---|---|
| E1 | IDM | 589.0 | 466.4 | 0.0 | 226.7 |
| E1 | Mock | 589.0 | 458.5 | 0.0 | 235.6 |
| E1 | Mock no-ant | 589.0 | 464.4 | 0.0 | 229.2 |
| E2 | IDM | 663.5 | 466.4 | 6.9 | 261.5 |
| E2 | Mock | 575.8 | 456.3 | 94.6 | 269.3 |
| E2 | Mock no-ant | 575.8 | 459.5 | 94.6 | 264.2 |
| E3 | IDM | 589.0 | 126.1 | 0.0 | 422.2 |
| E3 | Mock | 589.0 | 123.1 | 0.0 | 425.6 |
| E3 | Mock no-ant | 589.0 | 126.1 | 0.0 | 422.2 |
| E4 | IDM | 664.6 | 126.1 | 7.8 | 432.7 |
| E4 | Mock | 575.9 | 123.1 | 96.5 | 435.6 |
| E4 | Mock no-ant | 575.9 | 126.1 | 96.5 | 432.7 |

*Table 5. Demand, admission and accumulated-time comparison (eight-seed means).*

Mock's mean accumulated all-demand time is higher by 8.9, 7.8, 3.4 and 2.9 s in E1–E4; the difference is positive for every paired seed in each scenario. Exit throughput is lower by approximately 1.7%, 2.2%, 2.4% and 2.4%. The no-anticipation version has smaller penalties, but this does not establish that anticipation is universally harmful.

E2 illustrates the importance of scope. Completed-trip fleet means are 305.8 s for IDM and 266.1 s for Mock, yet the latter leaves approximately 94.6 scheduled vehicles outside, versus 6.9 for IDM. The admission difference is about 87.8 vehicles, not 95. Restricting comparison to the same completed IDs still gives shorter Mock on-road travel (about −39.8 s), but longer scheduled-arrival-to-exit time (about +11.3 s); both are computed from the per-vehicle `completed_*_by_id_s` records over IDs that completed under both modes. Additional waiting is not a travel-efficiency improvement. Common-ID analysis still excludes unfinished journeys; the all-demand measure and completion counts provide complementary coverage.

| Exp. | Mode | Mean run-min TTC (s) | TTC <3 s (pair·s) | HB events | HB duration (s) | Stop duration (s) |
|---|---|---|---|---|---|---|
| E1 | IDM | 2.15 | 292.7 | 5.0 | 6.5 | 19.6 |
| E1 | Mock | 2.58 | 10.2 | 2.8 | 0.3 | 251.6 |
| E1 | Mock no-ant | 2.25 | 39.4 | 4.8 | 6.4 | 0.0 |
| E2 | IDM | 1.79 | 1069.8 | 625.9 | 169.8 | 7660.5 |
| E2 | Mock | 2.67 | 7.5 | 637.8 | 593.5 | 210.2 |
| E2 | Mock no-ant | 2.25 | 41.3 | 639.9 | 599.6 | 0.0 |
| E3 | IDM | 1.96 | 4563.5 | 5.0 | 6.5 | 18648.0 |
| E3 | Mock | 2.30 | 98.5 | 2.8 | 0.3 | 18753.9 |
| E3 | Mock no-ant | 2.24 | 127.0 | 4.8 | 6.4 | 16475.9 |
| E4 | IDM | 1.88 | 5454.4 | 632.8 | 173.7 | 31612.0 |
| E4 | Mock | 2.39 | 63.2 | 635.9 | 589.4 | 16118.5 |
| E4 | Mock no-ant | 2.25 | 99.7 | 638.1 | 595.6 | 14517.1 |

*Table 6. HB denotes hard braking. These are seed averages of run-level measures, including run minima; a mean minimum is not a pooled minimum. Fleet-summed durations can exceed the 1,000 s horizon.*

Mock has higher mean run-minimum TTC, with substantially less low-TTC exposure, but its E2 and E4 hard-braking durations are about 3.5 and 3.4 times IDM's despite similar event counts. E3 stop duration is slightly higher rather than lower. E1 stopping is also worse. These metrics do not support an overall safety or comfort improvement, and they remain rule-planner findings.

Normalisation preserves the low-TTC direction in the random cases: mean fractions below 3 s are approximately 0.00622 versus 0.00006 in E2, and 0.01899 versus 0.00026 in E4, for IDM versus Mock. The fractions refer to observed vehicle-pair samples. Neither these ratios nor the absolute totals represent a real-world crash-rate estimate.

![E2 IDM](figures/exp2_idm_seed1_readable.png)

*Figure 5a. E2 S1 IDM trajectories, plotting one in five vehicles.*

![E2 Mock](figures/exp2_llm_mock_seed1_readable.png)

*Figure 5b. E2 S1 Mock trajectories under the same scheduled demand. A visually less congested road must be interpreted alongside the larger off-road queue; fewer admitted vehicles can alter the appearance.*

### 3.4 Limits of interpretation

These results depend on one road geometry, the configured inflow and disturbance, the teacher-derived IDM parameters and an uncalibrated noise implementation. The real-model sample uses one model, one prompt, one temperature and two seeds per scenario, without repeated generations at identical conditions. Different prompts, triggers, initial states or communication timing could change the outcomes. The fixed entering speed and boundary gate contribute heavily to braking in random-arrival scenarios. Large macro-level effects cannot be assigned solely to the planner's textual reason or one control parameter.

The simulator does not model response-time delays during HTTP requests, asynchronous plan delivery, steering or sensor uncertainty beyond the configured noise. Caching and a bounded actuator are useful mechanisms, not a proof of stability or safety. This is sufficient for examining the coursework's integration questions, but insufficient for a deployed autonomous-driving claim.

## 4. Challenges, investigation and problem-solving

### 4.1 Making the comparison independent of random-number consumption

The initial implementation shared random draws between traffic generation and control-related noise. Strategy-dependent changes could then change later demand or disturbances despite an identical seed. The revised code generates demand independently and keys other noise to vehicle and step. Equal schedule hashes verify common scheduled demand within each pair; they do not imply equal admissions or equal vehicle states. Per-vehicle data make comparison of vehicle 60 possible without using a fleet mean as its baseline.

### 4.2 Correcting an apparent efficiency advantage

Earlier drafts described a 9.5% improvement using a travel-time comparison. Review identified different admission counts and the inclusion of incomplete journeys in the old metric. Those figures are excluded from the formal result tables. The revision separates completed journeys, unfinished journeys and off-road waiting, and introduces the finite-horizon all-demand measure. It also distinguishes a difference between group means from a same-ID paired difference.

The entrance diagnosis adds a useful counterexample to a proposed explanation. In E2 S1, by 100 s demand is 72 vehicles, IDM has admitted 69 and both Mock variants 61. The leading vehicle is only around 3,000 m: the entrance difference already exists before any vehicle reaches the 4,500 m bottleneck. This rejects bottleneck spillback as an explanation for that early window. The blocking vehicles are slower and request longer headways under Mock, but the causal contribution of each mechanism has not been isolated.

### 4.3 Separating events, samples and failure validity

Counting each 0.1 s braking sample as an event overstates event frequency. The implementation now reports contiguous events together with their summed duration. Similarly, omitting only an overlapping pair at an individual time step does not make later statistics valid. A synthetic regression case uses 25 m spacing before an order crossing and 1 m after it: correct truncation returns a 25 m minimum with only two pre-crossing pair-samples and excludes later braking and jerk.

Fifteen targeted checks passed for the original reviewed snapshot, covering demand, plan validation, stopping, recovery, accounting, validity and execution counters. The subsequently supplied `source_snapshot_fixed/` adds an offline budget-abort regression and distinguishes a budget exception from ordinary planner failures, preserving completed results when the budget is reached. The historical `source_snapshot/` is retained without rewriting its provenance. These checks verify the tested behaviours, not every possible input or a formal safety property. None of the original real-model cases hit the 250-call ceiling, and no new paid experiment was required for these delivery fixes.

### 4.4 Distinguishing model decisions from executor interventions

An earlier counter incorrectly labelled any target below the road limit as an executor override. Normal low-speed planning was therefore counted as interference, while recovery from a stale plan was missed. The current counters instead distinguish planner clamping, road-limit caps, recovery activations and headway ramp steps. In the real cases no clamp or road-limit cap occurred, but five recoveries did. This distinction is necessary to attribute behaviour to the combined system without overstating model autonomy.

### 4.5 Auditability and remaining delivery work

Result rows record simulation version `3.0-fair-sim`, metrics version `3.0-metrics-v4` and hashes of ten source files. The reviewed data comprise 96 offline rows and 16 real-study rows. An offline replay of the 35 E4 S1 Qwen decisions reproduced every logged observation and the principal reported metrics without new network calls. Such replay checks consistency between supplied code, plans and outcomes; it does not independently authenticate provider billing or the original remote service.

The package retains its original experiment files, including the historical latency summary. A separate derived audit records the corrected latency. Original evidence is not overwritten. The 10 November supplement supplies fixed executable code, a highlighted ego comparison and a local entrance-event figure. Independent offline checks compare replay observations, sampled execution traces and metrics with the original logs; their results are stored in `supplement_20261110/replay_audit_codex.json`. Original experimental source hashes remain associated with the original snapshot; the fixed code is identified separately. No new model, paid batch or fleet-scale LLM experiment is needed to support the scope of this report.

## 5. Personal Reflection and Conclusions — student-authored sections

### 5.1 Personal Reflection

[Reserved for the student. No AI-generated personal reflection is provided.]

### 5.2 Conclusions

[Reserved for the student. No AI-generated conclusion is provided.]

## References

[1] Treiber, M., Hennecke, A. and Helbing, D. (2000). Congested traffic states in empirical observations and microscopic simulations. Physical Review E, 62, 1805–1824. https://doi.org/10.1103/PhysRevE.62.1805. Bibliographic record and abstract: https://arxiv.org/abs/cond-mat/0002177. The record and abstract were checked; no claim of a full-paper review is made.

[2] Treiber's traffic-simulation site. The Intelligent-Driver Model and its Variants. https://traffic-simulation.de/info/info_IDM.html. Accessed 9 November 2026. Used for the model's inputs, acceleration structure and interpretation of its parameters; experimental parameter values are taken from the coursework code instead.

[3] Coursework.pdf, supplied assignment brief. Part II and the general requirements. Used to determine the report scope and the student-only reflection/conclusion requirement.

[4] Supplied project evidence: Codex评审包_20261109.zip; source code, fair_v3 results and qwen_real decision/execution logs. The separate Codex_反思提问包_20261109.zip contains later narrative revisions but no updated executable code or raw dataset. The additional `supplement_20261110/` and `source_snapshot_fixed/` directories provide offline replay records, supplemental figures and later code fixes. Tables in this report are derived from the original metrics, not from external papers or figure annotations.

## Appendix A. Evidence and calculation notes

The accompanying `图表与资料索引.md` maps every figure and table to its source. The `evidence/` directory includes the supplied result files and Qwen logs; these are copies, not newly executed API experiments. `evidence/derived_audit.json` records the latency recalculation and selected comparisons. `evidence/technical_summary.csv` provides unrounded derived seed summaries for editing tables. All small rounding differences in the displayed tables are presentation choices.

Means and standard deviations, where needed, should be computed across the eight seed-level statistics rather than treating millions of time samples as independent runs. The main tables emphasise effect direction and counts; the full supplied summaries retain seed variability. With only two seeds per real-model scenario, no significance claim is made. Same-ID completed-vehicle comparisons condition on common completion and must remain labelled accordingly.

## Appendix B. Technical assistance and authorship record

AI tools were used extensively for code generation, debugging, review, technical analysis and preparation of this technical draft. The submitted report should accurately identify the student's actual choices and checks without claiming independent coding or first discovery of AI-identified issues. The separate personal worksheet is a set of questions and evidence pointers only. Sections 5.1 and 5.2 must be completed independently by the student; the supplied earlier AI-written reflection drafts and conclusion paragraphs are not incorporated here.
