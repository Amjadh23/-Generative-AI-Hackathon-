"""Manager / admin aggregates: rep overview and future-potential rankings."""

from __future__ import annotations

import sqlite3
from datetime import date, datetime
from pathlib import Path

from app.data.generate import DEFAULT_OUTPUT, ensure_runtime_schema
from app.ml.score import score_customer_row, top_customers_for_salesperson

OUTCOME_WEIGHT: dict[str, float] = {
    "order": 14.0,
    "closed": 12.0,
    "follow_up": 7.0,
    "no_interest": -10.0,
}


def _visit_signal(connection: sqlite3.Connection, customer_id: str) -> tuple[float, str | None]:
    """Return average weighted outcome momentum and last visit outcome from recent history."""
    rows = connection.execute(
        """
        SELECT id, outcome, notes
        FROM visit_history
        WHERE customer_id = ?
        ORDER BY visited_at DESC
        LIMIT 6
        """,
        (customer_id,),
    ).fetchall()
    if not rows:
        return 0.0, None

    total = 0.0
    for row in rows:
        weight = OUTCOME_WEIGHT.get(row["outcome"], 0.0)
        notes = row["notes"] or ""
        if "| next:" in notes:
            weight += 4.0
        visit_id = str(row["id"])
        if visit_id.startswith("visit-ai-") or visit_id.startswith("visit-sentiment-"):
            weight += 2.5
        total += weight

    avg = total / len(rows)
    last = rows[0]["outcome"] if rows else None
    return round(avg, 2), last


def _future_potential_index(base_score: float, visit_avg_signal: float) -> float:
    """Blend static scoring with recent visit / recap trajectory (0–100)."""
    trajectory = max(0.0, min(40.0, visit_avg_signal + 20.0))
    blended = base_score * 0.62 + trajectory * 0.95
    return round(max(0.0, min(100.0, blended)), 1)


def _future_potential_baseline(base_score: float) -> float:
    """Territory + CRM alone — before recent visits and recaps shape the story (0–100)."""
    return round(max(0.0, min(100.0, base_score * 0.58)), 1)


_SATISFIED_OUTCOMES = frozenset({"order", "closed", "follow_up"})
def _split_ai_recap_note(notes: str | None) -> tuple[str, str]:
    """Notes from `build_recap` look like: `{summary} | next: {next_action} (by YYYY-MM-DD)`."""
    raw = (notes or "").strip()
    if " | next:" not in raw:
        return raw, ""
    summary, rest = raw.split(" | next:", 1)
    next_action = rest.split("(by ", 1)[0].strip()
    return summary.strip(), next_action


def _interest_label(outcome: str | None) -> tuple[str, bool]:
    """Manager-facing label and whether to treat the account as an active opportunity."""
    o = (outcome or "").strip().lower()
    if o == "order":
        return "Order / strong interest", True
    if o == "closed":
        return "Closed won", True
    if o == "follow_up":
        return "Interested — follow up", True
    if o == "no_interest":
        return "Not interested", False
    return o or "Unknown", False


