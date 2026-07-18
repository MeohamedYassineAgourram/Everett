#!/usr/bin/env bash
set -euo pipefail

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
run_id="${1:-}"

if [[ ! "$run_id" =~ ^[A-Za-z0-9_-]+$ ]]; then
  echo "usage: scripts/watch_timelines.sh <run-id>" >&2
  exit 2
fi

if ! command -v tmux >/dev/null 2>&1; then
  echo "tmux is required for the live timeline view." >&2
  exit 1
fi

if tmux has-session -t everett 2>/dev/null; then
  echo "tmux session 'everett' already exists; attach with: tmux attach -t everett" >&2
  exit 1
fi

for timeline in A B C; do
  log_path="$repo_root/runs/$run_id/$timeline/worker.log"
  if [ ! -f "$log_path" ]; then
    echo "Missing worker log: $log_path" >&2
    exit 1
  fi
done

python_bin="$repo_root/.venv/bin/python"
if [ ! -x "$python_bin" ]; then
  python_bin="python3"
fi

quoted_python=$(printf '%q' "$python_bin")
quoted_viewer=$(printf '%q' "$repo_root/scripts/timeline_log.py")
tmux new-session -d -s everett -c "$repo_root" "$quoted_python $quoted_viewer $run_id A"
tmux split-window -h -t everett:0 -c "$repo_root" "$quoted_python $quoted_viewer $run_id B"
tmux split-window -h -t everett:0 -c "$repo_root" "$quoted_python $quoted_viewer $run_id C"
tmux select-layout -t everett:0 even-horizontal
tmux attach-session -t everett
