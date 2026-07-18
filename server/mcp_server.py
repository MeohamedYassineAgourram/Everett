from __future__ import annotations

import json
import sys
from pathlib import Path

from fastmcp import FastMCP

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from server.fitness import score_path
from server.multiverse import REPO_ROOT, RUNS_DIR, cleanup, create_timelines


mcp = FastMCP(
    "Everett",
    instructions=(
        "Everett exposes fork/judge/collapse tools over parallel git worktrees. "
        "Use fork to create timelines, judge to score them, and collapse to keep the winner."
    ),
)


@mcp.tool
def fork(strategies: list[str]) -> dict:
    """Create Everett timelines for up to three strategies."""
    return create_timelines(strategies[:3])


@mcp.tool
def judge(run_id: str) -> dict:
    """Score every timeline for a run."""
    state = _load_state(run_id)
    scoreboard = []

    for timeline in state["timelines"]:
        scores = score_path(REPO_ROOT / timeline["worktree"])
        scoreboard.append({"timeline": timeline["id"], **scores})

    return {"scoreboard": scoreboard}


@mcp.tool
def collapse(run_id: str, winner: str) -> dict:
    """Point everett/result at the winning timeline branch."""
    state = _load_state(run_id)
    timeline = _find_timeline(state, winner)
    _run_git("branch", "-f", "everett/result", timeline["branch"])
    cleanup(run_id)

    postmortem = (
        f"Collapsed run `{run_id}` to timeline `{timeline['id']}` "
        f"({timeline['strategy']}). Roads not taken will be distilled here."
    )
    return {"result_branch": "everett/result", "postmortem": postmortem}


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
