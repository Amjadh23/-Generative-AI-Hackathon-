from __future__ import annotations

import argparse
import csv
import math
import random
import sqlite3
from dataclasses import dataclass
from datetime import date, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_OUTPUT = ROOT / "data" / "seed" / "hilti.sqlite"
DEFAULT_CSV_DIR = ROOT / "data" / "seed" / "csv"
RANDOM_SEED = 20260509

SEGMENTS = ["contractor", "distributor", "project_site", "maintenance"]
PRODUCT_FAMILIES = ["anchors", "power_tools", "firestop", "measuring", "fasteners"]
OUTCOMES = ["order", "follow_up", "no_interest", "closed"]

CUSTOMER_PREFIXES = [
    "Apex",
    "Bintang",
    "Cahaya",
    "Delta",
    "Eagle",
    "Fortis",
    "Gemilang",
    "Harapan",
    "Ikon",
    "Jaya",
    "Kencana",
    "Metro",
]

CUSTOMER_SUFFIXES = [
    "Construction",
    "Buildmart",
    "Project Supply",
    "Engineering",
    "Contractors",
    "Trading",
    "Industrial",
    "Site Services",
]


@dataclass(frozen=True)
class TerritorySeed:
    id: str
    name: str
    center_lat: float
    center_lng: float
    radius_km: float
    salesperson_name: str


TERRITORIES = [
    TerritorySeed("terr-kl-central", "KL Central", 3.1390, 101.6869, 7.0, "Aina Rahman"),
    TerritorySeed("terr-ampang", "Ampang", 3.1496, 101.7611, 6.0, "Daniel Tan"),
    TerritorySeed("terr-pj", "Petaling Jaya", 3.1073, 101.6067, 7.0, "Mei Wong"),
    TerritorySeed("terr-shah-alam", "Shah Alam", 3.0738, 101.5183, 8.0, "Arif Hakim"),
    TerritorySeed("terr-cheras", "Cheras", 3.1056, 101.7252, 6.5, "Priya Nair"),
]


def create_schema(connection: sqlite3.Connection) -> None:
    connection.executescript(
        """
        DROP TABLE IF EXISTS orders;
        DROP TABLE IF EXISTS visit_history;
        DROP TABLE IF EXISTS customers;
        DROP TABLE IF EXISTS salespeople;
        DROP TABLE IF EXISTS territories;

        CREATE TABLE territories (
            id TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            center_lat REAL NOT NULL,
            center_lng REAL NOT NULL,
            radius_km REAL NOT NULL
        );

        CREATE TABLE salespeople (
            id TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            territory_id TEXT NOT NULL REFERENCES territories(id),
            home_lat REAL NOT NULL,
            home_lng REAL NOT NULL,
            max_daily_stops INTEGER NOT NULL
        );

        CREATE TABLE customers (
            id TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            segment TEXT NOT NULL,
            territory_id TEXT NOT NULL REFERENCES territories(id),
            assigned_salesperson_id TEXT NOT NULL REFERENCES salespeople(id),
            lat REAL NOT NULL,
            lng REAL NOT NULL,
            priority INTEGER NOT NULL,
            avg_order_value_rm REAL NOT NULL,
            open_pipeline_rm REAL NOT NULL,
            last_visit_days INTEGER NOT NULL,
            reorder_probability REAL NOT NULL
        );

        CREATE TABLE visit_history (
            id TEXT PRIMARY KEY,
            customer_id TEXT NOT NULL REFERENCES customers(id),
            salesperson_id TEXT NOT NULL REFERENCES salespeople(id),
            visited_at TEXT NOT NULL,
            outcome TEXT NOT NULL,
            notes TEXT
        );

        CREATE TABLE orders (
            id TEXT PRIMARY KEY,
            customer_id TEXT NOT NULL REFERENCES customers(id),
            order_date TEXT NOT NULL,
            amount_rm REAL NOT NULL,
            product_family TEXT NOT NULL
        );
        """
    )


def random_point_near(center_lat: float, center_lng: float, radius_km: float) -> tuple[float, float]:
    distance = radius_km * math.sqrt(random.random()) * 0.92
    bearing = random.random() * math.tau
    delta_lat = (distance * math.cos(bearing)) / 111.0
    delta_lng = (distance * math.sin(bearing)) / (111.0 * math.cos(math.radians(center_lat)))
    return round(center_lat + delta_lat, 6), round(center_lng + delta_lng, 6)


def customer_name(index: int) -> str:
    prefix = CUSTOMER_PREFIXES[index % len(CUSTOMER_PREFIXES)]
    suffix = CUSTOMER_SUFFIXES[(index * 3) % len(CUSTOMER_SUFFIXES)]
    return f"{prefix} {suffix} {index + 1:03d}"


