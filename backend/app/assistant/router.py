"""Intent-routed assistant for the in-app mascot chat.

Rule-based for hackathon reliability (works without any API keys), but the
``answer_question`` boundary is designed so a real LLM can be slotted in later
without changing the API contract.
"""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from datetime import date
from pathlib import Path

from app.core.schemas import AssistantResponse, DayPlan, DayPlanStop
from app.data.generate import DEFAULT_OUTPUT
from app.llm.explain import build_focus
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


def _format_rm(value: float) -> str:
    return f"RM{value:,.0f}"


def _stop_label(stop: DayPlanStop) -> str:
    return f"#{stop.sequence} {stop.customer_name}"


def _matches(question: str, keywords: list[str]) -> bool:
    return any(keyword in question for keyword in keywords)


def _next_stop_answer(ctx: AssistantContext) -> AssistantResponse:
    nxt = ctx.next_stop
    if nxt is None:
        return AssistantResponse(
            answer="You've cleared today's route — nice work. Want a summary?",
            intent="next_stop",
            suggestions=["Summarise today's plan."],
        )
    answer = (
        f"Next is {_stop_label(nxt)} ({nxt.segment}). "
        f"{nxt.distance_from_previous_km:.1f} km · ~{nxt.eta_minutes} min from the previous stop. "
        f"Expected return {_format_rm(nxt.expected_return_rm)}."
    )
    return AssistantResponse(
        answer=answer,
        intent="next_stop",
        related_customer_id=nxt.customer_id,
        suggestions=["Why this customer?", "What should I focus on?"],
    )


def _distance_answer(ctx: AssistantContext) -> AssistantResponse:
    target = ctx.current_stop or ctx.next_stop
    if target is None:
        return AssistantResponse(
            answer="No stops loaded yet — open Today and we'll plan a route.",
            intent="distance",
        )
    answer = (
        f"{_stop_label(target)} is {target.distance_from_previous_km:.1f} km "
        f"from the previous point — about {target.eta_minutes} minutes by road."
    )
    return AssistantResponse(
        answer=answer,
        intent="distance",
        related_customer_id=target.customer_id,
        suggestions=["What's after that?", "Why this customer?"],
    )


def _why_answer(ctx: AssistantContext) -> AssistantResponse:
    target = ctx.current_stop or ctx.next_stop
    if target is None:
        return AssistantResponse(
            answer="Open a stop on the map and I'll explain why it made the cut.",
            intent="why",
        )
    score = score_customer(target.customer_id, ctx.database_path)
    top_factors = sorted(score.contributions.items(), key=lambda item: item[1], reverse=True)[:2]
    factor_text = " and ".join(name.replace("_", " ") for name, _ in top_factors)
    answer = (
        f"{target.customer_name} scored {score.score:.0f}/100. "
        f"Top drivers: {factor_text}. {target.reason}"
    )
    return AssistantResponse(
        answer=answer,
        intent="why",
        related_customer_id=target.customer_id,
        suggestions=["What should I focus on?", "What's my next stop?"],
    )


def _focus_answer(ctx: AssistantContext) -> AssistantResponse:
    target = ctx.current_stop or ctx.next_stop
    if target is None:
        return AssistantResponse(
            answer="Pick a customer and I'll suggest what to lead with.",
            intent="focus",
        )
    focus = target.focus or build_focus(target.customer_id, ctx.database_path)
    answer = f"For {target.customer_name}: {focus}"
    return AssistantResponse(
        answer=answer,
        intent="focus",
        related_customer_id=target.customer_id,
        suggestions=["Why this customer?", "What's my next stop?"],
    )


def _best_stop_answer(ctx: AssistantContext) -> AssistantResponse:
    if not ctx.plan.stops:
        return AssistantResponse(answer="No stops loaded yet.", intent="best_stop")
    best = max(ctx.plan.stops, key=lambda stop: stop.expected_return_rm)
    answer = (
        f"Highest-value stop today is {_stop_label(best)} "
        f"at {_format_rm(best.expected_return_rm)} expected return. {best.reason}"
    )
    return AssistantResponse(
        answer=answer,
        intent="best_stop",
        related_customer_id=best.customer_id,
        suggestions=["What should I focus on?", "How far to it?"],
    )


def _list_answer(ctx: AssistantContext) -> AssistantResponse:
    if not ctx.plan.stops:
        return AssistantResponse(answer="No stops on the route yet.", intent="list_stops")
    lines = [
        f"{stop.sequence}. {stop.customer_name} — {_format_rm(stop.expected_return_rm)}"
        for stop in ctx.plan.stops
    ]
    answer = "Today's route:\n" + "\n".join(lines)
    return AssistantResponse(
        answer=answer,
        intent="list_stops",
        suggestions=["Summarise today's plan.", "What's my next stop?"],
    )


def _summary_answer(ctx: AssistantContext) -> AssistantResponse:
    plan = ctx.plan
    summary = plan.optimization_summary
    base = (
        f"{len(plan.stops)} stops · {plan.total_distance_km:.1f} km · "
        f"{_format_rm(plan.total_expected_return_rm)} expected return."
    )
    if summary:
        base += (
            f" That's +{summary.value_uplift_pct:.0f}% value vs a baseline route, "
            f"and {summary.distance_saved_km:.1f} km saved. "
            f"Picked from {summary.routes_evaluated:,} evaluated orderings."
        )
    return AssistantResponse(
        answer=base,
        intent="summary",
        suggestions=["What's my next stop?", "Highest-value stop today?"],
    )


def _greeting_answer(_: AssistantContext) -> AssistantResponse:
    return AssistantResponse(
        answer="Hi, I'm RIQ. Ask me about your stops, distances, or what to focus on.",
        intent="greeting",
        suggestions=DEFAULT_SUGGESTIONS[:3],
    )


def _fallback_answer(ctx: AssistantContext) -> AssistantResponse:
    nxt = ctx.next_stop
    hint = (
        f" Your next stop is {_stop_label(nxt)} — try asking 'why this customer?' or 'how far?'"
        if nxt is not None
        else ""
    )
    return AssistantResponse(
        answer="I can help with stops, distances, focus tips, and the day's value." + hint,
        intent="fallback",
        suggestions=DEFAULT_SUGGESTIONS,
    )


def _classify(question: str) -> str:
    q = question.lower().strip()
    if _matches(q, ["hi", "hello", "hey", "yo "]) and len(q) <= 12:
        return "greeting"
    if _matches(q, ["how far", "distance", "eta", "how long", "minutes away", "km away"]):
        return "distance"
    if _matches(q, ["next stop", "what's next", "after this", "after that", "where next", "where to"]):
        return "next_stop"
    if _matches(q, ["why", "reason", "explain"]):
        return "why"
    if _matches(q, ["focus", "pitch", "talk about", "discuss", "lead with", "say to"]):
        return "focus"
    if _matches(q, ["best", "top", "highest", "biggest", "most valuable", "richest"]):
        return "best_stop"
    if _matches(q, ["list", "all stops", "show all", "remaining", "left", "schedule"]):
        return "list_stops"
    if _matches(q, ["summary", "summarise", "summarize", "total", "overview", "today's plan"]):
        return "summary"
    return "fallback"


_HANDLERS = {
    "greeting": _greeting_answer,
    "distance": _distance_answer,
    "next_stop": _next_stop_answer,
    "why": _why_answer,
    "focus": _focus_answer,
    "best_stop": _best_stop_answer,
    "list_stops": _list_answer,
    "summary": _summary_answer,
    "fallback": _fallback_answer,
}


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

    intent = _classify(question)
    return _HANDLERS[intent](ctx)
