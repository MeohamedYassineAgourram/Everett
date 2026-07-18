# Everett

An MCP server that gives Codex fork/judge/collapse over parallel git worktrees.

Humans get undo. Codex gets do-over.

## Golden-Path Prompt

The endpoint in `demo/slowapi` is too slow. Use Everett: fork three strategies — add a caching layer; rewrite the query to eliminate N+1; precompute a summary table — then judge and collapse to the best.

## Setup

```bash
uv venv --python 3.11
uv pip install pytest fastapi uvicorn httpx rich fastmcp
npm install --prefix visualizer
```

Register the MCP server with Codex:

```bash
codex mcp add everett -- "$PWD/.venv/bin/python" "$PWD/server/mcp_server.py"
```

For the local Codex plugin that adds Everett's guided `showcase -> fork -> judge -> collapse` workflow, install it once on this machine:

```bash
codex plugin add everett-showcase@personal
```

Start a new Codex thread after installation, then ask Codex to use Everett and call `showcase()` first. The supported integration opens a live browser companion for the custom Three.js scene while Codex keeps the tool calls and final answer in its own interface.

Use this approval override for unattended MCP smoke tests:

```bash
-c 'mcp_servers.everett.default_tools_approval_mode="approve"'
```

## Verify

Launch the full projector demo in one command:

```bash
scripts/demo.sh
```

It opens the live 3D multiverse companion plus a four-pane tmux session: the Everett control panel and three worker timelines. Use `scripts/demo.sh --fast` for the deterministic no-model-credit backup. Detach with `Ctrl-b`, then `d`; end a completed session with `tmux kill-session -t everett-demo`.

Open the live 3D multiverse companion:

```bash
scripts/showcase.sh
```

From a Codex session, ask it to call the Everett `showcase` tool before `fork`; the visualizer follows the same live state and retains the final collapse result.

Run tests:

```bash
.venv/bin/pytest
```

Run the fast full-loop rehearsal:

```bash
scripts/dry_run.sh
```

Add `--verbose` to show postmortem text and worker-log locations instead of the concise demo view.

Run the real-worker rehearsal with three headless Codex workers:

```bash
scripts/dry_run.sh --real-workers
```

Reset generated demo state:

```bash
scripts/reset_demo.sh
```

Do not run `scripts/reset_demo.sh` or `scripts/dry_run.sh` while tests or another Everett run are active; reset intentionally removes runtime worktrees under `runs/`.

## Demo Checklist

1. Run `scripts/reset_demo.sh`.
2. Start screen recording.
3. Run `scripts/dry_run.sh --real-workers`.
4. If model calls stall, run `scripts/dry_run.sh` as the backup path.
5. Show the scoreboard, winner, `everett/result`, and the postmortem bullets.

While a live MCP `fork()` is running, show its three worker logs with:

```bash
scripts/watch_timelines.sh <run-id>
```

Install the one local presentation dependency with `brew install tmux`.

## MCP Smoke

```bash
codex exec -c 'mcp_servers.everett.default_tools_approval_mode="approve"' --sandbox read-only --ephemeral --json "Use the Everett MCP server's fork tool with strategies ['cache responses', 'rewrite query', 'precompute summary']. Do not run shell commands or read files. Return the tool result JSON and nothing else."
```

## Notes

- Codex CLI: `codex exec` is installed and non-interactive mode returned `codex-ok`.
- Worker baseline flags: `codex exec --cd <worktree> --sandbox workspace-write --json "<prompt>"`.
- Worker timeout: 4 minutes, leaving enough time for `judge()` to score and answer within Codex MCP's 5-minute tool-call limit.
- Useful unattended flags from `codex exec --help`: `--ephemeral`, `--skip-git-repo-check`, `--output-last-message <FILE>`, `--config <key=value>`.
- Avoid `--dangerously-bypass-approvals-and-sandbox` unless the outer demo environment is already sandboxed.
- Python env: `.venv` uses CPython 3.11.15; activate with `source .venv/bin/activate`.
