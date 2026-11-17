"""Targeted verification for the fair-comparison fixes (test_fixes.py).

Small, behaviour-level checks — not exhaustive unit tests. Run with:

    python test_fixes.py
"""

import math

from config import Config
from llm_client import MockLLMClient, build_client
from metrics import compute_metrics
from noise import normal as det_normal, uniform as det_uniform
from simulator import Simulator
from vehicle_llm import LLMVehicle
from vehicle_idm import IDMVehicle


def _run(mode_client, exp, seed, time_max=400.0):
    config = Config(seed=seed, experiment=exp, time_max=time_max)
    vc = IDMVehicle if mode_client is None else LLMVehicle
    sim = Simulator(config, vehicle_class=vc, llm_client=mode_client)
    sim.run(verbose=False)
    return config, sim


def test_common_demand():
    """Same (experiment, seed) → identical arrival schedule in every mode."""
    _, sim_idm = _run(None, 2, 3)
    _, sim_mock = _run(MockLLMClient(), 2, 3)
    _, sim_noant = _run(build_client("mock_noant"), 2, 3)
    a, b, c = (sim_idm.arrival_schedule, sim_mock.arrival_schedule,
               sim_noant.arrival_schedule)
    assert a == b == c, "arrival schedules differ across modes"
    # entry accounting exists and entered <= demand
    assert len(sim_idm.entry_log) == len(sim_idm.vehicles)
    assert all(e["entry_delay"] >= -1e-9 for e in sim_idm.entry_log)
    print("ok  common demand identical across modes "
          f"({len(a)} scheduled, {len(sim_idm.vehicles)} entered)")


def test_noise_independence():
    """Bottleneck-influence flag and perception noise are strategy-independent."""
    _, sim_idm = _run(None, 1, 1)
    _, sim_mock = _run(MockLLMClient(), 1, 1)
    v_idm = next(v for v in sim_idm.vehicles if v.id == 60)
    v_mock = next(v for v in sim_mock.vehicles if v.id == 60)
    assert v_idm.influenced_by_bottleneck == v_mock.influenced_by_bottleneck
    n1 = det_normal(7, 60, 1500, salt=23)
    n2 = det_normal(7, 60, 1500, salt=23)
    assert n1 == n2 and abs(n1) < 10
    u = det_uniform(7, 60, salt=11)
    assert 0.0 <= u < 1.0
    print(f"ok  noise deterministic (influence={v_idm.influenced_by_bottleneck}, "
          f"n(60,1500)={n1:.4f})")


def test_stop_target():
    """target_speed = 0 must not divide by zero and must stop comfortably."""
    config = Config(seed=1, experiment=1, time_max=200.0)
    sim = Simulator(config, vehicle_class=LLMVehicle, llm_client=MockLLMClient())
    v = LLMVehicle(config, 999, None, llm_client=MockLLMClient())
    v.position = 200.0
    v.speed = 10.0
    v.current_speed_limit = config.speed_limit
    v.llm_target_speed = 0.0          # explicit stop intent
    v.llm_time_headway = 1.0
    v.check_road(50.0)
    v.last_llm_time = v.current_time  # freeze the cached plan (no replan)
    accelerations = []
    for _ in range(2000):
        v.update_acceleration()
        v.update_motion()
        accelerations.append(v.acceleration)
        if v.speed <= 0.0:
            break
    assert v.speed == 0.0, f"vehicle did not stop (speed={v.speed})"
    assert min(accelerations) >= -v.maximum_deceleration
    # comfortable stop: first braking command should be near -b, not -8
    assert accelerations[0] > -3.0, f"stop was not comfortable: {accelerations[0]}"
    print(f"ok  stop target: v=10→0 in {len(accelerations) * config.time_step:.1f}s, "
          f"a0={accelerations[0]:.2f} m/s^2")


