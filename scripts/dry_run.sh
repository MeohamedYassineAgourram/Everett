#!/usr/bin/env bash
set -euo pipefail

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$repo_root"

mode="${1:---fake-workers}"
case "$mode" in
  --fake-workers) ;;
  --real-workers) ;;
  *)
    echo "usage: scripts/dry_run.sh [--fake-workers|--real-workers]" >&2
    exit 2
    ;;
esac

"$repo_root/scripts/reset_demo.sh" >/dev/null

if [ ! -x "$repo_root/.venv/bin/python" ]; then
  echo "Expected .venv/bin/python. Run: uv venv --python 3.11 && uv pip install pytest fastapi uvicorn httpx rich fastmcp" >&2
  exit 1
fi

export EVERETT_DRY_RUN_MODE="$mode"
"$repo_root/.venv/bin/python" - <<'PY'
from __future__ import annotations

import asyncio
import json
import os
import subprocess
import sys
from pathlib import Path

from server.fitness import render_scoreboard, score_path
from server.mcp_server import collapse
from server.multiverse import REPO_ROOT, RUNS_DIR, cleanup, create_timelines, launch_workers


STRATEGIES = [
    "Add a tiny marker file for the caching strategy. Do not change app behavior.",
    "Add a tiny marker file for the query rewrite strategy. Do not change app behavior.",
    "Add a tiny marker file for the precompute strategy. Do not change app behavior.",
]

FAKE_WORKER = """
import pathlib
import subprocess
import sys

worktree = pathlib.Path(sys.argv[1])
prompt = sys.argv[2]
timeline_id = worktree.name
marker = worktree / f"dry-run-{timeline_id}.txt"
marker.write_text(prompt + "\\n")
subprocess.run(["git", "add", marker.name], cwd=worktree, check=True)
subprocess.run(
    [
        "git",
        "-c",
        "user.name=Everett Worker",
        "-c",
        "user.email=worker@example.com",
        "commit",
        "-m",
        f"dry run {timeline_id}",
    ],
    cwd=worktree,
    check=True,
)
"""


def main() -> int:
    mode = os.environ["EVERETT_DRY_RUN_MODE"]
    worker_command = None
    timeout_seconds = 360
    if mode == "--fake-workers":
        worker_command = [sys.executable, "-c", FAKE_WORKER]
        timeout_seconds = 30

    state = create_timelines(STRATEGIES)
    run_id = state["run_id"]

    try:
        timelines = asyncio.run(
            launch_workers(
                state["timelines"],
                worker_command=worker_command,
                timeout_seconds=timeout_seconds,
            )
        )
        scoreboard = []
        for timeline in timelines:
            scores = score_path(REPO_ROOT / timeline["worktree"])
            scoreboard.append({"timeline": timeline["id"], **scores})

        print(f"Everett dry run: {run_id}")
        print(_worker_summary(timelines))
        print(render_scoreboard(scoreboard))

        passing = [entry for entry in scoreboard if entry["tests_passed"]]
        if not passing:
            print("No passing timelines; leaving run state for inspection.", file=sys.stderr)
            return 1

        winner = max(passing, key=lambda entry: entry["score"])["timeline"]
        result = collapse(run_id, winner)
        print(f"Winner: {winner}")
        print(result["postmortem"])

        result_exists = subprocess.run(
            ["git", "branch", "--list", "everett/result"],
            cwd=REPO_ROOT,
            text=True,
            capture_output=True,
            check=True,
        ).stdout.strip()
        if not result_exists:
            raise RuntimeError("collapse did not create everett/result")

        print(json.dumps({"run_id": run_id, "winner": winner, **result}, indent=2))
        return 0
    except Exception:
        if (RUNS_DIR / run_id).exists():
            cleanup(run_id)
        raise


def _worker_summary(timelines: list[dict]) -> str:
    lines = ["Worker logs:"]
    for timeline in timelines:
        worktree = REPO_ROOT / timeline["worktree"]
        log_path = worktree / "worker.log"
        lines.append(
            f"- {timeline['id']} {timeline['status']}: "
            f"{log_path.relative_to(REPO_ROOT)}"
        )
        tail = _tail(log_path)
        if tail:
            lines.append(f"  tail: {tail}")
    return "\n".join(lines)


def _tail(path: Path, count: int = 2) -> str:
    if not path.exists():
        return ""
    lines = path.read_text(errors="replace").splitlines()
    return " / ".join(line.strip() for line in lines[-count:] if line.strip())


raise SystemExit(main())
PY
