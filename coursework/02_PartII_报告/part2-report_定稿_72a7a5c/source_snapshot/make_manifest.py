# -*- coding: utf-8 -*-
"""Write results/<dir>/MANIFEST.md (versions, hashes, commands).

Usage: python make_manifest.py [results/fair_v3]
"""
import hashlib
import json
import platform
import sys
from pathlib import Path

import matplotlib
import numpy

ROOT = Path(__file__).resolve().parent
BASE = ROOT / (sys.argv[1] if len(sys.argv) > 1 else "results/fair_v3")
FILES = [
    "config.py", "vehicle.py", "vehicle_idm.py", "noise.py", "simulator.py",
    "metrics.py", "vehicle_llm.py", "vehicle_llm_direct.py", "llm_client.py",
    "plotting.py", "run_comparison.py", "test_fixes.py", "diagnose_entry.py",
    "analyze_paired.py", "summarize_results.py", "make_manifest.py",
    "make_report_figures.py", "make_qwen_figure.py", "run_qwen_real.py",
    "summarize_qwen_real.py",
    "README.md", "requirements.txt",
]

rows = {}
for exp in [1, 2, 3, 4]:
    path = BASE / f"exp{exp}" / "metrics.json"
    rows[exp] = json.loads(path.read_text(encoding="utf-8"))
first = rows[1][0]

lines = [
    f"# MANIFEST ({BASE.name})",
    "",
    "## Version stamps (recorded in every result row)",
    "",
    f"- sim_version: `{first.get('sim_version')}`",
    f"- metrics_version: `{first.get('metrics_version')}`",
    f"- runs: {sum(len(v) for v in rows.values())} "
    f"(4 experiments x 8 seeds x 3 controllers)",
    "",
    "## Environment",
    "",
    f"- Python: {sys.version.split()[0]} ({platform.platform()})",
    f"- numpy: {numpy.__version__}",
    f"- matplotlib: {matplotlib.__version__}",
    "",
    "## Source hashes (SHA-256, full 64 hex)",
    "",
    "These are re-hashed from the files as they exist in this package. "
    "The first 16 hex of the same files are embedded in every result row "
    "(`source_hashes`), so a row can be matched to its code without trusting "
    "a version label.",
    "",
    "| File | SHA-256 | in-row prefix |",
    "|---|---|---|",
]
for name in FILES:
    digest = hashlib.sha256((ROOT / name).read_bytes()).hexdigest()
    lines.append(f"| {name} | {digest} | {first.get('source_hashes', {}).get(name, '—')} |")

lines += ["", "## Result file hashes", "", "| File | SHA-256 | rows |", "|---|---|---|"]
for exp in [1, 2, 3, 4]:
    path = BASE / f"exp{exp}" / "metrics.json"
    lines.append(
        f"| {BASE.name}/exp{exp}/metrics.json "
        f"| {hashlib.sha256(path.read_bytes()).hexdigest()} | {len(rows[exp])} |"
    )

lines += [
    "",
    "## Real-model dataset (`results/qwen_real`)",
    "",
    "Vehicle 60 driven by the real DashScope model, all other vehicles IDM; the "
    "arrival schedule is shared with the fair_v3 dataset.",
    "",
]
qwen_metrics = ROOT / "results/qwen_real/metrics.json"
qwen_log = ROOT / "results/qwen_real/qwen_run_log.json"
if qwen_metrics.exists() and qwen_log.exists():
    qrows = json.loads(qwen_metrics.read_text(encoding="utf-8"))
    qlog = json.loads(qwen_log.read_text(encoding="utf-8"))
    models = sorted({m for r in qrows for m in (r.get("llm_models") or [])})
    prompts = sorted({r.get("prompt_version") for r in qrows
                      if r.get("prompt_version")})
    lines += [
        f"- runs: {len(qrows)} (4 experiments x 2 seeds x 2 controllers)",
        f"- model: `{', '.join(models) or '—'}`",
        f"- prompt_version: `{', '.join(prompts) or '—'}`",
        f"- API calls: {qlog['total_api_calls']} "
        f"(failures {qlog['total_api_failures']}, budget {qlog['budget']})",
        f"- mean latency: {qlog['mean_latency_s']} s, "
        f"total blocking {qlog['total_api_latency_s']} s",
        "- The client is synchronous: simulation time does not advance during a "
        "call, so these rows describe a zero-latency planner. Real communication "
        "delay is not tested.",
        "",
        "| File | SHA-256 |",
        "|---|---|",
        f"| results/qwen_real/metrics.json | {hashlib.sha256(qwen_metrics.read_bytes()).hexdigest()} |",
        f"| results/qwen_real/qwen_run_log.json | {hashlib.sha256(qwen_log.read_bytes()).hexdigest()} |",
        "",
    ]
