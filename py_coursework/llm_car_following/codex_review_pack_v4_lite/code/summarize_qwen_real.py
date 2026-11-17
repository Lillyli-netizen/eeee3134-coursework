# -*- coding: utf-8 -*-
"""Summarise the real-Qwen runs (single ego id 60) into a compact table.

Data directory resolution order: ``--results``, then ``results/qwen_real``,
then ``../results/qwen_real`` (the unzipped package layout, run from code/),
then the same relative to this script. No files need to be moved.

Latency is reported in two scopes, both computed from the raw decision logs:
success-only (what the run log's total_latency covers) and all calls including
the 10 s timeout waits. The raw logs are the source of truth and are not
modified.
"""

import argparse
import json
import statistics
from pathlib import Path

BASE = Path(__file__).resolve().parent
ESTIMATED_CALLS = {1: 16, 2: 16, 3: 38, 4: 38}  # offline mock-policy estimate


def resolve_results(arg):
    candidates = [Path(arg)] if arg else []
    candidates += [
        Path("results/qwen_real"), Path("../results/qwen_real"),
        BASE / "results/qwen_real", BASE.parent / "results/qwen_real",
    ]
    for c in candidates:
        if (c / "metrics.json").exists():
            return c
    raise SystemExit("results/qwen_real not found; pass --results DIR")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--results", default=None, help="path to results/qwen_real")
    args = ap.parse_args()
    root = resolve_results(args.results)
    print("data dir:", root)

    rows = json.loads((root / "metrics.json").read_text(encoding="utf-8"))
    log = json.loads((root / "qwen_run_log.json").read_text(encoding="utf-8"))
    idx = {(r["experiment"], r["seed"], r["mode"]): r for r in rows}

    # --- latency from raw decision logs (failures included) ---
    succ_lat, fail_lat, decisions_by_run = [], [], {}
    for p in sorted(root.glob("exp*/exp*_llm_qwen_seed*_v60_decisions.json")):
        entries = json.loads(p.read_text(encoding="utf-8"))
        decisions_by_run[p.parent.name + "/" + p.name.split("_v60")[0]] = entries
        for x in entries:
            lat = x.get("latency_s")
            if lat is None:
                continue
            (fail_lat if x.get("status") == "invalid" else succ_lat).append(lat)

    print("\n## Real Qwen, single ego (id 60), rest IDM\n")
    print("| Exp | Seed | Calls (est.) | Ego travel IDM / Qwen (s) | Delta | Ego HB IDM / Qwen | "
          "Fleet minTTC IDM / Qwen (s) | Entered IDM / Qwen | Recover | Ramp |")
    print("|---|---|---|---|---|---|---|---|---|---|")
    deltas = []
    for e in (1, 2, 3, 4):
        for s in (1, 2):
            i, q = idx[(e, s, "idm")], idx[(e, s, "llm_qwen")]
            ei, eq = i["per_vehicle"]["60"], q["per_vehicle"]["60"]
            n_calls = sum(1 for k, v in decisions_by_run.items()
                          if f"exp{e}" in k and f"seed{s}" in k for _ in v)
            d = eq["travel_time_s"] - ei["travel_time_s"]
            deltas.append(d)
            print(f"| {e} | {s} | {n_calls} ({ESTIMATED_CALLS[e]}) | "
                  f"{ei['travel_time_s']:.1f} / {eq['travel_time_s']:.1f} | {d:+.1f} | "
                  f"{ei['hard_brake_events']} / {eq['hard_brake_events']} | "
                  f"{i['min_ttc_s']:.2f} / {q['min_ttc_s']:.2f} | "
                  f"{i['entered']} / {q['entered']} | "
                  f"{q['llm_recovery_guard_activations']} | {q['llm_headway_ramp_steps']} |")

    print("\nEgo travel-time delta (Qwen - IDM, paired per run):")
    print("  per-run:", ", ".join(f"{d:+.1f}" for d in deltas))
    print("  mean %+.1f s | median %+.1f s | min %+.1f s | max %+.1f s" % (
        statistics.fmean(deltas), statistics.median(deltas),
        min(deltas), max(deltas)))

    print("\nCall volume vs offline estimate (per experiment, both seeds):")
    for e in (1, 2, 3, 4):
        actual = [sum(len(v) for k, v in decisions_by_run.items()
                      if f"exp{e}" in k and f"seed{s}" in k) for s in (1, 2)]
        rel = ["below" if a < ESTIMATED_CALLS[e] else "above" if a > ESTIMATED_CALLS[e]
               else "equal" for a in actual]
        print(f"  exp{e}: actual {actual} vs estimate {ESTIMATED_CALLS[e]} -> {rel}")

    print("\nLatency (from raw decision logs):")
    print("  success: n=%d total=%.1fs mean=%.2fs" % (
        len(succ_lat), sum(succ_lat), statistics.fmean(succ_lat)))
    if fail_lat:
        print("  failed : n=%d total=%.1fs mean=%.2fs (all 10s client timeouts)" % (
            len(fail_lat), sum(fail_lat), statistics.fmean(fail_lat)))
    all_lat = succ_lat + fail_lat
    print("  ALL    : n=%d total=%.1fs mean=%.2fs" % (
        len(all_lat), sum(all_lat), statistics.fmean(all_lat)))
    print("  run log total_latency_s=%.1f (success-only scope)" % log["total_api_latency_s"])

    print("\nTotals: calls=%d failures=%d budget=%d stopped_early=%s" % (
        log["total_api_calls"], log["total_api_failures"], log["budget"],
        log.get("stopped_early", False)))
    print("Schedule hashes equal per (exp, seed):",
          all(idx[(e, s, "idm")]["arrival_schedule_hash"] ==
              idx[(e, s, "llm_qwen")]["arrival_schedule_hash"]
              for e in (1, 2, 3, 4) for s in (1, 2)))
    print("Statistics invalid runs:",
          sum(1 for r in rows if r.get("statistics_invalid")))


if __name__ == "__main__":
    main()
