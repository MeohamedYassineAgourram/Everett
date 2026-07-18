#!/usr/bin/env bash
set -euo pipefail

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$repo_root"

mode="--fake-workers"
verbose="false"
for argument in "$@"; do
  case "$argument" in
    --fake-workers|--real-workers) mode="$argument" ;;
    --verbose) verbose="true" ;;
    *)
      echo "usage: scripts/dry_run.sh [--fake-workers|--real-workers] [--verbose]" >&2
      exit 2
      ;;
  esac
done

"$repo_root/scripts/reset_demo.sh" >/dev/null

if [ ! -x "$repo_root/.venv/bin/python" ]; then
  echo "Expected .venv/bin/python. Run: uv venv --python 3.11 && uv pip install pytest fastapi uvicorn httpx rich fastmcp" >&2
  exit 1
fi

export EVERETT_DRY_RUN_MODE="$mode"
export EVERETT_DRY_RUN_VERBOSE="$verbose"
"$repo_root/.venv/bin/python" - <<'PY'
from __future__ import annotations

import asyncio
import json
import os
import subprocess
import sys
from pathlib import Path

from server.fitness import score_path
from server.mcp_server import collapse
from server.multiverse import REPO_ROOT, RUNS_DIR, cleanup, create_timelines, launch_workers


STRATEGIES = [
    "Add a tiny marker file for the caching strategy. Do not change app behavior.",
    "Add a tiny marker file for the query rewrite strategy. Do not change app behavior.",
    "Add a tiny marker file for the precompute strategy. Do not change app behavior.",
]
TIMELINE_NAMES = ("Cache", "Query rewrite", "Precompute")

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
    verbose = os.environ["EVERETT_DRY_RUN_VERBOSE"] == "true"
    worker_command = None
    timeout_seconds = 240
    if mode == "--fake-workers":
        worker_command = [sys.executable, "-c", FAKE_WORKER]
        timeout_seconds = 30

    ui = RehearsalUI(mode, verbose)
    ui.header()
    ui.phase("1/4", "Forking three timelines")
    state = create_timelines(STRATEGIES)
    run_id = state["run_id"]
    ui.run_id(run_id)

    try:
        ui.phase("2/4", "Workers are exploring in parallel")
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

        passing = [entry for entry in scoreboard if entry["tests_passed"]]
        if not passing:
            ui.workers(timelines)
            ui.failure("No timeline passed its tests. Run again with --verbose to inspect logs.")
            return 1

        winner = max(passing, key=lambda entry: entry["score"])["timeline"]
        ui.workers(timelines)
        ui.phase("3/4", "Judging timelines")
        ui.scoreboard(scoreboard, winner)

        ui.phase("4/4", f"Collapsing to timeline {winner}")
        result = collapse(run_id, winner)

        result_exists = subprocess.run(
            ["git", "branch", "--list", "everett/result"],
            cwd=REPO_ROOT,
            text=True,
            capture_output=True,
            check=True,
        ).stdout.strip()
        if not result_exists:
            raise RuntimeError("collapse did not create everett/result")

        ui.result(run_id, winner, timelines)
        if verbose:
            ui.details(result["postmortem"])
        return 0
    except Exception:
        if (RUNS_DIR / run_id).exists():
            cleanup(run_id)
        raise


class RehearsalUI:
    def __init__(self, mode: str, verbose: bool) -> None:
        self.mode = mode
        self.verbose = verbose
        try:
            from rich.console import Console

            self.console = Console()
        except ImportError:
            self.console = None

    def header(self) -> None:
        label = "LIVE CODEX WORKERS" if self.mode == "--real-workers" else "FAST LOCAL REHEARSAL"
        self._print(f"\nEVERETT  |  {label}", "bold cyan")
        self._print("Fork. Judge. Collapse.\n", "dim")

    def phase(self, number: str, label: str) -> None:
        self._print(f"[{number}] {label}", "bold cyan")

    def run_id(self, run_id: str) -> None:
        self._print(f"Run {run_id} created.\n", "dim")

    def workers(self, timelines: list[dict]) -> None:
        rows = [
            (timeline["id"], TIMELINE_NAMES[index], timeline["status"].upper())
            for index, timeline in enumerate(timelines)
        ]
        if self.console is None:
            print("\nWORKERS")
            for timeline_id, name, status in rows:
                print(f"  {timeline_id}  {name:<14} {status}")
            return

        from rich.table import Table

        table = Table(title="Workers", show_edge=False, pad_edge=False)
        table.add_column("Timeline", style="bold cyan")
        table.add_column("Strategy")
        table.add_column("Status", justify="right")
        for timeline_id, name, status in rows:
            style = "green" if status == "SUCCEEDED" else "red"
            table.add_row(timeline_id, name, f"[{style}]{status}[/{style}]")
        self.console.print(table)

    def scoreboard(self, scoreboard: list[dict], winner: str) -> None:
        if self.console is None:
            print("\nSCOREBOARD")
            for entry in scoreboard:
                mark = "WINNER" if entry["timeline"] == winner else ""
                print(
                    f"  {entry['timeline']}  {entry['speedup']:.2f}x  "
                    f"{entry['p50_ms']:.1f} ms  score {entry['score']:.2f} {mark}"
                )
            return

        from rich.table import Table

        table = Table(title="Scoreboard", show_edge=False, pad_edge=False)
        table.add_column("Timeline", style="bold cyan")
        table.add_column("Tests")
        table.add_column("p50", justify="right")
        table.add_column("Speedup", justify="right")
        table.add_column("Diff", justify="right")
        table.add_column("Score", justify="right")
        for entry in scoreboard:
            is_winner = entry["timeline"] == winner
            style = "bold green" if is_winner else ""
            label = "WINNER" if is_winner else ""
            table.add_row(
                f"{entry['timeline']} {label}".rstrip(),
                "PASS" if entry["tests_passed"] else "FAIL",
                f"{entry['p50_ms']:.1f} ms",
                f"{entry['speedup']:.2f}x",
                str(entry["diff_lines"]),
                f"{entry['score']:.2f}",
                style=style,
            )
        self.console.print(table)

    def result(self, run_id: str, winner: str, timelines: list[dict]) -> None:
        winner_timeline = next(timeline for timeline in timelines if timeline["id"] == winner)
        message = (
            f"WINNER  {winner} - {TIMELINE_NAMES[ord(winner) - ord('A')]}\n"
            "Result branch  everett/result\n"
            f"Kept strategy  {winner_timeline['strategy']}"
        )
        if self.console is None:
            print(f"\n{message}\n")
            return

        from rich.panel import Panel

        self.console.print(Panel.fit(message, title="Collapse complete", border_style="green"))
        self._print("\nUse scripts/reset_demo.sh before the next rehearsal.\n", "dim")

    def details(self, postmortem: str) -> None:
        self._print("\nDETAILS", "bold yellow")
        self._print(postmortem, "dim")

    def failure(self, message: str) -> None:
        self._print(message, "bold red")

    def _print(self, message: str, style: str = "") -> None:
        if self.console is None:
            print(message)
        else:
            self.console.print(message, style=style)


raise SystemExit(main())
PY
