"""Initial City Air Tracker schema."""

from alembic import op

revision = "001_initial_schema"
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    # cities
    op.execute(
        """
        CREATE TABLE cities (
            city_id       TEXT PRIMARY KEY,
            city_name     TEXT NOT NULL,
            country_code  CHAR(2) NOT NULL,
            state_code    TEXT,
            timezone      TEXT NOT NULL,
            active        BOOLEAN NOT NULL
        )
        """
    )

    op.execute(
        """
        CREATE UNIQUE INDEX cities_city_identity_unique
            ON cities (
                city_name,
                country_code,
                COALESCE(state_code, '')
            )
        """
    )

    # pipeline_runs
    op.execute(
        """
        CREATE TABLE pipeline_runs (
            pipeline_run_id    BIGSERIAL PRIMARY KEY,
            run_id             TEXT NOT NULL UNIQUE,
            source              TEXT NOT NULL,
            history_hours       INTEGER NOT NULL,
            window_start_utc    TIMESTAMPTZ NOT NULL,
            window_end_utc      TIMESTAMPTZ NOT NULL,
            status              TEXT NOT NULL DEFAULT 'running',
            city_count          INTEGER NOT NULL DEFAULT 0,
            raw_response_count  INTEGER NOT NULL DEFAULT 0,
            gold_row_count      INTEGER NOT NULL DEFAULT 0,
            error_message       TEXT,
            finished_at         TIMESTAMPTZ,
            created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW(),

            CONSTRAINT pipeline_runs_history_hours_positive
                CHECK (history_hours > 0),

            CONSTRAINT pipeline_runs_window_valid
                CHECK (window_end_utc >= window_start_utc),

            CONSTRAINT pipeline_runs_city_count_nonnegative
                CHECK (city_count >= 0),

            CONSTRAINT pipeline_runs_raw_response_count_nonnegative
                CHECK (raw_response_count >= 0),

            CONSTRAINT pipeline_runs_gold_row_count_nonnegative
                CHECK (gold_row_count >= 0),

            CONSTRAINT pipeline_runs_status_valid
                CHECK (
                    status IN ('running', 'succeeded', 'failed')
                )
        )
        """
    )

    # raw_geocoding_responses
    op.execute(
        """
        CREATE TABLE raw_geocoding_responses (
            raw_geocoding_response_id BIGSERIAL PRIMARY KEY,
            pipeline_run_id           BIGINT NOT NULL,
            city_id                   TEXT NOT NULL,
            city_name                 TEXT NOT NULL,
            country_code              CHAR(2) NOT NULL,
            state_code                TEXT,
            lat                       DOUBLE PRECISION,
            lon                       DOUBLE PRECISION,
            coordinate_source         TEXT NOT NULL,
            endpoint                  TEXT NOT NULL,
            retrieved_at              TIMESTAMPTZ NOT NULL,
            http_status               INTEGER,
            payload                   JSONB NOT NULL,

            CONSTRAINT raw_geocoding_pipeline_run_fk
                FOREIGN KEY (pipeline_run_id)
                REFERENCES pipeline_runs (pipeline_run_id),

            CONSTRAINT raw_geocoding_city_fk
                FOREIGN KEY (city_id)
                REFERENCES cities (city_id),

            CONSTRAINT raw_geocoding_coordinate_source_valid
                CHECK (
                    coordinate_source IN (
                        'geocoded',
                        'fallback',
                        'absent'
                    )
                ),

            CONSTRAINT raw_geocoding_lat_valid
                CHECK (
                    lat IS NULL
                    OR lat BETWEEN -90 AND 90
                ),

            CONSTRAINT raw_geocoding_lon_valid
                CHECK (
                    lon IS NULL
                    OR lon BETWEEN -180 AND 180
                ),

            CONSTRAINT raw_geocoding_http_status_valid
                CHECK (
                    http_status IS NULL
                    OR http_status BETWEEN 100 AND 599
                )
        )
        """
    )

    # raw_air_pollution_responses
    op.execute(
        """
        CREATE TABLE raw_air_pollution_responses (
            raw_air_pollution_response_id BIGSERIAL PRIMARY KEY,
            pipeline_run_id               BIGINT NOT NULL,
            city_id                       TEXT NOT NULL,
            city_name                     TEXT NOT NULL,
            country_code                  CHAR(2) NOT NULL,
            state_code                    TEXT,
            lat                           DOUBLE PRECISION NOT NULL,
            lon                           DOUBLE PRECISION NOT NULL,
            start                         TIMESTAMPTZ NOT NULL,
            "end"                         TIMESTAMPTZ NOT NULL,
            endpoint                      TEXT NOT NULL,
            retrieved_at                  TIMESTAMPTZ NOT NULL,
            http_status                   INTEGER,
            payload                       JSONB NOT NULL,

            CONSTRAINT raw_air_pollution_pipeline_run_fk
                FOREIGN KEY (pipeline_run_id)
                REFERENCES pipeline_runs (pipeline_run_id),

            CONSTRAINT raw_air_pollution_city_fk
                FOREIGN KEY (city_id)
                REFERENCES cities (city_id),

            CONSTRAINT raw_air_pollution_lat_valid
                CHECK (lat BETWEEN -90 AND 90),

            CONSTRAINT raw_air_pollution_lon_valid
                CHECK (lon BETWEEN -180 AND 180),

            CONSTRAINT raw_air_pollution_window_valid
                CHECK ("end" >= start),

            CONSTRAINT raw_air_pollution_http_status_valid
                CHECK (
                    http_status IS NULL
                    OR http_status BETWEEN 100 AND 599
                )
        )
        """
    )

    # air_pollution_gold
    op.execute(
        """
        CREATE TABLE air_pollution_gold (
            city_id         TEXT NOT NULL,
            city_name       TEXT NOT NULL,
            country_code    CHAR(2) NOT NULL,
            state_code      TEXT,
            run_id          TEXT NOT NULL,
            pipeline_run_id BIGINT NOT NULL,
            observed_at     TIMESTAMPTZ NOT NULL,
            aqi             INTEGER NOT NULL,
            aqi_label       TEXT NOT NULL,
            pm2_5           DOUBLE PRECISION,
            pm10            DOUBLE PRECISION,
            co              DOUBLE PRECISION,
            no              DOUBLE PRECISION,
            no2             DOUBLE PRECISION,
            o3              DOUBLE PRECISION,
            so2              DOUBLE PRECISION,
            nh3             DOUBLE PRECISION,
            lat             DOUBLE PRECISION NOT NULL,
            lon             DOUBLE PRECISION NOT NULL,
            retrieved_at    TIMESTAMPTZ NOT NULL,

            CONSTRAINT air_pollution_gold_pk
                PRIMARY KEY (city_id, observed_at),

            CONSTRAINT air_pollution_gold_observation_time_valid
                CHECK (retrieved_at >= observed_at),

            CONSTRAINT air_pollution_gold_city_fk
                FOREIGN KEY (city_id)
                REFERENCES cities (city_id),

            CONSTRAINT air_pollution_gold_pipeline_run_fk
                FOREIGN KEY (pipeline_run_id)
                REFERENCES pipeline_runs (pipeline_run_id),

            CONSTRAINT air_pollution_gold_aqi_valid
                CHECK (aqi BETWEEN 1 AND 5),

            CONSTRAINT air_pollution_gold_pm2_5_valid
                CHECK (
                    pm2_5 IS NULL OR pm2_5 >= 0
                ),

            CONSTRAINT air_pollution_gold_pm10_valid
                CHECK (
                    pm10 IS NULL OR pm10 >= 0
                ),

            CONSTRAINT air_pollution_gold_co_valid
                CHECK (
                    co IS NULL OR co >= 0
                ),

            CONSTRAINT air_pollution_gold_no_valid
                CHECK (
                    no IS NULL OR no >= 0
                ),

            CONSTRAINT air_pollution_gold_no2_valid
                CHECK (
                    no2 IS NULL OR no2 >= 0
                ),

            CONSTRAINT air_pollution_gold_o3_valid
                CHECK (
                    o3 IS NULL OR o3 >= 0
                ),

            CONSTRAINT air_pollution_gold_so2_valid
                CHECK (
                    so2 IS NULL OR so2 >= 0
                ),

            CONSTRAINT air_pollution_gold_nh3_valid
                CHECK (
                    nh3 IS NULL OR nh3 >= 0
                ),

            CONSTRAINT air_pollution_gold_lat_valid
                CHECK (lat BETWEEN -90 AND 90),

            CONSTRAINT air_pollution_gold_lon_valid
                CHECK (lon BETWEEN -180 AND 180)
        )
        """
    )

    # Indexes
    op.execute(
        """
        CREATE INDEX idx_raw_geocoding_pipeline_run
            ON raw_geocoding_responses (pipeline_run_id)
        """
    )

    op.execute(
        """
        CREATE INDEX idx_raw_geocoding_city
            ON raw_geocoding_responses (city_id)
        """
    )

    op.execute(
        """
        CREATE INDEX idx_raw_air_pollution_pipeline_run
            ON raw_air_pollution_responses (pipeline_run_id)
        """
    )

    op.execute(
        """
        CREATE INDEX idx_raw_air_pollution_city
            ON raw_air_pollution_responses (city_id)
        """
    )

    op.execute(
        """
        CREATE INDEX idx_air_pollution_gold_observed_at
            ON air_pollution_gold (observed_at)
        """
    )

    op.execute(
        """
        CREATE INDEX idx_air_pollution_gold_pipeline_run
            ON air_pollution_gold (pipeline_run_id)
        """
    )


def downgrade() -> None:
    """Drop the entire initial schema in reverse dependency order."""

    op.execute(
        """
        DROP TABLE IF EXISTS air_pollution_gold
        """
    )

    op.execute(
        """
        DROP TABLE IF EXISTS raw_air_pollution_responses
        """
    )

    op.execute(
        """
        DROP TABLE IF EXISTS raw_geocoding_responses
        """
    )

    op.execute(
        """
        DROP TABLE IF EXISTS pipeline_runs
        """
    )

    op.execute(
        """
        DROP INDEX IF EXISTS cities_city_identity_unique
        """
    )

    op.execute(
        """
        DROP TABLE IF EXISTS cities
        """
    )