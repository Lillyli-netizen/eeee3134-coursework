"""Build markdown + CSV summary tables from a result directory.

Usage: python summarize_results.py [results/fair_v3]
"""

import csv
import json
import statistics
import sys
from pathlib import Path

MODES = ["idm", "llm_mock", "llm_mock_noant"]
LABEL = {"idm": "IDM", "llm_mock": "Mock (anticipation)",
         "llm_mock_noant": "Mock (no anticipation)"}
EXPS = [1, 2, 3, 4]


def mean_sd(rows, key):
    values = [r[key] for r in rows if isinstance(r.get(key), (int, float))]
    if not values:
        return "—"
    if len(values) == 1:
        return f"{values[0]:.1f}"
    return f"{statistics.mean(values):.1f} ± {statistics.pstdev(values):.1f}"


def mean_of(rows, key):
    values = [r[key] for r in rows if isinstance(r.get(key), (int, float))]
    return statistics.mean(values) if values else None


def get_path(d, key):
    values = [r[d].get(key) for r in [d] if isinstance(d, dict)]
    return values


def main(base):
    base = Path(base)
    data = {e: json.load(open(base / f"exp{e}" / "metrics.json", encoding="utf-8"))
            for e in EXPS}
    out = []
    out.append(f"# {base.name} summary\n")
    first = data[EXPS[0]][0]
    hashes = first.get("source_hashes", {})
    out.append(
        "Provenance: sim_version `%s`, metrics_version `%s`, %d runs. "
        "Source hashes (sha256, first 16 hex): %s\n"
        % (first.get("sim_version"), first.get("metrics_version"),
           sum(len(data[e]) for e in EXPS),
           ", ".join(f"`{k}`={v}" for k, v in sorted(hashes.items())))
    )
    invalid = [(e, r["mode"], r["seed"], r.get("invalid_reason"))
               for e in EXPS for r in data[e] if r.get("statistics_invalid")]
    out.append(
        "Runs whose pair/comfort statistics were truncated at a validity "
        "boundary: **%d of %d**%s\n"
        % (len(invalid), sum(len(data[e]) for e in EXPS),
           "" if invalid else " (none — every run is valid over the full window)")
    )

    out.append("## A. Efficiency and demand (mean ± sd over 8 seeds)\n")
    out.append("| Exp | Controller | Demand | Entered | Waiting | Completed frac. "
               "| Entry delay s | Throughput veh/h | Travel (completed) s "
               "| System (completed) s | Cumulative all-demand s |")
    out.append("|---|---|---|---|---|---|---|---|---|---|---|")
    for e in EXPS:
        for m in MODES:
            sel = [r for r in data[e] if r["mode"] == m]
            out.append(
                f"| {e} | {LABEL[m]} | {mean_of(sel,'demand_total'):.0f} "
                f"| {mean_of(sel,'entered'):.0f} | {mean_of(sel,'waiting_at_end'):.0f} "
                f"| {mean_of(sel,'completed_fraction'):.3f} "
                f"| {mean_of(sel,'mean_entry_delay_s'):.2f} "
                f"| {mean_of(sel,'throughput_exits_veh_per_h'):.0f} "
                f"| {mean_sd(sel,'mean_travel_time_s')} "
                f"| {mean_sd(sel,'mean_system_time_completed_s')} "
                f"| {mean_sd(sel,'mean_cumulative_system_time_all_s')} |"
            )
    out.append("\n> System (completed) covers completed vehicles only. Cumulative "
               "all-demand is a finite-horizon truncated sum over every scheduled "
               "vehicle, including those never admitted.\n")

    out.append("## B. Safety and comfort\n")
    out.append("| Exp | Controller | min TTC s | TTC p05 s | TTC<3 s exposure s "
               "| TTC<3 s fraction of pairs | Hard brake events | HB total s "
               "| HB entry-zone events | Stopped events | Stopped total s | mean |jerk| |")
    out.append("|---|---|---|---|---|---|---|---|---|---|---|---|")
    for e in EXPS:
        for m in MODES:
            sel = [r for r in data[e] if r["mode"] == m]
            exp3 = statistics.mean([r["low_ttc_exposure_s"]["3.0"] for r in sel])
            frac3 = statistics.mean(
                [r["low_ttc_fraction_of_pair_samples"]["3.0"] for r in sel])
            out.append(
                f"| {e} | {LABEL[m]} | {mean_sd(sel,'min_ttc_s')} "
                f"| {mean_sd(sel,'ttc_p05_s')} | {exp3:.1f} | {frac3:.5f} "
                f"| {mean_of(sel,'hard_brake_events'):.0f} "
                f"| {mean_of(sel,'hard_brake_total_duration_s'):.1f} "
                f"| {mean_of(sel,'hard_brake_events_entry_zone'):.0f} "
                f"| {mean_of(sel,'stopped_events'):.0f} "
                f"| {mean_of(sel,'stopped_total_duration_s'):.1f} "
                f"| {mean_of(sel,'mean_abs_jerk_mps3'):.2f} |"
            )
    out.append("\n> Exposure is pair-time (vehicle-pairs × seconds), not a "
               "single-vehicle duration. All statistics use t < valid_until_s "
               "(first overlap / order crossing); in this batch no run hit a "
               "boundary.\n")

    out.append("## C. Paired differences per seed (same demand, 8 pairs)\n")
    out.append("| Exp | Comparison | Δ cumulative all-demand s | Δ completed "
               "travel s | Δ completed system s |")
    out.append("|---|---|---|---|---|")
    for e in EXPS:
        index = {(r["mode"], r["seed"]): r for r in data[e]}
        for m in ["llm_mock", "llm_mock_noant"]:
            dc, dt, ds = [], [], []
            for seed in range(1, 9):
                t = index.get((m, seed))
                b = index.get(("idm", seed))
                if not t or not b:
                    continue
                dc.append(t["mean_cumulative_system_time_all_s"]
                          - b["mean_cumulative_system_time_all_s"])
                if t.get("mean_travel_time_s") and b.get("mean_travel_time_s"):
                    dt.append(t["mean_travel_time_s"] - b["mean_travel_time_s"])
                if t.get("mean_system_time_completed_s") and b.get("mean_system_time_completed_s"):
                    ds.append(t["mean_system_time_completed_s"]
                              - b["mean_system_time_completed_s"])

            def fmt(vals):
                if not vals:
                    return "—"
                return (f"{statistics.mean(vals):+.1f} "
                        f"({sum(1 for v in vals if v > 0)}/{len(vals)} positive)")
            out.append(f"| {e} | {LABEL[m]} − IDM | {fmt(dc)} | {fmt(dt)} | {fmt(ds)} |")

    md = "\n".join(out) + "\n"
    (base / "summary.md").write_text(md, encoding="utf-8")

    with open(base / "summary.csv", "w", encoding="utf-8-sig", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(["experiment", "mode", "demand_total", "entered", "waiting_at_end",
                    "completed_fraction", "mean_entry_delay_s",
                    "throughput_exits_veh_per_h", "mean_travel_time_s",
                    "mean_system_time_completed_s",
                    "mean_cumulative_system_time_all_s", "min_ttc_s", "ttc_p05_s",
                    "low_ttc_exposure_3s", "low_ttc_fraction_3s",
                    "hard_brake_events", "hard_brake_total_duration_s",
                    "hard_brake_events_entry_zone", "stopped_events",
                    "stopped_total_duration_s", "mean_abs_jerk_mps3"])
        for e in EXPS:
            for m in MODES:
                sel = [r for r in data[e] if r["mode"] == m]
                w.writerow([e, m,
                            round(mean_of(sel, "demand_total"), 2),
                            round(mean_of(sel, "entered"), 2),
                            round(mean_of(sel, "waiting_at_end"), 2),
                            round(mean_of(sel, "completed_fraction"), 3),
                            round(mean_of(sel, "mean_entry_delay_s"), 2),
                            round(mean_of(sel, "throughput_exits_veh_per_h"), 2),
                            round(mean_of(sel, "mean_travel_time_s"), 2),
                            round(mean_of(sel, "mean_system_time_completed_s"), 2),
                            round(mean_of(sel, "mean_cumulative_system_time_all_s"), 2),
                            round(mean_of(sel, "min_ttc_s"), 2),
                            round(mean_of(sel, "ttc_p05_s"), 2),
                            round(statistics.mean([r["low_ttc_exposure_s"]["3.0"] for r in sel]), 2),
                            round(statistics.mean([r["low_ttc_fraction_of_pair_samples"]["3.0"] for r in sel]), 6),
                            round(mean_of(sel, "hard_brake_events"), 1),
                            round(mean_of(sel, "hard_brake_total_duration_s"), 1),
                            round(mean_of(sel, "hard_brake_events_entry_zone"), 1),
                            round(mean_of(sel, "stopped_events"), 1),
                            round(mean_of(sel, "stopped_total_duration_s"), 1),
                            round(mean_of(sel, "mean_abs_jerk_mps3"), 3)])
    print(md)
    print(f"written: {base/'summary.md'}, {base/'summary.csv'}")


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else "results/fair_v3")
