# City Air Tracker — Architecture

## 1. Product and Data Pipeline Summary

### The problem

Air quality data for different cities exists and is accessible (e.g., through the OpenWeather API), but in its raw form it's scattered and impractical to use directly: getting readings for multiple cities means making separate geocoding and historical air-pollution requests for each city individually, and the results come back as nested JSON with possible gaps, duplicates, and inconsistent timestamp formats. Having the dashboard hit the API and parse this raw data on every request would be slow and unreliable. City Air Tracker solves this by collecting data for all the configured cities in one place and turning it into a single clean format the dashboard can rely on.

### Data the product needs

- a list of cities from configuration (which cities to track);
- coordinates for those cities, obtained via OpenWeather's geocoding API;
- historical air pollution data for those coordinates, also from the OpenWeather API.

### What the ETL stages do

- **Extract** — calls the OpenWeather geocoding and air pollution endpoints for each configured city and stores the raw responses as-is in PostgreSQL, so they can be re-inspected later without making another API call.
- **Transform** — parses these raw responses, removes duplicate or invalid records, normalizes timestamps to a consistent format, and calculates any derived metrics needed.
- **Load** — writes the resulting cleaned ("gold") dataset to PostgreSQL, which is the data source for the dashboard.

### How this supports the dashboard

By the time the dashboard needs the data, all the prep work is already done: the React frontend requests the data from our Python API, which queries the prepared tables in PostgreSQL. As a result, no OpenWeather API calls or JSON parsing occur during the request. This keeps the dashboard fast and reliable, and keeps all the data-cleaning logic centralized and easy to test separately from the UI.

## 2. Target Architecture

**Plan:** _This architecture may change as the team learns more_

```mermaid
flowchart TD
	A["<b>City Input / Configuration + Geocoding</b><br/>Provides the cities to track and converts city names to latitude / longitude"]

	B["<b>Data Extraction</b><br/>Retrieves air pollution data from OpenWeather API"]

	C["<b>Data Transformation</b><br/>Cleans, normalizes, and prepares the extracted data for storage"]

	D["<b>PostgreSQL</b><br/>Stores city, pipeline, raw, and prepared air quality data"]

	E["<b>Python Dashboard API</b><br/>Queries prepared data from PostgreSQL and returns it to the frontend"]

	F["<b>React Frontend</b><br/>Displays city air quality data through the dashboard"]

    G["<b>Optional Extension — Dynamic City Search</b><br/>Dynamic city search using the geocoding API<br/>Allows cities beyond the configured list"]

A --> B
B --> C
C --> D
D -->|"Query prepared data"| E
E -->|"HTTP / JSON"| F

G -.->|"Triggers"| B

classDef input fill:#e0f2fe,stroke:#0284c7,stroke-width:2px,color:#0c4a6e
classDef process fill:#f3f4f6,stroke:#6b7280,stroke-width:2px,color:#111827
classDef database fill:#dcfce7,stroke:#16a34a,stroke-width:2px,color:#14532d
classDef api fill:#fef3c7,stroke:#d97706,stroke-width:2px,color:#78350f
classDef frontend fill:#fce7f3,stroke:#db2777,stroke-width:2px,color:#831843
classDef optional fill:#f5f3ff,stroke:#7c3aed,stroke-width:2px,stroke-dasharray:5 5,color:#4c1d95

class A input
class B,C process
class D database
class E api
class F frontend
class G optional
```
