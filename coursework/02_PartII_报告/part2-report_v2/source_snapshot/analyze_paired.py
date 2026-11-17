"""Paired comparison on the same completed vehicle IDs.

Travel time is only defined for vehicles that exited. Different controllers
may complete different subsets, so comparing fleet averages mixes different
vehicles. This script restricts the comparison to the intersection of
completed IDs for a given (experiment, seed) and reports the paired
difference, plus the demand-wide cumulative metric which needs no
intersection.

Usage:
    python analyze_paired.py results/fair_v3/exp2/metrics.json
"""

import json
import statistics
import sys

PAIRS = [("llm_mock", "idm"), ("llm_mock_noant", "idm")]


def main(path):
    with open(path, encoding="utf-8") as fh:
        rows = json.load(fh)
    seeds = sorted({r["seed"] for r in rows})
    print(f"{path}: {len(rows)} rows, {len(seeds)} seeds\n")
    for treatment, baseline in PAIRS:
        print(f"== {treatment} vs {baseline} ==")
        d_travel, d_system, n_common = [], [], []
        d_cumulative = []
        for seed in seeds:
            by_mode = {r["mode"]: r for r in rows if r["seed"] == seed}
            if treatment not in by_mode or baseline not in by_mode:
                continue
            t = by_mode[treatment]
            b = by_mode[baseline]
            t_travel = t.get("completed_travel_time_by_id_s", {})
            b_travel = b.get("completed_travel_time_by_id_s", {})
            common = sorted(set(t_travel) & set(b_travel), key=int)
            if common:
                n_common.append(len(common))
                d_travel.append(
                    statistics.mean(t_travel[i] - b_travel[i] for i in common)
                )
                d_system.append(
                    statistics.mean(
                        t["completed_system_time_by_id_s"][i]
                        - b["completed_system_time_by_id_s"][i]
                        for i in common
                    )
                )
            d_cumulative.append(
                t["mean_cumulative_system_time_all_s"]
                - b["mean_cumulative_system_time_all_s"]
            )
        if not d_travel:
            print("  no common completed vehicles; supply a longer run\n")
            continue
        print(f"  common completed vehicles: mean={statistics.mean(n_common):.0f} "
              f"(min {min(n_common)}, max {max(n_common)})")
        print(f"  paired travel time diff : mean={statistics.mean(d_travel):+.1f}s "
              f"min={min(d_travel):+.1f} max={max(d_travel):+.1f} "
              f"faster in {sum(1 for d in d_travel if d < 0)}/{len(d_travel)} seeds")
        print(f"  paired system time diff : mean={statistics.mean(d_system):+.1f}s "
              f"min={min(d_system):+.1f} max={max(d_system):+.1f} "
              f"faster in {sum(1 for d in d_system if d < 0)}/{len(d_system)} seeds")
        print(f"  demand-wide cumulative diff (no pairing needed): "
              f"mean={statistics.mean(d_cumulative):+.1f}s "
              f"worse in {sum(1 for d in d_cumulative if d > 0)}/{len(d_cumulative)} seeds\n")


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else "results/fair_v3/exp2/metrics.json")
