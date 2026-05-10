import sqlite3

from app.data.generate import seed_database


def test_seed_database_shape(tmp_path) -> None:
    db_path = seed_database(tmp_path / "hilti.sqlite", customers_per_territory=80)

    with sqlite3.connect(db_path) as connection:
        territories = connection.execute("SELECT COUNT(*) FROM territories").fetchone()[0]
        salespeople = connection.execute("SELECT COUNT(*) FROM salespeople").fetchone()[0]
        customers = connection.execute("SELECT COUNT(*) FROM customers").fetchone()[0]
        min_customers = connection.execute(
            """
            SELECT MIN(customer_count)
            FROM (
                SELECT assigned_salesperson_id, COUNT(*) AS customer_count
                FROM customers
                GROUP BY assigned_salesperson_id
            )
            """
        ).fetchone()[0]
        max_customers = connection.execute(
            """
            SELECT MAX(customer_count)
            FROM (
                SELECT assigned_salesperson_id, COUNT(*) AS customer_count
                FROM customers
                GROUP BY assigned_salesperson_id
            )
            """
        ).fetchone()[0]

    assert territories == 5
    assert salespeople == 5
    assert customers == 400
    assert min_customers == 80
    assert max_customers == 80
