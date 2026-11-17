"""Post-run metrics: travel time, throughput, safety and LLM statistics.

Fair-comparison revision. The metric definitions below are deliberately
strict; the previous version of this file is superseded and its numbers
must not be mixed with these.

Definitions
-----------
Demand / entry / exit:
  * demand_total  — scheduled arrivals within [0, time_max] (identical
    across strategies for a given experiment+seed).
  * entered       — vehicles actually admitted to the road.
  * exited        — vehicles that reached the road end before time_max.
  * incomplete    — entered but still on the road at time_max.
  * waiting       — scheduled but never admitted (still queued off-road).

Travel time / system time:
  Only EXITED vehicles contribute to mean_travel_time_s and to
  mean_system_time_completed_s (scheduled arrival -> exit). Using the time
  a still-travelling vehicle has spent on the road as if it were a
  completed trip would systematically flatter slow strategies, so
  incomplete trips are reported separately and never mixed in.

  Because the completed-only system time says nothing about vehicles that
  never entered, a second, demand-wide metric is reported:
  mean_cumulative_system_time_all_s = mean over ALL scheduled arrivals of
  min(exit_time, time_max) - scheduled_arrival, with never-admitted
  vehicles contributing time_max - scheduled_arrival. It is a TRUNCATED
  cumulative time (it grows with the observation window), not a completed
  travel time. completed_fraction, waiting_at_end and incomplete are
  always reported next to it.

Events vs records:
  A *record* is one history sample (every time_step) meeting a condition;
  an *event* is a maximal run of consecutive records meeting it. Hard
  braking uses acceleration <= -hard_brake_threshold; stopped uses
  speed < stop_threshold. Events are additionally split by the position
  where they START (entry zone x < entry_zone_length vs road interior), so
  boundary effects stay visible instead of being deleted. Total and maximum
  event durations are reported because the same event count can hide very
  different exposure.

Safety (TTC):
  Computed at full simulation resolution (every time_step, every
  consecutive pair). We report the minimum, exposure time below 3.0 s and
  1.5 s, and percentiles (p1, p5) estimated from a 1 s subsample to bound
  memory. Exposure is a PAIR-time quantity (vehicle-pairs x seconds), not
  the duration experienced by one vehicle; low_ttc_fraction_of_pair_samples
  gives the same information normalised by pair_samples.

Validity boundary:
  The first overlap (gap < 0) or the first order crossing between adjacent
  vehicles ends the period in which car-following statistics are
  meaningful. Either event terminates the interval, and the EARLIER of the
  two is used as the single boundary. All pair statistics AND
  hard-brake/stop events are computed for t < valid_until_s only; the
  statistics are recomputed from scratch on that truncated interval so no
  post-boundary sample can leak in.

  statistics_invalid is the unified flag (True if any boundary was hit) and
  invalid_reason says which one. overlap_invalid keeps the narrower meaning
  "the bodies actually overlapped". Speed, jerk and acceleration aggregates
  use the same boundary, so every comfort/efficiency figure in a row has
  the same scope as its pair statistics.
"""

HARD_BRAKE_THRESHOLD = -6.0
STOP_SPEED_THRESHOLD = 0.1
TTC_CUTOFF = 1000.0
ENTRY_ZONE_LENGTH = 500.0
LOW_TTC_LEVELS = (3.0, 1.5)


def _percentile(sorted_values, fraction):
    if not sorted_values:
        return None
    index = min(len(sorted_values) - 1, int(fraction * len(sorted_values)))
    return sorted_values[index]


