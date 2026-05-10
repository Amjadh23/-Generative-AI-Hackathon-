"""Feature engineering for visit prioritization (Submodule 1). Never uses raw `priority` column."""

from __future__ import annotations

import json
import math
import random
import sqlite3
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Any

EARTH_RADIUS_KM = 6371.0


def haversine_km(lat1: float, lng1: float, lat2: float, lng2: float) -> float:
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlamb = math.radians(lng2 - lng1)
    a = math.sin(dphi / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dlamb / 2) ** 2
    return 2 * EARTH_RADIUS_KM * math.asin(min(1, math.sqrt(a)))


def open_pipeline_band(value: float) -> int:
    if value < 5000:
        return 0
    if value < 15000:
        return 1
    if value < 30000:
        return 2
    return 3


OPEN_PIPELINE_BAND_LABELS = [
    "under RM5k",
    "RM5k–RM15k",
    "RM15k–RM30k",
    "above RM30k",
]


def avg_order_band(value: float) -> int:
    if value < 3000:
        return 0
    if value < 7000:
        return 1
    if value < 12000:
        return 2
    return 3


AVG_ORDER_BAND_LABELS = [
    "under RM3k",
    "RM3k–RM7k",
    "RM7k–RM12k",
    "above RM12k",
]


def total_order_band(total: float) -> int:
    if total < 10_000:
        return 0
    if total < 30_000:
        return 1
    if total < 80_000:
        return 2
    return 3


TOTAL_ORDER_BAND_LABELS = [
    "under RM10k",
    "RM10k–RM30k",
    "RM30k–RM80k",
    "above RM80k",
]

FEATURE_COLUMNS: list[str] = [
    "segment_encoded",
    "territory_id_encoded",
    "avg_order_value_band_encoded",
    "open_pipeline_band_encoded",
    "last_visit_days",
    "reorder_probability",
    "past_order_count",
    "total_order_value_band_encoded",
    "days_since_last_order",
    "visit_count",
    "last_visit_outcome_encoded",
    "distance_from_salesperson_home_km",
    "nearby_customer_count",
]


@dataclass
class EncoderMaps:
    segment: dict[str, int]
    territory_id: dict[str, int]
    last_visit_outcome: dict[str, int]

    def to_json(self) -> dict[str, Any]:
        return {
            "segment": self.segment,
            "territory_id": self.territory_id,
            "last_visit_outcome": self.last_visit_outcome,
        }

    @classmethod
    def from_json(cls, raw: dict[str, Any]) -> EncoderMaps:
        return cls(
            segment=raw["segment"],
            territory_id=raw["territory_id"],
            last_visit_outcome=raw["last_visit_outcome"],
        )


def fit_encoders(connection: sqlite3.Connection) -> EncoderMaps:
    segments = sorted(
        {row[0] for row in connection.execute("SELECT DISTINCT segment FROM customers").fetchall()}
    )
    territories = sorted(
        {row[0] for row in connection.execute("SELECT DISTINCT territory_id FROM customers").fetchall()}
    )
    outcomes = sorted(
        {row[0] for row in connection.execute("SELECT DISTINCT outcome FROM visit_history").fetchall()}
    )
    outcome_keys = outcomes + ["none"]
    return EncoderMaps(
        segment={s: i for i, s in enumerate(segments)},
        territory_id={t: i for i, t in enumerate(territories)},
        last_visit_outcome={o: i for i, o in enumerate(outcome_keys)},
    )


def _aggregate_orders(connection: sqlite3.Connection, customer_id: str) -> tuple[int, float, int | None]:
    rows = connection.execute(
        """
        SELECT order_date, amount_rm FROM orders WHERE customer_id = ? ORDER BY order_date DESC
        """,
        (customer_id,),
    ).fetchall()
    if not rows:
        return 0, 0.0, None
    total = sum(float(r["amount_rm"]) for r in rows)
    latest = rows[0]["order_date"]
    od = date.fromisoformat(str(latest))
    days_since = (date.today() - od).days
    return len(rows), total, days_since


def _visit_stats(connection: sqlite3.Connection, customer_id: str) -> tuple[int, str]:
    row = connection.execute(
        """
        SELECT outcome FROM visit_history
        WHERE customer_id = ? ORDER BY visited_at DESC LIMIT 1
        """,
        (customer_id,),
    ).fetchone()
    cnt_row = connection.execute(
        "SELECT COUNT(*) AS c FROM visit_history WHERE customer_id = ?",
        (customer_id,),
    ).fetchone()
    count = int(cnt_row["c"]) if cnt_row else 0
    outcome = str(row["outcome"]) if row else "none"
    return count, outcome