def build_manager_dashboard(
    database_path: Path = DEFAULT_OUTPUT,
    ranking_limit: int = 50,
) -> dict[str, object]:
    with sqlite3.connect(database_path) as connection:
        connection.row_factory = sqlite3.Row
        ensure_runtime_schema(connection)

        salespeople = connection.execute(
            """
            SELECT s.id, s.name, s.territory_id, t.name AS territory_name
            FROM salespeople s
            JOIN territories t ON t.id = s.territory_id
            ORDER BY s.name
            """
        ).fetchall()

        rep_summaries: list[dict[str, object]] = []
        for sp in salespeople:
            sp_id = sp["id"]
            count_row = connection.execute(
                "SELECT COUNT(*) AS c FROM customers WHERE assigned_salesperson_id = ?",
                (sp_id,),
            ).fetchone()
            customer_count = int(count_row["c"]) if count_row else 0

            scored = top_customers_for_salesperson(sp_id, limit=8, database_path=database_path)
            top_return = sum(s.expected_return_rm for s in scored)

            ai_row = connection.execute(
                """
                SELECT COUNT(*) AS c
                FROM visit_history vh
                JOIN customers c ON c.id = vh.customer_id
                WHERE c.assigned_salesperson_id = ?
                  AND (vh.id LIKE 'visit-ai-%' OR vh.id LIKE 'visit-sentiment-%')
                """,
                (sp_id,),
            ).fetchone()
            ai_recaps = int(ai_row["c"]) if ai_row else 0

            warm_row = connection.execute(
                """
                SELECT COUNT(*) AS c
                FROM visit_history vh
                JOIN customers c ON c.id = vh.customer_id
                WHERE c.assigned_salesperson_id = ?
                  AND (vh.id LIKE 'visit-ai-%' OR vh.id LIKE 'visit-sentiment-%')
                  AND vh.outcome IN ('order', 'follow_up', 'closed')
                  AND substr(vh.visited_at, 1, 10) >= date('now', '-30 days')
                """,
                (sp_id,),
            ).fetchone()
            interested_recaps_30d = int(warm_row["c"]) if warm_row else 0

            fu_row = connection.execute(
                """
                SELECT COUNT(*) AS c
                FROM visit_history vh
                JOIN customers c ON c.id = vh.customer_id
                WHERE c.assigned_salesperson_id = ?
                  AND vh.outcome = 'follow_up'
                  AND vh.visited_at >= date('now', '-21 days')
                """,
                (sp_id,),
            ).fetchone()
            active_follow = int(fu_row["c"]) if fu_row else 0

            rep_summaries.append(
                {
                    "salesperson_id": sp_id,
                    "name": sp["name"],
                    "territory_id": sp["territory_id"],
                    "territory_name": sp["territory_name"],
                    "customer_count": customer_count,
                    "today_top_expected_return_rm": round(top_return, 2),
                    "ai_recap_visit_count": ai_recaps,
                    "interested_recaps_30d": interested_recaps_30d,
                    "active_follow_ups": active_follow,
                }
            )

        customers = connection.execute(
            """
            SELECT c.id, c.name, c.segment, c.territory_id, t.name AS territory_name,
                   c.assigned_salesperson_id, s.name AS salesperson_name,
                   c.lat, c.lng,
                   c.last_visit_days, c.priority, c.avg_order_value_rm, c.open_pipeline_rm,
                   c.reorder_probability,
                   cs.initial_confidence_score AS sentiment_initial_confidence_score,
                   cs.current_confidence_score AS sentiment_confidence_score,
                   cs.sentiment AS sentiment_label,
                   cs.source AS sentiment_source,
                   cs.updated_at AS sentiment_updated_at
            FROM customers c
            JOIN territories t ON t.id = c.territory_id
            JOIN salespeople s ON s.id = c.assigned_salesperson_id
            LEFT JOIN customer_sentiment cs ON cs.customer_id = c.id
            """
        ).fetchall()

        raw_rankings: list[dict[str, object]] = []
        for row in customers:
            scored = score_customer_row(row, database_path=database_path, connection=connection)
            visit_signal, last_outcome = _visit_signal(connection, row["id"])
            baseline = _future_potential_baseline(scored.score)
            fut = _future_potential_index(scored.score, visit_signal)
            raw_rankings.append(
                {
                    "customer_id": row["id"],
                    "customer_name": row["name"],
                    "segment": row["segment"],
                    "territory_id": row["territory_id"],
                    "territory_name": row["territory_name"],
                    "assigned_salesperson_id": row["assigned_salesperson_id"],
                    "assigned_salesperson_name": row["salesperson_name"],
                    "routeiq_score": scored.score,
                    "expected_return_rm": scored.expected_return_rm,
                    "last_visit_days": row["last_visit_days"],
                    "visit_signal": visit_signal,
                    "last_visit_outcome": last_outcome,
                    "future_potential_baseline": baseline,
                    "future_potential_index": fut,
                    "sentiment_initial_confidence_score": row["sentiment_initial_confidence_score"]
                    if row["sentiment_initial_confidence_score"] is not None
                    else 0.5,
                    "sentiment_confidence_score": row["sentiment_confidence_score"]
                    if row["sentiment_confidence_score"] is not None
                    else 0.5,
                    "sentiment_label": row["sentiment_label"] or "neutral",
                    "sentiment_source": row["sentiment_source"] or "initial",
                    "sentiment_updated_at": row["sentiment_updated_at"],
                }
            )

        raw_rankings.sort(key=lambda item: float(item["future_potential_index"]), reverse=True)
        rankings = raw_rankings[:ranking_limit]

        baselines = [float(r["future_potential_baseline"]) for r in raw_rankings]
        futures = [float(r["future_potential_index"]) for r in raw_rankings]
        avg_before = round(sum(baselines) / len(baselines), 1) if baselines else 0.0
        avg_after = round(sum(futures) / len(futures), 1) if futures else 0.0

        latest_sentiment = connection.execute(
            """
            SELECT cs.customer_id, c.name AS customer_name,
                   cs.initial_confidence_score, cs.current_confidence_score,
                   cs.sentiment, cs.source, cs.updated_at
            FROM customer_sentiment cs
            JOIN customers c ON c.id = cs.customer_id
            ORDER BY cs.updated_at DESC
            LIMIT 1
            """
        ).fetchone()

        latest_sentiment_pool = (
            [
                r
                for r in raw_rankings
                if latest_sentiment is not None and r["customer_id"] == latest_sentiment["customer_id"]
            ]
            if latest_sentiment is not None
            else []
        )
        spotlight_pool = [r for r in raw_rankings if r.get("last_visit_outcome") in _SATISFIED_OUTCOMES]
        search_pool = spotlight_pool or raw_rankings
        spotlight_customer_name: str | None = None
        spotlight_before = 0.0
        spotlight_after = 0.0
        spotlight_outcome: str | None = None
        if latest_sentiment_pool or search_pool:

            def _lift(record: dict[str, object]) -> float:
                return float(record["future_potential_index"]) - float(record["future_potential_baseline"])

            best_row = latest_sentiment_pool[0] if latest_sentiment_pool else max(search_pool, key=_lift)
            spotlight_customer_name = str(best_row["customer_name"])
            spotlight_before = float(best_row["future_potential_baseline"])
            spotlight_after = float(best_row["future_potential_index"])
            lo = best_row.get("last_visit_outcome")
            spotlight_outcome = str(lo) if lo is not None else None

        recap_impact: dict[str, object] = {
            "headline": "Field visits and recaps raise future potential",
            "subhead": (
                "Baseline uses territory data only. The updated score blends satisfied outcomes "
                "and structured recap notes."
            ),
            "avg_before": avg_before,
            "avg_after": avg_after,
            "spotlight_customer_name": spotlight_customer_name,
            "spotlight_before": round(spotlight_before, 1),
            "spotlight_after": round(spotlight_after, 1),
            "spotlight_outcome": spotlight_outcome,
            "spotlight_confidence_before": round(
                float(latest_sentiment["initial_confidence_score"]) * 100,
                1,
            )
            if latest_sentiment is not None
            else None,
            "spotlight_confidence_after": round(
                float(latest_sentiment["current_confidence_score"]) * 100,
                1,
            )
            if latest_sentiment is not None
            else None,
            "spotlight_sentiment": str(latest_sentiment["sentiment"])
            if latest_sentiment is not None
            else None,
            "spotlight_sentiment_source": str(latest_sentiment["source"])
            if latest_sentiment is not None
            else None,
            "spotlight_sentiment_updated_at": str(latest_sentiment["updated_at"])
            if latest_sentiment is not None
            else None,
        }

        picks: list[dict[str, object]] = [
            {
                "customer_id": row["id"],
                "name": row["name"],
                "segment": row["segment"],
                "territory_name": row["territory_name"],
                "assigned_salesperson_id": row["assigned_salesperson_id"],
                "assigned_salesperson_name": row["salesperson_name"],
            }
            for row in customers
        ]
        picks.sort(key=lambda p: p["name"])

        recap_rows = connection.execute(
            """
            SELECT vh.id AS visit_id, vh.customer_id, c.name AS customer_name, c.segment,
                   vh.salesperson_id, s.name AS salesperson_name,
                   t.name AS territory_name, vh.visited_at, vh.outcome, vh.notes
            FROM visit_history vh
            JOIN customers c ON c.id = vh.customer_id
            JOIN salespeople s ON s.id = vh.salesperson_id
            JOIN territories t ON t.id = c.territory_id
            WHERE vh.id LIKE 'visit-ai-%'
               OR vh.id LIKE 'visit-sentiment-%'
            ORDER BY vh.visited_at DESC
            LIMIT 40
            """
        ).fetchall()

        recent_ai_recaps: list[dict[str, object]] = []
        for rv in recap_rows:
            summary, next_action = _split_ai_recap_note(str(rv["notes"] or ""))
            label, is_interested = _interest_label(str(rv["outcome"] or ""))
            recent_ai_recaps.append(
                {
                    "visit_id": str(rv["visit_id"]),
                    "customer_id": str(rv["customer_id"]),
                    "customer_name": str(rv["customer_name"]),
                    "segment": str(rv["segment"]),
                    "salesperson_id": str(rv["salesperson_id"]),
                    "salesperson_name": str(rv["salesperson_name"]),
                    "territory_name": str(rv["territory_name"]),
                    "visited_at": str(rv["visited_at"]),
                    "outcome": str(rv["outcome"] or ""),
                    "interest_label": label,
                    "is_interested": is_interested,
                    "summary": summary[:220] + ("…" if len(summary) > 220 else ""),
                    "next_action": (next_action[:160] + ("…" if len(next_action) > 160 else ""))
                    if next_action
                    else "",
                }
            )

    return {
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "date": date.today().isoformat(),
        "reps": rep_summaries,
        "rankings": rankings,
        "customers_for_assignment": picks,
        "recent_ai_recaps": recent_ai_recaps,
        "ranking_note": (
            "Future potential blends RouteIQ score with recent visit outcomes; "
            "structured AI recaps and quick sentiment evaluations add extra visit signal."
        ),
        "recap_monitor_note": (
            "Below: each row is a persisted AI recap or quick visit sentiment evaluation. "
            "Use it to see which companies showed interest (order, follow-up, closed) vs no interest."
        ),
        "recap_impact": recap_impact,
    }


def assign_customer_to_salesperson(
    customer_id: str,
    salesperson_id: str,
    database_path: Path = DEFAULT_OUTPUT,
) -> dict[str, str]:
    with sqlite3.connect(database_path) as connection:
        connection.row_factory = sqlite3.Row
        customer = connection.execute(
            "SELECT id FROM customers WHERE id = ?",
            (customer_id,),
        ).fetchone()
        if customer is None:
            raise ValueError("Customer not found")

        sp = connection.execute(
            "SELECT id, territory_id FROM salespeople WHERE id = ?",
            (salesperson_id,),
        ).fetchone()
        if sp is None:
            raise ValueError("Salesperson not found")

        connection.execute(
            """
            UPDATE customers
            SET assigned_salesperson_id = ?, territory_id = ?
            WHERE id = ?
            """,
            (salesperson_id, sp["territory_id"], customer_id),
        )
        connection.commit()

    return {
        "customer_id": customer_id,
        "salesperson_id": salesperson_id,
        "territory_id": str(sp["territory_id"]),
    }
