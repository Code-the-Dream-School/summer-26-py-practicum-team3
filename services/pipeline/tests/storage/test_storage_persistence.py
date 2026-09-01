""" test load/ - insert, raw, gold response, transformed record, upsert """

def test_sanity_insert(db_connection, seeded_city_and_run):
    """Sanity test: fixture inserts city + pipeline_run correctly."""
    city_id, pipeline_run_id = seeded_city_and_run

    # Verify city exists
    with db_connection.cursor() as cur:
        cur.execute("SELECT city_name FROM cities WHERE city_id = %s;", (city_id,))
        row = cur.fetchone()
    assert row == ("Los Angeles",)

    # Verify pipeline_run exists
    with db_connection.cursor() as cur:
        cur.execute(
            "SELECT run_id FROM pipeline_runs WHERE pipeline_run_id = %s;",
            (pipeline_run_id,),
        )
        row = cur.fetchone()

    assert row == ("test-run-1",)
