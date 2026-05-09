from __future__ import annotations

import sqlite3
from typing import Any

import pytest
from fastapi.testclient import TestClient

from app.data.generate import DEFAULT_OUTPUT, seed_database
from app.llm import recap as recap_module
from app.main import app

client = TestClient(app)


@pytest.fixture(autouse=True)
def ensure_seed() -> None:
    if not DEFAULT_OUTPUT.exists():
        seed_database(DEFAULT_OUTPUT)


@pytest.fixture
def fake_recap_llm(monkeypatch: pytest.MonkeyPatch):
    def _fake(system_prompt: str, user_prompt: str, *, temperature: float = 0.0) -> dict[str, Any]:
        transcript = user_prompt.split("TRANSCRIPT:\n", 1)[1].lower()
        outcome = "follow_up"
        if "ordered" in transcript or "order placed" in transcript:
            outcome = "order"
        elif "not interested" in transcript or "no interest" in transcript:
            outcome = "no_interest"
        elif "closed" in transcript or "won" in transcript:
            outcome = "closed"

        sentiment = "neutral"
        if "great" in transcript or "happy" in transcript or "excited" in transcript:
            sentiment = "positive"
        elif "frustrated" in transcript or "angry" in transcript or "upset" in transcript:
            sentiment = "negative"

        products: list[str] = []
        for family in ("anchors", "power_tools", "firestop", "measuring", "fasteners"):
            label = family.replace("_", " ")
            if family in transcript or label in transcript:
                products.append(family)

        return {
            "summary": "Discussed needs, agreed to follow up next week with quote.",
            "outcome": outcome,
            "next_action": "Send a formal quote with project pricing",
            "due_date_offset_days": 7,
            "products_mentioned": products,
            "sentiment": sentiment,
            "confidence": 0.82,
        }

    monkeypatch.setattr(recap_module, "chat_json", _fake)


def test_recap_returns_structured_fields(fake_recap_llm: None) -> None:
    response = client.post(
        "/visits/recap",
        json={
            "customer_id": "cust-0001",
            "salesperson_id": "sp-kl-central",
            "transcript": "Met with site manager. They were happy. Ordered anchors and need firestop quote.",
            "persist": False,
        },
    )
    assert response.status_code == 200, response.text
    data = response.json()
    assert data["outcome"] == "order"
    assert data["sentiment"] == "positive"
    assert "anchors" in data["products_mentioned"]
    assert "firestop" in data["products_mentioned"]
    assert data["due_date"] is not None
    assert 0.0 <= data["confidence"] <= 1.0
    assert data["persisted"] is False
    assert data["visit_id"] is None


def test_recap_persists_visit_when_requested(fake_recap_llm: None) -> None:
    response = client.post(
        "/visits/recap",
        json={
            "customer_id": "cust-0002",
            "salesperson_id": "sp-kl-central",
            "transcript": "They were not interested in fasteners right now, will revisit next quarter.",
            "persist": True,
        },
    )
    assert response.status_code == 200, response.text
    data = response.json()
    assert data["outcome"] == "no_interest"
    assert data["persisted"] is True
    assert data["visit_id"] and data["visit_id"].startswith("visit-ai-")

    with sqlite3.connect(DEFAULT_OUTPUT) as connection:
        row = connection.execute(
            "SELECT outcome, customer_id FROM visit_history WHERE id = ?",
            (data["visit_id"],),
        ).fetchone()
        last_visit = connection.execute(
            "SELECT last_visit_days FROM customers WHERE id = ?", ("cust-0002",)
        ).fetchone()
    assert row is not None
    assert row[0] == "no_interest"
    assert row[1] == "cust-0002"
    assert last_visit[0] == 0


def test_recap_404_for_unknown_customer(fake_recap_llm: None) -> None:
    response = client.post(
        "/visits/recap",
        json={
            "customer_id": "cust-9999-fake",
            "salesperson_id": "sp-kl-central",
            "transcript": "anything",
        },
    )
    assert response.status_code == 404
