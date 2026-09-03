from pipeline.load.upsert import (
    AIR_QUALITY_UPSERT_SQL,
    upsert_air_quality_record,
    upsert_air_quality_records,
)

def make_record(**overrides):
    record = {
        "city_id": "us-san-francisco-ca",
        "observed_at": "2024-07-03T00:26:40Z",
        "city_name": "San Francisco",
        "country_code": "US",
        "state_code": "CA",
        "lat": 37.7749,
        "lon": -122.4194,
        "aqi": 2,
        "aqi_label": "Fair",
        "co": 201.94,
        "no": 0.0,
        "no2": 1.2,
        "o3": 68.6,
        "so2": 0.6,
        "pm2_5": 4.3,
        "pm10": 5.1,
        "nh3": 0.12,
        "run_id": "run-2024-07-03-001",
        "pipeline_run_id": "pipeline-2024-07-03-001",
        "retrieved_at": "2024-07-04T00:00:00Z",
    }

    record.update(overrides)
    return record


class FakeCursor:
    def __init__(self):
        self.executed = []
        self.rowcount = 0

    def execute(self, sql, parameters):
        self.executed.append((sql, parameters))
        self.rowcount = 1


def test_new_record_is_inserted():
    cursor = FakeCursor()
    record = make_record()

    upsert_air_quality_record(cursor, record)

    assert len(cursor.executed) == 1
    sql, parameters = cursor.executed[0]

    assert "INSERT INTO air_pollution_gold" in sql
    assert "ON CONFLICT (city_id, observed_at)" in sql
    assert parameters == record


def test_upsert_sql_includes_conflict_update():
    cursor = FakeCursor()
    record = make_record()

    upsert_air_quality_record(cursor, record)

    assert len(cursor.executed) == 1
    assert "ON CONFLICT (city_id, observed_at)" in cursor.executed[0][0]
    assert "DO UPDATE SET" in cursor.executed[0][0]


def test_changed_record_values_are_passed_to_upsert():
    cursor = FakeCursor()

    record = make_record(aqi=2, aqi_label="Fair")
    updated_record = make_record(aqi=4, aqi_label="Poor")

    upsert_air_quality_record(cursor, record)
    upsert_air_quality_record(cursor, updated_record)

    assert len(cursor.executed) == 2
    assert cursor.executed[1][1]["aqi"] == 4
    assert cursor.executed[1][1]["aqi_label"] == "Poor"


def test_different_observation_timestamp_is_a_different_record():
    cursor = FakeCursor()

    first_record = make_record(
        observed_at="2024-07-03T00:26:40Z"
    )
    second_record = make_record(
        observed_at="2024-07-03T01:26:40Z"
    )

    upsert_air_quality_records(
        cursor,
        [first_record, second_record],
    )

    assert len(cursor.executed) == 2
    assert (
        cursor.executed[0][1]["observed_at"]
        != cursor.executed[1][1]["observed_at"]
    )


def test_empty_records_do_nothing():
    cursor = FakeCursor()

    upsert_air_quality_records(cursor, [])

    assert cursor.executed == []


def test_none_record_does_nothing():
    cursor = FakeCursor()

    upsert_air_quality_record(cursor, None)

    assert cursor.executed == []
