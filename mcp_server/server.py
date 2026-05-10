from __future__ import annotations

import json
import sys
from datetime import date
from pathlib import Path
from typing import Any

from mcp.server.fastmcp import FastMCP

ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "backend"
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))

from app.admin.service import build_manager_dashboard
from app.api.routes import get_customer
from app.data.generate import DEFAULT_OUTPUT, ensure_runtime_schema, seed_database
from app.llm.recap import build_recap
from app.llm.score_summary import summarize_score_reasons
from app.ml.score import score_customer
from app.recommend.service import build_day_plan

mcp = FastMCP("RouteIQ")


def _ensure_database() -> Path:
    if not DEFAULT_OUTPUT.exists():
        seed_database(DEFAULT_OUTPUT)
    import sqlite3

    with sqlite3.connect(DEFAULT_OUTPUT) as connection:
        ensure_runtime_schema(connection)
    return DEFAULT_OUTPUT


def _jsonable(value: Any) -> Any:
    if hasattr(value, "model_dump"):
        return value.model_dump(mode="json")
    return json.loads(json.dumps(value, default=str))


@mcp.tool()
def get_day_plan(salesperson_id: str = "sp-kl-central") -> dict[str, Any]:
    """Return today's optimized RouteIQ visit plan for a salesperson."""
    _ensure_database()
    plan = build_day_plan(salesperson_id=salesperson_id, plan_date=date.today())
    return _jsonable(plan)


@mcp.tool()
def get_top_visits(salesperson_id: str = "sp-kl-central", limit: int = 5) -> dict[str, Any]:
    """Return the top recommended visits from today's optimized route."""
    _ensure_database()
    limit = max(1, min(limit, 10))
    plan = build_day_plan(salesperson_id=salesperson_id, plan_date=date.today())
    payload = _jsonable(plan)
    payload["stops"] = payload["stops"][:limit]
    return payload


@mcp.tool()
def get_customer_profile(customer_id: str) -> dict[str, Any]:
    """Return CRM, scoring, visit, order, and sentiment details for a customer."""
    _ensure_database()
    return _jsonable(get_customer(customer_id))


@mcp.tool()
def explain_customer_score(customer_id: str) -> dict[str, Any]:
    """Explain why RouteIQ prioritized a customer."""
    database_path = _ensure_database()
    score = score_customer(customer_id, database_path)
    return {
        "customer_id": customer_id,
        "routeiq_score": round(score.score, 2),
        "visit_likelihood_score": round(score.visit_likelihood_score, 3),
        "priority_class": score.priority_class,
        "recommended_action": score.recommended_action,
        "expected_return_rm": round(score.expected_return_rm, 2),
        "top_reasons": summarize_score_reasons(tuple(score.top_reasons), limit=3),
        "raw_model_reasons": list(score.top_reasons),
    }


@mcp.tool()
def get_manager_dashboard() -> dict[str, Any]:
    """Return manager-level territory, recap, ranking, and follow-up insights."""
    database_path = _ensure_database()
    return _jsonable(build_manager_dashboard(database_path))


@mcp.tool()
def preview_visit_recap(
    customer_id: str,
    salesperson_id: str,
    transcript: str,
) -> dict[str, Any]:
    """Summarize a visit transcript without saving it to CRM."""
    database_path = _ensure_database()
    recap = build_recap(
        customer_id=customer_id,
        salesperson_id=salesperson_id,
        transcript=transcript,
        persist=False,
        database_path=database_path,
    )
    return _jsonable(recap)


if __name__ == "__main__":
    mcp.run()
