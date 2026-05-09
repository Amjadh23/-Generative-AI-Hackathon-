"""LLM-backed assistant for the in-app mascot chat.

Strategy: build a grounded **fact sheet** from the real ``DayPlan`` + customer
score, hand it to the LLM as the system prompt, and let the LLM phrase the
answer in natural English. The LLM is forbidden from inventing numbers — it
only paraphrases the facts we provide.
"""

from __future__ import annotations

import json
import sqlite3
from dataclasses import dataclass
from datetime import date
from pathlib import Path

from app.core.schemas import AssistantResponse, DayPlan, DayPlanStop
from app.data.generate import DEFAULT_OUTPUT
from app.llm.client import LLMError, chat_json
from app.ml.score import score_customer
from app.recommend.service import build_day_plan

DEFAULT_SUGGESTIONS = [
    "What's my next stop?",
    "How far to the next customer?",
    "Why is this customer a priority?",
    "What should I focus on?",
    "Show me the highest-value stop today.",
    "Summarise today's plan.",
]

SYSTEM_PROMPT = """You are RIQ, the friendly AI sales copilot inside Hilti RouteIQ.

You are talking to a Hilti field salesperson on their phone, on the road. Be
concise (1-3 sentences), warm, action-oriented, and professional. Refer to
yourself as RIQ when natural. Never invent customer names, distances, ringgit
amounts, or scores; use ONLY the facts in the FACTS block. If the user asks
something the facts don't cover, say so briefly and suggest a related question
they can ask.

Always respond with strict JSON in this exact shape and nothing else:
{
  "answer": "<your reply, plain text, no markdown>",
  "intent": "<one of: next_stop, distance, why, focus, best_stop, list_stops, summary, greeting, fallback>",
  "related_customer_id": "<a customer_id from the facts, or null>",
  "suggestions": ["<short follow-up 1>", "<short follow-up 2>", "<short follow-up 3>"]
}

Currency is RM (Malaysian ringgit). Distances are in km. Keep suggestions short
(under 7 words each)."""


@dataclass
class AssistantContext:
    salesperson_id: str
    plan: DayPlan
    current_customer_id: str | None
    database_path: Path

    @property
    def current_stop(self) -> DayPlanStop | None:
        if not self.current_customer_id:
            return None
        for stop in self.plan.stops:
            if stop.customer_id == self.current_customer_id:
                return stop
        return None

    @property
    def next_stop(self) -> DayPlanStop | None:
        current = self.current_stop
        if current is None:
            return self.plan.stops[0] if self.plan.stops else None
        for stop in self.plan.stops:
            if stop.sequence == current.sequence + 1:
                return stop
        return None


def _stop_fact(stop: DayPlanStop) -> dict[str, object]:
    return {
        "sequence": stop.sequence,
        "customer_id": stop.customer_id,
        "customer_name": stop.customer_name,
        "segment": stop.segment,
        "score": round(stop.score, 1),
        "visit_likelihood_score": round(stop.visit_likelihood_score, 4),
        "priority_class": stop.priority_class,
        "recommended_action": stop.recommended_action,
        "top_reasons": stop.top_reasons,
        "expected_return_rm": round(stop.expected_return_rm),
        "distance_from_previous_km": round(stop.distance_from_previous_km, 2),
        "eta_minutes": stop.eta_minutes,
        "visit_duration_minutes": stop.visit_duration_minutes,
        "reason": stop.reason,
        "focus": stop.focus,
    }


