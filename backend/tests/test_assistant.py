from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def _ask(question: str, current_customer_id: str | None = None) -> dict:
    response = client.post(
        "/assistant/ask",
        json={
            "salesperson_id": "sp-kl-central",
            "question": question,
            "current_customer_id": current_customer_id,
        },
    )
    assert response.status_code == 200, response.text
    return response.json()


def test_assistant_next_stop_intent() -> None:
    payload = _ask("What's my next stop?")
    assert payload["intent"] == "next_stop"
    assert payload["related_customer_id"] is not None
    assert "km" in payload["answer"].lower() or "min" in payload["answer"].lower()


def test_assistant_distance_intent() -> None:
    payload = _ask("How far to the next customer?")
    assert payload["intent"] == "distance"
    assert "km" in payload["answer"].lower()


def test_assistant_why_intent_uses_score() -> None:
    payload = _ask("Why this customer?")
    assert payload["intent"] == "why"
    assert "/100" in payload["answer"]


def test_assistant_summary_includes_optimization_uplift() -> None:
    payload = _ask("Summarise today's plan.")
    assert payload["intent"] == "summary"
    answer = payload["answer"]
    assert "RM" in answer
    assert "%" in answer
    assert "evaluated" in answer


def test_assistant_best_stop_intent_picks_highest_value() -> None:
    payload = _ask("What's the highest-value stop today?")
    assert payload["intent"] == "best_stop"
    assert payload["related_customer_id"] is not None


def test_assistant_fallback_offers_suggestions() -> None:
    payload = _ask("Will it rain today?")
    assert payload["intent"] == "fallback"
    assert len(payload["suggestions"]) > 0
