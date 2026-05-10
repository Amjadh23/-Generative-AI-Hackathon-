"""Submodule 1: XGBoost visit likelihood + Tree SHAP-style contributions."""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import Any

import xgboost as xgb

from app.ml.prioritization.features import (
    FEATURE_COLUMNS,
    EncoderMaps,
    band_legend_meta,
    build_customer_feature_row,
    fit_encoders,
    nearby_customer_count,
    row_to_matrix_row,
    training_labels_and_rows,
)
from app.ml.prioritization.meanings import build_top_reasons

MODEL_FILENAME = "prioritization_xgb.json"
META_FILENAME = "prioritization_meta.json"
FEATURE_COL_JSON = "prioritization_feature_columns.json"

# In-process caches: admin dashboard scores hundreds of customers; reloading the booster
# and re-scanning all rows per customer would be O(n²) and time out the HTTP request.
_bundle_cache: dict[str, tuple[xgb.Booster, EncoderMaps, dict[str, list[str]]]] = {}
_positions_cache: dict[str, list[tuple[str, float, float, str]]] = {}


def clear_prioritization_cache(database_path: Path | None = None) -> None:
    """Call after retraining or replacing the SQLite file so caches stay coherent."""
    global _bundle_cache, _positions_cache
    if database_path is None:
        _bundle_cache.clear()
        _positions_cache.clear()
        return
    key = str(database_path.resolve())
    _bundle_cache.pop(key, None)
    _positions_cache.pop(key, None)


def model_paths_for_db(database_path: Path) -> tuple[Path, Path, Path]:
    parent = database_path.parent
    return (
        parent / MODEL_FILENAME,
        parent / META_FILENAME,
        parent / FEATURE_COL_JSON,
    )


def train_and_save_artifacts(database_path: Path) -> None:
    with sqlite3.connect(database_path) as connection:
        connection.row_factory = sqlite3.Row
        encoders = fit_encoders(connection)
        xs, ys, _ids = training_labels_and_rows(connection, encoders)

    if len(xs) < 10:
        return

    dtrain = xgb.DMatrix(xs, label=ys, feature_names=FEATURE_COLUMNS)
    params = {
        "max_depth": 5,
        "eta": 0.08,
        "subsample": 0.9,
        "colsample_bytree": 0.9,
        "objective": "reg:squarederror",
        "seed": 42,
    }
    booster = xgb.train(params, dtrain, num_boost_round=120)

    model_path, meta_path, fc_path = model_paths_for_db(database_path)
    model_path.parent.mkdir(parents=True, exist_ok=True)
    booster.save_model(str(model_path))

    meta = {
        "encoders": encoders.to_json(),
        "band_legends": band_legend_meta(),
        "feature_columns": FEATURE_COLUMNS,
    }
    meta_path.write_text(json.dumps(meta, indent=2), encoding="utf-8")
    fc_path.write_text(json.dumps({"feature_columns": FEATURE_COLUMNS}, indent=2), encoding="utf-8")
    clear_prioritization_cache(database_path)


def bin_priority_class(score: float) -> str:
    if score < 0.40:
        return "Low"
    if score < 0.70:
        return "Medium"
    return "High"


def recommended_action_for_class(priority_class: str) -> str:
    """Aligned with architecture: Low visits are deferred; Medium/High warrant a visit today."""
    return "Schedule follow-up" if priority_class == "Low" else "Visit today"


def load_runtime_bundle(
    database_path: Path,
) -> tuple[xgb.Booster, EncoderMaps, dict[str, list[str]]] | None:
    model_path, meta_path, _ = model_paths_for_db(database_path)
    if not model_path.exists() or not meta_path.exists():
        return None
    booster = xgb.Booster()
    booster.load_model(str(model_path))
    meta = json.loads(meta_path.read_text(encoding="utf-8"))
    encoders = EncoderMaps.from_json(meta["encoders"])
    bands = meta["band_legends"]
    return booster, encoders, bands


def get_cached_bundle(
    database_path: Path,
) -> tuple[xgb.Booster, EncoderMaps, dict[str, list[str]]] | None:
    key = str(database_path.resolve())
    if key not in _bundle_cache:
        loaded = load_runtime_bundle(database_path)
        if loaded is None:
            return None
        _bundle_cache[key] = loaded
    return _bundle_cache[key]


def get_cached_customer_positions(
    connection: sqlite3.Connection, database_path: Path
) -> list[tuple[str, float, float, str]]:
    key = str(database_path.resolve())
    if key not in _positions_cache:
        _positions_cache[key] = [
            (str(r["id"]), float(r["lat"]), float(r["lng"]), str(r["territory_id"]))
            for r in connection.execute("SELECT id, lat, lng, territory_id FROM customers").fetchall()
        ]
    return _positions_cache[key]


def predict_with_explanations(
    customer_row: sqlite3.Row,
    connection: sqlite3.Connection,
    database_path: Path,
) -> dict[str, Any] | None:
    bundle = get_cached_bundle(database_path)
    if bundle is None:
        return None
    booster, encoders, band_legends = bundle
    sp = connection.execute(
        "SELECT * FROM salespeople WHERE id = ?",
        (customer_row["assigned_salesperson_id"],),
    ).fetchone()
    if sp is None:
        return None
    positions = get_cached_customer_positions(connection, database_path)
    near = nearby_customer_count(
        float(customer_row["lat"]),
        float(customer_row["lng"]),
        str(customer_row["territory_id"]),
        positions,
    )
    feat_row = build_customer_feature_row(customer_row, sp, encoders, near, connection)
    x_row = row_to_matrix_row(feat_row)
    dm = xgb.DMatrix([x_row], feature_names=FEATURE_COLUMNS)
    raw = float(booster.predict(dm)[0])
    visit_score = min(0.999, max(0.001, raw))
    pclass = bin_priority_class(visit_score)
    contribs_matrix = booster.predict(dm, pred_contribs=True)
    row_c = contribs_matrix[0]
    bias = float(row_c[-1])
    shap_part = row_c[:-1]
    top_payload, bullets = build_top_reasons(
        FEATURE_COLUMNS,
        [float(v) for v in shap_part],
        feat_row,
        band_legends,
        Path(__file__).resolve().parent / "feature_meanings.json",
    )
    return {
        "visit_likelihood_score": round(visit_score, 4),
        "priority_class": pclass,
        "recommended_action": recommended_action_for_class(pclass),
        "xgboost_explanation_payload": {
            "base_value": round(bias, 4),
            "top_priority_reasons": top_payload,
        },
        "top_reasons": bullets,
    }


def prioritization_paths_exist(database_path: Path | None = None) -> bool:
    if database_path is None:
        from app.data.generate import DEFAULT_OUTPUT

        database_path = DEFAULT_OUTPUT
    mp, m2, _ = model_paths_for_db(database_path)
    return mp.exists() and m2.exists()
