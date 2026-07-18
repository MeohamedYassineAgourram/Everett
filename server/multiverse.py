from __future__ import annotations

import asyncio
import json
import os
import shutil
import subprocess
import time
import uuid
from pathlib import Path
from typing import Sequence


REPO_ROOT = Path(__file__).resolve().parents[1]
RUNS_DIR = REPO_ROOT / "runs"
BASE_BRANCH = "main"
# Codex's MCP client allows five minutes per tool call. Leave a full minute for
# judging and the response so a root session can still receive the scoreboard.
WORKER_TIMEOUT_SECONDS = 4 * 60
WORKER_SUFFIX = "Run `python -m pytest demo/slowapi`. Commit your changes when they pass."


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


def _load_state(run_id: str) -> dict:
    return json.loads(_state_path(run_id).read_text())


def _write_state(state: dict) -> None:
    state_path = _state_path(state["run_id"])
    tmp_path = state_path.with_suffix(".json.tmp")
    tmp_path.write_text(json.dumps(state, indent=2) + "\n")
    tmp_path.replace(state_path)


def _run_id_from_timelines(timelines: list[dict]) -> str:
    if not timelines:
        raise ValueError("Cannot launch workers without timelines")
    parts = Path(timelines[0]["worktree"]).parts
    if len(parts) < 2 or parts[0] != "runs":
        raise ValueError(f"Unexpected worktree path: {timelines[0]['worktree']!r}")
    return parts[1]


def _worker_prompt(strategy: str) -> str:
    return f"{strategy}\n\n{WORKER_SUFFIX}"


def _default_worker_command(worktree: Path, prompt: str) -> list[str]:
    codex_bin = os.environ.get("EVERETT_CODEX_BIN", "codex")
    return [
        codex_bin,
        "exec",
        "--cd",
        str(worktree),
        "--sandbox",
        "workspace-write",
        "--json",
        prompt,
    ]


def _worker_command(
    worktree: Path,
    prompt: str,
    worker_command: Sequence[str] | None,
) -> list[str]:
    if worker_command is None:
        return _default_worker_command(worktree, prompt)
    return [*worker_command, str(worktree), prompt]


async def launch_workers(
    timelines: list[dict],
    *,
    worker_command: Sequence[str] | None = None,
    timeout_seconds: int = WORKER_TIMEOUT_SECONDS,
) -> list[dict]:
    run_id = _run_id_from_timelines(timelines)
    state = _load_state(run_id)
    state_lock = asyncio.Lock()

    async def set_status(timeline_id: str, status: str) -> None:
        async with state_lock:
            for timeline in state["timelines"]:
                if timeline["id"] == timeline_id:
                    timeline["status"] = status
                    break
            _write_state(state)

    await asyncio.gather(
        *[
            _run_worker(timeline, set_status, worker_command, timeout_seconds)
            for timeline in timelines[:3]
        ]
    )
    return _load_state(run_id)["timelines"]


async def _run_worker(
    timeline: dict,
    set_status,
    worker_command: Sequence[str] | None,
    timeout_seconds: int,
) -> None:
    worktree = REPO_ROOT / timeline["worktree"]
    log_path = worktree / "worker.log"
    prompt = _worker_prompt(timeline["strategy"])
    command = _worker_command(worktree, prompt, worker_command)
    before_head = _git_head(worktree)

    await set_status(timeline["id"], "running")
    started_at = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())

    with log_path.open("w") as log:
        log.write(f"[everett] timeline={timeline['id']} started={started_at}\n")
        log.write(f"[everett] strategy={timeline['strategy']}\n")
        log.flush()

        try:
            process = await asyncio.create_subprocess_exec(
                *command,
                cwd=worktree,
                # The MCP server itself communicates over stdin. Workers must not
                # inherit that pipe or Codex will wait for more prompt input.
                stdin=asyncio.subprocess.DEVNULL,
                stdout=log,
                stderr=asyncio.subprocess.STDOUT,
                env=_worker_environment(),
            )
        except OSError as error:
            log.write(f"\n[everett] could not start worker: {error}\n")
            await set_status(timeline["id"], "failed")
            return

        try:
            returncode = await asyncio.wait_for(process.wait(), timeout_seconds)
        except asyncio.TimeoutError:
            process.kill()
            await process.wait()
            log.write(f"\n[everett] timeout after {timeout_seconds}s\n")
            await set_status(timeline["id"], "timeout")
            return

        after_head = _git_head(worktree)
        if returncode == 0 and after_head == before_head and _has_changes(worktree):
            _commit_worker_changes(worktree, timeline)
            after_head = _git_head(worktree)

        if returncode == 0 and after_head != before_head:
            status = "succeeded"
        elif returncode == 0:
            status = "failed"
            log.write("\n[everett] worker exited 0 but did not create a commit\n")
        else:
            status = "failed"

        log.write(f"\n[everett] exit_code={returncode} status={status}\n")
        await set_status(timeline["id"], status)


def _git_head(path: Path) -> str:
    result = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=path,
        check=True,
        text=True,
        capture_output=True,
    )
    return result.stdout.strip()


def _worker_environment() -> dict[str, str]:
    """Make the project virtual environment available inside each worktree."""
    environment = os.environ.copy()
    venv_bin = REPO_ROOT / ".venv" / "bin"
    if venv_bin.is_dir():
        environment["PATH"] = f"{venv_bin}{os.pathsep}{environment.get('PATH', '')}"
    return environment


def _has_changes(path: Path) -> bool:
    result = subprocess.run(
        ["git", "status", "--porcelain"],
        cwd=path,
        check=True,
        text=True,
        capture_output=True,
    )
    return bool(result.stdout.strip())


def _commit_worker_changes(path: Path, timeline: dict) -> None:
    subprocess.run(["git", "add", "-A"], cwd=path, check=True)
    subprocess.run(
        [
            "git",
            "-c",
            "user.name=Everett Worker",
            "-c",
            "user.email=worker@example.com",
            "commit",
            "-m",
            f"Everett {timeline['id']}: {timeline['strategy'][:60]}",
        ],
        cwd=path,
        check=True,
        text=True,
        capture_output=True,
    )


def create_timelines(strategies: list[str]) -> dict:
    if not 1 <= len(strategies) <= 3:
        raise ValueError("Everett supports between one and three strategies per run")

    branches = [f"everett/{_timeline_id(index)}" for index in range(len(strategies))]
    occupied = [branch for branch in branches if _branch_exists(branch)]
    if occupied:
        joined = ", ".join(occupied)
        raise RuntimeError(
            f"Everett timeline branches are already in use: {joined}. "
            "Collapse or clean up the active run before forking again."
        )

    run_id = uuid.uuid4().hex[:8]
    run_dir = RUNS_DIR / run_id
    run_dir.mkdir(parents=True, exist_ok=False)

    timelines = []
    try:
        for index, strategy in enumerate(strategies):
            timeline_id = _timeline_id(index)
            branch = branches[index]
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


def _branch_exists(branch: str) -> bool:
    return _run_git("show-ref", "--verify", "--quiet", f"refs/heads/{branch}", check=False).returncode == 0


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
