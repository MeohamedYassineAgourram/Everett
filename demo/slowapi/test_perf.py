"""The benchmark is a test so every judged timeline writes its own perf.json."""

import json
import statistics
import time
from pathlib import Path

from fastapi.testclient import TestClient

from app import app


SAMPLES = 10
PERF_PATH = Path(__file__).with_name("perf.json")


def test_report_p50_latency():
    client = TestClient(app)
    client.get("/report")  # warm the application before taking samples
    timings = []

    for _ in range(SAMPLES):
        start = time.perf_counter()
        response = client.get("/report")
        timings.append((time.perf_counter() - start) * 1000)
        assert response.status_code == 200

    p50_ms = statistics.median(timings)
    PERF_PATH.write_text(json.dumps({"p50_ms": p50_ms, "samples": timings}, indent=2) + "\n")
    assert p50_ms < 10_000
