"""Offline replay figures for the Codex handoff. No API calls.

Re-runs two saved real-Qwen cases by feeding the logged planner decisions
back through the same two-layer code (ReplayClient replaces the network
client), then draws:

  fig_ego_highlight_E4S1.png - two-panel time-space diagram, vehicle 60
                               highlighted against the IDM baseline
  fig_ttc_event_E2S1.png     - zoom on the recorded min-TTC (0.76 s) event

Replay fidelity is checked against the recorded metrics (travel time,
fleet min TTC, API call count) before any figure is saved.
"""

import json
import sys
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
from matplotlib.collections import LineCollection

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE / "pack" / "code"))

from config import Config            # noqa: E402
from simulator import Simulator      # noqa: E402
from vehicle_llm import LLMVehicle   # noqa: E402
from vehicle_idm import IDMVehicle   # noqa: E402
from metrics import compute_metrics  # noqa: E402

QWEN = HERE / "pack" / "results" / "qwen_real"
OUT = HERE.parent / "补充图_20261110"
TRIGGER = {"min_call_interval": 10.0, "max_recheck_interval": 60.0,
           "notice_distance": 500.0}
EGO = 60

# Recorded values from results/qwen_real/metrics.json (the runs being
# replayed; per_vehicle["60"].travel_time_s and min_ttc_s).
EXPECTED = {
    # (exp, seed): (qwen ego travel s, fleet min TTC s, api calls)
    (4, 1): (632.3, 1.05, 35),
    (2, 1): (315.6, 0.76, 16),
}


class ReplayClient:
    """Feeds recorded decisions back in order; replaces the network client."""

    model = "replay-of-qwen-flash"
    PROMPT_VERSION = "v2-tuned-2026-11(replay)"

    def __init__(self, decisions):
        self.items = list(decisions)
        self.i = 0
        self.overflow = 0

    def decide(self, observation):
        if self.i >= len(self.items):
            self.overflow += 1
            return None
        d = self.items[self.i]
        self.i += 1
        if d.get("status") != "ok":
            return None  # recorded failure -> fail-operational branch
        return {
            "target_speed": d["requested_target_speed"],
            "time_headway": d["requested_time_headway"],
            "reason": d.get("reason", ""),
        }


def load_decisions(exp, seed):
    p = QWEN / f"exp{exp}" / f"exp{exp}_llm_qwen_seed{seed}_v{EGO}_decisions.json"
    return json.loads(p.read_text(encoding="utf-8"))


def run_case(exp, seed, replay):
    config = Config(seed=seed, experiment=exp, time_max=Config.DEFAULT_TIME_MAX)
    client = None
    if replay:
        client = ReplayClient(load_decisions(exp, seed))
    sim = Simulator(
        config,
        vehicle_class=LLMVehicle if replay else IDMVehicle,
        llm_client=client,
        llm_ego_id=EGO if replay else None,
        llm_trigger_params=dict(TRIGGER) if replay else None,
    )
    sim.run(verbose=False)
    return sim, config, client


def ego_of(sim):
    return next(v for v in sim.vehicles if v.id == EGO)


def travel_time(vehicle, road_length):
    t_exit = None
    for rec in vehicle.history:
        if rec["position"] >= road_length:
            t_exit = rec["t"]
            break
    return None if t_exit is None else t_exit - vehicle.entry_time


def check_fidelity(exp, seed, sim, config, client):
    """Compare the replay against the recorded metrics; abort on mismatch."""
    exp_ttc = compute_metrics(sim, config, ego_ids=[EGO])["min_ttc_s"]
    ego = ego_of(sim)
    travel = travel_time(ego, config.road_length)
    exp_travel, exp_minttc, exp_calls = EXPECTED[(exp, seed)]
    problems = []
    if client.overflow:
        raise SystemExit(f"E{exp}S{seed}: planner triggered {client.overflow} "
                         f"extra times beyond the recorded decisions")
    if ego.call_count != exp_calls:
        raise SystemExit(f"E{exp}S{seed}: call count {ego.call_count} "
                         f"!= recorded {exp_calls}")
    if travel is None or abs(travel - exp_travel) > 0.5:
        raise SystemExit(f"E{exp}S{seed}: ego travel {travel} "
                         f"!= recorded {exp_travel}")
    if abs(exp_ttc - exp_minttc) > 0.05:
        raise SystemExit(f"E{exp}S{seed}: fleet min TTC {exp_ttc:.3f} "
                         f"!= recorded {exp_minttc}")
    print(f"E{exp}S{seed} replay OK: travel {travel:.1f}s "
          f"(recorded {exp_travel}), fleet min TTC {exp_ttc:.2f}s "
          f"(recorded {exp_minttc}), calls {ego.call_count}")
    return ego


