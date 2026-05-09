from __future__ import annotations

import math
from dataclasses import dataclass
from itertools import permutations

# On-site time by segment (Submodule 2: estimated visit duration for scheduling).
VISIT_MINUTES_BY_SEGMENT: dict[str, int] = {
    "project_site": 45,
    "distributor": 25,
    "maintenance": 35,
}
DEFAULT_VISIT_MINUTES = 35


def estimate_visit_duration_minutes(segment: str, priority_class: str) -> int:
    """Heuristic visit length: segment base, nudged by Submodule 1 priority_class."""
    base = VISIT_MINUTES_BY_SEGMENT.get(segment, DEFAULT_VISIT_MINUTES)
    if priority_class == "High":
        return min(60, base + 5)
    if priority_class == "Low":
        return max(20, base - 5)
    return base


@dataclass(frozen=True)
class RouteCandidate:
    customer_id: str
    lat: float
    lng: float
    value_score: float
    priority_class: str = "Medium"
    visit_duration_minutes: int = DEFAULT_VISIT_MINUTES


@dataclass(frozen=True)
class RouteStop:
    customer_id: str
    sequence: int
    distance_from_previous_km: float
    eta_minutes: int
    visit_duration_minutes: int


@dataclass(frozen=True)
class RoutePlan:
    stops: list[RouteStop]
    total_distance_km: float
    routes_evaluated: int = 1


def haversine_km(origin_lat: float, origin_lng: float, destination_lat: float, destination_lng: float) -> float:
    radius_km = 6371.0
    lat_delta = math.radians(destination_lat - origin_lat)
    lng_delta = math.radians(destination_lng - origin_lng)
    origin_lat_rad = math.radians(origin_lat)
    destination_lat_rad = math.radians(destination_lat)

    a = (
        math.sin(lat_delta / 2) ** 2
        + math.cos(origin_lat_rad) * math.cos(destination_lat_rad) * math.sin(lng_delta / 2) ** 2
    )
    return radius_km * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))


def estimate_eta_minutes(distance_km: float, average_speed_kmh: float = 24) -> int:
    return max(4, round((distance_km / average_speed_kmh) * 60))


def _greedy_value_aware(
    candidates: list[RouteCandidate],
    start_lat: float,
    start_lng: float,
    max_stops: int,
) -> tuple[list[RouteCandidate], float]:
    remaining = candidates.copy()
    current_lat = start_lat
    current_lng = start_lng
    selected: list[RouteCandidate] = []
    total_distance = 0.0

    while remaining and len(selected) < max_stops:
        clat, clng = current_lat, current_lng

        def _marginal_value(candidate: RouteCandidate, *, _clat: float = clat, _clng: float = clng) -> float:
            travel_km = haversine_km(_clat, _clng, candidate.lat, candidate.lng)
            travel_min = float(estimate_eta_minutes(travel_km))
            return candidate.value_score / max(1.0, travel_min + float(candidate.visit_duration_minutes))

        next_candidate = max(remaining, key=_marginal_value)
        total_distance += haversine_km(current_lat, current_lng, next_candidate.lat, next_candidate.lng)
        selected.append(next_candidate)
        current_lat = next_candidate.lat
        current_lng = next_candidate.lng
        remaining.remove(next_candidate)

    return selected, total_distance


def _route_total_distance(
    sequence: tuple[RouteCandidate, ...],
    start_lat: float,
    start_lng: float,
) -> float:
    total = 0.0
    current_lat = start_lat
    current_lng = start_lng
    for candidate in sequence:
        total += haversine_km(current_lat, current_lng, candidate.lat, candidate.lng)
        current_lat = candidate.lat
        current_lng = candidate.lng
    return total


def _route_total_time_minutes(
    sequence: tuple[RouteCandidate, ...],
    start_lat: float,
    start_lng: float,
) -> float:
    """Travel time between stops plus on-site duration at each stop (Submodule 2)."""
    total = 0.0
    current_lat = start_lat
    current_lng = start_lng
    for candidate in sequence:
        dist = haversine_km(current_lat, current_lng, candidate.lat, candidate.lng)
        total += float(estimate_eta_minutes(dist)) + float(candidate.visit_duration_minutes)
        current_lat = candidate.lat
        current_lng = candidate.lng
    return total


def _build_route_plan(
    sequence: list[RouteCandidate],
    start_lat: float,
    start_lng: float,
    routes_evaluated: int,
) -> RoutePlan:
    stops: list[RouteStop] = []
    total_distance = 0.0
    current_lat = start_lat
    current_lng = start_lng

    for index, candidate in enumerate(sequence, start=1):
        distance = haversine_km(current_lat, current_lng, candidate.lat, candidate.lng)
        total_distance += distance
        stops.append(
            RouteStop(
                customer_id=candidate.customer_id,
                sequence=index,
                distance_from_previous_km=round(distance, 2),
                eta_minutes=estimate_eta_minutes(distance),
                visit_duration_minutes=candidate.visit_duration_minutes,
            )
        )
        current_lat = candidate.lat
        current_lng = candidate.lng

    return RoutePlan(
        stops=stops,
        total_distance_km=round(total_distance, 2),
        routes_evaluated=routes_evaluated,
    )


def optimize_route(
    candidates: list[RouteCandidate],
    start_lat: float,
    start_lng: float,
    max_stops: int = 8,
) -> RoutePlan:
    """Pick top stops with greedy value awareness, then exhaustively pick the best ordering.

    Selection is value-aware nearest-neighbor (handles up to ~100 candidates).
    Ordering uses brute-force permutations starting from the salesperson's home, which is
    optimal for the chosen N and remains fast for N <= 10 (10! = 3.6M, 8! = 40k).
    """
    selected, _ = _greedy_value_aware(candidates, start_lat, start_lng, max_stops)

    if not selected:
        return RoutePlan(stops=[], total_distance_km=0.0, routes_evaluated=0)

    best_sequence = list(selected)
    best_time = _route_total_time_minutes(tuple(best_sequence), start_lat, start_lng)
    routes_evaluated = 1

    if len(selected) <= 9:
        for permutation in permutations(selected):
            routes_evaluated += 1
            total_min = _route_total_time_minutes(permutation, start_lat, start_lng)
            if total_min < best_time:
                best_time = total_min
                best_sequence = list(permutation)

    return _build_route_plan(best_sequence, start_lat, start_lng, routes_evaluated)


def build_baseline_route(
    candidates: list[RouteCandidate],
    start_lat: float,
    start_lng: float,
    max_stops: int = 8,
) -> RoutePlan:
    """Naive baseline: visit nearest customer next, ignoring value.

    Represents 'what a salesperson would do without RouteIQ'.
    """
    remaining = candidates.copy()
    current_lat = start_lat
    current_lng = start_lng
    selected: list[RouteCandidate] = []

    while remaining and len(selected) < max_stops:
        nearest = min(
            remaining,
            key=lambda candidate: haversine_km(current_lat, current_lng, candidate.lat, candidate.lng),
        )
        selected.append(nearest)
        current_lat = nearest.lat
        current_lng = nearest.lng
        remaining.remove(nearest)

    return _build_route_plan(selected, start_lat, start_lng, routes_evaluated=1)
