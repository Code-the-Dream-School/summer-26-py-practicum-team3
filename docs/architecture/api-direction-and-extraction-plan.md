# City Air Tracker - API Direction & Extraction Plan

**Status:** API exploration artifact - not a final DB schema. 

**Scope:** Explore the available OpenWeather API(s) and identify which ones — potentially more than one, with alternates where it makes sense — could support the dashboard, confirm each choice against what the dashboard will show, and give the extract layer enough to build against.

---

## 1. Resolving coordinates: Geocoding API is primary

The **Geocoding API** is the dedicated, supported endpoint for turning a city name into `lat`/`lon`:

```
http://api.openweathermap.org/geo/1.0/direct?q={city name}&appid={API key}
```

```json
[
  {
    "name": "San Francisco",
    "lat": 37.7749295,
    "lon": -122.4194155,
    "country": "US",
    "state": "California"
  }
]
```

It returns only location data — no weather — but it's purpose-built for this step, isn't tied to a query param OpenWeather has deprecated, and is the recommended long-term path for resolving a new city's coordinates.

## 2. APIs Available by Name: three, not one

OpenWeather isn't a single API - it's a family of separate products. The dashboard's goal isn't "air quality in isolation," it's air quality **in context**. This bundle of is three APIs -- one proposal for consideration, not yet decided, and not the primary path -- would each answer one dashboard question:

