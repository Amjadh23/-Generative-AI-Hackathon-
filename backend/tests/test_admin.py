import sqlite3

from fastapi.testclient import TestClient

from app.data.generate import DEFAULT_OUTPUT, ensure_runtime_schema, seed_database
from app.main import app

client = TestClient(app)


def test_admin_dashboard_returns_reps_and_rankings() -> None:
    if not DEFAULT_OUTPUT.exists():
        seed_database(DEFAULT_OUTPUT)

    response = client.get("/admin/dashboard")
    assert response.status_code == 200
    payload = response.json()
    assert "reps" in payload
    assert "rankings" in payload
    assert "customers_for_assignment" in payload
    assert len(payload["reps"]) >= 1
    assert len(payload["rankings"]) >= 1
    assert "recap_impact" in payload
    assert "recent_ai_recaps" in payload
    assert isinstance(payload["recent_ai_recaps"], list)
    assert "recap_monitor_note" in payload
    ri = payload["recap_impact"]
    assert ri["avg_before"] <= ri["avg_after"]
    assert "spotlight_before" in ri
    first = payload["rankings"][0]
    assert "future_potential_index" in first
    assert "future_potential_baseline" in first
    assert float(first["future_potential_baseline"]) <= float(first["future_potential_index"])
    assert "visit_signal" in first


def test_admin_assign_customer() -> None:
    if not DEFAULT_OUTPUT.exists():
        seed_database(DEFAULT_OUTPUT)

    with client:
        resp = client.get("/admin/dashboard")
        cust = resp.json()["customers_for_assignment"][0]
        target_sp = "sp-kl-central"
        if cust["assigned_salesperson_id"] == target_sp:
            alt = next(
                r
                for r in resp.json()["reps"]
                if r["salesperson_id"] != target_sp
            )
            target_sp = alt["salesperson_id"]

        patch = client.patch(
            f"/admin/customers/{cust['customer_id']}/assignment",
            json={"salesperson_id": target_sp},
        )
        assert patch.status_code == 200, patch.text
        body = patch.json()
        assert body["customer_id"] == cust["customer_id"]
        assert body["salesperson_id"] == target_sp

        revert = client.patch(
            f"/admin/customers/{cust['customer_id']}/assignment",
            json={"salesperson_id": cust["assigned_salesperson_id"]},
        )
        assert revert.status_code == 200


def test_admin_dashboard_spotlights_latest_sentiment_confidence() -> None:
    if not DEFAULT_OUTPUT.exists():
        seed_database(DEFAULT_OUTPUT)
    with sqlite3.connect(DEFAULT_OUTPUT) as connection:
        ensure_runtime_schema(connection)
        previous_last_visit_days = connection.execute(
            "SELECT last_visit_days FROM customers WHERE id = ?",
            ("cust-0004",),
        ).fetchone()[0]
        connection.execute("DELETE FROM customer_sentiment")
        connection.commit()

    sentiment_response = client.post(
        "/visits/sentiment",
        json={
            "customer_id": "cust-0004",
            "salesperson_id": "sp-kl-central",
            "sentiment": "negative",
        },
    )
    assert sentiment_response.status_code == 201, sentiment_response.text
    visit_id = sentiment_response.json()["visit_id"]

    try:
        dashboard_response = client.get("/admin/dashboard")
        assert dashboard_response.status_code == 200
        impact = dashboard_response.json()["recap_impact"]
        assert impact["spotlight_confidence_before"] == 50.0
        assert impact["spotlight_confidence_after"] == 30.0
        assert impact["spotlight_sentiment"] == "negative"
        assert impact["spotlight_sentiment_source"] == "quick_button"
    finally:
        with sqlite3.connect(DEFAULT_OUTPUT) as connection:
            connection.execute("DELETE FROM customer_sentiment WHERE customer_id = ?", ("cust-0004",))
            connection.execute("DELETE FROM visit_history WHERE id = ?", (visit_id,))
            connection.execute(
                "UPDATE customers SET last_visit_days = ? WHERE id = ?",
                (previous_last_visit_days, "cust-0004"),
            )
            connection.commit()
