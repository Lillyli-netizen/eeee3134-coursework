import json
for tag, p in [
    ("LOCAL", r"../../py_coursework/llm_car_following/results/qwen_real/metrics.json"),
    ("PACK", r"pack/results/qwen_real/metrics.json"),
]:
    try:
        m = json.load(open(p))
    except Exception as e:
        print(tag, "load failed:", e)
        continue
    print("---", tag, len(m), "rows")
    for r in m:
        if r.get("mode") == "llm_qwen":
            pv = r.get("per_vehicle", {}).get("60", {})
            print(
                "E%dS%d: ego_travel=%s pv60=%s fleet_min_ttc=%s calls=%s ego_min_ttc=%s"
                % (
                    r["experiment"], r["seed"],
                    r.get("ego_travel_time_s"), pv.get("travel_time_s"),
                    r.get("min_ttc_s"), r.get("llm_api_calls"),
                    r.get("ego_min_ttc_s"),
                )
            )
