"""
TEMPORARY TEST DB LAYER
This fake in-memory DB is only for running tests without PostgreSQL.
It should be removed once the real storage layer is implemented
and replaced with proper integration tests using a real database.
"""

import pytest


# In-memory "tables"
FAKE_DB = {
    "raw_geocoding_responses": [],
    "raw_air_pollution_responses": [],
    "air_pollution_gold": [],
}

def reset_fake_db():
    FAKE_DB["raw_geocoding_responses"].clear()
    FAKE_DB["raw_air_pollution_responses"].clear()
    FAKE_DB["air_pollution_gold"].clear()

class FakeCursor:
    def __init__(self):
        self._result = None

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        pass

    def execute(self, sql, params=None):
        sql_lower = sql.lower()

        # --- INSERT handling ---
        if "insert into raw_geocoding_responses" in sql_lower:
            row = {
                "city_id": params["city_id"],
                "city_name": params["city_name"],
            }
            FAKE_DB["raw_geocoding_responses"].append(row)
            self._result = [(row["city_id"], row["city_name"])]

        elif "insert into raw_air_pollution_responses" in sql_lower:
            row = {
                "city_id": params["city_id"],
                "city_name": params["city_name"],
            }
            FAKE_DB["raw_air_pollution_responses"].append(row)
            self._result = [(row["city_id"], row["city_name"])]

        elif "insert into air_pollution_gold" in sql_lower:
            row = {
                "city_id": params["city_id"],
                "aqi": params["aqi"],
            }
            FAKE_DB["air_pollution_gold"].append(row)
            self._result = None

        # --- SELECT handling ---
        elif "from raw_geocoding_responses" in sql_lower:
            city_id = params[0]
            for row in FAKE_DB["raw_geocoding_responses"]:
                if row["city_id"] == city_id:
                    self._result = [(row["city_id"], row["city_name"])]
                    return
            self._result = None

        elif "from raw_air_pollution_responses" in sql_lower:
            city_id = params[0]
            for row in FAKE_DB["raw_air_pollution_responses"]:
                if row["city_id"] == city_id:
                    self._result = [(row["city_id"], row["city_name"])]
                    return
            self._result = None

        elif "from air_pollution_gold" in sql_lower:
            city_id = params[0]
            for row in FAKE_DB["air_pollution_gold"]:
                if row["city_id"] == city_id:
                    self._result = [(row["city_id"], row["aqi"])]
                    return
            self._result = None

    def executemany(self, sql, rows):
        for params in rows:
            self.execute(sql, params)

    def fetchone(self):
        if self._result:
            return self._result[0]
        return None


class FakeConnection:
    def cursor(self):
        return FakeCursor()

    def commit(self):
        pass

    def rollback(self):
        pass


@pytest.fixture(autouse=True)
def conn():
    print("FAKE_DB before reset:", FAKE_DB)
    reset_fake_db()
    print("FAKE_DB before test:", FAKE_DB)
    return FakeConnection()
