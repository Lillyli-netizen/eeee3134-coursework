"""Debug exp2 (random arrivals): find the first near-overlap and trace it."""

from config import Config
from simulator import Simulator
from vehicle_llm import LLMVehicle
from llm_client import MockLLMClient

config = Config(seed=1, experiment=2, time_max=1000.0)
client = MockLLMClient()
sim = Simulator(config, vehicle_class=LLMVehicle, llm_client=client)
sim.run(verbose=False)

# Index positions by time.
by_time = {}
for v in sim.vehicles:
    for rec in v.history:
        by_time.setdefault(round(rec["t"], 1), {})[v.id] = rec["position"]

# First instant any pair is closer than 0.5 m (about to overlap).
first_bad = None
for t in sorted(by_time):
    states = by_time[t]
    ids = sorted(states)
    for front, rear in zip(ids, ids[1:]):
        gap = states[front] - states[rear] - config.vehicle_length
        if gap < 0.5:
            first_bad = (t, front, rear, gap)
            break
    if first_bad:
        break

print("first near-overlap:", first_bad)

if first_bad:
    t0, front_id, rear_id = first_bad[0], first_bad[1], first_bad[2]
    for vid in (front_id, rear_id):
        v = sim.vehicles[vid - 1]
        leader_id = None if v.vehicle_front is None else v.vehicle_front.id
        print(f"vehicle {vid} (leader={leader_id}):")
        for rec in v.history:
            if t0 - 8.0 <= rec["t"] <= t0 + 1.0:
                print("    t=%6.1f pos=%8.1f speed=%7.2f acc=%8.2f" % (
                    rec["t"], rec["position"], rec["speed"], rec["acceleration"]))
        for d in v.decision_log:
            if t0 - 10.0 <= d["t"] <= t0 + 1.0:
                obs = d["observation"]
                print("    decision t=%s %s target=%s headway=%s | gap=%s rel=%s" % (
                    d["t"], d["status"], d.get("target_speed"),
                    d.get("time_headway"), obs.get("gap"), obs.get("relative_speed")))

    # Spawn info: when were these two vehicles inserted?
    for vid in (front_id, rear_id):
        v = sim.vehicles[vid - 1]
        h = v.history[0]
        print(f"vehicle {vid} spawned at t={h['t']} pos={h['position']:.1f} "
              f"speed={h['speed']:.1f}")
