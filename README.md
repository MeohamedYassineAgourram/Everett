# Everett

> **Humans get undo. Codex gets do-over.**

Everett is an MCP server that gives Codex a new move at high-uncertainty moments: do not pick one implementation and hope. Fork up to three real Git worktrees, let a headless Codex worker pursue each named strategy in parallel, judge the outcomes with an objective fitness harness, and collapse the repository to the branch that survives.

The result is not prompt resampling. Each timeline has its own branch, filesystem, worker log, test run, benchmark result, and commit. The winner becomes `everett/result`; the discarded timelines leave behind a compact post-mortem of the roads not taken.

Everett was built for a Codex hackathon.

## The Question

Every coding agent normally lives one linear life. It reaches a decision such as “add a cache, rewrite the query, or change the schema,” commits to one path, and only discovers the cost of that choice later.

Everett asks: **what if an agent could treat a risky implementation choice as a branch point instead of a bet?** Git worktrees make the filesystem forks cheap. Codex workers make the exploration parallel. Tests and performance measurements decide which reality is worth keeping.

## Technologies

- Python 3.11+
- FastMCP
- Git worktrees and local branches
- Codex CLI workers via `codex exec`
- Pytest fitness gate and benchmark artifacts
- Rich terminal UI and tmux projector demo
- Three.js live multiverse command center

## What Everett Does

- **Forks real timelines:** `fork(strategies)` creates one worktree and `everett/A`, `everett/B`, or `everett/C` branch per strategy.
- **Launches parallel Codex workers:** each worker receives its strategy, edits only its worktree, runs tests, and commits a result.
- **Judges observed outcomes:** `judge(run_id)` runs the fitness harness in every timeline and returns tests, latency, speedup, diff size, and score.
- **Collapses to the winner:** `collapse(run_id, winner)` points `everett/result` at the winning branch, removes temporary worktrees, and preserves a post-mortem.
- **Shows the multiverse live:** `showcase()` opens a Three.js operations dashboard with timelines, worker state, score bars, and selection evidence.
- **Keeps dead-end knowledge:** the final result includes a “Roads Not Taken” summary based on the losing branches’ diffs, statuses, and worker logs.

## How It Works

```text
                 strategy A ──> worktree A ──> Codex worker ──┐
Codex decision ── strategy B ──> worktree B ──> Codex worker ──┼──> judge() ──> collapse()
                 strategy C ──> worktree C ──> Codex worker ──┘
```

1. **Fork** creates isolated worktrees at `runs/<run-id>/A|B|C`, all branched from `main`.
2. **Explore** launches up to three independent Codex workers concurrently. Each writes `worker.log` and must create a commit to succeed.
3. **Judge** applies a hard test gate, reads the performance artifact, and measures the branch diff.
4. **Collapse** keeps the highest-scoring passing branch as `everett/result`, prunes the temporary universes, and records the alternatives.

### Fitness Formula

Tests are a hard gate. A failing timeline scores `0`.

```text
speedup = baseline_p50_ms / timeline_p50_ms
score   = speedup - (0.005 × changed_lines)
```

The formula rewards measurable improvement while making a 400-line detour less attractive than a smaller, equally correct fix.

## Why It Is Not Best-of-N

Best-of-N asks for several answers to one prompt and hopes one is good. Everett forks **mid-task** around a decision the agent has identified, names divergent strategies, gives each one real repository state, and evaluates them with a shared objective function.

The root agent controls when to branch and what to explore. The winner inherits evidence from the losing futures instead of merely discarding them.

## Live Multiverse Dashboard

`showcase()` opens a local Three.js command center that follows the run state in real time.

- Central multiverse world and linked timeline worlds
- Timeline completion and test status
- Objective judge score bars for speed, diff impact, and final score
- Decision evidence for the selected branch: test gate, observed speed, change impact, and score margin

The dashboard presents **decision evidence**, not hidden model reasoning. It explains selection using observable repository and fitness data.

## Quick Demo

The fastest rehearsal uses deterministic local workers, so it does not spend model credits:

```bash
scripts/demo.sh --fast
```

It opens the live 3D dashboard and a four-pane tmux session: one Everett control panel plus three timeline panes. The control panel forks, judges, and collapses a complete run.

For the full version with headless Codex workers:

```bash
scripts/demo.sh
```

Detach from the demo with `Ctrl-b`, then `d`. End a completed session with:

```bash
tmux kill-session -t everett-demo
```

## Run It Locally

### Prerequisites

- Git
- Python 3.11+
- Node.js 18+ and npm for the dashboard
- `tmux` for the four-pane demo
- Codex CLI, logged in, for real worker runs

