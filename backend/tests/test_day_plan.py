from fastapi.testclient import TestClient

from app.main import app


def test_day_plan_contract() -> None:
    client = TestClient(app)

    response = client.get("/salespeople/sp-kl-central/day-plan?date=2026-05-09")

    assert response.status_code == 200
    payload = response.json()
    assert payload["salesperson_id"] == "sp-kl-central"
    assert payload["date"] == "2026-05-09"
    assert payload["total_expected_return_rm"] > 0
    assert len(payload["stops"]) == 8
    assert payload["stops"][0]["reason"]
    assert payload["stops"][0]["focus"]
    assert payload["stops"][0]["segment"]

    summary = payload["optimization_summary"]
    assert summary is not None
    assert summary["routes_evaluated"] >= 40000
    assert summary["baseline_expected_return_rm"] > 0
    assert summary["value_gain_rm"] > 0
    assert summary["value_uplift_pct"] > 0


def test_day_plan_accepts_stop_count_override() -> None:
    client = TestClient(app)

    response = client.get("/salespeople/sp-kl-central/day-plan?date=2026-05-09&max_stops=5")

    assert response.status_code == 200
    payload = response.json()
    assert len(payload["stops"]) == 5
    assert [stop["sequence"] for stop in payload["stops"]] == [1, 2, 3, 4, 5]

    summary = payload["optimization_summary"]
    assert summary is not None
    assert summary["routes_evaluated"] >= 120
