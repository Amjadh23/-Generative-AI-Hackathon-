import sqlite3
from datetime import date, datetime
from pathlib import Path
from uuid import uuid4

from fastapi import APIRouter, HTTPException, Query

from app.admin.service import assign_customer_to_salesperson, build_manager_dashboard
from app.assistant.router import answer_question
from app.core.schemas import (
    AssistantRequest,
    AssistantResponse,
    CustomerAssignmentPayload,
    CustomerAssignmentResult,
    DayPlan,
    VisitCreate,
    VisitCreated,
    VisitRecapRequest,
    VisitRecapResponse,
    VisitSentimentRequest,
    VisitSentimentResponse,
)
from app.data.generate import DEFAULT_OUTPUT, ensure_runtime_schema, seed_database
from app.llm.client import LLMError
from app.llm.recap import build_recap
from app.llm.score_summary import summarize_score_reasons
from app.ml.score import score_customer
from app.recommend.service import build_day_plan
from app.sentiment.service import log_manual_sentiment_visit

router = APIRouter()


def _ensure_database(database_path: Path = DEFAULT_OUTPUT) -> Path:
    if not database_path.exists():
        seed_database(database_path)
    with sqlite3.connect(database_path) as connection:
        ensure_runtime_schema(connection)
    return database_path


@router.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@router.get("/salespeople/{salesperson_id}/day-plan", response_model=DayPlan)
def get_day_plan(
    salesperson_id: str,
    date_: date | None = Query(default=None, alias="date"),
    max_stops: int | None = Query(default=None, ge=1, le=10),
    start_lat: float | None = None,
    start_lng: float | None = None,
) -> DayPlan:
    return build_day_plan(
        salesperson_id=salesperson_id,
        plan_date=date_ or date.today(),
        start_lat=start_lat,
        start_lng=start_lng,
        max_stops=max_stops,
    )


@router.get("/customers/{customer_id}")
def get_customer(customer_id: str) -> dict[str, object]:
    database_path = _ensure_database()

    with sqlite3.connect(database_path) as connection:
        connection.row_factory = sqlite3.Row
        customer = connection.execute(
            "SELECT * FROM customers WHERE id = ?",
            (customer_id,),
        ).fetchone()
        if customer is None:
            raise HTTPException(status_code=404, detail="Customer not found")

        visits = connection.execute(
            """
            SELECT id, salesperson_id, visited_at, outcome, notes
            FROM visit_history
            WHERE customer_id = ?
            ORDER BY visited_at DESC
            LIMIT 5
            """,
            (customer_id,),
        ).fetchall()

        orders = connection.execute(
            """
            SELECT id, order_date, amount_rm, product_family
            FROM orders
            WHERE customer_id = ?
            ORDER BY order_date DESC
            LIMIT 5
            """,
            (customer_id,),
        ).fetchall()

        sentiment = connection.execute(
            """
            SELECT initial_confidence_score, current_confidence_score,
                   sentiment, source, updated_at
            FROM customer_sentiment
            WHERE customer_id = ?
            """,
            (customer_id,),
        ).fetchone()

    score = score_customer(customer_id, database_path)
    top_reasons = summarize_score_reasons(tuple(score.top_reasons), limit=3)
    return {
        "id": customer["id"],
        "name": customer["name"],
        "segment": customer["segment"],
        "territory_id": customer["territory_id"],
        "assigned_salesperson_id": customer["assigned_salesperson_id"],
        "lat": customer["lat"],
        "lng": customer["lng"],
        "crm_priority": customer["priority"],
        "avg_order_value_rm": customer["avg_order_value_rm"],
        "open_pipeline_rm": customer["open_pipeline_rm"],
        "last_visit_days": customer["last_visit_days"],
        "reorder_probability": customer["reorder_probability"],
        "score": score.score,
        "visit_likelihood_score": score.visit_likelihood_score,
        "priority_class": score.priority_class,
        "recommended_action": score.recommended_action,
        "expected_return_rm": score.expected_return_rm,
        "score_contributions": score.contributions,
        "top_reasons": top_reasons,
        "xgboost_explanation": score.xgboost_explanation_payload,
        "sentiment_initial_confidence_score": (
            sentiment["initial_confidence_score"] if sentiment else 0.5
        ),
        "sentiment_confidence_score": (
            sentiment["current_confidence_score"] if sentiment else 0.5
        ),
        "sentiment_label": sentiment["sentiment"] if sentiment else "neutral",
        "sentiment_source": sentiment["source"] if sentiment else "initial",
        "sentiment_updated_at": sentiment["updated_at"] if sentiment else None,
        "visits": [dict(visit) for visit in visits],
        "orders": [dict(order) for order in orders],
    }


