from __future__ import annotations

import sqlite3
from collections import Counter
from pathlib import Path

from app.data.generate import DEFAULT_OUTPUT, PRODUCT_FAMILIES

FAMILY_PITCHES: dict[str, str] = {
    "anchors": "show the new anchor range and confirm certified install spec",
    "power_tools": "demo the latest cordless power tools and Fleet Management plan",
    "firestop": "review compliance and offer firestop documentation support",
    "measuring": "introduce updated measuring tools and trade-in offer",
    "fasteners": "push fastener cross-sell and bulk-order pricing",
}


def build_focus(customer_id: str, database_path: Path = DEFAULT_OUTPUT) -> str:
    """Generate a one-line meeting focus from order history and segment context."""
    with sqlite3.connect(database_path) as connection:
        connection.row_factory = sqlite3.Row
        customer = connection.execute(
            "SELECT segment FROM customers WHERE id = ?",
            (customer_id,),
        ).fetchone()
        if customer is None:
            return "Confirm needs and capture next opportunity."

        family_counts = Counter(
            row["product_family"]
            for row in connection.execute(
                "SELECT product_family FROM orders WHERE customer_id = ?",
                (customer_id,),
            ).fetchall()
        )

    if family_counts:
        top_family, _ = family_counts.most_common(1)[0]
        missing_families = [family for family in PRODUCT_FAMILIES if family not in family_counts]
        if missing_families:
            cross_sell = missing_families[0]
            return (
                f"Reinforce {top_family.replace('_', ' ')} loyalty and "
                f"{FAMILY_PITCHES[cross_sell]}."
            )
        return f"Deepen {top_family.replace('_', ' ')} share-of-wallet and confirm next reorder."

    segment = customer["segment"]
    if segment == "project_site":
        return "Walk the site, identify upcoming phases, and propose an anchor + firestop kit."
    if segment == "distributor":
        return "Review stock turn, top up fast-moving SKUs, and align on co-marketing."
    if segment == "maintenance":
        return "Audit tool fleet status and offer Fleet Management subscription."
    return "Discover active projects and qualify two new opportunities."