def _scan_pairs(offsets, total_steps, dt, vehicle_length, stop_step=None):
    """Scan consecutive pairs step by step and collect safety statistics.

    Only steps before ``stop_step`` (exclusive) are included. The caller
    sets ``stop_step`` to the first overlap step when one exists, so the
    statistics describe the still-valid following period only.
    """
    min_gap = float("inf")
    gap_below_2m = 0
    ttc_min = float("inf")
    ttc_sample_small = []
    low_ttc_counts = {level: 0 for level in LOW_TTC_LEVELS}
    pair_samples = 0
    per_follower_min_gap = {}
    per_follower_min_ttc = {}
    sample_every = max(1, round(1.0 / dt))
    prev_index = {}
    first_crossing_step = None
    first_overlap_step = None
    overlap_pair_samples = 0

    limit = total_steps if stop_step is None else min(stop_step, total_steps)
    for step in range(limit):
        present = []
        for start, history, vid in offsets:
            index = step - start
            if 0 <= index < len(history):
                record = history[index]
                present.append((record["position"], vid, record["speed"]))
        if not present:
            prev_index = {}
            continue
        present.sort()

        # Overlap ends the valid following period. Stop here; the caller
        # re-runs this scan with stop_step set to this step so that no
        # post-overlap sample can enter any statistic.
        overlap_now = 0
        for i in range(len(present) - 1):
            if present[i + 1][0] - present[i][0] - vehicle_length < 0.0:
                overlap_now += 1
        if overlap_now:
            first_overlap_step = step
            overlap_pair_samples = overlap_now
            break

        # Order-crossing detection: if two currently adjacent vehicles were
        # in the opposite order at the previous step, they have swapped.
        if first_crossing_step is None and prev_index:
            for i in range(len(present) - 1):
                rear_id = present[i][1]
                lead_id = present[i + 1][1]
                if (
                    rear_id in prev_index
                    and lead_id in prev_index
                    and prev_index[rear_id] > prev_index[lead_id]
                ):
                    first_crossing_step = step
                    break
        prev_index = {vid: i for i, (_, vid, _) in enumerate(present)}

        for i in range(len(present) - 1):
            rear_x, rear_id, rear_speed = present[i]
            lead_x, lead_id, lead_speed = present[i + 1]
            gap = lead_x - rear_x - vehicle_length
            pair_samples += 1

            if gap < min_gap:
                min_gap = gap
            if gap < per_follower_min_gap.get(rear_id, float("inf")):
                per_follower_min_gap[rear_id] = gap
            if gap < 2.0:
                gap_below_2m += 1

            closing = rear_speed - lead_speed
            ttc = gap / closing if closing > 0 else TTC_CUTOFF
            if ttc < ttc_min:
                ttc_min = ttc
            if ttc < per_follower_min_ttc.get(rear_id, float("inf")):
                per_follower_min_ttc[rear_id] = ttc
            for level in LOW_TTC_LEVELS:
                if ttc < level:
                    low_ttc_counts[level] += 1
            if step % sample_every == 0:
                ttc_sample_small.append(ttc)

    return {
        "min_gap": min_gap,
        "gap_below_2m": gap_below_2m,
        "ttc_min": ttc_min,
        "ttc_sample_small": ttc_sample_small,
        "low_ttc_counts": low_ttc_counts,
        "pair_samples": pair_samples,
        "per_follower_min_gap": per_follower_min_gap,
        "per_follower_min_ttc": per_follower_min_ttc,
        "first_crossing_step": first_crossing_step,
        "first_overlap_step": first_overlap_step,
        "overlap_pair_samples": overlap_pair_samples,
    }


def _event_stats(records, dt, predicate):
    """Count records and events over one vehicle's history.

    records: iterable of (value, position) pairs, oldest first.
    predicate(value) -> bool.

    A record is one simulation step meeting the condition; an event is a
    maximal run of consecutive records meeting it. Position of the *first*
    record of an event decides whether it happened in the entry zone.
    Returns (records, events, total_duration_s, max_duration_s,
             events_in_entry_zone, events_in_interior).
    """
    records_count = events = 0
    entry_events = interior_events = 0
    run_length = 0
    max_run = 0
    for value, position in records:
        if predicate(value):
            records_count += 1
            run_length += 1
            if run_length == 1:
                events += 1
                if position < ENTRY_ZONE_LENGTH:
                    entry_events += 1
                else:
                    interior_events += 1
        else:
            if run_length > max_run:
                max_run = run_length
            run_length = 0
    if run_length > max_run:
        max_run = run_length
    return (records_count, events, records_count * dt, max_run * dt,
            entry_events, interior_events)


