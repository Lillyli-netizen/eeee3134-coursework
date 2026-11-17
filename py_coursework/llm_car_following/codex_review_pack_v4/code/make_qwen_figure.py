# -*- coding: utf-8 -*-
"""Figures for the real-Qwen single-ego case (report section 3.2)."""

import json
import sys
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

ROOT = Path(__file__).resolve().parent
OUT = Path(sys.argv[1]) if len(sys.argv) > 1 else ROOT / "figures"
OUT.mkdir(parents=True, exist_ok=True)

# Data dir: explicit arg wins, else package layouts are tried in order.
_data_arg = Path(sys.argv[2]) if len(sys.argv) > 2 else None
for _c in ([_data_arg] if _data_arg else []) + [
    Path("results/qwen_real"), Path("../results/qwen_real"),
    ROOT / "results/qwen_real", ROOT.parent / "results/qwen_real",
]:
    if _c is not None and (_c / "metrics.json").exists():
        DATA = _c
        break
else:
    raise SystemExit("results/qwen_real not found; pass it as the 2nd argument")

rows = json.loads((DATA / "metrics.json").read_text(encoding="utf-8"))
idx = {(r["experiment"], r["seed"], r["mode"]): r for r in rows}

labels, idm_t, qwen_t, deltas = [], [], [], []
for e in (1, 2, 3, 4):
    for s in (1, 2):
        i, q = idx[(e, s, "idm")], idx[(e, s, "llm_qwen")]
        labels.append(f"E{e}S{s}")
        idm_t.append(i["per_vehicle"]["60"]["travel_time_s"])
        qwen_t.append(q["per_vehicle"]["60"]["travel_time_s"])
        deltas.append(qwen_t[-1] - idm_t[-1])

fig, axes = plt.subplots(1, 2, figsize=(11, 3.8))

x = range(len(labels))
axes[0].bar([v - 0.2 for v in x], idm_t, width=0.4, label="IDM (same demand)", color="#7f8c8d")
axes[0].bar([v + 0.2 for v in x], qwen_t, width=0.4, label="Qwen ego (id 60)", color="#c0392b")
axes[0].set_xticks(list(x), labels, fontsize=8)
axes[0].set_ylabel("Ego travel time (s)")
axes[0].set_title("Vehicle 60 travel time, real Qwen vs IDM", fontsize=10)
axes[0].legend(fontsize=8, frameon=False)

axes[1].bar(list(x), deltas, color=["#c0392b" if d > 0 else "#27ae60" for d in deltas])
axes[1].axhline(0, color="black", linewidth=0.8)
for xi, d in zip(x, deltas):
    axes[1].text(xi, d + (1.5 if d >= 0 else -4.5), f"{d:+.0f}", ha="center", fontsize=7)
axes[1].set_xticks(list(x), labels, fontsize=8)
axes[1].set_ylabel("Qwen − IDM (s)")
axes[1].set_title("Ego travel-time difference", fontsize=10)

for ax in axes:
    ax.spines[["top", "right"]].set_visible(False)
    ax.grid(axis="y", alpha=0.25)

fig.tight_layout()
fig.savefig(OUT / "qwen_real_ego.png", dpi=200)
print("written:", OUT / "qwen_real_ego.png")
