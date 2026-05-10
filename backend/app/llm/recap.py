"""Turn a free-form spoken/typed visit note into a structured recap via LLM."""

from __future__ import annotations

import sqlite3
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any

from app.core.schemas import VisitRecapResponse
from app.data.generate import DEFAULT_OUTPUT, PRODUCT_FAMILIES, ensure_runtime_schema
from app.llm.client import LLMError, chat_json
from app.sentiment.service import persist_customer_sentiment, score_from_ai_sentiment

VALID_OUTCOMES = ["order", "follow_up", "no_interest", "closed"]
VALID_SENTIMENTS = ["positive", "neutral", "negative"]

SYSTEM_PROMPT = """You are RIQ, an assistant that turns a Hilti salesperson's
free-form visit note into a clean structured CRM record.

Read the transcript and output ONLY this JSON object:
{
  "summary": "<one-sentence recap, 12-25 words>",
  "outcome": "<one of: order | follow_up | no_interest | closed>",
  "next_action": "<concrete next step the salesperson should take, 6-15 words>",
  "due_date_offset_days": <integer 0-30, or null if no follow-up>,
  "products_mentioned": ["<lowercase Hilti product family>", ...],
  "sentiment": "<positive | neutral | negative>",
  "confidence": <float 0.0-1.0 reflecting how certain you are>
}

Allowed product families: anchors, power_tools, firestop, measuring, fasteners.
If a product is mentioned but doesn't fit, omit it.
Be honest about confidence. If the note is vague, use lower confidence and
sensible defaults (outcome=follow_up, sentiment=neutral). Use negative
sentiment for no-interest or unhappy visits, positive sentiment for orders,
closed-won visits, or clear follow-up interest, and neutral only for mixed
or unclear notes."""


def _normalize_outcome(value: Any) -> str:
    if isinstance(value, str):
        cleaned = value.strip().lower().replace(" ", "_").replace("-", "_")
        if cleaned in VALID_OUTCOMES:
            return cleaned
    return "follow_up"


def _normalize_sentiment(value: Any) -> str:
    if isinstance(value, str) and value.strip().lower() in VALID_SENTIMENTS:
        return value.strip().lower()
    return "neutral"


def _normalize_products(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    cleaned: list[str] = []
    for item in value:
        if not isinstance(item, str):
            continue
        candidate = item.strip().lower().replace(" ", "_").replace("-", "_")
        if candidate in PRODUCT_FAMILIES and candidate not in cleaned:
            cleaned.append(candidate)
    return cleaned


def _coerce_due_date(payload: dict[str, Any]) -> str | None:
    raw = payload.get("due_date_offset_days")
    if raw is None:
        return None
    try:
        offset = max(0, min(30, int(raw)))
    except (TypeError, ValueError):
        return None
    return (date.today() + timedelta(days=offset)).isoformat()


def _coerce_confidence(value: Any) -> float:
    try:
        confidence = float(value)
    except (TypeError, ValueError):
        return 0.5
    return max(0.0, min(1.0, confidence))


def _persist_visit(
    customer_id: str,
    salesperson_id: str,
    outcome: str,
    note: str,
    sentiment: str,
    sentiment_confidence_score: float,
    database_path: Path,
) -> tuple[str, float]:
    visit_id = f"visit-ai-{datetime.now().strftime('%H%M%S%f')[:-3]}"
    visited_at = datetime.now().isoformat(timespec="seconds")
    with sqlite3.connect(database_path) as connection:
        connection.row_factory = sqlite3.Row
        ensure_runtime_schema(connection)
        connection.execute(
            "INSERT INTO visit_history VALUES (?, ?, ?, ?, ?, ?)",
            (visit_id, customer_id, salesperson_id, visited_at, outcome, note),
        )
        connection.execute(
            "UPDATE customers SET last_visit_days = 0 WHERE id = ?",
            (customer_id,),
        )
        previous_score = persist_customer_sentiment(
            connection,
            customer_id=customer_id,
            sentiment=sentiment,
            confidence_score=sentiment_confidence_score,
            source="ai_recap",
            updated_at=visited_at,
        )
        connection.commit()
    return visit_id, previous_score


def build_recap(
    customer_id: str,
    salesperson_id: str,
    transcript: str,
    persist: bool = True,
    database_path: Path = DEFAULT_OUTPUT,
) -> VisitRecapResponse:
    user_prompt = (
        f"CUSTOMER_ID: {customer_id}\n"
        f"SALESPERSON_ID: {salesperson_id}\n"
        f"TODAY: {date.today().isoformat()}\n\n"
        f"TRANSCRIPT:\n{transcript.strip()}"
    )

    payload = chat_json(SYSTEM_PROMPT, user_prompt, temperature=0.1)

    summary = str(payload.get("summary") or "").strip()
    if not summary:
        raise LLMError("LLM recap missing 'summary'.")

    outcome = _normalize_outcome(payload.get("outcome"))
    sentiment = _normalize_sentiment(payload.get("sentiment"))
    products = _normalize_products(payload.get("products_mentioned"))
    next_action = str(payload.get("next_action") or "Follow up with the customer.").strip()
    due_date = _coerce_due_date(payload)
    confidence = _coerce_confidence(payload.get("confidence"))
    sentiment_confidence_score = score_from_ai_sentiment(sentiment, confidence)

    persisted = False
    visit_id: str | None = None
    previous_sentiment_confidence_score: float | None = None
    if persist:
        note = f"{summary} | next: {next_action}"
        if due_date:
            note += f" (by {due_date})"
        visit_id, previous_sentiment_confidence_score = _persist_visit(
            customer_id=customer_id,
            salesperson_id=salesperson_id,
            outcome=outcome,
            note=note,
            sentiment=sentiment,
            sentiment_confidence_score=sentiment_confidence_score,
            database_path=database_path,
        )
        persisted = True

    return VisitRecapResponse(
        visit_id=visit_id,
        persisted=persisted,
        summary=summary,
        outcome=outcome,
        next_action=next_action,
        due_date=due_date,
        products_mentioned=products,
        sentiment=sentiment,
        confidence=confidence,
        previous_sentiment_confidence_score=previous_sentiment_confidence_score,
        sentiment_confidence_score=sentiment_confidence_score,
        raw_transcript=transcript.strip(),
    )
