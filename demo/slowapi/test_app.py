from fastapi.testclient import TestClient

from app import CUSTOMER_COUNT, ORDER_COUNT, app


def expected_total(customer_id: int) -> int:
    return sum((order_id % 97) + 3 for order_id in range(customer_id, ORDER_COUNT, CUSTOMER_COUNT))


def test_report_is_correct():
    response = TestClient(app).get("/report")

    assert response.status_code == 200
    payload = response.json()
    assert payload["count"] == CUSTOMER_COUNT
    assert payload["order_count"] == ORDER_COUNT
    assert payload["customers"]["Customer 000"] == expected_total(0)
    assert payload["customers"]["Customer 249"] == expected_total(249)
