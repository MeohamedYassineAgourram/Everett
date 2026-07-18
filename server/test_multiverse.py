import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from server.multiverse import REPO_ROOT, cleanup, create_timelines


def _branch_exists(branch: str) -> bool:
    result = subprocess.run(
        ["git", "branch", "--list", branch],
        cwd=REPO_ROOT,
        text=True,
        capture_output=True,
        check=True,
    )
    return bool(result.stdout.strip())


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
