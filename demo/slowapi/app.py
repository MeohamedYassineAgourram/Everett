from __future__ import annotations

from fastapi import FastAPI


app = FastAPI()


@app.get("/report")
def report() -> dict:
    rows = [{"group": i % 10, "value": i} for i in range(5000)]
    totals = {}
    for row in rows:
        group = row["group"]
        total = 0
        for candidate in rows:
            if candidate["group"] == group:
                total += candidate["value"]
        totals[group] = total
    return {"groups": totals, "count": len(rows)}
