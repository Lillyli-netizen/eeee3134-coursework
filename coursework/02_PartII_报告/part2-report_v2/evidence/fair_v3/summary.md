# fair_v3 summary

Provenance: sim_version `3.0-fair-sim`, metrics_version `3.0-metrics-v4`, 96 runs. Source hashes (sha256, first 16 hex): `config.py`=cfd58542cc7be022, `llm_client.py`=256a87ec2b6e57b5, `metrics.py`=7d025750fed1fa9d, `noise.py`=e0708f79dbd68802, `run_comparison.py`=353ed68939a4f106, `simulator.py`=478cb435a8837eb9, `vehicle.py`=ce2ea52885754d5f, `vehicle_idm.py`=392628fcf57a951a, `vehicle_llm.py`=1fd110316f069a68, `vehicle_llm_direct.py`=f080c783d59821ac

Runs whose pair/comfort statistics were truncated at a validity boundary: **0 of 96** (none — every run is valid over the full window)

## A. Efficiency and demand (mean ± sd over 8 seeds)

| Exp | Controller | Demand | Entered | Waiting | Completed frac. | Entry delay s | Throughput veh/h | Travel (completed) s | System (completed) s | Cumulative all-demand s |
|---|---|---|---|---|---|---|---|---|---|---|
| 1 | IDM | 589 | 589 | 0 | 0.792 | 0.04 | 1679 | 259.0 ± 0.8 | 259.0 ± 0.8 | 226.7 ± 0.6 |
| 1 | Mock (anticipation) | 589 | 589 | 0 | 0.778 | 0.04 | 1651 | 271.2 ± 4.3 | 271.3 ± 4.2 | 235.6 ± 3.0 |
| 1 | Mock (no anticipation) | 589 | 589 | 0 | 0.788 | 0.04 | 1672 | 262.4 ± 2.2 | 262.4 ± 2.2 | 229.2 ± 1.6 |
| 2 | IDM | 670 | 664 | 7 | 0.696 | 3.15 | 1679 | 305.8 ± 4.0 | 308.2 ± 5.2 | 261.5 ± 3.6 |
| 2 | Mock (anticipation) | 670 | 576 | 95 | 0.681 | 68.94 | 1642 | 266.1 ± 4.5 | 319.6 ± 4.7 | 269.3 ± 3.2 |
| 2 | Mock (no anticipation) | 670 | 576 | 95 | 0.686 | 68.94 | 1654 | 258.1 ± 2.3 | 312.0 ± 3.9 | 264.2 ± 2.9 |
| 3 | IDM | 589 | 589 | 0 | 0.214 | 0.04 | 454 | 529.5 ± 2.8 | 529.5 ± 2.8 | 422.2 ± 0.8 |
| 3 | Mock (anticipation) | 589 | 589 | 0 | 0.209 | 0.04 | 443 | 539.1 ± 2.5 | 539.1 ± 2.5 | 425.6 ± 0.5 |
| 3 | Mock (no anticipation) | 589 | 589 | 0 | 0.214 | 0.04 | 454 | 529.6 ± 2.8 | 529.6 ± 2.8 | 422.2 ± 0.8 |
| 4 | IDM | 672 | 665 | 8 | 0.188 | 3.94 | 454 | 540.4 ± 3.8 | 541.8 ± 4.3 | 432.7 ± 2.9 |
| 4 | Mock (anticipation) | 672 | 576 | 96 | 0.183 | 69.62 | 443 | 541.1 ± 2.5 | 551.1 ± 3.0 | 435.6 ± 2.9 |
| 4 | Mock (no anticipation) | 672 | 576 | 96 | 0.188 | 69.62 | 454 | 531.5 ± 2.9 | 541.9 ± 4.3 | 432.7 ± 2.9 |

> System (completed) covers completed vehicles only. Cumulative all-demand is a finite-horizon truncated sum over every scheduled vehicle, including those never admitted.

## B. Safety and comfort

