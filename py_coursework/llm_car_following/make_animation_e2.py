# -*- coding: utf-8 -*-
"""E2 seed1: IDM vs full-fleet Mock, side-by-side animation.

Top row   : road view (vehicle positions coloured by speed).
Bottom row: time-space speed field revealed as time advances.

No API calls: both modes run offline. Output: GIF.
"""
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.animation import FuncAnimation, PillowWriter
from pathlib import Path

from config import Config
from simulator import Simulator
from run_comparison import MODES
from llm_client import build_client

plt.rcParams["font.sans-serif"] = ["SimHei", "Microsoft YaHei", "DejaVu Sans"]
plt.rcParams["axes.unicode_minus"] = False

SEED = 1
EXP = 2
TIME_MAX = 1000
DT = 0.1
T_BIN = 1.0          # time resolution of the speed field (s)
X_BIN = 10.0         # space resolution (m)
FRAME_EVERY = 10     # one animation frame per 10 simulated seconds
FPS = 8

OUT = Path(r"D:\工作文件\学校文件\eeee3134\coursework\figures\animation_E2_idm_vs_mock.gif")


def run_mode(mode):
    vehicle_class, client_kind = MODES[mode]
    config = Config(seed=SEED, experiment=EXP, time_max=TIME_MAX)
    client = build_client(client_kind) if client_kind else None
    sim = Simulator(config, vehicle_class=vehicle_class, llm_client=client,
                    llm_ego_id=None, llm_trigger_params={},
                    llm_fraction=1.0 if client_kind else None)
    sim.run(verbose=False)
    return sim, config


def rasterise(sim, config):
    """Return speed field V[t, x] (m/s) and per-second road snapshots."""
    nt = int(TIME_MAX / T_BIN) + 1
    nx = int(config.road_length / X_BIN) + 1
    V = np.full((nt, nx), np.nan)
    snaps = {}
    for veh in sim.vehicles:
        for rec in veh.history:
            ti = int(rec["t"] / T_BIN)
            xi = int(rec["position"] / X_BIN)
            if not (0 <= ti < nt and 0 <= xi < nx):
                continue
            v = rec["speed"]
            # keep the slowest speed in each cell: congestion shows up
            if np.isnan(V[ti, xi]) or v < V[ti, xi]:
                V[ti, xi] = v
            snaps.setdefault(ti, {})[veh.id] = (rec["position"], v)
    return V, snaps


def main():
    print("running IDM ...", flush=True)
    sim_i, config = run_mode("idm")
    print("running full-fleet Mock ...", flush=True)
    sim_m, _ = run_mode("llm_mock")
    print("rasterising ...", flush=True)
    V_i, S_i = rasterise(sim_i, config)
    V_m, S_m = rasterise(sim_m, config)

    cmap = plt.get_cmap("RdYlBu").copy()
    cmap.set_bad("white")

    fig = plt.figure(figsize=(12.5, 7.6))
    gs = fig.add_gridspec(2, 2, height_ratios=[1, 2.3], hspace=0.28, wspace=0.18)
    road_axes = [fig.add_subplot(gs[0, j]) for j in range(2)]
    ts_axes = [fig.add_subplot(gs[1, j]) for j in range(2)]
    titles = ["IDM（基线，无预判）", "Mock 规划器（全车队，非真实 LLM）"]

    road_scat, ts_img, revealed = [], [], []
    for j, (V, title) in enumerate([(V_i, titles[0]), (V_m, titles[1])]):
        ax = road_axes[j]
        ax.set_xlim(0, config.road_length)
        ax.set_ylim(-0.6, 0.6)
        ax.set_yticks([])
        ax.set_xlabel("道路位置 x / m")
        ax.axhline(0, color="0.75", lw=6, zorder=0)
        ax.axvspan(config.bottleneck_x_start, config.bottleneck_x_end,
                   color="0.85", zorder=0)
        ax.text((config.bottleneck_x_start + config.bottleneck_x_end) / 2, 0.42,
                "低速区", ha="center", fontsize=9, color="0.35")
        ax.set_title(title, fontsize=12)
        sc = ax.scatter([], [], c=[], cmap=cmap, vmin=0, vmax=30, s=14,
                        edgecolors="none")
        road_scat.append(sc)

        bx = ts_axes[j]
        bx.set_xlabel("时间 t / s")
        bx.set_ylabel("位置 x / m")
        R = np.full_like(V, np.nan)          # revealed so far
        revealed.append(R)
        im = bx.imshow(R, origin="lower", aspect="auto", cmap=cmap,
                       vmin=0, vmax=30,
                       extent=[0, TIME_MAX, 0, config.road_length],
                       interpolation="nearest")
        ts_img.append(im)
        bx.axhline(config.bottleneck_x_start, color="0.4", lw=0.6, ls="--")
        bx.axhline(config.bottleneck_x_end, color="0.4", lw=0.6, ls="--")

    sm = plt.cm.ScalarMappable(cmap=cmap, norm=plt.Normalize(0, 30))
    cbar = fig.colorbar(sm, ax=ts_axes, shrink=0.85, pad=0.02)
    cbar.set_label("速度 v / (m/s)")

    frames = list(range(0, int(TIME_MAX / T_BIN), FRAME_EVERY))
    time_text = fig.text(0.5, 0.955, "", ha="center", fontsize=13)

    def update(k):
        ti = frames[k]
        time_text.set_text(f"E2 seed1　仿真时间 t = {ti:4d} s / {TIME_MAX} s")
        for j, (V, S) in enumerate([(V_i, S_i), (V_m, S_m)]):
            revealed[j][:ti + 1, :] = V[:ti + 1, :]
            ts_img[j].set_data(revealed[j])
            pts = list(S.get(ti, {}).values())
            if pts:
                arr = np.array(pts)
                road_scat[j].set_offsets(np.column_stack([arr[:, 0],
                                                          np.zeros(len(arr))]))
                road_scat[j].set_array(arr[:, 1])
            else:
                road_scat[j].set_offsets(np.empty((0, 2)))
        return road_scat + ts_img + [time_text]

    ani = FuncAnimation(fig, update, frames=len(frames), blit=False)
    OUT.parent.mkdir(parents=True, exist_ok=True)
    print(f"saving GIF ({len(frames)} frames) ...", flush=True)
    ani.save(str(OUT), writer=PillowWriter(fps=FPS))
    print("written:", OUT, OUT.stat().st_size, "bytes", flush=True)


if __name__ == "__main__":
    main()
