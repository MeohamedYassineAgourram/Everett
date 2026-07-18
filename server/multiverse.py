from __future__ import annotations

import json
import shutil
import subprocess
import uuid
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
RUNS_DIR = REPO_ROOT / "runs"
BASE_BRANCH = "main"


def _run_git(*args: str, check: bool = True) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", *args],
        cwd=REPO_ROOT,
        check=check,
        text=True,
        capture_output=True,
    )


def _timeline_id(index: int) -> str:
    letters = []
    index += 1
    while index:
        index, remainder = divmod(index - 1, 26)
        letters.append(chr(ord("A") + remainder))
    return "".join(reversed(letters))


def _state_path(run_id: str) -> Path:
    return RUNS_DIR / run_id / "state.json"


def create_timelines(strategies: list[str]) -> dict:
    run_id = uuid.uuid4().hex[:8]
    run_dir = RUNS_DIR / run_id
    run_dir.mkdir(parents=True, exist_ok=False)

    timelines = []
    try:
        for index, strategy in enumerate(strategies):
            timeline_id = _timeline_id(index)
            branch = f"everett/{timeline_id}"
            worktree = f"runs/{run_id}/{timeline_id}"

            _run_git("worktree", "add", "-b", branch, worktree, BASE_BRANCH)
            timelines.append(
                {
                    "id": timeline_id,
                    "branch": branch,
                    "worktree": worktree,
                    "strategy": strategy,
                    "status": "running",
                }
            )
    except Exception:
        for timeline in reversed(timelines):
            _run_git("worktree", "remove", "--force", timeline["worktree"], check=False)
            _run_git("branch", "-D", timeline["branch"], check=False)
        _run_git("worktree", "prune", check=False)
        shutil.rmtree(run_dir, ignore_errors=True)
        raise

    state = {"run_id": run_id, "timelines": timelines}
    _state_path(run_id).write_text(json.dumps(state, indent=2) + "\n")
    return state


def cleanup(run_id: str) -> None:
    state_file = _state_path(run_id)
    if not state_file.exists():
        raise FileNotFoundError(f"No state found for run_id {run_id!r}")

    state = json.loads(state_file.read_text())
    for timeline in state.get("timelines", []):
        _run_git("worktree", "remove", "--force", timeline["worktree"], check=False)

    _run_git("worktree", "prune")

    for timeline in state.get("timelines", []):
        _run_git("branch", "-D", timeline["branch"], check=False)

    shutil.rmtree(RUNS_DIR / run_id, ignore_errors=True)