def nearby_customer_count(
    lat: float,
    lng: float,
    territory_id: str,
    others: list[tuple[str, float, float, str]],
    radius_km: float = 3.0,
) -> int:
    n = 0
    for _cid, olat, olng, t in others:
        if t != territory_id:
            continue
        if haversine_km(lat, lng, olat, olng) <= radius_km:
            n += 1
    return max(0, n - 1)


def build_customer_feature_row(
    customer_row: sqlite3.Row,
    salesperson_row: sqlite3.Row,
    encoders: EncoderMaps,
    nearby_excluding_self: int,
    connection: sqlite3.Connection,
) -> dict[str, float]:
    cid = customer_row["id"]
    past_n, total_val, days_since_order = _aggregate_orders(connection, cid)
    visit_count, last_outcome = _visit_stats(connection, cid)

    seg = str(customer_row["segment"])
    terr = str(customer_row["territory_id"])
    avg_order = float(customer_row["avg_order_value_rm"])
    pipeline = float(customer_row["open_pipeline_rm"])

    return {
        "segment_encoded": float(encoders.segment[seg]),
        "territory_id_encoded": float(encoders.territory_id[terr]),
        "avg_order_value_band_encoded": float(avg_order_band(avg_order)),
        "open_pipeline_band_encoded": float(open_pipeline_band(pipeline)),
        "last_visit_days": float(customer_row["last_visit_days"]),
        "reorder_probability": float(customer_row["reorder_probability"]),
        "past_order_count": float(past_n),
        "total_order_value_band_encoded": float(total_order_band(total_val)),
        "days_since_last_order": float(days_since_order if days_since_order is not None else 365),
        "visit_count": float(visit_count),
        "last_visit_outcome_encoded": float(encoders.last_visit_outcome[last_outcome]),
        "distance_from_salesperson_home_km": haversine_km(
            float(customer_row["lat"]),
            float(customer_row["lng"]),
            float(salesperson_row["home_lat"]),
            float(salesperson_row["home_lng"]),
        ),
        "nearby_customer_count": float(nearby_excluding_self),
    }


def row_to_matrix_row(row: dict[str, float]) -> list[float]:
    return [row[c] for c in FEATURE_COLUMNS]


def training_labels_and_rows(
    connection: sqlite3.Connection,
    encoders: EncoderMaps,
    *,
    noise_rng: random.Random | None = None,
) -> tuple[list[list[float]], list[float], list[str]]:
    rng = noise_rng or random.Random(42)
    customers = connection.execute("SELECT c.* FROM customers c ORDER BY c.id").fetchall()
    positions = [
        (str(r["id"]), float(r["lat"]), float(r["lng"]), str(r["territory_id"])) for r in customers
    ]
    xs: list[list[float]] = []
    ys: list[float] = []
    ids: list[str] = []
    for cust in customers:
        sp = connection.execute(
            "SELECT * FROM salespeople WHERE id = ?",
            (cust["assigned_salesperson_id"],),
        ).fetchone()
        if sp is None:
            continue
        near = nearby_customer_count(
            float(cust["lat"]),
            float(cust["lng"]),
            str(cust["territory_id"]),
            positions,
        )
        feat = build_customer_feature_row(cust, sp, encoders, near, connection)
        xs.append(row_to_matrix_row(feat))
        ids.append(str(cust["id"]))
        last = connection.execute(
            """
            SELECT outcome FROM visit_history
            WHERE customer_id = ? ORDER BY visited_at DESC LIMIT 1
            """,
            (cust["id"],),
        ).fetchone()
        if last is None:
            y = 0.18 + float(cust["reorder_probability"]) * 0.62
        else:
            o = str(last["outcome"])
            y = {"order": 0.92, "closed": 0.88, "follow_up": 0.70, "no_interest": 0.15}.get(o, 0.45)
        ys.append(min(0.999, max(0.001, y + rng.uniform(-0.03, 0.03))))
    return xs, ys, ids


def save_feature_columns(path: Path) -> None:
    path.write_text(json.dumps({"feature_columns": FEATURE_COLUMNS}, indent=2), encoding="utf-8")


def band_legend_meta() -> dict[str, list[str]]:
    return {
        "open_pipeline_band_encoded": OPEN_PIPELINE_BAND_LABELS,
        "avg_order_value_band_encoded": AVG_ORDER_BAND_LABELS,
        "total_order_value_band_encoded": TOTAL_ORDER_BAND_LABELS,
    }
