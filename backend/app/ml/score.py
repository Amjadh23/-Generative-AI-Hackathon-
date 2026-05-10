from __future__ import annotations

import sqlite3
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from app.data.generate import DEFAULT_OUTPUT
from app.ml.prioritization.engine import predict_with_explanations, recommended_action_for_class


@dataclass(frozen=True)
class CustomerScore:
    customer_id: str
    score: float
    visit_likelihood_score: float
    priority_class: str
    recommended_action: str
    expected_return_rm: float
    reason: str
    contributions: dict[str, float]
    top_reasons: list[str] = field(default_factory=list)
    xgboost_explanation_payload: dict[str, Any] | None = None


def normalize(value: float, maximum: float) -> float:
    if maximum <= 0:
        return 0
    return min(1, max(0, value / maximum))


def _expected_return_rm_row(row: sqlite3.Row, visit_likelihood: float) -> float:
    """Deal value is a feature elsewhere; keep a transparent business estimate (no CRM `priority`)."""
    reorder_component = min(1, max(0, row["reorder_probability"]))
    base = (row["avg_order_value_rm"] * 0.55 + row["open_pipeline_rm"] * 0.45) * (
        0.45 + reorder_component * 0.65
    )
    lift = 0.82 + 0.18 * visit_likelihood
    return round(float(base * lift), 2)


def _heuristic_score(row: sqlite3.Row, visit_likelihood: float) -> CustomerScore:
    """Fallback when XGBoost artifacts are missing."""
    recency_component = normalize(row["last_visit_days"], 120)
    pipeline_component = normalize(row["open_pipeline_rm"], 18000)
    order_value_component = normalize(row["avg_order_value_rm"], 16000)
    reorder_component = min(1, max(0, row["reorder_probability"]))
    contributions = {
        "last_visit_days": recency_component * 0.24,
        "open_pipeline_rm": pipeline_component * 0.26,
        "avg_order_value_rm": order_value_component * 0.22,
        "reorder_probability": reorder_component * 0.28,
    }
    score = round(visit_likelihood * 100, 2)
    expected_return = _expected_return_rm_row(row, visit_likelihood)
    reason = (
        f"{row['last_visit_days']} days since last visit, "
        f"{row['reorder_probability']:.0%} reorder likelihood, "
        f"RM{expected_return:,.0f} expected return."
    )
    pc = "High" if visit_likelihood >= 0.7 else "Medium" if visit_likelihood >= 0.4 else "Low"
    return CustomerScore(
        customer_id=row["id"],
        score=score,
        visit_likelihood_score=round(visit_likelihood, 4),
        priority_class=pc,
        recommended_action=recommended_action_for_class(pc),
        expected_return_rm=expected_return,
        reason=reason,
        contributions={key: round(value, 4) for key, value in contributions.items()},
        top_reasons=[],
        xgboost_explanation_payload=None,
    )


def score_customer_row(
    row: sqlite3.Row,
    database_path: Path = DEFAULT_OUTPUT,
    connection: sqlite3.Connection | None = None,
) -> CustomerScore:
    own_connection = False
    if connection is None:
        own_connection = True
        connection = sqlite3.connect(database_path)
        connection.row_factory = sqlite3.Row

    try:
        pri = predict_with_explanations(row, connection, database_path)
        if pri is None:
            blended = (
                normalize(row["last_visit_days"], 120) * 0.22
                + normalize(row["open_pipeline_rm"], 18000) * 0.24
                + normalize(row["avg_order_value_rm"], 16000) * 0.18
                + min(1, max(0, row["reorder_probability"])) * 0.36
            )
            return _heuristic_score(row, blended)

        visit_score = float(pri["visit_likelihood_score"])
        top = pri.get("xgboost_explanation_payload") or {}
        reasons_list = top.get("top_priority_reasons") or []
        contribs = {
            str(r["feature"]): float(r["shap_value"]) for r in reasons_list if r.get("shap_value") is not None
        }
        expected_return = _expected_return_rm_row(row, visit_score)
        reason_bits = pri.get("top_reasons") or []
        reason = (
            reason_bits[0]
            if reason_bits
            else (
                f"Visit likelihood {visit_score:.0%}, {row['last_visit_days']} days since visit, "
                f"RM{expected_return:,.0f} expected return."
            )
        )
        return CustomerScore(
            customer_id=row["id"],
            score=round(visit_score * 100, 2),
            visit_likelihood_score=visit_score,
            priority_class=str(pri["priority_class"]),
            recommended_action=str(pri.get("recommended_action") or recommended_action_for_class(str(pri["priority_class"]))),
            expected_return_rm=expected_return,
            reason=reason,
            contributions=contribs,
            top_reasons=list(reason_bits),
            xgboost_explanation_payload=pri.get("xgboost_explanation_payload"),
        )
    finally:
        if own_connection:
            connection.close()


def score_customer(customer_id: str, database_path: Path = DEFAULT_OUTPUT) -> CustomerScore:
    with sqlite3.connect(database_path) as connection:
        connection.row_factory = sqlite3.Row
        row = connection.execute("SELECT * FROM customers WHERE id = ?", (customer_id,)).fetchone()

    if row is None:
        raise ValueError(f"Customer not found: {customer_id}")

    return score_customer_row(row, database_path=database_path)


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
        scored = [score_customer_row(row, database_path=database_path, connection=connection) for row in rows]
    return sorted(scored, key=lambda customer: customer.score, reverse=True)[:limit]
