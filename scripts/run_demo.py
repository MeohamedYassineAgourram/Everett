#!/usr/bin/env python3
"""Run Everett's projector-friendly fork, judge, and collapse demonstration."""

from __future__ import annotations

import argparse
import asyncio
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from rich.console import Console, Group
from rich.live import Live
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

from server.fitness import score_path
from server.mcp_server import collapse
from server.multiverse import REPO_ROOT, RUNS_DIR, cleanup, create_timelines, launch_workers


TIMELINES = (
    (
        "Cache",
        "Add an in-memory response cache for demo/slowapi /report. Preserve correctness, run the demo tests, and commit the result.",
    ),
    (
        "Query rewrite",
        "Rewrite demo/slowapi /report to eliminate the N+1 SQLite query pattern. Preserve correctness, run the demo tests, and commit the result.",
    ),
    (
        "Precompute",
        "Precompute a report summary for demo/slowapi /report. Preserve correctness, run the demo tests, and commit the result.",
    ),
)

FAKE_WORKER = """
import pathlib
import subprocess
import sys

worktree = pathlib.Path(sys.argv[1])
marker = worktree / f"demo-{worktree.name}.txt"
marker.write_text("Everett demo worker completed.\\n")
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
        f"Everett demo {worktree.name}",
    ],
    cwd=worktree,
    check=True,
)
"""


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--fast",
        action="store_true",
        help="Use local deterministic workers instead of Codex workers.",
    )
    return parser.parse_args()


async def main() -> int:
    args = parse_args()
    console = Console()
    console.print()
    console.print(
        Panel.fit(
            "[bold cyan]EVERETT[/]\n[dim]Fork reality. Judge the futures. Keep the one that works.[/]",
            border_style="cyan",
        )
    )

    console.print("\n[bold cyan]BASELINE[/] Measuring the slow endpoint...")
    baseline = score_path(REPO_ROOT)
    console.print(
        f"[dim]Current report p50:[/] [bold]{baseline['p50_ms']:.1f} ms[/]\n"
    )

    state = create_timelines([strategy for _, strategy in TIMELINES])
    run_id = state["run_id"]
    (RUNS_DIR / ".active-demo-run").write_text(run_id + "\n")
    console.print(
        f"[bold cyan]FORK[/] Created run [bold]{run_id}[/] with three independent realities."
    )
    console.print("[dim]The adjacent panes are the three Codex workers.\n[/]")

    worker_command = [sys.executable, "-c", FAKE_WORKER] if args.fast else None
    timeout_seconds = 30 if args.fast else 240
    workers = asyncio.create_task(
        launch_workers(
            state["timelines"],
            worker_command=worker_command,
            timeout_seconds=timeout_seconds,
        )
    )

    try:
        with Live(
            worker_dashboard(state["timelines"], run_id, args.fast),
            console=console,
            refresh_per_second=4,
        ) as live:
            while not workers.done():
                await asyncio.sleep(0.25)
                live.update(worker_dashboard(load_timelines(run_id), run_id, args.fast))
            timelines = await workers
            live.update(worker_dashboard(timelines, run_id, args.fast, complete=True))

        console.print("\n[bold cyan]JUDGE[/] Running the fitness harness across every timeline...")
        scoreboard = [
            {"timeline": timeline["id"], **score_path(REPO_ROOT / timeline["worktree"])}
            for timeline in timelines
        ]
        passing = [entry for entry in scoreboard if entry["tests_passed"]]
        if not passing:
            console.print("[bold red]No timeline passed. Runtime state has been kept for inspection.[/]")
            return 1

        winner = max(passing, key=lambda entry: entry["score"])["timeline"]
        console.print(scoreboard_table(scoreboard, winner))
        console.print(f"\n[bold cyan]COLLAPSE[/] Keeping timeline [bold green]{winner}[/].")
        result = collapse(run_id, winner)
        verify_result_branch()
        console.print(
            Panel.fit(
                f"[bold green]WINNER: TIMELINE {winner}[/]\n"
                "Result branch: [bold]everett/result[/]\n"
                "The other futures have been distilled into lessons.",
                title="Wavefunction collapsed",
                border_style="green",
            )
        )
        console.print(roads_not_taken(result["postmortem"]))
        console.print(
            "\n[dim]Demo complete. Inspect everett/result, then run scripts/reset_demo.sh before another take.[/]"
        )
        return 0
    except Exception:
        if (RUNS_DIR / run_id).exists():
            cleanup(run_id)
        raise


def load_timelines(run_id: str) -> list[dict]:
    import json

    state_path = RUNS_DIR / run_id / "state.json"
    return json.loads(state_path.read_text())["timelines"]


def worker_dashboard(
    timelines: list[dict], run_id: str, fast: bool, *, complete: bool = False
) -> Panel:
    table = Table(show_header=True, header_style="bold cyan", expand=True)
    table.add_column("Timeline", style="bold cyan", width=10)
    table.add_column("Strategy")
    table.add_column("Status", justify="right", width=12)

    for index, timeline in enumerate(timelines):
        status = timeline["status"].upper()
        style = {
            "RUNNING": "yellow",
            "SUCCEEDED": "green",
            "FAILED": "red",
            "TIMEOUT": "red",
        }.get(status, "white")
        table.add_row(timeline["id"], TIMELINES[index][0], f"[{style}]{status}[/{style}]")

    state = "COMPLETE" if complete else "EXPLORING"
    mode = "FAST LOCAL" if fast else "LIVE CODEX"
    footer = Text(f"{state}  |  {mode}  |  RUN {run_id}", style="dim")
    return Panel(Group(table, footer), title="Parallel timelines", border_style="cyan")


def scoreboard_table(scoreboard: list[dict], winner: str) -> Table:
    table = Table(title="Fitness scoreboard", header_style="bold cyan", expand=True)
    table.add_column("Timeline", style="bold cyan")
    table.add_column("Tests")
    table.add_column("p50", justify="right")
    table.add_column("Speedup", justify="right")
    table.add_column("Diff", justify="right")
    table.add_column("Score", justify="right")

    for entry in scoreboard:
        is_winner = entry["timeline"] == winner
        style = "bold green" if is_winner else ""
        label = f"{entry['timeline']}  WINNER" if is_winner else entry["timeline"]
        table.add_row(
            label,
            "PASS" if entry["tests_passed"] else "FAIL",
            f"{entry['p50_ms']:.1f} ms",
            f"{entry['speedup']:.2f}x",
            str(entry["diff_lines"]),
            f"{entry['score']:.2f}",
            style=style,
        )
    return table


def roads_not_taken(postmortem: str) -> Panel:
    lines = [
        line
        for line in postmortem.splitlines()
        if line.startswith("- Timeline ") and " explored " in line
    ]
    lessons = "\n".join(lines) or "No losing timelines to summarize."
    return Panel(lessons, title="Roads not taken", border_style="yellow")


def verify_result_branch() -> None:
    result = subprocess.run(
        ["git", "show-ref", "--verify", "--quiet", "refs/heads/everett/result"],
        cwd=REPO_ROOT,
        check=False,
    )
    if result.returncode != 0:
        raise RuntimeError("collapse did not create everett/result")


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