def _build_fact_sheet(ctx: AssistantContext) -> str:
    plan = ctx.plan
    summary = plan.optimization_summary
    facts: dict[str, object] = {
        "today": plan.date.isoformat(),
        "salesperson_id": plan.salesperson_id,
        "total_stops": len(plan.stops),
        "total_distance_km": round(plan.total_distance_km, 2),
        "total_expected_return_rm": round(plan.total_expected_return_rm),
        "stops": [_stop_fact(stop) for stop in plan.stops],
    }
    if summary:
        facts["optimization"] = {
            "routes_evaluated": summary.routes_evaluated,
            "value_uplift_pct": summary.value_uplift_pct,
            "value_gain_rm": round(summary.value_gain_rm),
            "distance_saved_km": round(summary.distance_saved_km, 2),
            "baseline_distance_km": round(summary.baseline_distance_km, 2),
            "baseline_expected_return_rm": round(summary.baseline_expected_return_rm),
        }

    target = ctx.current_stop or ctx.next_stop
    if target is not None:
        score = score_customer(target.customer_id, ctx.database_path)
        xgb = score.xgboost_explanation_payload or {}
        top_payload = xgb.get("top_priority_reasons") if isinstance(xgb, dict) else None
        facts["focused_customer"] = {
            "customer_id": target.customer_id,
            "customer_name": target.customer_name,
            "is_next_stop": target.customer_id == (ctx.next_stop.customer_id if ctx.next_stop else None),
            "is_current_stop": ctx.current_stop is not None
            and target.customer_id == ctx.current_stop.customer_id,
            "score": round(score.score, 1),
            "visit_likelihood_score": round(score.visit_likelihood_score, 4),
            "priority_class": score.priority_class,
            "recommended_action": score.recommended_action,
            "top_reasons": list(score.top_reasons),
            "xgboost_top_priority_reasons": list(top_payload)
            if isinstance(top_payload, list)
            else [],
            "expected_return_rm": round(score.expected_return_rm),
            "score_contributions": {
                key: round(value, 3) for key, value in score.contributions.items()
            },
            "reason": score.reason,
            "focus": target.focus,
            "distance_from_previous_km": round(target.distance_from_previous_km, 2),
            "eta_minutes": target.eta_minutes,
        }
    return json.dumps(facts, ensure_ascii=False, indent=2)


def _coerce_response(payload: dict[str, object], ctx: AssistantContext) -> AssistantResponse:
    answer = str(payload.get("answer") or "").strip()
    if not answer:
        raise LLMError("LLM response missing 'answer' field.")

    intent = str(payload.get("intent") or "fallback").strip().lower()
    valid_intents = {
        "next_stop", "distance", "why", "focus", "best_stop",
        "list_stops", "summary", "greeting", "fallback",
    }
    if intent not in valid_intents:
        intent = "fallback"

    related = payload.get("related_customer_id")
    related_id: str | None = None
    if isinstance(related, str) and related:
        valid_ids = {stop.customer_id for stop in ctx.plan.stops}
        if related in valid_ids:
            related_id = related

    suggestions_raw = payload.get("suggestions") or []
    suggestions: list[str] = []
    if isinstance(suggestions_raw, list):
        for item in suggestions_raw[:4]:
            if isinstance(item, str) and item.strip():
                suggestions.append(item.strip())
    if not suggestions:
        suggestions = DEFAULT_SUGGESTIONS[:3]

    return AssistantResponse(
        answer=answer,
        intent=intent,
        related_customer_id=related_id,
        suggestions=suggestions,
    )


def answer_question(
    salesperson_id: str,
    question: str,
    current_customer_id: str | None = None,
    database_path: Path = DEFAULT_OUTPUT,
) -> AssistantResponse:
    plan = build_day_plan(
        salesperson_id=salesperson_id,
        plan_date=date.today(),
        database_path=database_path,
    )

    if current_customer_id and not any(
        stop.customer_id == current_customer_id for stop in plan.stops
    ):
        with sqlite3.connect(database_path) as connection:
            exists = connection.execute(
                "SELECT 1 FROM customers WHERE id = ?",
                (current_customer_id,),
            ).fetchone()
        if exists is None:
            current_customer_id = None

    ctx = AssistantContext(
        salesperson_id=salesperson_id,
        plan=plan,
        current_customer_id=current_customer_id,
        database_path=database_path,
    )

    fact_sheet = _build_fact_sheet(ctx)
    user_prompt = (
        "FACTS (JSON, the only source of truth — do not invent anything beyond this):\n"
        f"{fact_sheet}\n\n"
        f"USER QUESTION:\n{question.strip()}"
    )

    raw = chat_json(SYSTEM_PROMPT, user_prompt, temperature=0.3)
    return _coerce_response(raw, ctx)
