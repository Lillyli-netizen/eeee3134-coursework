"""Run one car-following experiment.

Extended for the LLM coursework: choose the vehicle model with --vehicle
and the planner client with --llm (mock runs fully offline).
"""

import argparse
from pathlib import Path

from config import Config
from plotting import plot_time_space_diagram
from simulator import Simulator
from vehicle_idm import IDMVehicle
from vehicle_llm import LLMVehicle
from llm_client import build_client


def main():
    parser = argparse.ArgumentParser(description="Run a car-following simulation.")
    parser.add_argument(
        "--experiment",
        type=int,
        choices=[1, 2, 3, 4],
        default=1,
    )
    parser.add_argument(
        "--time-max",
        type=float,
        default=Config.DEFAULT_TIME_MAX,
        help="Simulation duration in seconds.",
    )
    parser.add_argument(
        "--vehicle",
        choices=["idm", "llm"],
        default="idm",
        help="Vehicle model: plain IDM or two-layer LLM+IDM.",
    )
    parser.add_argument(
        "--llm",
        choices=["mock", "qwen"],
        default="mock",
        help="Planner client used when --vehicle llm (mock = offline rules).",
    )
    parser.add_argument("--llm-model", default=None, help="Model name for qwen.")
    parser.add_argument("--seed", type=int, default=1)
    parser.add_argument(
        "--decisions-output",
        type=Path,
        help="Write the LLM decision log of one vehicle to this JSON file.",
    )
    parser.add_argument("--output", type=Path)
    parser.add_argument("--no-show", action="store_true")
    args = parser.parse_args()

    config = Config(seed=args.seed, experiment=args.experiment, time_max=args.time_max)

    vehicle_class = IDMVehicle
    llm_client = None
    if args.vehicle == "llm":
        vehicle_class = LLMVehicle
        llm_client = build_client(args.llm, model=args.llm_model)

    simulator = Simulator(config, vehicle_class=vehicle_class, llm_client=llm_client)
    simulator.run()

    if args.vehicle == "llm" and args.decisions_output and simulator.vehicles:
        import json

        sample = max(simulator.vehicles, key=lambda v: len(v.decision_log))
        args.decisions_output.parent.mkdir(parents=True, exist_ok=True)
        args.decisions_output.write_text(
            json.dumps(sample.decision_log, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )
        print(f"Decision log saved to: {args.decisions_output}")

    if isinstance(llm_client, object) and args.vehicle == "llm":
        print(
            f"LLM planner: client={llm_client.name}, "
            f"calls={getattr(llm_client, 'calls', 'n/a')}, "
            f"failures={getattr(llm_client, 'failures', 'n/a')}"
        )

    plot_time_space_diagram(
        simulator,
        config,
        output=args.output,
        show=not args.no_show,
    )


if __name__ == "__main__":
    main()
