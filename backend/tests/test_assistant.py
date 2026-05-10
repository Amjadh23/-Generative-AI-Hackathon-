from __future__ import annotations

import json
from typing import Any

import pytest
from fastapi.testclient import TestClient

from app.assistant import router as assistant_router
from app.main import app

client = TestClient(app)


@pytest.fixture
def captured_calls() -> list[dict[str, Any]]:
    return []


@pytest.fixture
def fake_llm(monkeypatch: pytest.MonkeyPatch, captured_calls: list[dict[str, Any]]):
    """Replace ``chat_json`` so tests don't need Ollama running.

    The fake parses the embedded fact sheet to build deterministic answers and
    records every call so we can assert prompt content too.
    """

    def _fake(system_prompt: str, user_prompt: str, *, temperature: float = 0.0) -> dict[str, Any]:
        captured_calls.append(
            {"system": system_prompt, "user": user_prompt, "temperature": temperature}
        )
        facts_blob = user_prompt.split("FACTS (JSON, the only source of truth", 1)[1]
        facts_json = facts_blob.split("\n", 1)[1]
        facts_json = facts_json.split("USER QUESTION", 1)[0].strip(": -\n")
        if facts_json.endswith("USER"):
            facts_json = facts_json[:-4]
        end_index = facts_json.rfind("}")
        facts = json.loads(facts_json[: end_index + 1])

        question = user_prompt.split("USER QUESTION:\n", 1)[1].strip().lower()
        first_stop = facts["stops"][0] if facts.get("stops") else None

        if "how far" in question or "distance" in question:
            return {
                "answer": f"{first_stop['distance_from_previous_km']} km away.",
                "intent": "distance",
                "related_customer_id": first_stop["customer_id"],
                "suggestions": ["Why this customer?", "Next stop?", "Focus?"],
            }
        if "next" in question:
            return {
                "answer": f"Next is {first_stop['customer_name']} ({first_stop['eta_minutes']} min away).",
                "intent": "next_stop",
                "related_customer_id": first_stop["customer_id"],
                "suggestions": ["Why this customer?", "How far?", "Focus tips?"],
            }
        if "summarise" in question or "summary" in question:
            opt = facts.get("optimization", {})
            return {
                "answer": (
                    f"{facts['total_stops']} stops, RM{facts['total_expected_return_rm']:,} expected, "
                    f"+{opt.get('value_uplift_pct', 0):.0f}% vs baseline, "
                    f"picked from {opt.get('routes_evaluated', 0)} routes."
                ),
                "intent": "summary",
                "related_customer_id": None,
                "suggestions": ["Next stop?", "Best stop?", "List all stops"],
            }
        if "why" in question:
            focused = facts.get("focused_customer", first_stop)
            return {
                "answer": f"{focused['customer_name']} scored {focused['score']}/100.",
                "intent": "why",
                "related_customer_id": focused["customer_id"],
                "suggestions": ["What to focus on?", "Next stop?", "How far?"],
            }
        if "best" in question or "highest" in question:
            best = max(facts["stops"], key=lambda stop: stop["expected_return_rm"])
            return {
                "answer": (
                    f"Highest value today is {best['customer_name']} at "
                    f"RM{best['expected_return_rm']:,}."
                ),
                "intent": "best_stop",
                "related_customer_id": best["customer_id"],
                "suggestions": ["Why?", "How far?", "Focus?"],
            }
        return {
            "answer": "I can help with stops, distances, and focus tips.",
            "intent": "fallback",
            "related_customer_id": None,
            "suggestions": ["Next stop?", "Summary?", "Why this customer?"],
        }

    monkeypatch.setattr(assistant_router, "chat_json", _fake)
    return captured_calls


def _ask(question: str, current_customer_id: str | None = None) -> dict[str, Any]:
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


def test_assistant_calls_llm_with_grounded_facts(fake_llm: list[dict[str, Any]]) -> None:
    payload = _ask("What's my next stop?")
    assert payload["intent"] == "next_stop"
    assert payload["related_customer_id"] is not None
    assert len(fake_llm) == 1
    user_prompt = fake_llm[0]["user"]
    assert "FACTS" in user_prompt
    assert "stops" in user_prompt
    assert "salesperson_id" in user_prompt


def test_assistant_distance_intent(fake_llm: list[dict[str, Any]]) -> None:
    payload = _ask("How far is the next customer?")
    assert payload["intent"] == "distance"
    assert "km" in payload["answer"].lower()


def test_assistant_summary_includes_optimization_uplift(fake_llm: list[dict[str, Any]]) -> None:
    payload = _ask("Summarise today's plan.")
    assert payload["intent"] == "summary"
    assert "%" in payload["answer"]
    assert "RM" in payload["answer"]


def test_assistant_best_stop_picks_highest_value(fake_llm: list[dict[str, Any]]) -> None:
    payload = _ask("Highest-value stop today?")
    assert payload["intent"] == "best_stop"
    assert payload["related_customer_id"] is not None


def test_assistant_why_uses_focused_customer(fake_llm: list[dict[str, Any]]) -> None:
    payload = _ask("Why this customer?", current_customer_id="cust-0001")
    assert payload["intent"] == "why"
    assert "/100" in payload["answer"]


def test_assistant_fallback_provides_suggestions(fake_llm: list[dict[str, Any]]) -> None:
    payload = _ask("Will it rain today?")
    assert payload["intent"] == "fallback"
    assert len(payload["suggestions"]) > 0


def test_assistant_rejects_invalid_related_customer(
    monkeypatch: pytest.MonkeyPatch, fake_llm: list[dict[str, Any]]
) -> None:
    """If the LLM hallucinates a customer_id that isn't in the plan, drop it."""

    def _hallucinating(*_: Any, **__: Any) -> dict[str, Any]:
        return {
            "answer": "Sure, here's the next stop.",
            "intent": "next_stop",
            "related_customer_id": "cust-9999-fake",
            "suggestions": ["Why?", "Focus?"],
        }

    monkeypatch.setattr(assistant_router, "chat_json", _hallucinating)
    payload = _ask("Next stop?")
    assert payload["related_customer_id"] is None
