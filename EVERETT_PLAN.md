# EVERETT — Build Plan
### Codex Community Hackathon · Paris · 18 July 2026

**One-liner:** An MCP server that gives Codex a new cognitive move: when uncertain, don't choose. `fork()` reality into parallel git worktrees, pursue every strategy at once with headless Codex workers, `judge()` them with an objective fitness harness, `collapse()` to the winner — which inherits the losers' lessons.

**Team:** 2 people · **Build window:** ~5h (10:30–13:00, 14:00–16:30) · **Demo:** 3 min at 16:30

**Closing line (memorize it):** *"Humans get undo. Codex gets do-over."*

---

## 0. Roles

| | Codename | Owns |
|---|---|---|
| **Player 1** | **The Forker** | Multiverse engine: MCP server, git worktrees, spawning headless Codex workers, `collapse()`, post-mortem digest |
| **Player 2** | **The Judge** | Fitness harness, the demo target app, scoreboard rendering, demo staging (tmux), pitch assets |

**Working agreement:**
- Each of you drives your **own Codex session** on your own machine, in the same GitHub repo. You are supervisors; Codex writes the code. (This is a Codex hackathon — "Everett was itself built by Codex" is a pitch line.)
- Sync via git every ~25 minutes. Pull before push. Never leave `main` broken.
- Ping before touching a shared file (`mcp_server.py` is the only real shared surface).
- Disagreements get 60 seconds, then The Forker decides on engine questions and The Judge decides on demo questions. No bikeshedding today.

---

## 1. The Contract (agree on this together, 10 min, BEFORE splitting)

This section is the interface between your two halves. Build to it exactly and integration at 14:00 is trivial. Change it only by mutual agreement, then commit the change immediately.

### Repo layout

```
everett/
├── AGENTS.md                  # context file Codex reads automatically (template in §5)
├── PLAN.md                    # this file
├── README.md                  # one-liner + run instructions (write at freeze time)
├── server/
│   ├── mcp_server.py          # MCP entry point: fork / judge / collapse   [shared]
│   ├── multiverse.py          # worktrees + worker lifecycle               [P1]
│   ├── fitness.py             # run harness in a path → scores             [P2]
│   └── postmortem.py          # distill loser transcripts → lessons        [P1]
├── demo/
│   └── slowapi/               # demo target: FastAPI app + tests           [P2]
├── runs/                      # runtime state: runs/<run_id>/... (gitignored)
└── scripts/
    ├── reset_demo.sh          # nuke runs/, prune worktrees, restore slow app
    └── dry_run.sh             # end-to-end rehearsal, no MCP client needed
```

### Tool signatures (locked)

```python
fork(strategies: list[str]) -> {
  "run_id": str,
  "timelines": [
    {"id": "A", "branch": "everett/A", "worktree": "runs/<run_id>/A",
     "strategy": str, "status": "running"}
  ]
}

judge(run_id: str) -> {
  "scoreboard": [
    {"timeline": "A", "tests_passed": bool, "p50_ms": float,
     "speedup": float, "diff_lines": int, "score": float}
  ]
}

collapse(run_id: str, winner: str) -> {
  "result_branch": "everett/result",
  "postmortem": str   # markdown, "roads not taken"
}
```

### Locked decisions (do not reopen today)

- **Language/stack:** Python 3.11+, `pytest`, `fastapi`, `uvicorn`, `httpx`, `rich`. MCP via the official Python SDK or FastMCP — whichever gets hello-world working first.
- **Scoring:** tests passing is a **hard gate**. Among passers: `score = speedup − 0.005 × diff_lines`. Highest wins. Simple beats clever.
- **Worker:** `codex exec` running inside the timeline's worktree, prompt = strategy + fixed suffix: *"Run the tests. Commit your changes when they pass."* Hard timeout: 6 minutes, then kill.
- **Collapse = no merging.** Point a fresh `everett/result` branch at the winner's branch (`git branch -f` / checkout). Three-way merges are where hackathon demos go to die.
- **Parallelism cap:** n = 3 timelines. Protects rate limits and fits three tmux panes on a projector.

---

## 2. Timeline with hard checkpoints

### Pre-flight (before / during 10:00 kickoff)

- [ ] Both laptops: Codex CLI installed, logged in; verify non-interactive mode works and note the exact flags (`codex exec --help` — check sandbox/approval flags for unattended runs; CLI flags drift between versions, spend 5 min here, not 30 at 2pm)
- [ ] GitHub repo `everett` created, both members can push; skeleton + this file + `.gitignore` (`runs/`) committed
- [ ] `AGENTS.md` committed (template in §5)
- [ ] Python env up (`uv venv` or venv) with deps installed
- [ ] Both enrolled in the Global Build Week challenge (2 minutes, $100k pool, do it now or never)
- [ ] Phones charged — one of them is your backup-video camera

