from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
BASELINE_MS = 1000.0


def _run(command: list[str], cwd: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(command, cwd=cwd, text=True, capture_output=True)


def _python_for(path: Path) -> str:
    local_python = REPO_ROOT / ".venv" / "bin" / "python"
    if local_python.exists():
        return str(local_python)
    return sys.executable


def _read_p50(path: Path) -> float:
    perf_path = path / "perf.json"
    if not perf_path.exists():
        return BASELINE_MS

    data = json.loads(perf_path.read_text())
    return float(data.get("p50_ms", BASELINE_MS))


def _diff_lines(path: Path) -> int:
    result = _run(["git", "diff", "--numstat", "main...HEAD"], cwd=path)
    if result.returncode != 0:
        return 0

    total = 0
    for line in result.stdout.splitlines():
        added, deleted, *_ = line.split("\t")
        if added != "-":
            total += int(added)
        if deleted != "-":
            total += int(deleted)
    return total


def score_path(path: str | Path) -> dict:
    repo_path = Path(path)
    pytest_target = repo_path / "demo" / "slowapi"
    command = [_python_for(repo_path), "-m", "pytest", str(pytest_target)]
    result = _run(command, cwd=repo_path)

    tests_passed = result.returncode == 0
    p50_ms = _read_p50(pytest_target)
    speedup = BASELINE_MS / p50_ms if p50_ms > 0 else 0.0
    diff_lines = _diff_lines(repo_path)
    score = speedup - 0.005 * diff_lines if tests_passed else 0.0

    return {
        "tests_passed": tests_passed,
        "p50_ms": p50_ms,
        "speedup": speedup,
        "diff_lines": diff_lines,
        "score": score,
    }


def main() -> int:
    if len(sys.argv) != 2:
        print("usage: python -m server.fitness <path>", file=sys.stderr)
        return 2

    print(json.dumps(score_path(sys.argv[1]), indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