else:
    lines += ["_No real-model dataset found in this package._", ""]

lines += [
    "",
    "## Commands (run from the directory that contains these .py files)",
    "",
    "The paths below assume the working copy, where `results/` sits next to the "
    "`.py` files. In the delivered package the code is in `code/` and the dataset "
    "in `../results/`, so run the same commands from `code/` with `results/...` "
    "replaced by `../results/...`.",
    "",
    "```powershell",
    "# 15 targeted checks (offline, < 2 min)",
    "python test_fixes.py",
    "",
    "# entry-backlog diagnostic (exp2, seed1, 0-100 s)",
    "python diagnose_entry.py",
    "",
    "# 96-run fair comparison, metrics only",
    "foreach ($e in 1..4) {",
    "  python run_comparison.py --experiment $e --seed 1 2 3 4 5 6 7 8 `",
    "    --modes idm llm_mock llm_mock_noant --ego-ids 60 --no-plots `",
    "    --json-output \"results/fair_v3/exp$e/metrics.json\"",
    "}",
    "",
    "# summary tables, paired analysis, this manifest",
    "python summarize_results.py results/fair_v3",
    "python analyze_paired.py results/fair_v3/exp2/metrics.json",
    "python make_manifest.py results/fair_v3",
    "",
    "# offline real-API call estimate (ego only, qwen trigger spacing)",
    "python run_comparison.py --experiment 1 2 3 4 --seed 1 --modes llm_mock `",
    "  --llm-ego-id 60 --ego-ids 60 --trigger-profile qwen --no-plots `",
    "  --json-output results/qwen_estimate/metrics.json",
    "",
    "# real model (key read from DASHSCOPE_API_KEY; never written to disk)",
    "python run_qwen_real.py --experiments 1 --seeds 1 --budget 25",
    "python run_qwen_real.py --experiments 1 2 3 4 --seeds 1 2 --budget 250",
    "python summarize_qwen_real.py",
    "python make_qwen_figure.py figures",
    "```",
    "",
    "## Data notes",
    "",
    f"- `{BASE.name}` is the dataset used by the report.",
    "- Every row carries sim_version, metrics_version and source hashes.",
    "- `statistics_invalid` / `valid_until_s` scope the pair and comfort "
    "statistics; `invalid_reason` says whether an overlap or an order crossing "
    "ended the interval.",
    "- `results/qwen_real/` is the real-model dataset (189 calls, 4 timeouts); "
    "`results/qwen_estimate/` is the offline estimate and is not a measurement.",
    "- `sample_decisions/` holds pre-fix, prompt-v1 historical logs. Do not mix "
    "their numbers with either dataset.",
    "- `llm_api_calls` counts API calls in `qwen_real` rows and local planner "
    "invocations in mock rows.",
    "- `figures/` contains report figures. `architecture.png` is drawn from the "
    "code structure; the time-space panels and the real-model chart are rendered "
    "from the datasets in this package.",
    "",
]

out = BASE / "MANIFEST.md"
out.write_text("\n".join(lines), encoding="utf-8")
print("written:", out)