def test_plan_validation():
    """Malformed LLM replies are rejected and counted, never crash."""
    config = Config(seed=1, experiment=1)
    v = LLMVehicle(config, 1, None, llm_client=MockLLMClient())
    v.current_time = 0.0
    bad_inputs = [
        None,
        "not a dict",
        {"target_speed": float("nan"), "time_headway": 1.0},
        {"target_speed": 5.0},                          # missing headway
        {"target_speed": "fast", "time_headway": 1.0},  # non-numeric
        {"target_speed": float("inf"), "time_headway": 1.0},
    ]
    for bad in bad_inputs:
        target, headway, error = LLMVehicle.validate_plan(bad)
        assert error is not None and target is None, f"accepted {bad!r}"
    target, headway, error = LLMVehicle.validate_plan(
        {"target_speed": 5.0, "time_headway": 1.2}
    )
    assert error is None and target == 5.0 and headway == 1.2
    print("ok  validation rejects NaN/inf/missing/non-numeric/non-dict")


def test_recovery_guard_persistent_bottleneck():
    """Past the zone end the cached slow plan is lifted even in exp 3/4."""
    config = Config(seed=1, experiment=3, time_max=1000.0)
    v = LLMVehicle(config, 1, None, llm_client=MockLLMClient())
    v.position = config.bottleneck_x_end + 50.0     # past the zone
    v.speed = 2.0
    v.llm_target_speed = 2.0                         # stale slow plan
    v.llm_time_headway = 1.0
    v.bottleneck_active_now = True                   # exp 3/4: still active
    v.current_speed_limit = config.speed_limit  # zone limit no longer applies
    v.update_acceleration()
    assert v.llm_target_speed == config.speed_limit, (
        f"stale target {v.llm_target_speed} kept past zone end"
    )
    print("ok  recovery guard lifts stale plan past zone end (persistent bottleneck)")


def test_travel_time_only_completed():
    """Travel time counts exited vehicles only; counts are consistent."""
    config, sim = _run(None, 1, 1, time_max=300.0)
    m = compute_metrics(sim, config)
    assert m["entered"] == len(sim.vehicles)
    assert m["exited"] + m["incomplete"] == m["entered"]
    assert m["demand_total"] >= m["entered"]
    assert m["completed_trips"] == m["exited"]
    if m["incomplete"] > 0:
        assert m["mean_censored_time_on_road_s"] is not None
    # completed travel times are physically plausible (> road/vmax - slack)
    assert m["mean_travel_time_s"] is None or m["mean_travel_time_s"] > 100.0
    print(f"ok  travel time: demand={m['demand_total']} entered={m['entered']} "
          f"exited={m['exited']} incomplete={m['incomplete']} "
          f"tt={m['mean_travel_time_s']}s")


def test_ttc_distribution_reported():
    """Safety metrics include percentiles and exposure, not just the minimum."""
    config, sim = _run(None, 1, 1, time_max=300.0)
    m = compute_metrics(sim, config)
    assert m["min_ttc_s"] is not None
    assert m["ttc_p05_s"] is not None and m["ttc_p05_s"] >= m["min_ttc_s"]
    assert set(m["low_ttc_exposure_s"]) == {"3.0", "1.5"}
    assert m["overlap_invalid"] is False
    print(f"ok  ttc: min={m['min_ttc_s']} p05={m['ttc_p05_s']} "
          f"exposure<3s={m['low_ttc_exposure_s']['3.0']}s")


def test_ego_tracked_in_idm():
    """Per-vehicle stats for id 60 exist under pure IDM (fair ego baseline)."""
    config, sim = _run(None, 1, 1)
    m = compute_metrics(sim, config, ego_ids=[60])
    pv = m["per_vehicle"]["60"]
    assert pv["entered"] and pv["scheduled_arrival_s"] is not None
    assert pv["travel_time_s"] is not None
    print(f"ok  idm ego60: scheduled={pv['scheduled_arrival_s']}s "
          f"entered={pv['entry_time_s']}s travel={pv['travel_time_s']:.1f}s")


