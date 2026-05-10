from app.routing.solve import (
    RouteCandidate,
    build_baseline_route,
    haversine_km,
    optimize_route,
)


def test_haversine_kuala_lumpur_distance() -> None:
    distance = haversine_km(3.139, 101.6869, 3.1496, 101.7611)

    assert 8 <= distance <= 9


def test_optimize_route_returns_limited_ordered_stops() -> None:
    candidates = [
        RouteCandidate("a", 3.14, 101.69, 90),
        RouteCandidate("b", 3.16, 101.72, 75),
        RouteCandidate("c", 3.09, 101.62, 80),
    ]

    route = optimize_route(candidates, start_lat=3.139, start_lng=101.6869, max_stops=2)

    assert len(route.stops) == 2
    assert route.stops[0].sequence == 1
    assert route.total_distance_km > 0


def test_optimize_route_brute_forces_optimal_ordering() -> None:
    """For a 4-corner rectangle, the optimal tour traces the perimeter (no diagonal crossings).

    Optimal distance is 3 sides ~= 33 km. A crossing path would add a ~15 km diagonal.
    """
    candidates = [
        RouteCandidate("a", 3.10, 101.70, 100),
        RouteCandidate("b", 3.20, 101.70, 100),
        RouteCandidate("c", 3.20, 101.80, 100),
        RouteCandidate("d", 3.10, 101.80, 100),
    ]

    route = optimize_route(candidates, start_lat=3.10, start_lng=101.70, max_stops=4)

    assert route.routes_evaluated >= 24
    assert len(route.stops) == 4
    assert route.stops[0].customer_id == "a"
    assert route.stops[-1].customer_id in {"b", "d"}
    assert route.total_distance_km < 35


def test_baseline_route_is_value_blind() -> None:
    far_high_value = RouteCandidate("far", 3.30, 101.90, 95)
    near_low_value = RouteCandidate("near", 3.11, 101.69, 5)

    baseline = build_baseline_route(
        [far_high_value, near_low_value],
        start_lat=3.10,
        start_lng=101.70,
        max_stops=2,
    )

    assert baseline.stops[0].customer_id == "near"
