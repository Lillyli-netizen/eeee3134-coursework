# MANIFEST (fair_v3)

## Version stamps (recorded in every result row)

- sim_version: `3.0-fair-sim`
- metrics_version: `3.0-metrics-v4`
- runs: 96 (4 experiments x 8 seeds x 3 controllers)

## Environment

- Python: 3.12.7 (Windows-11-10.0.26200-SP0)
- numpy: 1.26.4
- matplotlib: 3.9.2

## Source hashes (SHA-256, full 64 hex)

These are re-hashed from the files as they exist in this package. The first 16 hex of the same files are embedded in every result row (`source_hashes`), so a row can be matched to its code without trusting a version label.

| File | SHA-256 | in-row prefix |
|---|---|---|
| config.py | cfd58542cc7be02292ce778fbd8454375d09fc0851accdfb279f6006137bed48 | cfd58542cc7be022 |
| vehicle.py | ce2ea52885754d5f543828f19113444fcc1320f1e9300b5c2e41d91b8f640a3e | ce2ea52885754d5f |
| vehicle_idm.py | 392628fcf57a951a117ac2e233ad95dbd84aa6ce3dd56bf8088c601908900a51 | 392628fcf57a951a |
| noise.py | e0708f79dbd68802b88238c8f55220d4e0d5e1f410545fb2ddec7a2cce0d4973 | e0708f79dbd68802 |
| simulator.py | 478cb435a8837eb9ea0131b97c6427f98ed444aab37c900e7bd0b1b164524c63 | 478cb435a8837eb9 |
| metrics.py | 7d025750fed1fa9d4813c44c23837b12b36aedf42e757631395fe1e72a420d3f | 7d025750fed1fa9d |
| vehicle_llm.py | 1fd110316f069a68696a053634e298995d46f3e2dab334e4af06394919bacde2 | 1fd110316f069a68 |
| vehicle_llm_direct.py | f080c783d59821ac3817720b15c78bec96dbd78b964436ee1c0ec210595a9228 | f080c783d59821ac |
| llm_client.py | 256a87ec2b6e57b59542744570892065d554af50392cf5a1fa62343cb22cd74e | 256a87ec2b6e57b5 |
| plotting.py | 1c682b58b61dacb4ded757d7dd43c81df971612a07ae60bc773672531952dd5c | — |
| run_comparison.py | 353ed68939a4f1060ca9d1199801f9b493a2dc8d6fb9d944f8bdbbe661e13d23 | 353ed68939a4f106 |
| test_fixes.py | f0825fd439f8bc6396d20d773bdf4f079a664eced08f55de851dcff5069397fa | — |
| diagnose_entry.py | a7afa0483686b99ab6154c24238777d47a9b1aa779832addf5e2117309ff9b76 | — |
| analyze_paired.py | 77b2e85fcba6112e2095ecef7791cec612d7f6c71c511a342a126152597d61cd | — |
| summarize_results.py | de13880e4d520497b53a7ef80c75c559ccbb604e81a74579b699a0399507a384 | — |
| make_manifest.py | 443205ea921bc9b89622ecf60c2932adf5c1aa8a89a755fb54a720ff4836c8ec | — |
| make_report_figures.py | c3bc1713134420e2d19ae31c68eecdef7d13468febc59f38acce2d17ab37da64 | — |
| make_qwen_figure.py | 6cf7ee58c4a04ba00ab474bc3403d75922a43a089aeba387d57b5012d0a8184d | — |
| run_qwen_real.py | 2afc647bb563010d6bd20911035af208b9634163916111a3774508e61e5708f4 | — |
| summarize_qwen_real.py | e1e5dfce813e09b8b687edbf91b98b85db13e18150d44933c20fa3ee25f6f60e | — |
| README.md | ed89e952215ba937847e47b863a973ef5a4ca1079f53818d6037e302335b491e | — |
| requirements.txt | 0e1b11c39b5a5b52f0ae1c9d178730a9dbc30d6a858284b116ad39d80ffa6c4e | — |

## Result file hashes