def test_cumulative_system_time():
    """Demand-wide cumulative time counts waiting and incomplete vehicles."""
    config = Config(seed=1, experiment=2, time_max=100.0)
    sim = Simulator(config, vehicle_class=LLMVehicle, llm_client=MockLLMClient())
    sim.run(verbose=False)
    m = compute_metrics(sim, config)
    assert m["demand_total"] == m["entered"] + m["waiting_at_end"]
    # Reconstruct the cumulative total from the same definition.
    expected = 0.0
    for v in sim.vehicles:
        end = v.history[-1]["t"] if not v.active else config.time_max
        expected += end - v.scheduled_arrival
    for scheduled in sim.arrival_schedule[m["entered"]:]:
        expected += config.time_max - scheduled
    assert abs(expected - m["cumulative_system_time_all_s"]) < 0.2, (
        expected, m["cumulative_system_time_all_s"]
    )
    assert m["mean_cumulative_system_time_all_s"] >= (
        m["mean_system_time_completed_s"] or 0.0
    )
    assert 0.0 <= m["completed_fraction"] <= 1.0
    print(f"ok  cumulative: demand={m['demand_total']} entered={m['entered']} "
          f"waiting={m['waiting_at_end']} cum={m['mean_cumulative_system_time_all_s']}s "
          f"completed-only={m['mean_system_time_completed_s']}s")


def test_overlap_truncation():
    """Statistics stop at the first overlap / order crossing."""

    class _V:
        def __init__(self, vid, xs, speeds, accels):
            self.id = vid
            self.active = False
            self.entry_time = 0.0
            self.scheduled_arrival = 0.0
            self.history = [
                {"t": round(i * 0.1, 1), "position": x, "speed": s,
                 "acceleration": a}
                for i, (x, s, a) in enumerate(zip(xs, speeds, accels))
            ]

    def _sim(vehicles):
        class _Sim:
            llm_ego_id = None
            admission_blocks = []
            entry_log = [{"id": v.id, "scheduled_arrival": 0.0,
                          "entry_time": 0.0, "entry_delay": 0.0}
                         for v in vehicles]
            arrival_schedule = [0.0] * len(vehicles)
        _Sim.vehicles = vehicles
        return _Sim()

    config = Config(seed=1, experiment=1, time_max=0.3)

    # Case 1: follower closes on the leader until the bodies overlap at
    # t = 0.2 s (no order swap yet).
    overlap_sim = _sim([
        _V(1, [0, 6, 12, 18], [5, 5, 5, 5], [0, 0, 0, -8]),
        _V(2, [20, 14, 15, 16], [5, 5, 5, 5], [0, 0, 0, 0]),
    ])
    m = compute_metrics(overlap_sim, config)
    assert m["first_overlap_time_s"] == 0.2, m["first_overlap_time_s"]
    assert m["overlap_invalid"] is True
    assert m["valid_until_s"] == 0.2
    assert m["min_gap_m"] == 14 - 6 - config.vehicle_length, m["min_gap_m"]
    # The -8 m/s^2 sample at t=0.3 s is after the overlap: must not count.
    assert m["hard_brake_events"] == 0, m["hard_brake_events"]
    assert m["hard_brake_records"] == 0

    # Case 2: the vehicles swap order between steps without an overlapping
    # adjacent pair at that instant; the crossing still ends the valid period.
    crossing_sim = _sim([
        _V(1, [0, 5, 15], [5, 5, 5], [0, 0, 0]),
        _V(2, [20, 10, 5], [5, 5, 5], [0, 0, 0]),
    ])
    c = compute_metrics(crossing_sim, config)
    assert c["first_order_crossing_time_s"] == 0.2, c["first_order_crossing_time_s"]
    assert c["valid_until_s"] == 0.2
    assert c["min_gap_m"] == 10 - 5 - config.vehicle_length
    print("ok  overlap truncation: overlap@0.2s (min_gap 3.5 m, post-overlap "
          "hard brake excluded); order crossing@0.2s also flagged")


