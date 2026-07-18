#!/usr/bin/env bash
set -euo pipefail

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
mode=""

case "${1:-}" in
  "") ;;
  --fast) mode="--fast" ;;
  *)
    echo "usage: scripts/demo.sh [--fast]" >&2
    exit 2
    ;;
esac

python_bin="$repo_root/.venv/bin/python"
if [ ! -x "$python_bin" ]; then
  echo "Expected .venv/bin/python. Run the setup steps in README.md first." >&2
  exit 1
fi

if ! command -v tmux >/dev/null 2>&1; then
  echo "tmux is required. Install it with: brew install tmux" >&2
  exit 1
fi

if [ -z "$mode" ] && ! command -v codex >/dev/null 2>&1; then
  echo "Codex CLI is required for the live demo. Run: codex login" >&2
  exit 1
fi

session="everett-demo"
if tmux has-session -t "$session" 2>/dev/null; then
  echo "The Everett demo session is already open. Attach with: tmux attach -t $session" >&2
  exit 1
fi

"$repo_root/scripts/reset_demo.sh" >/dev/null
"$repo_root/scripts/showcase.sh" >/dev/null

quoted_python=$(printf '%q' "$python_bin")
quoted_runner=$(printf '%q' "$repo_root/scripts/run_demo.py")
quoted_viewer=$(printf '%q' "$repo_root/scripts/timeline_log.py")
runner_command="$quoted_python $quoted_runner $mode"

tmux new-session -d -s "$session" -c "$repo_root" "$runner_command"
tmux set-option -t "$session" remain-on-exit on
tmux set-option -t "$session" pane-border-status top
tmux set-option -t "$session" pane-border-style fg=cyan
tmux set-option -t "$session" pane-active-border-style fg=green
tmux set-option -t "$session" status-style bg=black,fg=cyan
tmux set-option -t "$session" status-left " EVERETT "
tmux set-option -t "$session" status-right " Fork / Judge / Collapse "

tmux select-pane -t "$session:0.0" -T "Everett control"
for timeline in A B C; do
  tmux split-window -t "$session:0" -c "$repo_root" "$quoted_python $quoted_viewer --exit-on-complete --active $timeline"
done
tmux select-pane -t "$session:0.1" -T "Timeline A"
tmux select-pane -t "$session:0.2" -T "Timeline B"
tmux select-pane -t "$session:0.3" -T "Timeline C"
tmux select-layout -t "$session:0" tiled
tmux attach-session -t "$session"