| File | SHA-256 | rows |
|---|---|---|
| fair_v3/exp1/metrics.json | cd0fc3bca8f766fa6dfb24183285dc2fcc53c6668fba3bfc015a30c3d8015f6e | 24 |
| fair_v3/exp2/metrics.json | a21ba5e2b0f271c62a86acc8fe5dc617e3730c6cef4b8deb99463bf313322408 | 24 |
| fair_v3/exp3/metrics.json | a8ff9b21e886c0a65417918c4cd94d09213b89c5601293b544a7d0eb75334d5f | 24 |
| fair_v3/exp4/metrics.json | aa402e5f87444dd7fb50a845f5b1e2558ee8817bc4917181bfe17f155c12d6cc | 24 |

## Real-model dataset (`results/qwen_real`)

Vehicle 60 driven by the real DashScope model, all other vehicles IDM; the arrival schedule is shared with the fair_v3 dataset.

- runs: 16 (4 experiments x 2 seeds x 2 controllers)
- model: `qwen-flash`
- prompt_version: `v2-tuned-2026-11`
- API calls: 189 (failures 4, budget 250)
- mean latency: 0.6 s, total blocking 113.7 s
- The client is synchronous: simulation time does not advance during a call, so these rows describe a zero-latency planner. Real communication delay is not tested.

| File | SHA-256 |
|---|---|
| results/qwen_real/metrics.json | 9ee6756a4d436b9809e29b4a5d9728ce777250cedcc4dc0b1d4c166b3970651c |
| results/qwen_real/qwen_run_log.json | c97c434a2224b68f64dfcb3367439a177c66ec629cffa79c766e961f4b5cc5d1 |


## Commands (run from the directory that contains these .py files)

The paths below assume the working copy, where `results/` sits next to the `.py` files. In the delivered package the code is in `code/` and the dataset in `../results/`, so run the same commands from `code/` with `results/...` replaced by `../results/...`.

```powershell
# 15 targeted checks (offline, < 2 min)
python test_fixes.py

# entry-backlog diagnostic (exp2, seed1, 0-100 s)
python diagnose_entry.py

# 96-run fair comparison, metrics only
foreach ($e in 1..4) {
  python run_comparison.py --experiment $e --seed 1 2 3 4 5 6 7 8 `
    --modes idm llm_mock llm_mock_noant --ego-ids 60 --no-plots `
    --json-output "results/fair_v3/exp$e/metrics.json"
}

# summary tables, paired analysis, this manifest
python summarize_results.py results/fair_v3
python analyze_paired.py results/fair_v3/exp2/metrics.json
python make_manifest.py results/fair_v3

# offline real-API call estimate (ego only, qwen trigger spacing)
python run_comparison.py --experiment 1 2 3 4 --seed 1 --modes llm_mock `
  --llm-ego-id 60 --ego-ids 60 --trigger-profile qwen --no-plots `
  --json-output results/qwen_estimate/metrics.json

# real model (key read from DASHSCOPE_API_KEY; never written to disk)
python run_qwen_real.py --experiments 1 --seeds 1 --budget 25
python run_qwen_real.py --experiments 1 2 3 4 --seeds 1 2 --budget 250
python summarize_qwen_real.py
python make_qwen_figure.py figures
```

## Data notes

- `fair_v3` is the dataset used by the report.
- Every row carries sim_version, metrics_version and source hashes.
- `statistics_invalid` / `valid_until_s` scope the pair and comfort statistics; `invalid_reason` says whether an overlap or an order crossing ended the interval.
- `results/qwen_real/` is the real-model dataset (189 calls, 4 timeouts); `results/qwen_estimate/` is the offline estimate and is not a measurement.
- `sample_decisions/` holds pre-fix, prompt-v1 historical logs. Do not mix their numbers with either dataset.
- `llm_api_calls` counts API calls in `qwen_real` rows and local planner invocations in mock rows.
- `figures/` contains report figures. `architecture.png` is drawn from the code structure; the time-space panels and the real-model chart are rendered from the datasets in this package.
