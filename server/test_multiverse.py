import asyncio
import json
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from server.multiverse import REPO_ROOT, RUNS_DIR, cleanup, create_timelines, launch_workers


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
            assert "Run the tests. Commit your changes when they pass." in (
                worktree / "worker-output.txt"
            ).read_text()
            assert _git_output(["log", "-1", "--format=%s"], worktree) == (
                f"worker commit {timeline['id']}"
            )
    finally:
        if (REPO_ROOT / "runs" / run_id).exists():
            cleanup(run_id)