def test_crossing_truncation_keeps_pre_crossing_gap():
    """A pure order crossing must truncate the data, not just set a flag.

    Geometry: the pair keeps a 25 m gap until the two vehicles swap order in
    one step; from the crossing step on the gap is 1 m. If the statistics
    still used post-crossing samples, min_gap would be 1 m. The correct
    answer is 25 m, with pair_samples covering only the pre-crossing steps.
    """

    class _V:
        def __init__(self, vid, xs, accels):
            self.id = vid
            self.active = False
            self.entry_time = 0.0
            self.scheduled_arrival = 0.0
            self.history = [
                {"t": round(i * 0.1, 1), "position": x, "speed": 10.0,
                 "acceleration": a}
                for i, (x, a) in enumerate(zip(xs, accels))
            ]

    class _Sim:
        llm_ego_id = None
        admission_blocks = []
        arrival_schedule = [0.0, 0.0]
        entry_log = [
            {"id": 1, "scheduled_arrival": 0.0, "entry_time": 0.0,
             "entry_delay": 0.0},
            {"id": 2, "scheduled_arrival": 0.0, "entry_time": 0.0,
             "entry_delay": 0.0},
        ]

    # Before the crossing: 130 - 100 - 5 = 25 m. At t=0.2 the vehicles have
    # swapped: 141 - 135 - 5 = 1 m. A hard brake is placed after the swap so
    # a leaked sample would also show up in the comfort statistics.
    vehicles = [
        _V(1, [100, 100, 141, 151], [0.0, 0.0, -8.0, -8.0]),
        _V(2, [130, 130, 135, 145], [0.0, 0.0, 0.0, 0.0]),
    ]
    _Sim.vehicles = vehicles

    config = Config(seed=1, experiment=1, time_max=0.4)
    m = compute_metrics(_Sim(), config)

    assert m["first_order_crossing_time_s"] == 0.2, m["first_order_crossing_time_s"]
    assert m["valid_until_s"] == 0.2, m["valid_until_s"]
    assert m["statistics_invalid"] is True
    assert m["invalid_reason"] == "order_crossing", m["invalid_reason"]
    assert m["overlap_invalid"] is False
    # Only the two pre-crossing steps may contribute.
    assert m["pair_samples"] == 2, m["pair_samples"]
    assert m["min_gap_m"] == 25.0, m["min_gap_m"]
    # The post-crossing -8 m/s^2 samples must not appear in comfort stats.
    assert m["hard_brake_events"] == 0, m["hard_brake_events"]
    assert m["mean_abs_jerk_mps3"] == 0.0, m["mean_abs_jerk_mps3"]
    print(f"ok  crossing truncation: gap 25 m before / 1 m after, "
          f"min_gap={m['min_gap_m']} m from {m['pair_samples']} pre-crossing "
          f"samples; post-crossing brake excluded")


def test_low_ttc_normalisation():
    """Exposure seconds and pair-sample fraction are consistent."""
    config, sim = _run(None, 2, 2, time_max=300.0)
    m = compute_metrics(sim, config)
    assert m["pair_samples"] > 0
    for level in ("3.0", "1.5"):
        exposure = m["low_ttc_exposure_s"][level]
        fraction = m["low_ttc_fraction_of_pair_samples"][level]
        expected = exposure / (m["pair_samples"] * config.time_step)
        assert abs(expected - fraction) < 1e-4, (level, exposure, fraction, expected)
        assert 0.0 <= fraction <= 1.0
    print(f"ok  low-TTC normalised: <3s exposure={m['low_ttc_exposure_s']['3.0']}s "
          f"= {m['low_ttc_fraction_of_pair_samples']['3.0']:.5f} of "
          f"{m['pair_samples']} pair-samples")


