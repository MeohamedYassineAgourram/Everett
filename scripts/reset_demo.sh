#!/usr/bin/env bash
# Reset only generated Everett state. The demo source itself is never modified.
set -euo pipefail

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$repo_root"

while IFS= read -r worktree; do
  case "$worktree" in
    "$repo_root"/runs/*) git worktree remove --force "$worktree" ;;
  esac
done < <(git worktree list --porcelain | awk '/^worktree / {print substr($0, 10)}')

git worktree prune
while IFS= read -r branch; do
  [ -n "$branch" ] && git branch -D "$branch"
done < <(git for-each-ref --format='%(refname:short)' refs/heads/everett)
rm -rf "$repo_root/runs"
find "$repo_root/demo/slowapi" -name perf.json -delete

echo "Everett demo reset: runtime worktrees and benchmark artifacts removed."
