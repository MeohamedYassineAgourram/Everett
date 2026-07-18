#!/usr/bin/env python3
"""Render a Codex JSONL worker log as a readable timeline stream."""

from __future__ import annotations

import json
import sys
import time
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]


def main() -> int:
    if len(sys.argv) != 3:
        print("usage: scripts/timeline_log.py <run-id> <timeline>", file=sys.stderr)
        return 2

    run_id, timeline = sys.argv[1:]
    if not timeline.isalpha() or len(timeline) != 1:
        print("timeline must be A, B, or C", file=sys.stderr)
        return 2

    log_path = REPO_ROOT / "runs" / run_id / timeline.upper() / "worker.log"
    print(f"EVERETT | TIMELINE {timeline.upper()}")
    print(f"Following {log_path.relative_to(REPO_ROOT)}\n")
    follow(log_path)
    return 0


def follow(path: Path) -> None:
    position = 0
    while True:
        if not path.exists():
            time.sleep(0.2)
            continue

        with path.open(errors="replace") as log:
            log.seek(position)
            for raw_line in log:
                line = format_line(raw_line.strip())
                if line:
                    print(line, flush=True)
            position = log.tell()
        time.sleep(0.2)


def format_line(line: str) -> str:
    if not line:
        return ""
    if line.startswith("[everett]"):
        return f"Everett  {line.removeprefix('[everett] ').strip()}"

    try:
        event = json.loads(line)
    except json.JSONDecodeError:
        return ""

    event_type = event.get("type")
    if event_type == "item.completed":
        item = event.get("item", {})
        if item.get("type") == "agent_message":
            return f"Codex    {item.get('text', '').strip()}"
        if item.get("type") == "error":
            return f"Error    {item.get('message', '').strip()}"
    if event_type == "turn.completed":
        return "Codex    Turn completed"
    if event_type == "turn.started":
        return "Codex    Working"
    return ""


if __name__ == "__main__":
    raise SystemExit(main())