| API | Dashboard question it answers |
|---|---|
| **Current Weather Data** | What are conditions right now? (temp, wind, humidity - context for today's air quality reading) |
| **5 Day / 3 Hour Forecast** | What's coming in the next couple of days? |
| **Air Pollution** | What's the air quality - now, and (via its own forecast endpoint) over the next 4 days? |

All three are free-tier, coordinate-based (`lat`/`lon`), and share the same key and account limits (60 calls/min, 1,000,000 calls/month) - so they compose cleanly into one extract layer without separate billing or auth to manage.

### Why this bundle fits the dashboard goal

- **Weather and air quality are correlated, not independent** - wind, rain, and temperature all move pollutant concentrations. Pulling current + forecast weather alongside air pollution lets the dashboard explain *why* a reading looks the way it does, not just display a number.
- **Air Pollution API alone still covers current, forecast, and history** (back to 27 Nov 2020) from one endpoint family, so the "trend" side of the dashboard doesn't need a fourth API. 
- **Coordinate-based across the board** - once a city's `lat`/`lon` is resolved (see Geocoding below), the same coordinates drive all three calls.

### Free tier confirmed sufficient

Current weather, the 5-day/3-hour forecast, air pollution, and geocoding all fall under the free tier (60 calls/min, 1,000,000 calls/month, no card required). OpenWeather's own Air Pollution API documentation states historical data is accessible starting from 27 November 2020, confirmed as included in the free/freemium plan.

The Pro-tier hourly forecast (`pro.openweathermap.org`) and the paid Weather History product (`history.openweathermap.org`) are **not** in scope for this project.


### Resolving coordinates: from a city name 

Current Weather's city-name query returns `coord` in the same response as the weather data:

```
https://api.openweathermap.org/data/2.5/weather?q={city name},{state code},{country code}&appid={API key}
```

```json
{
  "coord": {"lon":-122.4194,"lat":37.7749},
  "weather":[{"id":804,"main":"Clouds","description":"overcast clouds","icon":"04n"}],
  "base":"stations",
  "main":{"temp":287.68,"feels_like":287.41,"temp_min":286.71,"temp_max":289.17,"pressure":1010,"humidity":85,"sea_level":1010,"grnd_level":1007},
  "visibility":10000,
  "wind":{"speed":4.92,"deg":232,"gust":6.26},
  "clouds":{"all":92},
  "dt":1786597474,
  "sys":{"type":2,"id":2017837, "country":"US","sunrise":1786540965,"sunset":1786590408},
  "timezone":-25200,
  "id":5391959,"name":"San Francisco","cod":200
}

```

This call happens to return `lat/lon` alongside the weather data, which can look convenient at first glance. But per §1, Geocoding is the default way to resolve coordinates — this endpoint is documented here only as the fallback.
But the city-name query param on the weather endpoints is marked **deprecated** in OpenWeather's docs — still functional, but no longer maintained. That's why it's documented here as the alternate, not the primary: if it ever breaks, the pipeline should already be built around Geocoding as the default.

**Cadence — open decision:** the City Input Contract as written doesn't have a field for storing `latitude`/`longitude`, and it treats getting coordinates as something the Extract layer does on the fly, not something saved. That leaves two options:

| Option | How it works | Trade-off |
|---|---|---|
| **A. Look up coordinates on every run** | The Extract layer calls Current Weather by city name on each scheduled run and uses the result immediately, without saving it | Requires no change to the contract, but the same coordinates are requested repeatedly, run after run |
| **B. Look up coordinates once and store them** | Coordinates are resolved with one call per city, then saved and reused on every future run | Reduces the number of API calls, but requires adding `latitude`/`longitude` as stored fields to the City Input Contract |

This decision affects the contract itself, not just how the Extract layer is built, so it should be confirmed with whoever owns `city-input-contract.md` rather than decided here.

---

## 3. Endpoints & Required Parameters

Free tier covers everything the project needs - confirmed sufficient, no paid subscription required.

| API                         | Endpoint | Used for                                                                                                                           | Required params |
|-----------------------------|---|------------------------------------------------------------------------------------------------------------------------------------|---|
| Geocoding (primary)         | `/geo/1.0/direct` | Resolve `lat`/`lon` for a new city - once per city or every run                                                                    | `q` (city name), `appid` |
| Current Weather (by city name) | `/data/2.5/weather` | Fallback only, if Geocoding is unavailable - the deprecated `q=` param on this endpoint also returns `lat`/`lon` alongside a reading | `q` (`city name`, optionally `,{state code},{country code}`), `appid` |
| Current Weather (by coordinates) | `/data/2.5/weather` | Every poll: current conditions                                                                                                     | `lat`, `lon`, `appid` |
| Forecast (5 day / 3 hr)     | `/data/2.5/forecast` | Every poll: upcoming conditions                                                                                                    | `lat`, `lon`, `appid` |
| Air Pollution - current     | `/data/2.5/air_pollution` | Every poll: current AQI                                                                                                            | `lat`, `lon`, `appid` |
| Air Pollution - forecast    | `/data/2.5/air_pollution/forecast` | Every poll: 4-day AQI outlook                                                                                                      | `lat`, `lon`, `appid` |
| Air Pollution - history     | `/data/2.5/air_pollution/history` | On demand: trend/history panel                                                                                                     | `lat`, `lon`, `start`, `end`, `appid` |

- `lat`, `lon` - decimal degrees.
- `start`, `end` - Unix timestamps (UTC). Air Pollution history's earliest available data is 27 Nov 2020.
- `appid` - API key (see below).

No pagination on any of these - each returns its full result set in one response.

---

## 4. API Key Handling

- Keys are **never committed**. Store the real key in a local `.env` file, which is already covered by `.gitignore`.
- Commit an **`.env.example`** with placeholder values so any teammate can copy it and know exactly what's required to run the extractor.
- The extract layer reads the key via env var (e.g. `process.env.OPENWEATHER_API_KEY` / `os.environ["OPENWEATHER_API_KEY"]`) - never hardcode it into a request URL string in source.

**`.env.example`:**
```bash
# Copy this file to .env and fill in your own key. Never commit .env.
OPENWEATHER_API_KEY=your_api_key_here

# Optional: default city coordinates for local testing
DEFAULT_LAT=37.7749
DEFAULT_LON=-122.4194
```

---

## 5. Response Fields the Project Expects to Use

### Air Pollution (current / forecast / history - same shape)

| Field | Why we need it |
|---|---|
| `coord` (`[lon, lat]`) | Confirms which location the row belongs to - joins back to the city table. |
| `list[].dt` | Unix timestamp of the reading - the time axis for every dashboard chart. |
| `list[].main.aqi` | The 1–5 headline index (Good → Very Poor) - drives the dashboard's primary status indicator/color. |
| `list[].components.co` | Carbon monoxide, μg/m³ - pollutant breakdown panel. |
| `list[].components.no` | Nitrogen monoxide, μg/m³ - pollutant breakdown panel. |
| `list[].components.no2` | Nitrogen dioxide, μg/m³ - pollutant breakdown panel. |
| `list[].components.o3` | Ozone, μg/m³ - pollutant breakdown panel. |
| `list[].components.so2` | Sulphur dioxide, μg/m³ - pollutant breakdown panel. |
| `list[].components.pm2_5` | Fine particulates, μg/m³ - often the most health-relevant single number; likely a secondary highlighted metric alongside AQI. |
| `list[].components.pm10` | Coarse particulates, μg/m³ - pollutant breakdown panel. |
| `list[].components.nh3` | Ammonia, μg/m³ - included for completeness; returned in every response, not worth special-casing out. |

### Current Weather

| Field | Why we need it |
|---|---|
| `dt` | Timestamp of the reading - aligns weather context with the matching air quality reading. |
| `main.temp`, `main.humidity` | Context fields for the dashboard - "what was it like when this reading was taken." |
| `wind.speed`, `wind.deg` | Wind is a direct driver of pollutant dispersion; useful to show alongside AQI, and potentially for later correlation analysis. |
| `weather[].main`, `weather[].description` | Human-readable condition ("Rain," "Clear") - cheap, high-value context label for the dashboard card. |
| `coord` | Confirms location, same purpose as in Air Pollution. On the onboarding call, this is also the value we store as the city's `lat`/`lon`. |
| `name`, `sys.country` | Returned by the onboarding call - useful to confirm the resolved city/country match what was entered, catching typos or ambiguous city names before they get stored. |

### Forecast (5 day / 3 hour)

| Field | Why we need it |
|---|---|
| `list[].dt` | Timestamp per forecast step - time axis for the "coming days" panel. |
| `list[].main.temp` | Headline forecast value shown per step. |
| `list[].weather[].main` | Condition summary per step, same as Current Weather. |
| `city.coord` | Confirms location for the whole forecast set (returned once, not per step). |

We're pulling every field each response returns rather than pre-filtering - the payloads are small, and it avoids re-requesting data later if a field becomes relevant that we didn't originally flag.

---

## 6. Errors & Limits the Extract Layer Should Anticipate

| Case | What it means | Handling |
|---|---|---|
| **401 Unauthorized** | Key missing, wrong, or not yet activated (new keys can take a short time to activate after signup). | Fail fast, log clearly - don't retry in a loop. |
| **404 Not Found** | Requested params (e.g. bad `lat`/`lon` combination) have no data. | Don't blind-retry the same params; flag the coordinate as invalid. |
| **429 Too Many Requests** | Free tier cap of 60 calls/minute (or monthly cap of 1,000,000) exceeded. | Back off and retry after a delay; this is the main reason to add caching rather than calling on every dashboard page load. |
| **5xx (500/502/503/504)** | Transient server-side issue. | Safe to retry with backoff. |
| **Rate/refresh cadence** | OpenWeather's underlying model updates roughly every 10 minutes; polling faster than that returns the same data. | Poll on a ~10-minute schedule per city rather than on-demand per dashboard request; cache results between polls. |

---

## 7. Trimmed Example Responses

**Air Pollution - current** (`forecast`/`history` return the same shape, with multiple entries in `list`):

```json
{
  "coord": [50.0, 50.0],
  "list": [
    {
      "dt": 1605182400,
      "main": { "aqi": 1 },
      "components": {
        "co": 201.94,
        "no": 0.02,
        "no2": 0.77,
        "o3": 68.66,
        "so2": 0.64,
        "pm2_5": 0.5,
        "pm10": 0.54,
        "nh3": 0.12
      }
    }
  ]
}
```

`aqi: 1` = Good (scale is 1 Good → 5 Very Poor; concentrations are μg/m³).

**Current Weather - onboarding call by city name** (also the shape of the recurring `lat`/`lon` call, minus `name`/`sys` being less relevant on repeat polls):

```json
{
  "coord": { "lon": -0.13, "lat": 51.51 },
  "weather": [
    { "id": 300, "main": "Drizzle", "description": "light intensity drizzle" }
  ],
  "main": {
    "temp": 280.32,
    "humidity": 81,
    "temp_min": 279.15,
    "temp_max": 281.15
  },
  "wind": { "speed": 4.1, "deg": 80 },
  "dt": 1485789600,
  "sys": { "country": "GB" },
  "name": "London"
}
```

**Forecast (5 day / 3 hour) - one step of many in `list`:**

```json
{
  "city": { "coord": { "lon": 50.0, "lat": 50.0 } },
  "list": [
    {
      "dt": 1605189600,
      "main": { "temp": 288.9 },
      "weather": [{ "main": "Rain" }]
    }
  ]
}
```