### 10:30–11:00 · TOGETHER — kill the riskiest unknown first

- [ ] Hello-world MCP server exposing a dummy `fork` tool that returns canned JSON
- [ ] Register it in Codex's MCP config; confirm a **live Codex session can call the dummy tool and read the result**

If MCP wiring works, everything else is plumbing you control. Prove it in the first 30 minutes while you're fresh, together.

### 11:00–12:30 · SPLIT

**P1 — The Forker (`multiverse.py`):**
- [ ] Create/destroy worktrees: `git worktree add -b everett/A runs/<run_id>/A main` (and `git worktree prune` in cleanup)
- [ ] Spawn ONE headless worker in a worktree; confirm it actually edits files and commits
- [ ] Then 3 concurrently (`asyncio.create_subprocess_exec`), statuses + worker logs written to `runs/<run_id>/state.json` and `runs/<run_id>/<id>/worker.log`
- [ ] Timeout + kill logic (6 min cap per worker)

**P2 — The Judge (`demo/slowapi` + `fitness.py`):**
- [ ] Demo target: FastAPI `GET /report` that is *honestly* slow — N+1 SQLite queries over ~50k generated rows (or an O(n²) aggregation). It must be slow for a real reason so real strategies really differ.
- [ ] Tests: a correctness suite + `test_perf.py` that hits the endpoint ~10 times warm and writes p50 latency to `perf.json`
- [ ] `fitness.py`: given a repo path → run pytest → parse results + `perf.json` → score dict per the contract. Must be CLI-callable: `python -m server.fitness <path>` (so P1 can integrate without you)
- [ ] `scripts/reset_demo.sh`

### 12:30–13:00 · CHECKPOINT 1 (hard gate)

- [ ] P1 shows: `fork(["a","b","c"])` → 3 worktrees, 3 real workers ran, commits landed on 3 branches
- [ ] P2 shows: `fitness.py` gives the untouched slow app a bad score and a hand-optimized copy a good one

If either fails: pair on it through lunch. Cut scope from §4, never from the core loop.

### 13:00–14:00 · Lunch — eat fast, integrate slowly

Wire `judge()` to loop `fitness.py` across all worktrees. Walk through the demo beats out loud once.

### 14:00–14:40 · TOGETHER — integration

- [ ] Full loop, headless: fork → workers finish → judge → scoreboard → collapse → `everett/result` exists with winning code
- [ ] Write down the **golden-path prompt** for the root Codex session, verbatim, in `README.md`. Something like: *"The endpoint in demo/slowapi is too slow. Use Everett: fork three strategies — add a caching layer; rewrite the query to eliminate N+1; precompute a summary table — then judge and collapse to the best."*

### 14:40–15:10 · SPLIT

- **P1:** `postmortem.py` — gather loser diffs + tail of worker logs → one API call → 5-bullet "roads not taken" markdown, appended to the result. (First feature to cut if late.)
- **P2:** presentation layer — tmux 3-pane layout tailing each `worker.log`, `rich` scoreboard table, font sizes legible from 5 meters. Test on the projector if you can get 2 minutes on it.

### 15:10–15:40 · Dry run #1 — expect it to break; fix what breaks

### 15:40–16:05 · Dry run #2 + **record the backup video** of one full successful run (screen-rec + phone). This is your insurance policy. Non-negotiable.

### 16:05–16:30 · FREEZE

- [ ] Code freeze — no "one more improvement," this is how demos die
- [ ] Push everything; `reset_demo.sh`; laptop plugged in; notifications off
- [ ] Rehearse the pitch twice, out loud, timed under 3:00

---

## 3. Codex usage playbook

- Small, scoped asks. One file or one function per prompt. Commit after every green step.
- Start every fresh session with: *"Read AGENTS.md and PLAN.md before doing anything."*
- Don't let Codex refactor across the contract boundary. The signatures in §1 are law.

**Starter prompt — P1:**
> Read AGENTS.md and PLAN.md. Implement `server/multiverse.py` per the contract: `create_timelines(strategies)` builds git worktrees under `runs/<run_id>/` on branches `everett/<id>`, and `launch_workers(timelines)` runs the Codex CLI non-interactively in each worktree as an async subprocess with a 6-minute timeout, streaming output to `worker.log` and status to `state.json`. Add a pytest for worktree creation/cleanup. Touch only this file and its test.

