from fastapi.testclient import TestClient

from app.data.generate import DEFAULT_OUTPUT, seed_database
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
