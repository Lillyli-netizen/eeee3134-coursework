# -*- coding: utf-8 -*-
"""Summarise the real-Qwen runs into a compact markdown table."""

import json
from pathlib import Path

BASE = Path(__file__).resolve().parent
rows = json.loads((BASE / "results/qwen_real/metrics.json").read_text(encoding="utf-8"))
log = json.loads((BASE / "results/qwen_real/qwen_run_log.json").read_text(encoding="utf-8"))

idx = {(r["experiment"], r["seed"], r["mode"]): r for r in rows}

print("## Real Qwen, single ego (id 60), rest IDM\n")
print("| Exp | Seed | Calls | Ego travel IDM / Qwen (s) | Delta | Ego HB IDM / Qwen | "
      "Fleet minTTC IDM / Qwen (s) | Entered IDM / Qwen | Guardrail | Recover | Cap | Ramp |")
print("|---|---|---|---|---|---|---|---|---|---|---|---|")
for e in (1, 2, 3, 4):
    for s in (1, 2):
        i = idx[(e, s, "idm")]
        q = idx[(e, s, "llm_qwen")]
        ei, eq = i["per_vehicle"]["60"], q["per_vehicle"]["60"]
        dec = json.loads((BASE / f"results/qwen_real/exp{e}/exp{e}_llm_qwen_seed{s}_v60_decisions.json")
                         .read_text(encoding="utf-8"))
        print(f"| {e} | {s} | {len(dec)} | {ei['travel_time_s']:.1f} / {eq['travel_time_s']:.1f} | "
              f"{eq['travel_time_s'] - ei['travel_time_s']:+.1f} | "
              f"{ei['hard_brake_events']} / {eq['hard_brake_events']} | "
              f"{i['min_ttc_s']:.2f} / {q['min_ttc_s']:.2f} | "
              f"{i['entered']} / {q['entered']} | "
              f"{q['llm_guardrail_corrections']} | {q['llm_recovery_guard_activations']} | "
              f"{q['llm_road_limit_cap_steps']} | {q['llm_headway_ramp_steps']} |")

print("\nTotals: calls=%d failures=%d mean_latency=%.2fs blocked=%.1fs budget=%d" % (
    log["total_api_calls"], log["total_api_failures"], log["mean_latency_s"],
    log["total_api_latency_s"], log["budget"]))

print("\nSchedule hashes equal per (exp, seed): " +
      str(all(idx[(e, s, "idm")]["arrival_schedule_hash"] ==
              idx[(e, s, "llm_qwen")]["arrival_schedule_hash"]
              for e in (1, 2, 3, 4) for s in (1, 2))))
print("Statistics invalid runs: " + str(sum(1 for r in rows if r.get("statistics_invalid"))))
