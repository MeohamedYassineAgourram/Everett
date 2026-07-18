"""A deliberately slow reporting endpoint used by the Everett demo.

The implementation intentionally uses an N+1 query pattern over 50k orders.
"""

from __future__ import annotations

import sqlite3

from fastapi import FastAPI


CUSTOMER_COUNT = 250
ORDER_COUNT = 50_000


def create_database() -> sqlite3.Connection:
    """Create a deterministic 50k-row SQLite fixture for the report."""
    connection = sqlite3.connect(":memory:", check_same_thread=False)
    connection.execute("CREATE TABLE customers (id INTEGER PRIMARY KEY, name TEXT)")
    connection.execute(
        "CREATE TABLE orders (id INTEGER PRIMARY KEY, customer_id INTEGER, amount INTEGER)"
    )
    connection.executemany(
        "INSERT INTO customers (id, name) VALUES (?, ?)",
        ((customer_id, f"Customer {customer_id:03d}") for customer_id in range(CUSTOMER_COUNT)),
    )
    connection.executemany(
        "INSERT INTO orders (id, customer_id, amount) VALUES (?, ?, ?)",
        (
            (order_id, order_id % CUSTOMER_COUNT, (order_id % 97) + 3)
            for order_id in range(ORDER_COUNT)
        ),
    )
    connection.commit()
    return connection


database = create_database()
app = FastAPI()


@app.get("/report")
def report() -> dict:
    """Return per-customer sales totals using a deliberately slow N+1 query."""
    customers = database.execute("SELECT id, name FROM customers ORDER BY id").fetchall()
    totals: dict[str, int] = {}
    for customer_id, name in customers:
        # Intentional demo bug: 250 full-table aggregate queries, one per customer.
        total = database.execute(
            "SELECT COALESCE(SUM(amount), 0) FROM orders WHERE customer_id = ?",
            (customer_id,),
        ).fetchone()[0]
        totals[name] = total

    return {"customers": totals, "count": len(customers), "order_count": ORDER_COUNT}
