import json
import statistics
import time
from pathlib import Path

from fastapi.testclient import TestClient

from app import app


def test_report_p50_latency():
    client = TestClient(app)
    timings = []

    client.get("/report")
    for _ in range(3):
        start = time.perf_counter()
        response = client.get("/report")
        timings.append((time.perf_counter() - start) * 1000)
        assert response.status_code == 200

    p50_ms = statistics.median(timings)
    Path(__file__).with_name("perf.json").write_text(
        json.dumps({"p50_ms": p50_ms}, indent=2) + "\n"
    )
    assert p50_ms < 5000
