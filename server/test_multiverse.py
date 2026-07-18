import asyncio
import json
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from server.multiverse import (
    REPO_ROOT,
    RUNS_DIR,
    WORKER_SUFFIX,
    cleanup,
    create_timelines,
    launch_workers,
)
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
