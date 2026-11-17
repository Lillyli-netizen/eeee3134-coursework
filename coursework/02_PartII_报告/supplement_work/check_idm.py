import json
m = json.load(open(r"pack/results/qwen_real/metrics.json"))
for r in m:
    if r.get("mode") == "idm":
        print(
            "E%dS%d IDM: ego_travel=%s fleet_min_ttc=%s"
            % (r["experiment"], r["seed"],
               r.get("ego_travel_time_s"), r.get("min_ttc_s"))
        )
