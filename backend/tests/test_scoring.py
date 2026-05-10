from app.data.generate import seed_database
from app.ml.prioritization.engine import bin_priority_class, recommended_action_for_class
from app.ml.prioritization.features import FEATURE_COLUMNS
from app.ml.score import score_customer, top_customers_for_salesperson


def test_submodule1_feature_set_excludes_crm_priority() -> None:
    assert "priority" not in FEATURE_COLUMNS
    assert bin_priority_class(0.39) == "Low"
    assert bin_priority_class(0.40) == "Medium"
    assert bin_priority_class(0.69) == "Medium"
    assert bin_priority_class(0.70) == "High"
    assert recommended_action_for_class("Low") == "Schedule follow-up"
    assert recommended_action_for_class("High") == "Visit today"


def test_score_customer_returns_explainable_score(tmp_path) -> None:
    db_path = seed_database(tmp_path / "hilti.sqlite", customers_per_territory=80)

    score = score_customer("cust-0001", db_path)

    assert score.customer_id == "cust-0001"
    assert 0 <= score.visit_likelihood_score <= 1
    assert 0 <= score.score <= 100
    assert score.priority_class in {"Low", "Medium", "High"}
    assert score.recommended_action in {"Visit today", "Schedule follow-up"}
    assert score.expected_return_rm > 0
    assert "expected return" in score.reason or score.top_reasons
    assert "priority" not in score.contributions
    if score.top_reasons:
        assert all(isinstance(s, str) for s in score.top_reasons)


def test_top_customers_are_sorted_by_score(tmp_path) -> None:
    db_path = seed_database(tmp_path / "hilti.sqlite", customers_per_territory=80)

    top_customers = top_customers_for_salesperson("sp-kl-central", limit=10, database_path=db_path)

    assert len(top_customers) == 10
    assert top_customers[0].score >= top_customers[-1].score
