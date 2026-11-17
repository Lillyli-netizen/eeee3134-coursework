"""Diagnose the entry backlog (experiment 2, seed 1, first 100 s).

Codex observed: demand 72, IDM entered 69 / waiting 3, Mock and
mock_noant entered 61 / waiting 11, while the leading vehicle was still at
~3000 m — i.e. nowhere near the 4500 m bottleneck. This script collects the
evidence needed to describe WHAT happens at the entrance without assuming a
cause: which admission rule fired, where the blocking vehicle was, how fast
it was going, what headway it was using, and how long the queued vehicle
had been waiting.

Run: python diagnose_entry.py
"""

import statistics

from config import Config
from llm_client import MockLLMClient, build_client
from metrics import compute_metrics
from simulator import Simulator
from vehicle_llm import LLMVehicle

TIME_MAX = 100.0
EXPERIMENT = 2
SEED = 1
MODES = [
    ("idm", None),
    ("llm_mock", MockLLMClient()),
    ("llm_mock_noant", build_client("mock_noant")),
]


def run_mode(client):
    config = Config(seed=SEED, experiment=EXPERIMENT, time_max=TIME_MAX)
    vc = LLMVehicle if client is not None else None
    from vehicle_idm import IDMVehicle
    sim = Simulator(
        config, vehicle_class=vc or IDMVehicle, llm_client=client
    )
    sim.run(verbose=False)
    return config, sim, compute_metrics(sim, config)


def main():
    print(f"experiment {EXPERIMENT}, seed {SEED}, time_max {TIME_MAX:.0f}s, "
          f"bottleneck {Config(seed=SEED, experiment=EXPERIMENT).bottleneck_x_start:.0f}"
          f"-{Config(seed=SEED, experiment=EXPERIMENT).bottleneck_x_end:.0f} m, "
          f"active from {Config(seed=SEED, experiment=EXPERIMENT).bottleneck_t_start:.0f}s\n")
    for name, client in MODES:
        config, sim, m = run_mode(client)
        leader = max((v for v in sim.vehicles if v.active),
                     key=lambda v: v.position, default=None)
        delays = [e["entry_delay"] for e in sim.entry_log]
        print(f"== {name} ==")
        print(f"  demand={m['demand_total']} entered={m['entered']} "
              f"waiting={m['waiting_at_end']} incomplete={m['incomplete']}")
        print(f"  entry delay: mean={statistics.mean(delays):.2f}s "
              f"max={max(delays):.2f}s"
              if delays else "  entry delay: n/a")
        print(f"  leading vehicle at end: id={leader.id if leader else None} "
              f"x={leader.position:.1f}m v={leader.speed:.2f}m/s"
              if leader else "  leading vehicle: none")
        if sim.admission_blocks:
            print(f"  blocked attempts={m['admission_block_attempts']} "
                  f"(spacing={m['admission_blocks_spacing']}, "
                  f"kinematic={m['admission_blocks_kinematic']}, "
                  f"during bottleneck={m['admission_blocks_while_bottleneck_active']})")
            print(f"  blocking vehicle: x~{m['admission_block_mean_front_position_m']}m "
                  f"v~{m['admission_block_mean_front_speed_mps']}m/s "
                  f"headway~{m['admission_block_mean_front_headway_s']}s "
                  f"queued~{m['admission_block_mean_waiting_s']}s")
        else:
            print("  blocked attempts=0")
        # Speed and headway of admitted LLM vehicles near the entrance.
        if client is not None:
            near = []
            headways = []
            for v in sim.vehicles:
                if not v.history:
                    continue
                for r in v.history:
                    if r["position"] < 500.0:
                        near.append(r["speed"])
                if hasattr(v, "time_headway"):
                    headways.append(v.time_headway)
            if near:
                print(f"  admitted vehicles: mean speed in first 500 m="
                      f"{statistics.mean(near):.2f}m/s (n={len(near)} samples)")
            if headways:
                print(f"  admitted vehicles: final time headway "
                      f"mean={statistics.mean(headways):.2f}s "
                      f"max={max(headways):.2f}s")
        print()


if __name__ == "__main__":
    main()