@router.post("/visits", status_code=201, response_model=VisitCreated)
def create_visit(payload: VisitCreate) -> VisitCreated:
    database_path = _ensure_database()
    visit_id = f"visit-{uuid4().hex[:8]}"
    visited_at = datetime.now().isoformat(timespec="seconds")

    with sqlite3.connect(database_path) as connection:
        cursor = connection.cursor()
        existing = cursor.execute(
            "SELECT id FROM customers WHERE id = ?",
            (payload.customer_id,),
        ).fetchone()
        if existing is None:
            raise HTTPException(status_code=404, detail="Customer not found")

        cursor.execute(
            "INSERT INTO visit_history VALUES (?, ?, ?, ?, ?, ?)",
            (
                visit_id,
                payload.customer_id,
                payload.salesperson_id,
                visited_at,
                payload.outcome,
                payload.notes,
            ),
        )
        cursor.execute(
            "UPDATE customers SET last_visit_days = 0 WHERE id = ?",
            (payload.customer_id,),
        )
        connection.commit()

    return VisitCreated(id=visit_id, status="logged")


@router.get("/salespeople/{salesperson_id}/territory")
def get_territory(salesperson_id: str) -> dict[str, object]:
    database_path = _ensure_database()

    with sqlite3.connect(database_path) as connection:
        connection.row_factory = sqlite3.Row
        salesperson = connection.execute(
            "SELECT * FROM salespeople WHERE id = ?",
            (salesperson_id,),
        ).fetchone()
        if salesperson is None:
            raise HTTPException(status_code=404, detail="Salesperson not found")

        territory = connection.execute(
            "SELECT * FROM territories WHERE id = ?",
            (salesperson["territory_id"],),
        ).fetchone()

    return {
        "id": territory["id"],
        "name": territory["name"],
        "salesperson_id": salesperson["id"],
        "salesperson_name": salesperson["name"],
        "center_lat": territory["center_lat"],
        "center_lng": territory["center_lng"],
        "radius_km": territory["radius_km"],
        "home_lat": salesperson["home_lat"],
        "home_lng": salesperson["home_lng"],
    }


@router.post("/assistant/ask", response_model=AssistantResponse)
def assistant_ask(payload: AssistantRequest) -> AssistantResponse:
    try:
        return answer_question(
            salesperson_id=payload.salesperson_id,
            question=payload.question,
            current_customer_id=payload.current_customer_id,
            max_stops=payload.max_stops,
        )
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except LLMError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc


@router.post("/visits/recap", response_model=VisitRecapResponse)
def visits_recap(payload: VisitRecapRequest) -> VisitRecapResponse:
    database_path = _ensure_database()
    with sqlite3.connect(database_path) as connection:
        exists = connection.execute(
            "SELECT 1 FROM customers WHERE id = ?", (payload.customer_id,)
        ).fetchone()
    if exists is None:
        raise HTTPException(status_code=404, detail="Customer not found")
    try:
        return build_recap(
            customer_id=payload.customer_id,
            salesperson_id=payload.salesperson_id,
            transcript=payload.transcript,
            persist=payload.persist,
            database_path=database_path,
        )
    except LLMError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc


@router.post("/visits/sentiment", status_code=201, response_model=VisitSentimentResponse)
def visits_sentiment(payload: VisitSentimentRequest) -> VisitSentimentResponse:
    try:
        result = log_manual_sentiment_visit(
            customer_id=payload.customer_id,
            salesperson_id=payload.salesperson_id,
            sentiment=payload.sentiment,
            database_path=_ensure_database(),
        )
    except ValueError as exc:
        status_code = 404 if "not found" in str(exc).lower() else 400
        raise HTTPException(status_code=status_code, detail=str(exc)) from exc
    return VisitSentimentResponse(**result)


@router.get("/admin/dashboard")
def admin_dashboard() -> dict[str, object]:
    return build_manager_dashboard(_ensure_database())


@router.patch("/admin/customers/{customer_id}/assignment", response_model=CustomerAssignmentResult)
def admin_assign_customer(
    customer_id: str,
    payload: CustomerAssignmentPayload,
) -> CustomerAssignmentResult:
    try:
        result = assign_customer_to_salesperson(
            customer_id=customer_id,
            salesperson_id=payload.salesperson_id,
            database_path=_ensure_database(),
        )
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return CustomerAssignmentResult(**result)


@router.get("/salespeople")
def list_salespeople() -> list[dict[str, object]]:
    database_path = _ensure_database()

    with sqlite3.connect(database_path) as connection:
        connection.row_factory = sqlite3.Row
        rows = connection.execute(
            """
            SELECT s.id, s.name, s.home_lat, s.home_lng, s.max_daily_stops,
                   t.id AS territory_id, t.name AS territory_name
            FROM salespeople s
            JOIN territories t ON t.id = s.territory_id
            ORDER BY s.name
            """
        ).fetchall()

    return [dict(row) for row in rows]
