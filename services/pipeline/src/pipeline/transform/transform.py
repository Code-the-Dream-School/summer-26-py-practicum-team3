from datetime import datetime, timezone

def transform_raw_response(raw_response):
    """
    Transform one RawResponse envelope into a list of clean
    air-quality observation records.

    One observation in payload["list"] becomes one output record.
    """

    # Response-level validation
    if not isinstance(raw_response, dict):
        raise ValueError("raw_response must be a dictionary")

    payload = raw_response.get("payload")

    if not isinstance(payload, dict):
        raise ValueError("RawResponse payload is missing or invalid")

    observations = payload.get("list")

    if observations is None:
        raise ValueError("RawResponse payload.list is missing")

    if not isinstance(observations, list):
        raise ValueError("RawResponse payload.list must be a list")

    # Empty response produces no records
    if not observations:
        return []

    records = []

    for observation in observations:
        if not isinstance(observation, dict):
            continue

        # Required location/context fields
        city_id = raw_response.get("city_id")
        lat = raw_response.get("lat")
        lon = raw_response.get("lon")

        if city_id is None or lat is None or lon is None:
            continue

        # Required observation timestamp
        dt = observation.get("dt")

        if dt is None:
            continue

        try:
            observed_at = datetime.fromtimestamp(
                int(dt),
                tz=timezone.utc,
            )
        except (TypeError, ValueError, OSError):
            continue

        # Coordinates
        try:
            lat = float(lat)
            lon = float(lon)
        except (TypeError, ValueError):
            continue

        if not (-90 <= lat <= 90):
            continue

        if not (-180 <= lon <= 180):
            continue

        # AQI
        main = observation.get("main") or {}

        try:
            aqi = int(main.get("aqi"))
        except (TypeError, ValueError):
            continue

        if aqi not in (1, 2, 3, 4, 5):
            continue

        aqi_labels = {
            1: "Good",
            2: "Fair",
            3: "Moderate",
            4: "Poor",
            5: "Very Poor",
        }

        # Pollutants
        components = observation.get("components") or {}

        clean_components = {}

        for field in (
            "co",
            "no",
            "no2",
            "o3",
            "so2",
            "pm2_5",
            "pm10",
            "nh3",
        ):
            value = components.get(field)

            if value is None:
                clean_components[field] = None
                continue

            try:
                value = float(value)
            except (TypeError, ValueError):
                clean_components[field] = None
                continue

            if value < 0:
                clean_components[field] = None
            else:
                clean_components[field] = round(value, 2)

        # Text cleanup
        def clean_text(value):
            if value is None:
                return None

            value = str(value).strip()

            return value if value else None

        record = {
            "city_id": city_id,
            "city_name": clean_text(raw_response.get("city_name")),
            "country_code": clean_text(raw_response.get("country_code")),
            "state_code": clean_text(raw_response.get("state_code")),
            "lat": lat,
            "lon": lon,
            "observed_at": observed_at,
            "aqi": aqi,
            "aqi_label": aqi_labels[aqi],
            **clean_components,
            "run_id": raw_response.get("run_id"),
            "pipeline_run_id": raw_response.get("pipeline_run_id"),
            "retrieved_at": raw_response.get("retrieved_at"),
        }

        records.append(record)

    return records
