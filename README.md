# Everett

An MCP server that gives Codex fork/judge/collapse over parallel git worktrees.

Pre-flight is in progress. Full run instructions land at freeze time.

## Pre-flight Notes

- Codex CLI: `codex exec` is installed and non-interactive mode returned `codex-ok`.
- Worker baseline flags: `codex exec --cd <worktree> --sandbox workspace-write --json "<prompt>"`.
- Useful unattended flags from `codex exec --help`: `--ephemeral`, `--skip-git-repo-check`, `--output-last-message <FILE>`, `--config <key=value>`.
- Avoid `--dangerously-bypass-approvals-and-sandbox` unless the outer demo environment is already sandboxed.
- Python env: `.venv` uses CPython 3.11.15; activate with `source .venv/bin/activate`.
