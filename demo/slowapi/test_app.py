from fastapi.testclient import TestClient

from app import app


def test_report_is_correct():
    response = TestClient(app).get("/report")

    assert response.status_code == 200
    payload = response.json()
    assert payload["count"] == 5000
    assert payload["groups"]["0"] == sum(range(0, 5000, 10))
    assert payload["groups"]["9"] == sum(range(9, 5000, 10))
