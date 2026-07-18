from __future__ import annotations

from fastmcp import FastMCP


mcp = FastMCP(
    "Everett",
    instructions=(
        "Everett exposes fork/judge/collapse tools over parallel git worktrees. "
        "This checkpoint server provides a dummy fork tool for MCP wiring tests."
    ),
)


@mcp.tool
def fork(strategies: list[str]) -> dict:
    """Return a canned Everett fork response for MCP hello-world verification."""
    if not strategies:
        strategies = ["dummy strategy"]

    timelines = []
    for index, strategy in enumerate(strategies[:3]):
        timeline_id = chr(ord("A") + index)
        timelines.append(
            {
                "id": timeline_id,
                "branch": f"everett/{timeline_id}",
                "worktree": f"runs/demo-run/{timeline_id}",
                "strategy": strategy,
                "status": "running",
            }
        )

    return {"run_id": "demo-run", "timelines": timelines}


if __name__ == "__main__":
    mcp.run(transport="stdio", show_banner=False)
