import random
import sqlite3
from datetime import date
from pathlib import Path

from app.core.schemas import DayPlan, DayPlanStop, OptimizationSummary
from app.data.generate import DEFAULT_OUTPUT, seed_database
from app.llm.explain import build_focus
from app.ml.score import score_customer_row, top_customers_for_salesperson
from app.routing.solve import RouteCandidate, build_baseline_route, optimize_route

BASELINE_SEED = 20260509


def build_day_plan(
    salesperson_id: str,
    plan_date: date,
    start_lat: float | None = None,
    start_lng: float | None = None,
    database_path: Path = DEFAULT_OUTPUT,
) -> DayPlan:
    if not database_path.exists():
        seed_database(database_path)

    with sqlite3.connect(database_path) as connection:
        connection.row_factory = sqlite3.Row
        salesperson = connection.execute(
            "SELECT * FROM salespeople WHERE id = ?",
            (salesperson_id,),
        ).fetchone()
        if salesperson is None:
            raise ValueError(f"Salesperson not found: {salesperson_id}")

        customer_rows = {
            row["id"]: row
            for row in connection.execute(
                """
                SELECT *
                FROM customers
                WHERE assigned_salesperson_id = ?
                """,
                (salesperson_id,),
            ).fetchall()
        }

    home_lat = start_lat if start_lat is not None else salesperson["home_lat"]
    home_lng = start_lng if start_lng is not None else salesperson["home_lng"]
    max_stops = salesperson["max_daily_stops"]

    scored_customers = top_customers_for_salesperson(salesperson_id, limit=18, database_path=database_path)
    candidates = [
        RouteCandidate(
            customer_id=scored.customer_id,
            lat=customer_rows[scored.customer_id]["lat"],
            lng=customer_rows[scored.customer_id]["lng"],
            value_score=scored.score,
        )
        for scored in scored_customers
    ]

    route = optimize_route(
        candidates,
        start_lat=home_lat,
        start_lng=home_lng,
        max_stops=max_stops,
    )

    score_by_customer = {score.customer_id: score for score in scored_customers}
    stops: list[DayPlanStop] = []
    for route_stop in route.stops:
        customer = customer_rows[route_stop.customer_id]
        score = score_by_customer[route_stop.customer_id]
        stops.append(
            DayPlanStop(
                sequence=route_stop.sequence,
                customer_id=route_stop.customer_id,
                customer_name=customer["name"],
                segment=customer["segment"],
                lat=customer["lat"],
                lng=customer["lng"],
                score=score.score,
                expected_return_rm=score.expected_return_rm,
                distance_from_previous_km=route_stop.distance_from_previous_km,
                eta_minutes=route_stop.eta_minutes,
                reason=score.reason,
                focus=build_focus(route_stop.customer_id, database_path),
            )
        )

    optimization_summary = _build_optimization_summary(
        all_customer_rows=list(customer_rows.values()),
        optimized_distance_km=route.total_distance_km,
        optimized_expected_return_rm=sum(stop.expected_return_rm for stop in stops),
        routes_evaluated=route.routes_evaluated,
        home_lat=home_lat,
        home_lng=home_lng,
        max_stops=max_stops,
    )

    return DayPlan(
        salesperson_id=salesperson_id,
        date=plan_date,
        total_expected_return_rm=sum(stop.expected_return_rm for stop in stops),
        total_distance_km=route.total_distance_km,
        stops=stops,
        optimization_summary=optimization_summary,
    )


def _build_optimization_summary(
    all_customer_rows: list[sqlite3.Row],
    optimized_distance_km: float,
    optimized_expected_return_rm: float,
    routes_evaluated: int,
    home_lat: float,
    home_lng: float,
    max_stops: int,
) -> OptimizationSummary:
    """Compare against a naive baseline: random selection of customers, visited nearest-first."""
    rng = random.Random(BASELINE_SEED)
    sample_size = min(max_stops, len(all_customer_rows))
    if sample_size == 0:
        return OptimizationSummary(
            routes_evaluated=routes_evaluated,
            baseline_expected_return_rm=0.0,
            baseline_distance_km=0.0,
            value_gain_rm=0.0,
            distance_saved_km=0.0,
            value_uplift_pct=0.0,
        )

    baseline_rows = rng.sample(all_customer_rows, sample_size)
    baseline_candidates = [
        RouteCandidate(
            customer_id=row["id"],
            lat=row["lat"],
            lng=row["lng"],
            value_score=score_customer_row(row).score,
        )
        for row in baseline_rows
    ]

    baseline_route = build_baseline_route(
        baseline_candidates,
        start_lat=home_lat,
        start_lng=home_lng,
        max_stops=max_stops,
    )
    baseline_expected_return = sum(
        score_customer_row(row).expected_return_rm for row in baseline_rows
    )

    value_gain = optimized_expected_return_rm - baseline_expected_return
    distance_saved = baseline_route.total_distance_km - optimized_distance_km
    value_uplift_pct = (
        (value_gain / baseline_expected_return * 100) if baseline_expected_return > 0 else 0.0
    )

    return OptimizationSummary(
        routes_evaluated=routes_evaluated,
        baseline_expected_return_rm=round(baseline_expected_return, 2),
        baseline_distance_km=round(baseline_route.total_distance_km, 2),
        value_gain_rm=round(value_gain, 2),
        distance_saved_km=round(distance_saved, 2),
        value_uplift_pct=round(value_uplift_pct, 1),
    )
