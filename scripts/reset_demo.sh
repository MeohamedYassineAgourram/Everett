#!/usr/bin/env bash
# Reset only generated Everett state. The demo source itself is never modified.
set -euo pipefail

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$repo_root"

for worktree in "$repo_root"/runs/*; do
  [ -d "$worktree" ] || continue
  git worktree remove --force "$worktree"
done
git worktree prune
while IFS= read -r branch; do
  [ -n "$branch" ] && git branch -D "$branch"
done < <(git branch --format='%(refname:short)' 'everett/*')
rm -rf "$repo_root/runs"
find "$repo_root/demo/slowapi" -name perf.json -delete

echo "Everett demo reset: runtime worktrees and benchmark artifacts removed."
