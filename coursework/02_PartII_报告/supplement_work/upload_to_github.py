"""Upload supplement figures, verification note, replay script and the
fixed code snapshot to study/part2-report/ via the GitHub contents API
(uses `gh api`; works around the flaky git TLS path)."""

import base64
import json
import subprocess
import sys
import time
from pathlib import Path
from urllib.parse import quote

ROOT = Path(__file__).resolve().parent
REPO = "Lillyli-netizen/study"
FIG_DIR = ROOT.parent / "补充图_20261110"
CODE_DIR = ROOT / "pack" / "code"

uploads = []
for name in ("fig_ego_highlight_E4S1.png", "fig_ttc_event_E2S1.png",
             "回放验证记录.md"):
    uploads.append((FIG_DIR / name, f"part2-report/supplement_20261110/{name}"))
uploads.append((ROOT / "make_supplement_figures.py",
                "part2-report/supplement_20261110/make_supplement_figures.py"))
for f in sorted(CODE_DIR.glob("*.py")) + [CODE_DIR / "README.md"]:
    uploads.append((f, f"part2-report/source_snapshot_fixed/{f.name}"))

ok, failed = 0, []
body_path = ROOT / "_upload_body.json"
for local, remote in uploads:
    if not local.exists():
        failed.append(remote)
        print("MISSING LOCAL:", local)
        continue
    body = {
        "message": "Add supplement figures, replay verification, "
                   "and fixed code snapshot",
        "content": base64.b64encode(local.read_bytes()).decode("ascii"),
        "branch": "main",
    }
    body_path.write_text(json.dumps(body), encoding="utf-8")
    url = f"repos/{REPO}/contents/{quote(remote)}"
    done = False
    err = ""
    for _ in range(3):
        r = subprocess.run(["gh", "api", url, "-X", "PUT", "--input",
                            str(body_path)], capture_output=True, text=True)
        if r.returncode == 0:
            done = True
            break
        err = r.stderr.strip()[:200]
        time.sleep(3)
    if done:
        ok += 1
        print("uploaded:", remote)
    else:
        failed.append(remote)
        print("FAILED:", remote, err)
if body_path.exists():
    body_path.unlink()
print(f"done: {ok} ok, {len(failed)} failed")
sys.exit(1 if failed else 0)
