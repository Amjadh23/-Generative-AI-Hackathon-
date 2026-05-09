from app.data.generate import seed_database
from app.ml.score import score_customer, top_customers_for_salesperson


def test_score_customer_returns_explainable_score(tmp_path) -> None:
    db_path = seed_database(tmp_path / "hilti.sqlite", customers_per_territory=80)

    score = score_customer("cust-0001", db_path)

    assert score.customer_id == "cust-0001"
    assert 0 <= score.score <= 100
    assert score.expected_return_rm > 0
    assert "expected return" in score.reason
    assert set(score.contributions) == {
        "priority",
        "recency",
        "pipeline",
        "order_value",
        "reorder_probability",
    }


def test_top_customers_are_sorted_by_score(tmp_path) -> None:
    db_path = seed_database(tmp_path / "hilti.sqlite", customers_per_territory=80)

    top_customers = top_customers_for_salesperson("sp-kl-central", limit=10, database_path=db_path)

    assert len(top_customers) == 10
    assert top_customers[0].score >= top_customers[-1].score
