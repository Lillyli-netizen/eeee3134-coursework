import json
import zipfile
from pathlib import Path

SOURCES = [
    ("local_results", None, r"../../py_coursework/llm_car_following/results/qwen_real/metrics.json"),
    ("v4_pack", None, r"pack/results/qwen_real/metrics.json"),
    ("review_pack_zip", r"../Codex评审包_20261109.zip", "results/qwen_real/metrics.json"),
    ("github_evidence", None, r"../part2-report_来自GitHub/evidence/qwen_real/metrics.json"),
]

for tag, zippath, member in SOURCES:
    try:
        if zippath:
            with zipfile.ZipFile(zippath) as z:
                names = [n for n in z.namelist() if n.endswith("qwen_real/metrics.json")]
                if not names:
                    print(tag, "NO qwen_real/metrics.json; candidates:",
                          [n for n in z.namelist() if "metrics.json" in n][:5])
                    continue
                m = json.loads(z.read(names[0]).decode("utf-8"))
                print(tag, "-> member:", names[0])
        else:
            m = json.load(open(member))
    except Exception as e:
        print(tag, "load failed:", e)
        continue
    vals = []
    for r in m:
        if r.get("mode") == "llm_qwen":
            vals.append("E%dS%d=%s/%s/%s" % (
                r["experiment"], r["seed"],
                r.get("ego_travel_time_s"), r.get("min_ttc_s"),
                r.get("llm_api_calls")))
    print(tag, len(m), "rows:", "; ".join(vals))
