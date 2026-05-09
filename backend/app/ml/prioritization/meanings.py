"""Map XGBoost SHAP-style contributions to human-readable sentences."""

from __future__ import annotations

import json
from pathlib import Path


def load_meanings(path: Path) -> dict[str, str]:
    return json.loads(path.read_text(encoding="utf-8"))


def format_meaning(
    feature: str,
    template: str,
    feat_row: dict[str, float],
    band_legends: dict[str, list[str]],
) -> str:
    val = feat_row.get(feature)
    if val is None:
        return template

    if feature == "reorder_probability":
        return template.format(percent_value=round(float(val) * 100))
    if feature in (
        "last_visit_days",
        "past_order_count",
        "days_since_last_order",
        "visit_count",
        "nearby_customer_count",
    ):
        return template.format(int_value=int(round(float(val))))
    if feature == "distance_from_salesperson_home_km":
        return template.format(value_rounded=round(float(val), 1))
    if feature in band_legends:
        idx = int(round(float(val)))
        idx = max(0, min(len(band_legends[feature]) - 1, idx))
        band = band_legends[feature][idx]
        return template.format(band_value=band)
    if feature == "last_visit_outcome_encoded":
        return template
    if feature in ("segment_encoded", "territory_id_encoded"):
        return template
    return template.format(int_value=int(round(float(val))), percent_value=round(float(val) * 100))


def _display_actual_for_feature(
    name: str,
    feat_row: dict[str, float],
    band_legends: dict[str, list[str]],
) -> object:
    actual = feat_row.get(name, 0.0)
    if name in band_legends:
        idx = int(round(float(actual)))
        idx = max(0, min(len(band_legends[name]) - 1, idx))
        return band_legends[name][idx]
    return round(float(actual), 4)


def _human_feature_label(name: str) -> str:
    return name.replace("_encoded", "").replace("_", " ")


def build_top_reasons(
    feature_names: list[str],
    contributions: list[float],
    feat_row: dict[str, float],
    band_legends: dict[str, list[str]],
    meanings_path: Path,
    *,
    max_reasons: int = 5,
    max_decreased: int = 2,
) -> tuple[list[dict[str, object]], list[str]]:
    """contributions: per-feature SHAP values (excluding bias column)."""
    meanings = load_meanings(meanings_path)
    pairs = list(zip(feature_names, contributions, strict=True))
    positive = [(n, c) for n, c in pairs if c > 0 and n in meanings]
    positive.sort(key=lambda x: x[1], reverse=True)
    top = positive[:max_reasons]

    payload_reasons: list[dict[str, object]] = []
    bullets: list[str] = []
    for name, shap_val in top:
        template = meanings[name]
        meaning = format_meaning(name, template, feat_row, band_legends)
        display_actual = _display_actual_for_feature(name, feat_row, band_legends)
        payload_reasons.append(
            {
                "feature": name,
                "actual_value": display_actual,
                "shap_value": round(float(shap_val), 4),
                "effect": "increased_priority",
                "meaning": meaning,
            }
        )
        short = meaning.split(", which")[0].strip()
        if short.endswith("."):
            bullets.append(short)
        else:
            bullets.append(f"{short}.")

    negative = [(n, c) for n, c in pairs if c < 0 and n in meanings]
    negative.sort(key=lambda x: x[1])
    for name, shap_val in negative[:max_decreased]:
        display_actual = _display_actual_for_feature(name, feat_row, band_legends)
        label = _human_feature_label(name)
        meaning = (
            f"For this customer, {label} (value: {display_actual}) pulled the visit likelihood "
            "below the model baseline for that factor."
        )
        payload_reasons.append(
            {
                "feature": name,
                "actual_value": display_actual,
                "shap_value": round(float(shap_val), 4),
                "effect": "decreased_priority",
                "meaning": meaning,
            }
        )
        bullets.append(f"Downward factor: {label}.")

    return payload_reasons, bullets
