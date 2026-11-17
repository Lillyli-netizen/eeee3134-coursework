# -*- coding: utf-8 -*-
"""Small-scale REAL Qwen experiment driver (single ego id 60, rest IDM).

Runs the two-layer controller with the real DashScope-backed client through
run_comparison.run_one, with a hard global call budget. When the budget is
exceeded the run raises RuntimeError("QWEN_CALL_BUDGET_EXCEEDED") and stops —
no silent degradation, no retries.

The API key is read from DASHSCOPE_API_KEY by llm_client itself; this driver
never touches, prints or stores it.

Usage:
    python run_qwen_real.py --experiments 1 --seeds 1 --budget 25     # pilot
    python run_qwen_real.py --experiments 1 2 3 4 --seeds 1 2 --budget 250
"""

import argparse
import json
import time
from pathlib import Path

import llm_client
from run_comparison import run_one

# --- global budget enforcement -------------------------------------------------
class QwenCallBudgetExceeded(BaseException):
    """Hard stop when the API call budget is reached.

    Deliberately a BaseException, not Exception: vehicle_llm wraps planner
    calls in ``except Exception`` (fail-operational), and a normal exception
    raised by the budget check would be swallowed there and the run would
    continue silently past its budget.
    """


STATE = {"calls": 0, "failures": 0, "latency": 0.0, "budget": None, "clients": []}

_orig_init = llm_client.QwenLLMClient.__init__
_orig_decide = llm_client.QwenLLMClient.decide


def _init(self, *a, **kw):
    _orig_init(self, *a, **kw)
    STATE["clients"].append(self)


def _decide(self, observation):
    if STATE["budget"] is not None and STATE["calls"] >= STATE["budget"]:
        raise QwenCallBudgetExceeded(
            "QWEN_CALL_BUDGET_EXCEEDED: %d calls reached (budget %d). "
            "Stopping as instructed; no retry." % (STATE["calls"], STATE["budget"])
        )
    out = _orig_decide(self, observation)
    STATE["calls"] += 1
    STATE["failures"] = sum(c.failures for c in STATE["clients"])
    STATE["latency"] = sum(c.total_latency for c in STATE["clients"])
    return out


llm_client.QwenLLMClient.__init__ = _init
llm_client.QwenLLMClient.decide = _decide


def _write_outputs(out_dir, budget, rows, run_log, stopped_early):
    """Write metrics and the run log, including on an early budget stop."""
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "metrics.json").write_text(
        json.dumps(rows, indent=2, ensure_ascii=False), encoding="utf-8")
    summary = {
        "budget": budget,
        "stopped_early": stopped_early,
        "total_api_calls": STATE["calls"],
        "total_api_failures": STATE["failures"],
        # Success-only latency: failed calls raise before total_latency grows.
        # Per-call latencies (including 10 s timeouts) are in the decisions
        # logs; summarize_qwen_real.py reports both scopes.
        "total_api_latency_s": round(STATE["latency"], 1),
        "mean_latency_s": round(STATE["latency"] / max(1, STATE["calls"]), 2),
        "runs": run_log,
        "note": ("Synchronous client: the Python process blocks during each "
                 "call but simulation time does not advance. Results describe a "
                 "zero-latency planner; real communication delay is NOT tested."),
    }
    (out_dir / "qwen_run_log.json").write_text(
        json.dumps(summary, indent=2, ensure_ascii=False), encoding="utf-8")
    return summary


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--experiments", type=int, nargs="+", default=[1])
    ap.add_argument("--seeds", type=int, nargs="+", default=[1])
    ap.add_argument("--budget", type=int, default=250,
                    help="Hard cap on total API calls; exceeding it aborts.")
    ap.add_argument("--time-max", type=float, default=1000.0)
    ap.add_argument("--out", type=Path, default=Path("results/qwen_real"))
    args = ap.parse_args()

    STATE["budget"] = args.budget
    args.out.mkdir(parents=True, exist_ok=True)

    rows = []
    run_log = []
    try:
        for exp in args.experiments:
            for seed in args.seeds:
                for mode in ("idm", "llm_qwen"):
                    t0 = time.time()
                    print(f"running: exp={exp} seed={seed} mode={mode}", flush=True)
                    m = run_one(
                        mode, exp, seed, time_max=args.time_max,
                        output_dir=args.out / f"exp{exp}",
                        llm_ego_id=60 if mode == "llm_qwen" else None,
                        ego_ids=[60], plot_stride=5, save_decisions=True,
                    )
                    rows.append(m)
                    if mode == "llm_qwen":
                        run_log.append({
                            "experiment": exp, "seed": seed,
                            "api_calls_cumulative": STATE["calls"],
                            "api_failures_cumulative": STATE["failures"],
                            "wall_seconds": round(time.time() - t0, 1),
                            "model": m.get("llm_models"),
                            "prompt_version": m.get("prompt_version"),
                        })
    except QwenCallBudgetExceeded as exc:
        # Budget reached: keep whatever completed, then stop loudly.
        _write_outputs(args.out, args.budget, rows, run_log, stopped_early=True)
        print("\nSTOPPED:", exc)
        print("partial results saved to", args.out)
        raise SystemExit(3)

    summary = _write_outputs(args.out, args.budget, rows, run_log,
                             stopped_early=False)
    print("\nAPI calls used: %d / %d (failures: %d, mean latency %.2fs)" % (
        STATE["calls"], args.budget, STATE["failures"],
        summary["mean_latency_s"]))
    print("metrics:", args.out / "metrics.json")


if __name__ == "__main__":
    main()