| Exp | Controller | min TTC s | TTC p05 s | TTC<3 s exposure s | TTC<3 s fraction of pairs | Hard brake events | HB total s | HB entry-zone events | Stopped events | Stopped total s | mean |jerk| |
|---|---|---|---|---|---|---|---|---|---|---|---|
| 1 | IDM | 2.2 ± 0.1 | 21.4 ± 2.5 | 292.7 | 0.00221 | 5 | 6.5 | 0 | 11 | 19.6 | 2.77 |
| 1 | Mock (anticipation) | 2.6 ± 0.3 | 13.3 ± 3.2 | 10.2 | 0.00007 | 3 | 0.3 | 0 | 64 | 251.6 | 2.81 |
| 1 | Mock (no anticipation) | 2.3 ± 0.0 | 15.0 ± 1.6 | 39.4 | 0.00029 | 5 | 6.4 | 0 | 0 | 0.0 | 2.79 |
| 2 | IDM | 1.8 ± 0.4 | 7.4 ± 0.6 | 1069.8 | 0.00622 | 626 | 169.8 | 621 | 899 | 7660.5 | 3.11 |
| 2 | Mock (anticipation) | 2.7 ± 0.2 | 12.4 ± 2.2 | 7.5 | 0.00006 | 638 | 593.5 | 635 | 38 | 210.2 | 2.70 |
| 2 | Mock (no anticipation) | 2.3 ± 0.0 | 14.7 ± 1.5 | 41.3 | 0.00032 | 640 | 599.6 | 635 | 0 | 0.0 | 2.67 |
| 3 | IDM | 2.0 ± 0.0 | 3.8 ± 0.1 | 4563.5 | 0.01842 | 5 | 6.5 | 0 | 4534 | 18648.0 | 2.08 |
| 3 | Mock (anticipation) | 2.3 ± 0.1 | 5.4 ± 0.1 | 98.5 | 0.00039 | 3 | 0.3 | 0 | 3157 | 18753.9 | 2.09 |
| 3 | Mock (no anticipation) | 2.2 ± 0.0 | 5.3 ± 0.1 | 127.0 | 0.00051 | 5 | 6.4 | 0 | 3228 | 16475.9 | 2.10 |
| 4 | IDM | 1.9 ± 0.2 | 3.6 ± 0.1 | 5454.4 | 0.01899 | 632 | 173.7 | 627 | 5952 | 31612.0 | 2.25 |
| 4 | Mock (anticipation) | 2.4 ± 0.1 | 5.3 ± 0.1 | 63.2 | 0.00026 | 636 | 589.4 | 633 | 2900 | 16118.5 | 2.10 |
| 4 | Mock (no anticipation) | 2.3 ± 0.0 | 5.2 ± 0.1 | 99.7 | 0.00041 | 638 | 595.6 | 633 | 2928 | 14517.1 | 2.10 |

> Exposure is pair-time (vehicle-pairs × seconds), not a single-vehicle duration. All statistics use t < valid_until_s (first overlap / order crossing); in this batch no run hit a boundary.

## C. Paired differences per seed (same demand, 8 pairs)

| Exp | Comparison | Δ cumulative all-demand s | Δ completed travel s | Δ completed system s |
|---|---|---|---|---|
| 1 | Mock (anticipation) − IDM | +8.9 (8/8 positive) | +12.2 (8/8 positive) | +12.2 (8/8 positive) |
| 1 | Mock (no anticipation) − IDM | +2.5 (8/8 positive) | +3.4 (8/8 positive) | +3.4 (8/8 positive) |
| 2 | Mock (anticipation) − IDM | +7.8 (8/8 positive) | -39.7 (0/8 positive) | +11.4 (8/8 positive) |
| 2 | Mock (no anticipation) − IDM | +2.6 (8/8 positive) | -47.6 (0/8 positive) | +3.8 (8/8 positive) |
| 3 | Mock (anticipation) − IDM | +3.4 (8/8 positive) | +9.6 (8/8 positive) | +9.6 (8/8 positive) |
| 3 | Mock (no anticipation) − IDM | +0.0 (1/8 positive) | +0.1 (6/8 positive) | +0.1 (6/8 positive) |
| 4 | Mock (anticipation) − IDM | +2.9 (8/8 positive) | +0.8 (5/8 positive) | +9.4 (8/8 positive) |
| 4 | Mock (no anticipation) − IDM | +0.1 (4/8 positive) | -8.8 (0/8 positive) | +0.1 (6/8 positive) |
