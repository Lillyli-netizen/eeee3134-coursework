import json
import statistics

m = json.load(open(r"pack/results/qwen_real/metrics.json"))
idx = {(r["mode"], r["experiment"], r["seed"]): r for r in m}
print("True paired ego (vehicle 60) differences, from per_vehicle records:")
diffs = []
for e in (1, 2, 3, 4):
    for s in (1, 2):
        q = idx[("llm_qwen", e, s)]["per_vehicle"]["60"]
        b = idx[("idm", e, s)]["per_vehicle"]["60"]
        dq = q["travel_time_s"]
        db = b["travel_time_s"]
        diffs.append(dq - db)
        print(f"  E{e}S{s}: qwen {dq:.1f} vs idm {db:.1f} -> {dq - db:+.1f} s")
print("mean %+.1f  median %+.1f" % (statistics.mean(diffs), statistics.median(diffs)))
