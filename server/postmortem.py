from __future__ import annotations

import subprocess
from pathlib import Path

from server.multiverse import REPO_ROOT


def generate_postmortem(
    run_id: str,
    winner: str,
    state: dict,
    *,
    repo_root: Path = REPO_ROOT,
) -> str:
    winner_timeline = _find_timeline(state, winner)
    losers = [timeline for timeline in state["timelines"] if timeline["id"] != winner]

    bullets = [
        (
            f"Winner `{winner_timeline['id']}` survived with strategy: "
            f"{winner_timeline['strategy']}"
        )
    ]

    for loser in losers:
        worktree = repo_root / loser["worktree"]
        files = _changed_files(repo_root, loser["branch"])
        log_tail = _log_tail(worktree / "worker.log")
        touched = ", ".join(files[:5]) if files else "no committed files"
        if len(files) > 5:
            touched += f", +{len(files) - 5} more"

        bullets.append(
            f"Timeline `{loser['id']}` explored `{loser['strategy']}` "
            f"and ended `{loser.get('status', 'unknown')}`; touched {touched}."
        )
        if log_tail:
            bullets.append(f"Timeline `{loser['id']}` log tail: {log_tail}")

    bullets.append(
        "Collapse kept the highest-scoring branch and discarded temporary A/B/C "
        "worktrees after preserving `everett/result`."
    )

    while len(bullets) < 5:
        bullets.append(
            "Road not taken: dead timelines still contributed evidence through "
            "their diffs, statuses, and worker transcripts."
        )

    lines = [f"# Roads Not Taken: `{run_id}`", ""]
    lines.extend(f"- {bullet}" for bullet in bullets[:5])
    return "\n".join(lines)


def _find_timeline(state: dict, timeline_id: str) -> dict:
    for timeline in state["timelines"]:
        if timeline["id"] == timeline_id:
            return timeline
    raise ValueError(f"Unknown timeline {timeline_id!r}")


def _changed_files(repo_root: Path, branch: str) -> list[str]:
    result = subprocess.run(
        ["git", "diff", "--name-only", f"main...{branch}"],
        cwd=repo_root,
        text=True,
        capture_output=True,
        check=False,
    )
    if result.returncode != 0:
        return []
    return [line for line in result.stdout.splitlines() if line]


def _log_tail(path: Path, lines: int = 3) -> str:
    if not path.exists():
        return ""
    tail = path.read_text(errors="replace").splitlines()[-lines:]
    return " / ".join(line.strip() for line in tail if line.strip())
