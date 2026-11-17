"""Debug: find the first vehicle that slows down before the jam."""

from config import Config
from simulator import Simulator
from vehicle_llm import LLMVehicle
from llm_client import MockLLMClient

config = Config(seed=1, experiment=1, time_max=120.0)
client = MockLLMClient()
sim = Simulator(config, vehicle_class=LLMVehicle, llm_client=client)
sim.run(verbose=False)

# Find the earliest record with speed below 25 m/s.
best = None  # (t, vehicle_id, record)
for v in sim.vehicles:
    for rec in v.history:
        if rec["speed"] < 25.0 and (best is None or rec["t"] < best[0]):
            best = (rec["t"], v.id, rec)
print("first slowdown below 25 m/s:", best)

t0, vid = best[0], best[1]
# Trace that vehicle and its leader around the event.
for vid_show in (vid, vid - 1):
    v = sim.vehicles[vid_show - 1]
    print(f"vehicle {vid_show} (front={None if v.vehicle_front is None else v.vehicle_front.id}):")
    for rec in v.history:
        if t0 - 4.0 <= rec["t"] <= t0 + 3.0:
            print("    t=%6.1f pos=%8.1f speed=%7.2f acc=%7.2f" % (
                rec["t"], rec["position"], rec["speed"], rec["acceleration"]))
    for d in v.decision_log:
        if t0 - 6.0 <= d["t"] <= t0 + 3.0:
            print("    decision:", d["t"], d["status"],
                  d.get("target_speed"), d.get("time_headway"), d.get("reason"),
                  "| obs:", {k: d["observation"][k] for k in
                             ("gap", "relative_speed", "distance_to_bottleneck_start")})
