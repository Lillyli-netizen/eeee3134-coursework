"""Run IDM vs LLM-controlled simulations and compare them.

Example:
    python run_comparison.py --experiment 1
    python run_comparison.py --experiment 1 2 3 4 --llm qwen
"""

import argparse
import hashlib
import json
import zlib
from pathlib import Path

from config import Config
from llm_client import build_client
from metrics import compute_metrics, format_table
from plotting import plot_time_space_diagram
from simulator import Simulator
from vehicle_idm import IDMVehicle
from vehicle_llm import LLMVehicle
from vehicle_llm_direct import LLMDirectVehicle


# Version stamps are recorded IN EVERY ROW so a result file can never be
# separated from the code that produced it. Simulation and metrics are
# versioned separately: the simulation can stay identical while the metric
# definitions change (and vice versa).
SIM_VERSION = "3.0-fair-sim"
METRICS_VERSION = "3.0-metrics-v4"

# SHA-256 prefix of every source file that can change a result. Recorded per
# row; this is what settles "which code produced this number" when a version
# constant was forgotten or a file changed after a batch.
SOURCE_FILES = [
    "config.py", "vehicle.py", "vehicle_idm.py", "noise.py", "simulator.py",
    "metrics.py", "vehicle_llm.py", "vehicle_llm_direct.py", "llm_client.py",
    "run_comparison.py",
]


def source_hashes():
    root = Path(__file__).resolve().parent
    out = {}
    for name in SOURCE_FILES:
        path = root / name
        if path.exists():
            out[name] = hashlib.sha256(path.read_bytes()).hexdigest()[:16]
    return out


SOURCE_HASHES = source_hashes()

MODES = {
    "idm": (IDMVehicle, None),
    "llm_mock": (LLMVehicle, "mock"),
    "llm_mock_noant": (LLMVehicle, "mock_noant"),
    "llm_qwen": (LLMVehicle, "qwen"),
    "llm_qwen_direct": (LLMDirectVehicle, "qwen_accel"),
}

METRIC_COLUMNS = [
    "mode",
    "demand_total",
    "entered",
    "exited",
    "incomplete",
    "waiting_at_end",
    "mean_entry_delay_s",
    "throughput_exits_veh_per_h",
    "mean_travel_time_s",
    "mean_system_time_completed_s",
    "mean_cumulative_system_time_all_s",
    "completed_fraction",
    "mean_speed_mps",
    "mean_abs_jerk_mps3",
    "min_ttc_s",
    "ttc_p05_s",
    "hard_brake_events",
    "hard_brake_total_duration_s",
    "stopped_events",
    "min_gap_m",
    "llm_api_calls",
]


def run_one(mode, experiment, seed, time_max, llm_model=None, output_dir=None,
            llm_ego_id=None, llm_fraction=None, plot_stride=1,
            plot_line_width=1.2, save_decisions=True, ego_ids=None,
            trigger_profile=None):
    vehicle_class, client_kind = MODES[mode]
    config = Config(seed=seed, experiment=experiment, time_max=time_max)

    client = build_client(client_kind, model=llm_model) if client_kind else None
    # Real APIs need wider call spacing than the offline mock. The same
    # profile can be forced offline (trigger_profile="qwen") to estimate how
    # many calls a real run would make before spending any quota.
    if client_kind in ("qwen", "qwen_accel") or trigger_profile == "qwen":
        trigger_params = {"min_call_interval": 10.0,
                          "max_recheck_interval": 60.0,
                          "notice_distance": 500.0}
    else:
        trigger_params = {}
    sim = Simulator(
        config, vehicle_class=vehicle_class, llm_client=client,
        llm_ego_id=llm_ego_id, llm_trigger_params=trigger_params,
        llm_fraction=llm_fraction,
    )
    sim.run(verbose=False)

    # Always track the ego vehicle (default id 60) in EVERY mode, so the
    # LLM-ego runs are compared against the same vehicle under pure IDM,
    # not against a fleet average.
    ego_ids = list(ego_ids or [])
    for vid in ([llm_ego_id] if llm_ego_id else []):
        if vid is not None and vid not in ego_ids:
            ego_ids.append(vid)
    metrics = compute_metrics(sim, config, ego_ids=ego_ids or None)

    # Traceability: every row records the exact code/prompt/demand version
    # that produced it, so results can never be misattributed later.
    metrics["mode"] = mode
    metrics["experiment"] = experiment
    metrics["seed"] = seed
    metrics["llm_ego_id"] = llm_ego_id
    metrics["llm_fraction_requested"] = llm_fraction
    metrics["sim_version"] = SIM_VERSION
    metrics["metrics_version"] = METRICS_VERSION
    metrics["source_hashes"] = SOURCE_HASHES
    metrics["prompt_version"] = getattr(client, "PROMPT_VERSION", None)
    metrics["trigger_params"] = trigger_params
    metrics["arrival_schedule_hash"] = "%08x" % (
        zlib.crc32(
            ",".join(str(round(t, 2)) for t in sim.arrival_schedule).encode()
        )
    )

    if output_dir is not None:
        output_dir.mkdir(parents=True, exist_ok=True)
        plot_time_space_diagram(
            sim,
            config,
            output=output_dir / f"exp{experiment}_{mode}_seed{seed}.png",
            show=False,
        )
        # Readable view: fewer, thinner trajectories so that individual
        # vehicle paths and stop-and-go waves stay visible. Saved next to
        # the macroscopic view so both can be compared in the report.
        if plot_stride > 1:
            plot_time_space_diagram(
                sim,
                config,
                output=output_dir / f"exp{experiment}_{mode}_seed{seed}_readable.png",
                show=False,
                vehicle_stride=plot_stride,
                line_width=plot_line_width,
            )
        # Save planner decisions only for the ego vehicle(s). Writing one
        # file per LLM vehicle means ~589 files per full-fleet run, which
        # made the 96-run batch produce ~19k files and stall. Aggregated
        # counts live in the metrics JSON; the raw reason strings of the
        # tracked ego are all the report needs.
        if save_decisions:
            for vehicle in sim.vehicles:
                if vehicle.id not in ego_ids:
                    continue
                if hasattr(vehicle, "decision_log") and vehicle.decision_log:
                    log_path = output_dir / (
                        f"exp{experiment}_{mode}_seed{seed}_v{vehicle.id}_decisions.json"
                    )
                    log_path.write_text(
                        json.dumps(vehicle.decision_log, indent=2, ensure_ascii=False),
                        encoding="utf-8",
                    )
                # Execution trace: what the executor actually applied, so the
                # report can separate model output from executor overrides.
                if getattr(vehicle, "execution_trace", None):
                    trace_path = output_dir / (
                        f"exp{experiment}_{mode}_seed{seed}_v{vehicle.id}_execution.json"
                    )
                    trace_path.write_text(
                        json.dumps(vehicle.execution_trace, indent=2,
                                   ensure_ascii=False),
                        encoding="utf-8",
                    )
    return metrics