### Setup

```bash
git clone https://github.com/MeohamedYassineAgourram/Everett.git
cd Everett

uv venv --python 3.11
uv pip install -r requirements.txt
npm install --prefix visualizer
```

Install tmux on macOS if needed:

```bash
brew install tmux
```

### Verify the Engine

```bash
.venv/bin/pytest
scripts/dry_run.sh
```

`scripts/dry_run.sh` uses local deterministic workers by default. Use the actual Codex worker path with:

```bash
scripts/dry_run.sh --real-workers
```

Add `--verbose` to include worker-log locations and the full post-mortem:

```bash
scripts/dry_run.sh --verbose
```

## Use It From Codex

Register Everett as a local MCP server:

```bash
codex mcp add everett -- "$PWD/.venv/bin/python" "$PWD/server/mcp_server.py"
```

Start a new Codex session and give it a decision-oriented task, for example:

```text
The endpoint in demo/slowapi is too slow. Use Everett: open the showcase, fork three strategies — add a caching layer, rewrite the N+1 query, and precompute a summary — then judge and collapse to the best result.
```

Everett exposes four tools:

| Tool | Purpose |
|---|---|
| `fork(strategies)` | Creates timelines and starts parallel workers. |
| `judge(run_id)` | Scores each timeline using tests, performance, and diff size. |
| `collapse(run_id, winner)` | Preserves the winner as `everett/result` and removes temporary worktrees. |
| `showcase()` | Opens the live 3D command center for the current run. |

## Demo Flow

For a reliable projector run:

1. Run `scripts/reset_demo.sh` to remove previous runtime state.
2. Start a screen recording.
3. Run `scripts/demo.sh` for real workers, or `scripts/demo.sh --fast` for the deterministic backup.
4. Let the audience see the three timelines, judge score bars, and final selection evidence.
5. Show `everett/result` and the “Roads Not Taken” post-mortem after collapse.

Open the dashboard independently at any time:

```bash
scripts/showcase.sh
```

It is served locally at `http://127.0.0.1:4317`.

## Project Structure

```text
Everett/
├── server/
│   ├── mcp_server.py     # FastMCP tools: fork, judge, collapse, showcase
│   ├── multiverse.py     # Worktree lifecycle and concurrent Codex workers
│   ├── fitness.py        # Pytest gate, latency, diff stats, and score
│   ├── postmortem.py     # Roads-not-taken summary
│   └── showcase.py       # Local visualizer state API and HTTP server
├── visualizer/
│   ├── index.html        # Live command-center shell
│   ├── app.js            # Three.js scene and state-driven telemetry
│   └── styles.css        # Mission-control visual system
├── scripts/
│   ├── demo.sh           # One-command dashboard and tmux demo
│   ├── dry_run.sh        # Rehearsal loop with fake or real workers
│   ├── showcase.sh       # Local visualizer launcher
│   ├── run_demo.py       # Projector-friendly terminal control plane
│   └── reset_demo.sh     # Removes generated runs and result branches
└── demo/slowapi/         # Deliberately slow endpoint and fitness target
```

## What We Learned

- **Parallelism changes the agent’s decision-making posture.** It is easier to attempt a risky change when exploration is isolated and the test suite is the arbiter.
- **A branch is not enough without an objective judge.** Worktrees make divergence cheap; a shared fitness function makes the final selection defensible.
- **The loser timelines still matter.** Their commits, diffs, tests, and logs provide useful engineering context for the surviving solution.
- **Demo reliability is a product feature.** Everett includes fast local workers, real Codex workers, an explicit reset script, a tmux layout, and a live dashboard so the core loop can be rehearsed instead of hoped for.

## Current Limits

- Everett is a local hackathon prototype, not a multi-tenant hosted service.
- It supports one to three timelines per run to keep rate limits and demo complexity bounded.
- The fitness harness is intentionally task-specific: the included demo evaluates Pytest, p50 latency, and changed lines.
- Real worker runs require a logged-in Codex CLI and use model credits.
- `scripts/reset_demo.sh` intentionally removes generated `runs/` worktrees and `everett/*` runtime branches. Do not run it during an active run.

## Next Steps

- Make fitness harnesses configurable per repository.
- Support multi-level branching when a timeline reaches another hard decision.
- Persist run history and post-mortems beyond the local workspace.
- Add a hosted dashboard for reviewing completed multiverse runs.
- Add policy controls for token budget, worker timeout, and maximum branch depth.

## License

This repository is a hackathon prototype. Add a license before production use or redistribution.
