from __future__ import annotations

import asyncio
import json
import sys
from pathlib import Path

from fastmcp import FastMCP

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from server.fitness import score_path
from server.multiverse import REPO_ROOT, RUNS_DIR, cleanup, create_timelines, launch_workers
from server.postmortem import generate_postmortem
from server.showcase import launch_showcase, save_result, save_scoreboard


mcp = FastMCP(
    "Everett",
    instructions=(
        "Everett exposes fork/judge/collapse tools over parallel git worktrees. "
        "Use fork to create timelines, judge to score them, and collapse to keep the winner."
    ),
)

_worker_tasks: dict[str, asyncio.Task] = {}


@mcp.tool
async def fork(strategies: list[str]) -> dict:
    """Create Everett timelines and launch headless workers."""
    state = create_timelines(strategies)
    _worker_tasks[state["run_id"]] = asyncio.create_task(
        launch_workers(state["timelines"])
    )
    return state


@mcp.tool
async def judge(run_id: str) -> dict:
    """Score every timeline for a run."""
    task = _worker_tasks.get(run_id)
    if task is not None:
        # A client-side MCP timeout cancels this tool call; it must not cancel
        # the shared worker task because a later judge retry can still finish it.
        await asyncio.shield(task)

    state = _load_state(run_id)
    scoreboard = []

    for timeline in state["timelines"]:
        scores = score_path(REPO_ROOT / timeline["worktree"])
        scoreboard.append({"timeline": timeline["id"], **scores})

    save_scoreboard(state, scoreboard)
    return {"scoreboard": scoreboard}


@mcp.tool
def collapse(run_id: str, winner: str) -> dict:
    """Point everett/result at the winning timeline branch."""
    task = _worker_tasks.get(run_id)
    if task is not None and not task.done():
        raise RuntimeError("Workers are still running; call judge before collapse")

    state = _load_state(run_id)
    timeline = _find_timeline(state, winner)
    _run_git("branch", "-f", "everett/result", timeline["branch"])
    postmortem = generate_postmortem(run_id, winner, state)
    save_result(state, winner, postmortem)
    cleanup(run_id)
    return {"result_branch": "everett/result", "postmortem": postmortem}


@mcp.tool
def showcase() -> dict:
    """Open the live 3D Everett multiverse companion for the current run."""
    url = launch_showcase()
    return {
        "url": url,
        "message": "Opened the Everett 3D showcase. It updates as fork, judge, and collapse run.",
    }


def _load_state(run_id: str) -> dict:
    state_path = RUNS_DIR / run_id / "state.json"
    if not state_path.exists():
        raise FileNotFoundError(f"No state found for run_id {run_id!r}")
    return json.loads(state_path.read_text())


def _find_timeline(state: dict, winner: str) -> dict:
    for timeline in state["timelines"]:
        if timeline["id"] == winner:
            return timeline
    raise ValueError(f"Unknown winner {winner!r}")


def _run_git(*args: str) -> None:
    import subprocess

    subprocess.run(["git", *args], cwd=REPO_ROOT, check=True)


if __name__ == "__main__":
    mcp.run(transport="stdio", show_banner=False)