**Starter prompt — P2:**
> Read AGENTS.md and PLAN.md. Build `demo/slowapi`: a FastAPI app with `GET /report` over a generated SQLite database (~50k rows) implemented with a deliberate N+1 query pattern; a correctness test suite; and `test_perf.py` measuring p50 latency over 10 warm requests, written to `perf.json`. Then implement `server/fitness.py` per the contract, CLI-callable with a path argument. Touch only these files.

---

## 4. Cut list (pre-agreed — cut in this order, without discussion)

1. **Post-mortem digest** → replace with one static sentence in the pitch
2. **Live tmux streaming** → run headless, show scoreboard + winning diff afterwards
3. **Parallel workers** → sequential mode (same story, slower; start the demo run earlier)
4. **Live run entirely** → play the backup video and narrate over it, then show the real code and the real result branch

**Never cut:** real Codex workers really editing real code in real worktrees. That's the soul. Everything else is garnish.

---

## 5. AGENTS.md template

```markdown
# Everett
MCP server that gives Codex fork/judge/collapse over parallel git worktrees.

- Python 3.11+. Run tests with `pytest`.
- Tool schemas and repo layout are specified in PLAN.md §1 — do not change signatures.
- Work only in the files you were asked to touch.
- Never commit with failing tests. `runs/` is runtime state — never commit it.
```

---

## 6. Demo script (3:00) + Q&A pocket answers

- **0:00 — Problem.** "Every coding agent lives one life. It hits a fork — cache it? rewrite it? restructure? — bets everything on one guess, and rides that timeline to the end. Humans built branches, staging, undo: an entire infrastructure of courage. Codex has none of it."
- **0:30 — Move.** "Everett gives Codex a new move: don't choose. Fork reality." Type the golden-path prompt into the root Codex session, live.
- **0:50 — The race.** Three panes light up. "Three Codexes. Three strategies. Same task: make this endpoint 10× faster." Narrate the strategies while they run.
- **1:50 — Judgment.** Scoreboard appears. "Timeline A: tests failed — that universe dies. B: 11× faster, green. C: 9×, but a 400-line diff."
- **2:15 — Collapse.** `collapse(B)`. "And the winner inherits the losers' memories" — read one line of the post-mortem. "Human teams pay senior engineers to write the roads-not-taken doc. Everett's agent gets it as a by-product of exploring."
- **2:40 — Close.** "Best-of-n resamples a prompt and hopes. Everett forks mid-task, at decision points the agent itself chooses, with real filesystem state and an objective judge. Humans get undo. Codex gets do-over."

**Q&A pocket answers:**
- *Isn't this just best-of-n?* — Best-of-n resamples one prompt. Everett forks mid-task, agent-initiated, with named divergent strategies, real state, and an objective fitness function. It's tree search over codebases.
- *Cost?* — You pay ~3× tokens only on the forked segment, only at high-uncertainty moments — versus the compounding cost of one wrong architectural bet. Even dead timelines return lessons.
- *Safety?* — Workers are sandboxed to their own worktree; the outcome lands as a branch, not a push. Nothing touches main without a human.

---

## 7. Fallbacks & gotchas

| Risk | Plan |
|---|---|
| CLI flag drift on non-interactive Codex | Timebox 20 min. Fallback worker = minimal loop calling the API with file-edit instructions (P1 owns) |
| Rate limits | n=3 cap, terse worker prompts, `--sequential` flag ready |
| Flaky perf numbers | Benchmark locally, warm-up requests, p50 of 10, laptop plugged in, close Chrome |
| State pollution between rehearsals | `reset_demo.sh`: delete `runs/`, `git worktree prune`, delete `everett/*` branches, restore slow app |
| Wifi dies mid-demo | Backup video + everything runs locally except the model calls; if even that dies, video + real code walkthrough |
| Two people, one repo | Pull before push; `mcp_server.py` is the only shared file — announce before editing it |

---

## 8. Definition of done (by 16:05)

- [ ] One prompt to the root Codex session triggers fork → judge → collapse on a clean checkout
- [ ] Backup video recorded and playable
- [ ] Scoreboard readable from 5 meters
- [ ] Pitch rehearsed twice out loud, under 3:00
- [ ] Repo pushed; README has the one-liner, the golden-path prompt, and run instructions
- [ ] Both enrolled in the Global Build Week challenge

*Name it after Hugh Everett. Put three universes on the projector. Collapse the wavefunction.* 🌌
