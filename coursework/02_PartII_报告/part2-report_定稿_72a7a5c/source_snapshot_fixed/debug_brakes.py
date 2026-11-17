"""Diagnose where hard brakes happen: exp2 seed1, IDM vs LLM-mock."""

from config import Config
from simulator import Simulator
from vehicle_idm import IDMVehicle
from vehicle_llm import LLMVehicle
from llm_client import MockLLMClient


def histogram(vehicle_class, client_kind):
    config = Config(seed=1, experiment=2, time_max=config_default_time)
    client = MockLLMClient() if client_kind else None
    sim = Simulator(config, vehicle_class=vehicle_class, llm_client=client)
    sim.run(verbose=False)

    buckets = {"x=0-100": 0, "x=100-300": 0, "x=300-600": 0,
               "x=600-900": 0, "x=900+": 0}
    entry_brakes = 0
    speeds = []
    for v in sim.vehicles:
        for i, rec in enumerate(v.history):
            if rec["acceleration"] <= -6.0:
                x = rec["position"]
                if x < 100:
                    buckets["x=0-100"] += 1
                elif x < 300:
                    buckets["x=100-300"] += 1
                elif x < 600:
                    buckets["x=300-600"] += 1
                elif x < 900:
                    buckets["x=600-900"] += 1
                else:
                    buckets["x=900+"] += 1
                if i <= 20:          # first 2 s after insertion
                    entry_brakes += 1
                speeds.append(rec["speed"])
    mean_speed_at_brake = sum(speeds) / len(speeds) if speeds else 0
    return buckets, entry_brakes, mean_speed_at_brake, len(speeds)


config_default_time = 1000.0

for label, vclass, ckind in (("IDM", IDMVehicle, None), ("LLM-mock", LLMVehicle, True)):
    buckets, entry, mean_v, total = histogram(vclass, ckind)
    print(f"{label}: total hard-brake records = {total}")
    for k, v in buckets.items():
        print(f"   {k:>10}: {v}")
    print(f"   within first 2 s of entry: {entry}")
    print(f"   mean speed at hard brake: {mean_v:.2f} m/s")