def draw_fleet(ax, sim, config, cmap, norm, stride=3):
    for vehicle in sim.vehicles[::stride]:
        if vehicle.id == EGO or len(vehicle.history) < 2:
            continue
        t = np.array([r["t"] for r in vehicle.history])
        x = np.array([r["position"] for r in vehicle.history])
        v = np.array([r["speed"] for r in vehicle.history])
        pts = np.column_stack((t, x)).reshape(-1, 1, 2)
        segs = np.concatenate((pts[:-1], pts[1:]), axis=1)
        lc = LineCollection(segs, cmap=cmap, norm=norm, linewidths=0.6)
        lc.set_array(0.5 * (v[:-1] + v[1:]))
        ax.add_collection(lc)


def fig_ego_highlight(exp, seed):
    sim_q, cfg_q, client_q = run_case(exp, seed, replay=True)
    ego_q = check_fidelity(exp, seed, sim_q, cfg_q, client_q)
    sim_i, cfg_i, _ = run_case(exp, seed, replay=False)
    travel_i = travel_time(ego_of(sim_i), cfg_i.road_length)
    travel_q = travel_time(ego_q, cfg_q.road_length)

    fig, axes = plt.subplots(1, 2, figsize=(14, 6), sharex=True, sharey=True)
    cmap = plt.get_cmap("jet_r")
    norm = plt.Normalize(0.0, cfg_q.speed_limit)
    for ax, sim, cfg, name, tt in (
        (axes[0], sim_i, cfg_i, "IDM baseline", travel_i),
        (axes[1], sim_q, cfg_q, "Real Qwen + IDM", travel_q),
    ):
        draw_fleet(ax, sim, cfg, cmap, norm)
        ego = ego_of(sim)
        ax.plot([r["t"] for r in ego.history],
                [r["position"] for r in ego.history],
                color="black", linewidth=2.2,
                label=f"vehicle {EGO} (tracked)")
        ax.set_xlim(0, cfg.time_max)
        ax.set_ylim(0, cfg.road_length)
        ax.set_xlabel("Time (s)")
        ax.set_title(f"{name} - vehicle {EGO} travel {tt:.1f} s")
        ax.legend(frameon=False, loc="upper left")
        ax.grid(linestyle="--", alpha=0.3)
    axes[0].set_ylabel("Position (m)")
    sm = plt.cm.ScalarMappable(cmap=cmap, norm=norm)
    # Reserve a dedicated strip on the far right for the colorbar so it
    # does not get squeezed between the two panels by tight_layout.
    fig.subplots_adjust(left=0.06, right=0.90, top=0.88, bottom=0.12,
                        wspace=0.12)
    cbar_ax = fig.add_axes([0.92, 0.12, 0.018, 0.76])
    fig.colorbar(sm, cax=cbar_ax, label="Speed (m/s)")
    fig.suptitle(f"E{exp} seed{seed}: identical demand, only vehicle {EGO} "
                 f"is model-controlled (right panel)")
    OUT.mkdir(parents=True, exist_ok=True)
    path = OUT / f"fig_ego_highlight_E{exp}S{seed}.png"
    fig.savefig(path, dpi=160)
    plt.close(fig)
    print("saved:", path)


def ttc_series(ego, road_length):
    leader = ego.vehicle_front
    lh = {r["t"]: r for r in leader.history}
    rows = []
    for r in ego.history:
        lr = lh.get(r["t"])
        if lr is None or lr["position"] >= road_length:
            continue
        gap = lr["position"] - r["position"] - ego.vehicle_length
        rel = r["speed"] - lr["speed"]
        ttc = gap / rel if rel > 1e-9 else float("inf")
        rows.append((r["t"], gap, ttc, r["speed"], lr["speed"]))
    return rows, leader


