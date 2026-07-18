import asyncio
import json
import subprocess
import sys
from contextlib import suppress
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from server.multiverse import (
    REPO_ROOT,
    RUNS_DIR,
    WORKER_SUFFIX,
    _run_worker,
    cleanup,
    create_timelines,
    launch_workers,
)
from server import mcp_server
from server.postmortem import generate_postmortem


def _branch_exists(branch: str) -> bool:
    result = subprocess.run(
        ["git", "branch", "--list", branch],
        cwd=REPO_ROOT,
        text=True,
        capture_output=True,
        check=True,
    )
    return bool(result.stdout.strip())


def _git_output(args: list[str], cwd: Path) -> str:
    result = subprocess.run(
        ["git", *args],
        cwd=cwd,
        text=True,
        capture_output=True,
        check=True,
    )
    return result.stdout.strip()


def test_create_timelines_and_cleanup():
    state = create_timelines(["cache responses", "rewrite query", "precompute summary"])
    run_id = state["run_id"]

    try:
        assert list(state) == ["run_id", "timelines"]
        assert len(state["timelines"]) == 3

        for timeline in state["timelines"]:
            assert timeline["id"] in {"A", "B", "C"}
            assert timeline["branch"] == f"everett/{timeline['id']}"
            assert timeline["worktree"] == f"runs/{run_id}/{timeline['id']}"
            assert timeline["status"] == "running"
            assert (REPO_ROOT / timeline["worktree"]).is_dir()
            assert _branch_exists(timeline["branch"])

        cleanup(run_id)

        for timeline in state["timelines"]:
            assert not (REPO_ROOT / timeline["worktree"]).exists()
            assert not _branch_exists(timeline["branch"])
        assert not (REPO_ROOT / "runs" / run_id).exists()
    finally:
        if (REPO_ROOT / "runs" / run_id).exists():
            cleanup(run_id)


def test_create_timelines_rejects_invalid_or_occupied_timeline_branches():
    with pytest.raises(ValueError, match="between one and three"):
        create_timelines([])
    with pytest.raises(ValueError, match="between one and three"):
        create_timelines(["A", "B", "C", "D"])

    state = create_timelines(["first run"])
    try:
        with pytest.raises(RuntimeError, match="everett/A"):
            create_timelines(["second run"])
    finally:
        cleanup(state["run_id"])


def test_launch_workers_commits_and_updates_state():
    state = create_timelines(["cache responses", "rewrite query", "precompute summary"])
    run_id = state["run_id"]
    fake_worker = """
import pathlib
import subprocess
import sys

worktree = pathlib.Path(sys.argv[1])
prompt = sys.argv[2]
marker = worktree / "worker-output.txt"
marker.write_text(prompt + "\\n")
subprocess.run(["git", "add", "worker-output.txt"], cwd=worktree, check=True)
subprocess.run(
    [
        "git",
        "-c",
        "user.name=Everett Worker",
        "-c",
        "user.email=worker@example.com",
        "commit",
        "-m",
        f"worker commit {worktree.name}",
    ],
    cwd=worktree,
    check=True,
)
"""

    try:
        timelines = asyncio.run(
            launch_workers(
                state["timelines"],
                worker_command=[sys.executable, "-c", fake_worker],
                timeout_seconds=10,
            )
        )
        saved = json.loads((RUNS_DIR / run_id / "state.json").read_text())

        assert [timeline["status"] for timeline in timelines] == [
            "succeeded",
            "succeeded",
            "succeeded",
        ]
        assert [timeline["status"] for timeline in saved["timelines"]] == [
            "succeeded",
            "succeeded",
            "succeeded",
        ]

        for timeline in state["timelines"]:
            worktree = REPO_ROOT / timeline["worktree"]
            assert (worktree / "worker.log").is_file()
            assert WORKER_SUFFIX in (
                worktree / "worker-output.txt"
            ).read_text()
            assert _git_output(["log", "-1", "--format=%s"], worktree) == (
                f"worker commit {timeline['id']}"
            )
    finally:
        if (REPO_ROOT / "runs" / run_id).exists():
            cleanup(run_id)


def test_launch_workers_commits_successful_dirty_worktree():
    state = create_timelines(["write a marker"])
    run_id = state["run_id"]
    fake_worker = """
import pathlib
import sys

worktree = pathlib.Path(sys.argv[1])
(worktree / "worker-output.txt").write_text("changed by worker\\n")
"""

    try:
        timelines = asyncio.run(
            launch_workers(
                state["timelines"],
                worker_command=[sys.executable, "-c", fake_worker],
                timeout_seconds=10,
            )
        )
        worktree = REPO_ROOT / state["timelines"][0]["worktree"]

        assert timelines[0]["status"] == "succeeded"
        assert _git_output(["log", "-1", "--format=%s"], worktree).startswith(
            "Everett A: write a marker"
        )
    finally:
        if (REPO_ROOT / "runs" / run_id).exists():
            cleanup(run_id)


