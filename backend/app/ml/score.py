from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from pathlib import Path

from app.data.generate import DEFAULT_OUTPUT


@dataclass(frozen=True)
class CustomerScore:
    customer_id: str
    score: float
    expected_return_rm: float
    reason: str
    contributions: dict[str, float]


def normalize(value: float, maximum: float) -> float:
    if maximum <= 0:
        return 0
    return min(1, max(0, value / maximum))


def score_customer_row(row: sqlite3.Row) -> CustomerScore:
    priority_component = normalize(row["priority"], 5)
    recency_component = normalize(row["last_visit_days"], 120)
    pipeline_component = normalize(row["open_pipeline_rm"], 18000)
    order_value_component = normalize(row["avg_order_value_rm"], 16000)
    reorder_component = min(1, max(0, row["reorder_probability"]))

    contributions = {
        "priority": priority_component * 0.22,
        "recency": recency_component * 0.18,
        "pipeline": pipeline_component * 0.22,
        "order_value": order_value_component * 0.18,
        "reorder_probability": reorder_component * 0.20,
    }
    score = round(sum(contributions.values()) * 100, 2)
    expected_return = round(
        (row["avg_order_value_rm"] * 0.55 + row["open_pipeline_rm"] * 0.45)
        * (0.45 + reorder_component * 0.65)
        * (0.75 + row["priority"] / 10),
        2,
    )

    reason = (
        f"{row['last_visit_days']} days since last visit, "
        f"{row['reorder_probability']:.0%} reorder likelihood, "
        f"RM{expected_return:,.0f} expected return."
    )

    return CustomerScore(
        customer_id=row["id"],
        score=score,
        expected_return_rm=expected_return,
        reason=reason,
        contributions={key: round(value, 4) for key, value in contributions.items()},
    )


def score_customer(customer_id: str, database_path: Path = DEFAULT_OUTPUT) -> CustomerScore:
    with sqlite3.connect(database_path) as connection:
        connection.row_factory = sqlite3.Row
        row = connection.execute("SELECT * FROM customers WHERE id = ?", (customer_id,)).fetchone()

    if row is None:
        raise ValueError(f"Customer not found: {customer_id}")

    return score_customer_row(row)


def top_customers_for_salesperson(
    salesperson_id: str,
    limit: int = 15,
    database_path: Path = DEFAULT_OUTPUT,
) -> list[CustomerScore]:
    with sqlite3.connect(database_path) as connection:
        connection.row_factory = sqlite3.Row
        rows = connection.execute(
            """
            SELECT *
            FROM customers
            WHERE assigned_salesperson_id = ?
            """,
            (salesperson_id,),
        ).fetchall()

    scored = [score_customer_row(row) for row in rows]
    return sorted(scored, key=lambda customer: customer.score, reverse=True)[:limit]