def test_admission_block_evidence():
    """Admission failures record which rule blocked entry and where."""
    config = Config(seed=1, experiment=2, time_max=100.0)
    sim = Simulator(config, vehicle_class=LLMVehicle, llm_client=MockLLMClient())
    sim.run(verbose=False)
    m = compute_metrics(sim, config)
    assert m["admission_block_attempts"] > 0
    for b in sim.admission_blocks[:500]:
        assert b["reason"] in ("spacing", "kinematic")
        if b["front_position_m"] is not None:
            assert b["front_position_m"] >= 0.0
            assert 0.0 <= b["front_speed_mps"] < 40.0
    print(f"ok  admission evidence: demand={m['demand_total']} "
          f"entered={m['entered']} waiting={m['waiting_at_end']} "
          f"blocks={m['admission_block_attempts']} "
          f"(spacing={m['admission_blocks_spacing']}, "
          f"kinematic={m['admission_blocks_kinematic']}) "
          f"front_pos~{m['admission_block_mean_front_position_m']}m "
          f"front_v~{m['admission_block_mean_front_speed_mps']}m/s")


def test_execution_trace_and_per_vehicle_validity():
    """The ego keeps a 1 s trace, and every vehicle carries its boundary."""
    config = Config(seed=1, experiment=1, time_max=500.0)
    v = LLMVehicle(config, 60, None, llm_client=MockLLMClient())
    v.log_decisions = True
    v.current_time = 0.0
    v.position = 100.0
    v.speed = 10.0
    v.current_speed_limit = config.speed_limit
    v.llm_target_speed = 10.0
    v.llm_time_headway = 1.2
    v.last_llm_time = 0.0          # freeze cache: no replan during this test
    v.update_acceleration()
    assert len(v.execution_trace) == 1
    entry = v.execution_trace[0]
    for key in ("t", "speed", "cached_target_speed", "cached_time_headway",
                "executor_target_speed", "executor_time_headway",
                "recovery_guard_applied", "road_limit_capped",
                "headway_ramping", "stop_intent", "acceleration",
                "decision_count_so_far"):
        assert key in entry, f"missing trace field {key}"
    assert entry["executor_target_speed"] == 10.0
    v.current_time = 0.5
    v.update_acceleration()
    assert len(v.execution_trace) == 1, "trace must be sampled at 1 s, not every step"
    v.current_time = 1.0
    v.update_acceleration()
    assert len(v.execution_trace) == 2

    # per-vehicle validity boundary on the crossing case
    class _V:
        def __init__(self, vid, xs):
            self.id = vid
            self.active = False
            self.entry_time = 0.0
            self.scheduled_arrival = 0.0
            self.history = [
                {"t": round(i * 0.1, 1), "position": x, "speed": 10.0,
                 "acceleration": 0.0} for i, x in enumerate(xs)
            ]

    class _Sim:
        llm_ego_id = None
        admission_blocks = []
        arrival_schedule = [0.0, 0.0]
        entry_log = [
            {"id": 1, "scheduled_arrival": 0.0, "entry_time": 0.0,
             "entry_delay": 0.0},
            {"id": 2, "scheduled_arrival": 0.0, "entry_time": 0.0,
             "entry_delay": 0.0},
        ]

    _Sim.vehicles = [_V(1, [100, 100, 141]), _V(2, [130, 130, 135])]
    m = compute_metrics(
        _Sim(), Config(seed=1, experiment=1, time_max=0.3), ego_ids=[1, 2]
    )
    assert m["per_vehicle"]["1"]["stats_valid_until_s"] == 0.2
    assert m["per_vehicle"]["2"]["stats_valid_until_s"] == 0.2
    print("ok  ego execution trace (1 s sampling) and per-vehicle "
          "stats_valid_until_s recorded")