def main():
    parser = argparse.ArgumentParser(
        description="Compare IDM baseline and LLM-controlled runs."
    )
    parser.add_argument("--experiment", type=int, nargs="+", default=[1])
    parser.add_argument("--seed", type=int, nargs="+", default=[1])
    parser.add_argument("--time-max", type=float, default=Config.DEFAULT_TIME_MAX)
    parser.add_argument(
        "--modes", nargs="+", default=["idm", "llm_mock"],
        choices=list(MODES),
    )
    parser.add_argument("--llm-model", default=None)
    parser.add_argument(
        "--llm-ego-id", type=int, default=None,
        help="If set, only this vehicle id is LLM-controlled (mixed traffic).",
    )
    parser.add_argument(
        "--llm-fraction", type=float, default=None,
        help="If set (e.g. 0.2), every Nth vehicle is LLM-controlled.",
    )
    parser.add_argument(
        "--plot-stride", type=int, default=1,
        help="Also save a readable diagram drawing every Nth vehicle.",
    )
    parser.add_argument(
        "--plot-line-width", type=float, default=0.7,
        help="Line width for the readable diagram.",
    )
    parser.add_argument(
        "--ego-ids", type=int, nargs="+", default=[60],
        help="Vehicle ids tracked individually in every mode (default: 60).",
    )
    parser.add_argument(
        "--no-decisions", dest="save_decisions", action="store_false",
        help="Skip writing per-vehicle planner decision logs.",
    )
    parser.add_argument(
        "--output-dir", type=Path, default=Path("results/comparison"),
    )
    parser.add_argument(
        "--no-plots", action="store_true",
        help="Metrics only (skips time-space diagrams and decision logs).",
    )
    parser.add_argument(
        "--trigger-profile", choices=["qwen"], default=None,
        help="Force the real-API trigger spacing offline (call estimation).",
    )
    parser.add_argument(
        "--json-output", type=Path, default=Path("results/comparison/metrics.json"),
    )
    args = parser.parse_args()

    rows = []
    for experiment in args.experiment:
        for seed in args.seed:
            for mode in args.modes:
                print(f"running: exp={experiment} seed={seed} mode={mode}")
                rows.append(
                    run_one(
                        mode, experiment, seed,
                        time_max=args.time_max,
                        llm_model=args.llm_model,
                        output_dir=None if args.no_plots else args.output_dir,
                        llm_ego_id=args.llm_ego_id,
                        llm_fraction=args.llm_fraction,
                        plot_stride=args.plot_stride,
                        plot_line_width=args.plot_line_width,
                        save_decisions=args.save_decisions,
                        ego_ids=args.ego_ids,
                        trigger_profile=args.trigger_profile,
                    )
                )

    print()
    print(format_table(rows, METRIC_COLUMNS))

    args.json_output.parent.mkdir(parents=True, exist_ok=True)
    args.json_output.write_text(
        json.dumps(rows, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    print(f"\nmetrics saved to: {args.json_output}")


if __name__ == "__main__":
    main()
