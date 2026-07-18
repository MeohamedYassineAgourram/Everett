# Everett

An MCP server that gives Codex fork/judge/collapse over parallel git worktrees.

Pre-flight is in progress. Full run instructions land at freeze time.

## Pre-flight Notes

- Codex CLI: `codex exec` is installed and non-interactive mode returned `codex-ok`.
- Worker baseline flags: `codex exec --cd <worktree> --sandbox workspace-write --json "<prompt>"`.
- Useful unattended flags from `codex exec --help`: `--ephemeral`, `--skip-git-repo-check`, `--output-last-message <FILE>`, `--config <key=value>`.
- Avoid `--dangerously-bypass-approvals-and-sandbox` unless the outer demo environment is already sandboxed.
- Python env: `.venv` uses CPython 3.11.15; activate with `source .venv/bin/activate`.
- MCP server registered as `everett`:
  `codex mcp add everett -- /Users/mohamedyassineagourram/Desktop/HACKATHONS/Everett/.venv/bin/python /Users/mohamedyassineagourram/Desktop/HACKATHONS/Everett/server/mcp_server.py`
- MCP smoke test:
  `codex exec -c 'mcp_servers.everett.default_tools_approval_mode="approve"' --sandbox read-only --ephemeral --json "Use the Everett MCP server's fork tool with strategies ['cache responses', 'rewrite query', 'precompute summary']. Do not run shell commands or read files. Return the tool result JSON and nothing else."`