def test_guardrail_vs_executor_counted():
    """Model output, guarded cached plan and executed plan stay separate.

    The old code counted "effective limit < road limit" as an executor
    override, so a planner that correctly recommended 2 m/s in a jam was
    counted as being overruled, while the recovery guard raising 2 -> 30 was
    not counted at all. Each situation now has its own counter.
    """

    class _Client:
        PROMPT_VERSION = "test-v1"
        model = "test-model"

        def __init__(self, speed, headway=1.0):
            self.speed = speed
            self.headway = headway

        def decide(self, observation):
            return {"target_speed": self.speed,
                    "time_headway": self.headway,
                    "reason": "test"}

    config = Config(seed=1, experiment=1)

    # (a) ask for 100 m/s -> planner guardrail clamps the cached plan
    v = LLMVehicle(config, 1, None, llm_client=_Client(100.0, 5.0))
    v.position = 100.0
    v.speed = 10.0
    v.current_speed_limit = config.speed_limit
    v.check_road(0.0)
    v._call_planner()
    assert v.guardrail_corrections == 1
    assert v.llm_target_speed == config.speed_limit
    assert v.llm_time_headway == 2.0
    entry = v.decision_log[-1]
    assert entry["requested_target_speed"] == 100.0
    assert entry["target_speed"] == config.speed_limit
    assert entry["guardrail_correction"] is True
    for _ in range(5):
        v.update_acceleration()
    assert v.executor_steps == 5
    # cached plan == road limit, so this is NOT a road-limit override
    assert v.road_limit_cap_steps == 0
    assert v.recovery_guard_activations == 0
    assert v.model_name == "test-model"
    assert v.prompt_version == "test-v1"

    # (b) a LOW planner speed is executed as-is and must NOT be counted as
    #     an executor override (the old code counted it).
    v = LLMVehicle(config, 2, None, llm_client=_Client(2.0, 1.2))
    v.position = 100.0
    v.speed = 10.0
    v.current_speed_limit = config.speed_limit
    v.check_road(0.0)
    v._call_planner()
    assert v.guardrail_corrections == 0
    for _ in range(5):
        v.update_acceleration()
    assert v.executor_target_speed == 2.0
    assert v.road_limit_cap_steps == 0, v.road_limit_cap_steps
    assert v.headway_ramp_steps > 0  # 1.0 -> 1.2 s is genuinely ramped

    # (c) a cached plan ABOVE the road limit is a real executor override
    v = LLMVehicle(config, 3, None, llm_client=_Client(2.0))
    v.position = 100.0
    v.speed = 10.0
    v.llm_target_speed = 30.0
    v.current_speed_limit = 10.0
    v.last_llm_time = v.current_time        # freeze the cached plan
    v.update_acceleration()
    assert v.road_limit_cap_steps == 1
    assert v.executor_target_speed == 10.0

    # (d) recovery guard is counted when it RAISES a stale plan, once
    v = LLMVehicle(config, 4, None, llm_client=_Client(2.0))
    v.position = config.bottleneck_x_end + 50.0
    v.speed = 10.0
    v.current_speed_limit = config.speed_limit
    v._call_planner()               # cached plan = 2 m/s
    assert v.llm_target_speed == 2.0
    v.update_acceleration()
    assert v.recovery_guard_activations == 1
    assert v.executor_target_speed == config.speed_limit
    v.update_acceleration()
    assert v.recovery_guard_activations == 1  # not recounted every step

    print("ok  model/guardrail/executor split: clamp request 100->"
          f"{config.speed_limit}; low plan 2 m/s executed without being "
          "counted as an override; road cap 30->10 counted; recovery 2->30 "
          "counted once")


if __name__ == "__main__":
    test_common_demand()
    test_noise_independence()
    test_stop_target()
    test_plan_validation()
    test_recovery_guard_persistent_bottleneck()
    test_travel_time_only_completed()
    test_ttc_distribution_reported()
    test_ego_tracked_in_idm()
    test_cumulative_system_time()
    test_overlap_truncation()
    test_crossing_truncation_keeps_pre_crossing_gap()
    test_execution_trace_and_per_vehicle_validity()
    test_low_ttc_normalisation()
    test_admission_block_evidence()
    test_guardrail_vs_executor_counted()
    print("\nall targeted verification checks passed")