def compute_metrics(sim, config, ego_ids=None):
    dt = config.time_step
    vehicles = sim.vehicles

    # ------------------------------------------------------------------
    # Demand / entry / exit accounting
    # ------------------------------------------------------------------
    demand_total = len(sim.arrival_schedule)
    entered = len(sim.entry_log)
    delays = [e["entry_delay"] for e in sim.entry_log]
    exited = 0
    incomplete = 0
    travel_times = []          # completed trips only
    system_times = []          # completed: scheduled arrival -> exit
    censored_times = []        # incomplete trips: time on road at time_max
    censored_system = []       # incomplete: scheduled arrival -> time_max
    travel_by_id = {}          # completed trips, keyed by vehicle id
    system_by_id = {}
    # Finite-horizon cumulative system time over ALL scheduled demand:
    # every vehicle contributes (end - scheduled_arrival), where end is its
    # exit time, or time_max if it never exited. Vehicles that were never
    # admitted contribute (time_max - scheduled_arrival): the queue is
    # FIFO, so the un-admitted tail of the schedule is exactly the waiting
    # demand. This is a TRUNCATED cumulative time, not a completed trip
    # time; it grows with the observation window by construction.
    cumulative_all = 0.0
    for v in vehicles:
        scheduled = v.scheduled_arrival if v.scheduled_arrival is not None else 0.0
        if v.active:
            incomplete += 1
            censored_times.append(config.time_max - (v.entry_time or 0.0))
            censored_system.append(config.time_max - scheduled)
            cumulative_all += config.time_max - scheduled
        else:
            exited += 1
            v.exit_time = v.history[-1]["t"] if v.history else config.time_max
            travel_times.append(v.exit_time - (v.entry_time or 0.0))
            system_times.append(v.exit_time - scheduled)
            travel_by_id[v.id] = travel_times[-1]
            system_by_id[v.id] = system_times[-1]
            cumulative_all += v.exit_time - scheduled
    waiting = demand_total - entered
    for scheduled in sim.arrival_schedule[entered:]:
        cumulative_all += config.time_max - scheduled
    mean_cumulative_all = (
        cumulative_all / demand_total if demand_total else None
    )

    # ------------------------------------------------------------------
    # Validity boundary: first overlap OR first order crossing, whichever
    # comes first, ends the period in which following statistics are
    # meaningful. The pair scan is then re-run on the truncated interval so
    # no post-boundary sample can enter any statistic.
    # ------------------------------------------------------------------
    total_steps = int(round(config.time_max / dt)) + 1
    offsets = []
    for v in vehicles:
        if not v.history:
            continue
        start = int(round(v.history[0]["t"] / dt))
        offsets.append((start, v.history, v.id))

    full_scan = _scan_pairs(offsets, total_steps, dt, config.vehicle_length)
    boundary_candidates = [
        s for s in (full_scan["first_overlap_step"],
                    full_scan["first_crossing_step"])
        if s is not None
    ]
    boundary_step = min(boundary_candidates) if boundary_candidates else None
    if boundary_step is not None:
        scan = _scan_pairs(
            offsets, total_steps, dt, config.vehicle_length,
            stop_step=boundary_step,
        )
    else:
        scan = full_scan

    first_overlap_step = full_scan["first_overlap_step"]
    first_crossing_step = full_scan["first_crossing_step"]
    first_overlap_time = (
        round(first_overlap_step * dt, 3) if first_overlap_step is not None else None
    )
    first_crossing_time = (
        round(first_crossing_step * dt, 3) if first_crossing_step is not None else None
    )
    valid_until_s = (
        round(boundary_step * dt, 3) if boundary_step is not None else config.time_max
    )
    statistics_invalid = boundary_step is not None
    if boundary_step is None:
        invalid_reason = None
    elif first_overlap_step is not None and first_overlap_step == boundary_step:
        invalid_reason = "overlap"
    else:
        invalid_reason = "order_crossing"
    overlap_invalid = first_overlap_step is not None
    overlap_samples = full_scan["overlap_pair_samples"]

    min_gap = scan["min_gap"]
    gap_below_2m = scan["gap_below_2m"]
    ttc_min = scan["ttc_min"]
    ttc_sample_small = scan["ttc_sample_small"]
    low_ttc_counts = scan["low_ttc_counts"]
    pair_sample_count = scan["pair_samples"]
    per_follower_min_gap = scan["per_follower_min_gap"]
    per_follower_min_ttc = scan["per_follower_min_ttc"]

    ttc_sample_small.sort()

    # ------------------------------------------------------------------
    # Speed / jerk / acceleration (streaming: no per-step lists kept).
    # Same validity boundary as the pair statistics.
    # ------------------------------------------------------------------
    speed_sum = speed_n = 0
    jerk_sum = jerk_n = 0.0
    accel_sum = accel_sq_sum = 0.0
    accel_n = 0
    for v in vehicles:
        h = [r for r in v.history if r["t"] < valid_until_s]
        for i in range(len(h)):
            s = h[i]["speed"]
            a = h[i]["acceleration"]
            speed_sum += s
            speed_n += 1
            accel_sum += a
            accel_sq_sum += a * a
            accel_n += 1
            if i > 0:
                jerk_sum += abs((a - h[i - 1]["acceleration"]) / dt)
                jerk_n += 1
    mean_speed = speed_sum / speed_n if speed_n else 0.0
    mean_jerk = jerk_sum / jerk_n if jerk_n else 0.0
    if accel_n:
        mean_a = accel_sum / accel_n
        accel_std = max(0.0, accel_sq_sum / accel_n - mean_a * mean_a) ** 0.5
    else:
        accel_std = 0.0

    # ------------------------------------------------------------------
    # Hard-brake and stop events (records AND events, zone split)
    # ------------------------------------------------------------------
    # Restricted to t < valid_until_s: after an overlap the following
    # relationship no longer exists, so comfort/efficiency samples from
    # that period are not attributable to car-following behaviour.
    hb_records = hb_events = 0
    hb_duration = hb_max_duration = 0.0
    hb_entry = hb_interior = 0
    stop_records = stop_events = 0
    stop_duration = 0.0
    stop_entry = stop_interior = 0
    for v in vehicles:
        # Generator expressions instead of materialised lists: a full run
        # holds ~5.9M history records and copying them per metric pass was
        # what exhausted memory in the first batch attempt.
        rec, ev, dur, mx, ez, it = _event_stats(
            (
                (r["acceleration"], r["position"])
                for r in v.history if r["t"] < valid_until_s
            ),
            dt, lambda a: a <= HARD_BRAKE_THRESHOLD,
        )
        hb_records += rec
        hb_events += ev
        hb_duration += dur
        hb_max_duration = max(hb_max_duration, mx)
        hb_entry += ez
        hb_interior += it
        rec, ev, dur, mx, ez, it = _event_stats(
            (
                (r["speed"], r["position"])
                for r in v.history if r["t"] < valid_until_s
            ),
            dt, lambda s: s < STOP_SPEED_THRESHOLD,
        )
        stop_records += rec
        stop_events += ev
        stop_duration += dur
        stop_entry += ez
        stop_interior += it

    # ------------------------------------------------------------------
    # Per-vehicle (ego) statistics for requested ids
    # ------------------------------------------------------------------
    ego_ids = ego_ids or []
    per_vehicle = {}
    entry_by_id = {e["id"]: e for e in sim.entry_log}
    for vid in ego_ids:
        v = next((x for x in vehicles if x.id == vid), None)
        if v is None:
            per_vehicle[str(vid)] = {"entered": False}
            continue
        rec, ev, dur, mx, ez, it = _event_stats(
            (
                (r["acceleration"], r["position"])
                for r in v.history if r["t"] < valid_until_s
            ),
            dt, lambda a: a <= HARD_BRAKE_THRESHOLD,
        )
        entry = entry_by_id.get(vid)
        scheduled = entry["scheduled_arrival"] if entry else None
        per_vehicle[str(vid)] = {
            "entered": True,
            "stats_valid_until_s": round(valid_until_s, 1),
            "scheduled_arrival_s": scheduled,
            "entry_time_s": v.entry_time,
            "entry_delay_s": entry["entry_delay"] if entry else None,
            "exited": not v.active,
            "exit_time_s": getattr(v, "exit_time", None),
            "travel_time_s": (
                (v.exit_time - v.entry_time)
                if (not v.active and v.entry_time is not None)
                else None
            ),
            "system_time_completed_s": (
                (v.exit_time - scheduled)
                if (not v.active and scheduled is not None
                    and getattr(v, "exit_time", None) is not None)
                else None
            ),
            "cumulative_time_all_s": (
                ((v.exit_time if not v.active else config.time_max) - scheduled)
                if scheduled is not None else None
            ),
            "time_on_road_s": (
                config.time_max - v.entry_time
                if v.active and v.entry_time is not None
                else None
            ),
            "hard_brake_records": rec,
            "hard_brake_events": ev,
            "min_gap_m": (
                per_follower_min_gap.get(vid)
                if per_follower_min_gap.get(vid) != float("inf")
                else None
            ),
            "min_ttc_s": (
                per_follower_min_ttc.get(vid)
                if per_follower_min_ttc.get(vid) != float("inf")
                else None
            ),
        }

    # ------------------------------------------------------------------
    # LLM statistics
    # ------------------------------------------------------------------
    llm_vehicles = [v for v in vehicles if hasattr(v, "call_count")]
    llm_calls = sum(v.call_count for v in llm_vehicles)
    llm_failures = sum(v.failure_count for v in llm_vehicles)
    latencies = []
    for v in llm_vehicles:
        latencies.extend(getattr(v, "latency_log", []))
    ego = None
    if getattr(sim, "llm_ego_id", None) is not None:
        ego = next(
            (v for v in llm_vehicles if v.id == sim.llm_ego_id), None
        )

    # ------------------------------------------------------------------
    # Admission blockers: evidence about WHY entry was deferred, not a
    # causal story. Counted by the rule that blocked it, and summarised
    # with the blocking vehicle's position/speed so a reader can see
    # whether the bottleneck was anywhere near the entrance.
    # ------------------------------------------------------------------
    blocks = getattr(sim, "admission_blocks", [])
    spacing_blocks = sum(1 for b in blocks if b["reason"] == "spacing")
    kinematic_blocks = sum(1 for b in blocks if b["reason"] == "kinematic")
    front_speeds = [b["front_speed_mps"] for b in blocks
                    if b["front_speed_mps"] is not None]
    front_positions = [b["front_position_m"] for b in blocks
                       if b["front_position_m"] is not None]
    blocks_with_bottleneck = sum(1 for b in blocks if b["bottleneck_active"])
    front_headways = [
        b["front_time_headway_s"] for b in blocks
        if b["front_time_headway_s"] is not None
        and b["front_time_headway_s"] == b["front_time_headway_s"]  # not NaN
    ]
    block_waits = [b["waiting_s"] for b in blocks]

    metrics = {
        # demand / flow
        "demand_total": demand_total,
        "entered": entered,
        "exited": exited,
        "incomplete": incomplete,
        "waiting_at_end": waiting,
        "mean_entry_delay_s": (
            round(sum(delays) / len(delays), 3) if delays else 0.0
        ),
        "max_entry_delay_s": round(max(delays), 3) if delays else 0.0,
        "throughput_exits_veh_per_h": round(exited / config.time_max * 3600, 1),
        # Travel time: completed trips only (see module docstring).
        "mean_travel_time_s": (
            round(sum(travel_times) / len(travel_times), 1)
            if travel_times else None
        ),
        "completed_trips": len(travel_times),
        "mean_censored_time_on_road_s": (
            round(sum(censored_times) / len(censored_times), 1)
            if censored_times else None
        ),
        # System time over COMPLETED vehicles only: scheduled arrival ->
        # exit. It is NOT a demand-wide metric because vehicles that never
        # entered contribute nothing; use the cumulative metric below for
        # that comparison.
        "mean_system_time_completed_s": (
            round(sum(system_times) / len(system_times), 1)
            if system_times else None
        ),
        "max_system_time_completed_s": (
            round(max(system_times), 1) if system_times else None
        ),
        "mean_system_time_incomplete_partial_s": (
            round(sum(censored_system) / len(censored_system), 1)
            if censored_system else None
        ),
        # Demand-wide, finite-horizon cumulative system time (truncated):
        # every scheduled vehicle counts, including never-admitted ones.
        "cumulative_system_time_all_s": round(cumulative_all, 1),
        "mean_cumulative_system_time_all_s": (
            round(mean_cumulative_all, 1)
            if mean_cumulative_all is not None else None
        ),
        "completed_fraction": (
            round(exited / demand_total, 3) if demand_total else None
        ),
        "demand_served_fraction": (
            round(exited / demand_total, 3) if demand_total else None
        ),
        # comfort
        "mean_speed_mps": round(mean_speed, 2),
        "mean_abs_jerk_mps3": round(mean_jerk, 3),
        "accel_std_mps2": round(accel_std, 3),
        # hard braking
        "hard_brake_records": hb_records,
        "hard_brake_events": hb_events,
        "hard_brake_total_duration_s": round(hb_duration, 1),
        "hard_brake_max_duration_s": round(hb_max_duration, 1),
        "hard_brake_events_entry_zone": hb_entry,
        "hard_brake_events_interior": hb_interior,
        # stops
        "stopped_records": stop_records,
        "stopped_events": stop_events,
        "stopped_total_duration_s": round(stop_duration, 1),
        "stopped_events_entry_zone": stop_entry,
        "stopped_events_interior": stop_interior,
        # safety
        "min_gap_m": (
            round(min_gap, 2) if min_gap != float("inf") else None
        ),
        "gap_below_2m_samples": gap_below_2m,
        "min_ttc_s": round(ttc_min, 2) if ttc_min != float("inf") else None,
        "ttc_p01_s": (
            round(_percentile(ttc_sample_small, 0.01), 2)
            if ttc_sample_small else None
        ),
        "ttc_p05_s": (
            round(_percentile(ttc_sample_small, 0.05), 2)
            if ttc_sample_small else None
        ),
        "low_ttc_exposure_s": {
            str(level): round(low_ttc_counts[level] * dt, 1)
            for level in LOW_TTC_LEVELS
        },
        # Normalised exposure: fraction of observed pair-samples below the
        # threshold. This is a pair-time ratio, NOT a per-vehicle duration.
        "low_ttc_fraction_of_pair_samples": {
            str(level): (
                round(low_ttc_counts[level] / pair_sample_count, 5)
                if pair_sample_count else None
            )
            for level in LOW_TTC_LEVELS
        },
        "pair_samples": pair_sample_count,
        # overlap / collision bookkeeping
        "first_overlap_time_s": first_overlap_time,
        "overlap_pair_samples_at_first": overlap_samples,
        "overlap_invalid": overlap_invalid,
        "first_order_crossing_time_s": first_crossing_time,
        # Unified validity markers. statistics_invalid is True if ANY
        # boundary (overlap or order crossing) ended the valid interval;
        # invalid_reason says which one. Every pair/comfort statistic in
        # this row is scoped to t < valid_until_s.
        "statistics_invalid": statistics_invalid,
        "invalid_reason": invalid_reason,
        "valid_until_s": round(valid_until_s, 1),
        # admission blocking evidence
        "admission_block_attempts": len(blocks),
        "admission_blocks_spacing": spacing_blocks,
        "admission_blocks_kinematic": kinematic_blocks,
        "admission_blocks_while_bottleneck_active": blocks_with_bottleneck,
        "admission_block_mean_front_speed_mps": (
            round(sum(front_speeds) / len(front_speeds), 2)
            if front_speeds else None
        ),
        "admission_block_mean_front_position_m": (
            round(sum(front_positions) / len(front_positions), 1)
            if front_positions else None
        ),
        "admission_block_mean_front_headway_s": (
            round(sum(front_headways) / len(front_headways), 3)
            if front_headways else None
        ),
        "admission_block_mean_waiting_s": (
            round(sum(block_waits) / len(block_waits), 2)
            if block_waits else None
        ),
        # completed-trip times keyed by vehicle id (paired comparisons)
        "completed_travel_time_by_id_s": {
            str(k): round(v, 1) for k, v in travel_by_id.items()
        },
        "completed_system_time_by_id_s": {
            str(k): round(v, 1) for k, v in system_by_id.items()
        },
        # llm
        "llm_vehicle_count": len(llm_vehicles),
        "llm_vehicle_ids": [v.id for v in llm_vehicles],
        "llm_api_calls": llm_calls,
        "llm_api_failures": llm_failures,
        "llm_mean_latency_s": (
            round(sum(latencies) / len(latencies), 3) if latencies else None
        ),
        "llm_max_latency_s": round(max(latencies), 3) if latencies else None,
        # Model output vs guardrail vs executor action, counted separately.
        #   guardrail_corrections        cached plan differed from model output
        #   recovery_guard_activations   cached slow plan lifted past zone end
        #   road_limit_cap_steps         cached plan was ABOVE the road limit
        #   headway_ramp_steps           requested headway not yet reached
        # A planner that recommends a low speed is NOT an executor override.
        "llm_guardrail_corrections": sum(
            getattr(v, "guardrail_corrections", 0) for v in llm_vehicles
        ),
        "llm_recovery_guard_activations": sum(
            getattr(v, "recovery_guard_activations", 0) for v in llm_vehicles
        ),
        "llm_road_limit_cap_steps": sum(
            getattr(v, "road_limit_cap_steps", 0) for v in llm_vehicles
        ),
        "llm_headway_ramp_steps": sum(
            getattr(v, "headway_ramp_steps", 0) for v in llm_vehicles
        ),
        "llm_executor_steps": sum(
            getattr(v, "executor_steps", 0) for v in llm_vehicles
        ),
        "llm_models": sorted({
            getattr(v, "model_name", None) for v in llm_vehicles
            if getattr(v, "model_name", None)
        }),
        "llm_prompt_versions": sorted({
            getattr(v, "prompt_version", None) for v in llm_vehicles
            if getattr(v, "prompt_version", None)
        }),
        "llm_stop_intent_steps": sum(
            getattr(v, "stop_intent_steps", 0) for v in llm_vehicles
        ),
    }

    # Convenience ego block for the ego experiments.
    if ego is not None:
        ev = per_vehicle.get(str(ego.id)) or {}
        metrics["ego_id"] = ego.id
        metrics["ego_travel_time_s"] = ev.get("travel_time_s")
        metrics["ego_hard_brake_events"] = ev.get("hard_brake_events")
        metrics["ego_min_gap_m"] = ev.get("min_gap_m")
        metrics["ego_min_ttc_s"] = ev.get("min_ttc_s")
        metrics["ego_entry_delay_s"] = ev.get("entry_delay_s")
        metrics["ego_system_time_completed_s"] = ev.get("system_time_completed_s")
        metrics["ego_cumulative_time_all_s"] = ev.get("cumulative_time_all_s")
        metrics["ego_llm_calls"] = ego.call_count
        metrics["ego_llm_failures"] = ego.failure_count
        # Distinguish what the model asked for, what the guardrails stored,
        # and what the executor did.
        metrics["ego_guardrail_corrections"] = getattr(
            ego, "guardrail_corrections", 0
        )
        metrics["ego_recovery_guard_activations"] = getattr(
            ego, "recovery_guard_activations", 0
        )
        metrics["ego_road_limit_cap_steps"] = getattr(
            ego, "road_limit_cap_steps", 0
        )
        metrics["ego_headway_ramp_steps"] = getattr(
            ego, "headway_ramp_steps", 0
        )
        metrics["ego_executor_steps"] = getattr(ego, "executor_steps", 0)
        metrics["ego_model_name"] = getattr(ego, "model_name", None)
        metrics["ego_prompt_version"] = getattr(ego, "prompt_version", None)
        metrics["ego_stop_intent_steps"] = getattr(ego, "stop_intent_steps", 0)
        ego_lat = getattr(ego, "latency_log", [])
        metrics["ego_llm_mean_latency_s"] = (
            round(sum(ego_lat) / len(ego_lat), 3) if ego_lat else None
        )

    # Per-vehicle rows always carry the validity boundary of the run, so a
    # vehicle-level number can never be read without its scope.
    metrics["per_vehicle"] = per_vehicle
    return metrics


def format_table(rows, columns):
    """Render a list of metric dicts as a plain text table."""
    header = [str(c) for c in columns]
    lines = [" | ".join(header), "-+-".join("-" * len(h) for h in header)]
    for row in rows:
        lines.append(
            " | ".join(str(row.get(c, "")) for c in columns)
        )
    return "\n".join(lines)