def test_launch_workers_marks_timeout():
    state = create_timelines(["sleep too long"])
    run_id = state["run_id"]
    fake_worker = """
import time

time.sleep(5)
"""

    try:
        timelines = asyncio.run(
            launch_workers(
                state["timelines"],
                worker_command=[sys.executable, "-c", fake_worker],
                timeout_seconds=1,
            )
        )
        saved = json.loads((RUNS_DIR / run_id / "state.json").read_text())
        worktree = REPO_ROOT / state["timelines"][0]["worktree"]

        assert timelines[0]["status"] == "timeout"
        assert saved["timelines"][0]["status"] == "timeout"
        assert "timeout after 1s" in (worktree / "worker.log").read_text()
        assert _git_output(["rev-list", "--count", "main..HEAD"], worktree) == "0"
    finally:
        if (REPO_ROOT / "runs" / run_id).exists():
            cleanup(run_id)


def test_launch_workers_marks_startup_error_as_failed():
    state = create_timelines(["run a missing worker"])
    run_id = state["run_id"]

    try:
        timelines = asyncio.run(
            launch_workers(
                state["timelines"],
                worker_command=["everett-missing-worker-command"],
                timeout_seconds=10,
            )
        )
        log_path = REPO_ROOT / state["timelines"][0]["worktree"] / "worker.log"

        assert timelines[0]["status"] == "failed"
        assert "could not start worker" in log_path.read_text()
    finally:
        if (REPO_ROOT / "runs" / run_id).exists():
            cleanup(run_id)


def test_worker_detaches_mcp_stdin(monkeypatch):
    state = create_timelines(["verify detached stdin"])
    run_id = state["run_id"]
    captured: dict = {}

    class FailedProcess:
        async def wait(self) -> int:
            return 1

    async def fake_subprocess(*args, **kwargs):
        captured.update(kwargs)
        return FailedProcess()

    async def set_status(_: str, __: str) -> None:
        return None

    try:
        monkeypatch.setattr(asyncio, "create_subprocess_exec", fake_subprocess)
        asyncio.run(
            _run_worker(
                state["timelines"][0],
                set_status,
                worker_command=["fake-worker"],
                timeout_seconds=10,
            )
        )

        assert captured["stdin"] is asyncio.subprocess.DEVNULL
    finally:
        if (REPO_ROOT / "runs" / run_id).exists():
            cleanup(run_id)


def test_collapse_rejects_a_run_with_active_workers():
    state = create_timelines(["wait for worker"])
    run_id = state["run_id"]

    async def attempt_collapse() -> None:
        task = asyncio.create_task(asyncio.sleep(60))
        mcp_server._worker_tasks[run_id] = task
        try:
            with pytest.raises(RuntimeError, match="Workers are still running"):
                mcp_server.collapse(run_id, "A")
        finally:
            task.cancel()
            with suppress(asyncio.CancelledError):
                await task
            mcp_server._worker_tasks.pop(run_id, None)

    try:
        asyncio.run(attempt_collapse())
    finally:
        if (REPO_ROOT / "runs" / run_id).exists():
            cleanup(run_id)


def test_judge_retry_does_not_cancel_workers_after_client_timeout(monkeypatch):
    state = create_timelines(["wait for a retry"])
    run_id = state["run_id"]

    async def verify_shielding() -> None:
        worker_task = asyncio.create_task(asyncio.sleep(0.1))
        mcp_server._worker_tasks[run_id] = worker_task
        try:
            with pytest.raises(asyncio.TimeoutError):
                await asyncio.wait_for(mcp_server.judge(run_id), timeout=0.01)
            assert not worker_task.cancelled()
            await worker_task
        finally:
            mcp_server._worker_tasks.pop(run_id, None)

    monkeypatch.setattr(
        mcp_server,
        "score_path",
        lambda _: {
            "tests_passed": True,
            "p50_ms": 1.0,
            "speedup": 1.0,
            "diff_lines": 0,
            "score": 1.0,
        },
    )
    try:
        asyncio.run(verify_shielding())
    finally:
        if (REPO_ROOT / "runs" / run_id).exists():
            cleanup(run_id)


def test_generate_postmortem_includes_loser_logs_and_diffs():
    state = create_timelines(["winner path", "risky cache", "large rewrite"])
    run_id = state["run_id"]
    fake_worker = """
import pathlib
import subprocess
import sys

worktree = pathlib.Path(sys.argv[1])
prompt = sys.argv[2]
marker = worktree / f"postmortem-{worktree.name}.txt"
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
        f"postmortem commit {worktree.name}",
    ],
    cwd=worktree,
    check=True,
)
"""

    try:
        timelines = asyncio.run(
            launch_workers(
                state["timelines"],
                worker_command=[sys.executable, "-c", fake_worker],
                timeout_seconds=10,
            )
        )
        state["timelines"] = timelines
        postmortem = generate_postmortem(run_id, "A", state)

        assert postmortem.startswith(f"# Roads Not Taken: `{run_id}`")
        assert "Winner `A` survived with strategy: winner path" in postmortem
        assert "Timeline `B` explored `risky cache`" in postmortem
        assert "postmortem-B.txt" in postmortem
        assert "Timeline `C` explored `large rewrite`" in postmortem
        assert "postmortem-C.txt" in postmortem
        assert "worker.log" not in postmortem
    finally:
        if (REPO_ROOT / "runs" / run_id).exists():
            cleanup(run_id)
