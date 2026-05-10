"""Persist per-customer visit sentiment confidence."""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

from app.data.generate import DEFAULT_OUTPUT, ensure_runtime_schema

INITIAL_CONFIDENCE_SCORE = 0.5


@dataclass(frozen=True)
class ManualSentimentOption:
    label: str
    score: float
    outcome: str


MANUAL_SENTIMENT_OPTIONS: dict[str, ManualSentimentOption] = {
    "very_negative": ManualSentimentOption("Very negative", 0.1, "no_interest"),
    "negative": ManualSentimentOption("Negative", 0.3, "no_interest"),
    "neutral": ManualSentimentOption("Neutral", 0.5, "follow_up"),
    "positive": ManualSentimentOption("Positive", 0.7, "follow_up"),
    "very_positive": ManualSentimentOption("Very positive", 0.9, "order"),
}


def normalize_sentiment_key(value: Any) -> str:
    if isinstance(value, str):
        return value.strip().lower().replace(" ", "_").replace("-", "_")
    return ""


def clamp_score(value: float) -> float:
    return max(0.0, min(1.0, value))


def score_from_ai_sentiment(sentiment: str, confidence: float) -> float:
    """Turn 3-class AI sentiment and model certainty into a customer confidence score."""
    certainty = clamp_score(confidence)
    normalized = normalize_sentiment_key(sentiment)
    if normalized == "positive":
        return round(INITIAL_CONFIDENCE_SCORE + (0.4 * certainty), 3)
    if normalized == "negative":
        return round(INITIAL_CONFIDENCE_SCORE - (0.4 * certainty), 3)
    return INITIAL_CONFIDENCE_SCORE


def read_customer_sentiment(
    connection: sqlite3.Connection,
    customer_id: str,
) -> sqlite3.Row | None:
    ensure_runtime_schema(connection)
    return connection.execute(
        """
        SELECT initial_confidence_score, current_confidence_score,
               sentiment, source, updated_at
        FROM customer_sentiment
        WHERE customer_id = ?
        """,
        (customer_id,),
    ).fetchone()


def persist_customer_sentiment(
    connection: sqlite3.Connection,
    *,
    customer_id: str,
    sentiment: str,
    confidence_score: float,
    source: str,
    updated_at: str | None = None,
) -> float:
    """Update the current confidence score and return the previous score."""
    ensure_runtime_schema(connection)
    timestamp = updated_at or datetime.now().isoformat(timespec="seconds")
    current = read_customer_sentiment(connection, customer_id)
    previous_score = (
        float(current["current_confidence_score"])
        if current is not None
        else INITIAL_CONFIDENCE_SCORE
    )
    if current is None:
        connection.execute(
            """
            INSERT INTO customer_sentiment (
                customer_id, initial_confidence_score, current_confidence_score,
                sentiment, source, updated_at
            )
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                customer_id,
                INITIAL_CONFIDENCE_SCORE,
                clamp_score(confidence_score),
                normalize_sentiment_key(sentiment),
                source,
                timestamp,
            ),
        )
    else:
        connection.execute(
            """
            UPDATE customer_sentiment
            SET current_confidence_score = ?,
                sentiment = ?,
                source = ?,
                updated_at = ?
            WHERE customer_id = ?
            """,
            (
                clamp_score(confidence_score),
                normalize_sentiment_key(sentiment),
                source,
                timestamp,
                customer_id,
            ),
        )
    return previous_score


def log_manual_sentiment_visit(
    *,
    customer_id: str,
    salesperson_id: str,
    sentiment: str,
    database_path: Path = DEFAULT_OUTPUT,
) -> dict[str, object]:
    option_key = normalize_sentiment_key(sentiment)
    option = MANUAL_SENTIMENT_OPTIONS.get(option_key)
    if option is None:
        allowed = ", ".join(MANUAL_SENTIMENT_OPTIONS)
        raise ValueError(f"Unsupported sentiment '{sentiment}'. Use one of: {allowed}.")

    visit_id = f"visit-sentiment-{datetime.now().strftime('%H%M%S%f')[:-3]}"
    visited_at = datetime.now().isoformat(timespec="seconds")
    note = f"Quick visit sentiment: {option.label} | confidence: {round(option.score * 100)}%"

    with sqlite3.connect(database_path) as connection:
        connection.row_factory = sqlite3.Row
        ensure_runtime_schema(connection)
        customer = connection.execute(
            "SELECT id FROM customers WHERE id = ?",
            (customer_id,),
        ).fetchone()
        if customer is None:
            raise ValueError("Customer not found")

        salesperson = connection.execute(
            "SELECT id FROM salespeople WHERE id = ?",
            (salesperson_id,),
        ).fetchone()
        if salesperson is None:
            raise ValueError("Salesperson not found")

        connection.execute(
            "INSERT INTO visit_history VALUES (?, ?, ?, ?, ?, ?)",
            (
                visit_id,
                customer_id,
                salesperson_id,
                visited_at,
                option.outcome,
                note,
            ),
        )
        connection.execute(
            "UPDATE customers SET last_visit_days = 0 WHERE id = ?",
            (customer_id,),
        )
        previous_score = persist_customer_sentiment(
            connection,
            customer_id=customer_id,
            sentiment=option_key,
            confidence_score=option.score,
            source="quick_button",
            updated_at=visited_at,
        )
        connection.commit()

    return {
        "visit_id": visit_id,
        "status": "logged",
        "sentiment": option_key,
        "sentiment_label": option.label,
        "outcome": option.outcome,
        "previous_sentiment_confidence_score": previous_score,
        "sentiment_confidence_score": option.score,
    }