def seed_database(output_path: Path = DEFAULT_OUTPUT, customers_per_territory: int = 80) -> Path:
    random.seed(RANDOM_SEED)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    with sqlite3.connect(output_path) as connection:
        create_schema(connection)
        cursor = connection.cursor()

        for territory in TERRITORIES:
            cursor.execute(
                "INSERT INTO territories VALUES (?, ?, ?, ?, ?)",
                (
                    territory.id,
                    territory.name,
                    territory.center_lat,
                    territory.center_lng,
                    territory.radius_km,
                ),
            )
            cursor.execute(
                "INSERT INTO salespeople VALUES (?, ?, ?, ?, ?, ?)",
                (
                    f"sp-{territory.id.replace('terr-', '')}",
                    territory.salesperson_name,
                    territory.id,
                    territory.center_lat,
                    territory.center_lng,
                    8,
                ),
            )

        today = date.today()
        customer_index = 0
        for territory in TERRITORIES:
            salesperson_id = f"sp-{territory.id.replace('terr-', '')}"
            for _ in range(customers_per_territory):
                lat, lng = random_point_near(
                    territory.center_lat,
                    territory.center_lng,
                    territory.radius_km,
                )
                segment = random.choice(SEGMENTS)
                priority = random.choices([1, 2, 3, 4, 5], weights=[8, 16, 28, 30, 18])[0]
                avg_order_value = round(random.uniform(1200, 12000) * (1 + priority / 12), 2)
                open_pipeline = round(avg_order_value * random.uniform(0.2, 1.8), 2)
                last_visit_days = random.randint(5, 120)
                reorder_probability = round(
                    min(0.95, 0.18 + priority * 0.11 + last_visit_days / 260 + random.uniform(-0.08, 0.08)),
                    3,
                )
                customer_id = f"cust-{customer_index + 1:04d}"

                cursor.execute(
                    "INSERT INTO customers VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                    (
                        customer_id,
                        customer_name(customer_index),
                        segment,
                        territory.id,
                        salesperson_id,
                        lat,
                        lng,
                        priority,
                        avg_order_value,
                        open_pipeline,
                        last_visit_days,
                        reorder_probability,
                    ),
                )

                visit_count = random.randint(1, 5)
                for visit_number in range(visit_count):
                    visited_at = today - timedelta(days=random.randint(10, 240))
                    outcome = random.choices(OUTCOMES, weights=[42, 34, 14, 10])[0]
                    cursor.execute(
                        "INSERT INTO visit_history VALUES (?, ?, ?, ?, ?, ?)",
                        (
                            f"visit-{customer_index + 1:04d}-{visit_number + 1}",
                            customer_id,
                            salesperson_id,
                            visited_at.isoformat(),
                            outcome,
                            f"Synthetic {outcome.replace('_', ' ')} visit.",
                        ),
                    )

                order_count = random.randint(1, 6)
                for order_number in range(order_count):
                    order_date = today - timedelta(days=random.randint(7, 365))
                    amount = round(avg_order_value * random.uniform(0.35, 1.6), 2)
                    cursor.execute(
                        "INSERT INTO orders VALUES (?, ?, ?, ?, ?)",
                        (
                            f"order-{customer_index + 1:04d}-{order_number + 1}",
                            customer_id,
                            order_date.isoformat(),
                            amount,
                            random.choice(PRODUCT_FAMILIES),
                        ),
                    )

                customer_index += 1

        connection.commit()

    return output_path


def export_csv(sqlite_path: Path = DEFAULT_OUTPUT, csv_dir: Path = DEFAULT_CSV_DIR) -> None:
    csv_dir.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(sqlite_path) as connection:
        connection.row_factory = sqlite3.Row
        for table in ["territories", "salespeople", "customers", "visit_history", "orders"]:
            rows = connection.execute(f"SELECT * FROM {table}").fetchall()
            if not rows:
                continue

            with (csv_dir / f"{table}.csv").open("w", newline="", encoding="utf-8") as file:
                writer = csv.DictWriter(file, fieldnames=rows[0].keys())
                writer.writeheader()
                writer.writerows(dict(row) for row in rows)


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate synthetic Hilti KL sales data.")
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--customers-per-territory", type=int, default=80)
    parser.add_argument("--csv", action="store_true", help="Export CSV files beside the SQLite seed.")
    args = parser.parse_args()

    sqlite_path = seed_database(args.output, args.customers_per_territory)
    if args.csv:
        export_csv(sqlite_path)

    print(f"Generated {sqlite_path}")


if __name__ == "__main__":
    main()