def fleet_min_ttc_pair(sim, road_length):
    """Find the adjacent pair and moment of the fleet-wide min TTC."""
    best = None  # (ttc, t, gap, follower, leader, v_f, v_l)
    for veh in sim.vehicles:
        leader = veh.vehicle_front
        if leader is None:
            continue
        lh = {r["t"]: r for r in leader.history}
        for r in veh.history:
            lr = lh.get(r["t"])
            if lr is None or lr["position"] >= road_length:
                continue
            gap = lr["position"] - r["position"] - veh.vehicle_length
            rel = r["speed"] - lr["speed"]
            if rel <= 1e-9:
                continue
            ttc = gap / rel
            if best is None or ttc < best[0]:
                best = (ttc, r["t"], gap, veh, leader, r["speed"], lr["speed"])
    return best


def fig_ttc_event(exp, seed, window=40.0):
    sim_q, cfg_q, client_q = run_case(exp, seed, replay=True)
    check_fidelity(exp, seed, sim_q, cfg_q, client_q)
    best = fleet_min_ttc_pair(sim_q, cfg_q.road_length)
    ttc_min, t_min, gap_min, follower, leader, v_fol, v_lead = best
    print(f"E{exp}S{seed}: fleet min TTC {ttc_min:.2f}s at t={t_min:.1f} "
          f"between follower id{follower.id} and leader id{leader.id}")
    lo = t_min - window
    hi = min(t_min + window, cfg_q.time_max)
    rows, _ = ttc_series(follower, cfg_q.road_length)
    sel = [r for r in rows if lo <= r[0] <= hi]

    fig, axes = plt.subplots(1, 2, figsize=(14, 5.5))
    ax = axes[0]
    fh = {r["t"]: r for r in follower.history}
    lh = {r["t"]: r for r in leader.history}
    ts = [t for t in sorted(fh) if lo <= t <= hi]
    ax.plot(ts, [fh[t]["position"] for t in ts], lw=2.0,
            label=f"vehicle {follower.id} (follower)")
    ax.plot(ts, [lh[t]["position"] for t in ts], lw=2.0,
            label=f"vehicle {leader.id} (leader)")
    ax.axvline(t_min, color="red", linestyle="--", alpha=0.7)
    ax.set_xlim(lo, hi)
    ax.set_xlabel("Time (s)")
    ax.set_ylabel("Position (m)")
    ax.set_title(f"Positions around the closest approach (t = {t_min:.1f} s)")
    ax.legend(frameon=False)
    ax.grid(linestyle="--", alpha=0.3)

    ax = axes[1]
    ax.plot([r[0] for r in sel], [min(r[2], 15.0) for r in sel], lw=1.8,
            color="darkred")
    ax.plot([t_min], [ttc_min], "o", color="red")
    ax.annotate(f"min TTC = {ttc_min:.2f} s\n"
                f"gap {gap_min:.1f} m, follower {v_fol:.1f} m/s, "
                f"leader {v_lead:.1f} m/s",
                xy=(t_min, ttc_min), xytext=(lo + 3.0, 10.5),
                arrowprops=dict(arrowstyle="->", color="red"))
    ax.set_xlim(lo, hi)
    ax.set_xlabel("Time (s)")
    ax.set_ylabel("TTC (s, clipped at 15)")
    ax.set_title(f"E{exp} seed{seed}: fleet-minimum TTC event "
                 f"(pair {follower.id}/{leader.id})")
    ax.grid(linestyle="--", alpha=0.3)
    fig.subplots_adjust(left=0.07, right=0.98, wspace=0.25)
    OUT.mkdir(parents=True, exist_ok=True)
    path = OUT / f"fig_ttc_event_E{exp}S{seed}.png"
    fig.savefig(path, dpi=160, bbox_inches="tight")
    plt.close(fig)
    print("saved:", path, f"(min TTC in replay: {ttc_min:.2f}s)")


if __name__ == "__main__":
    fig_ego_highlight(4, 1)
    fig_ttc_event(2, 1)
