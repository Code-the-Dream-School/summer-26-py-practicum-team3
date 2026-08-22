# City Air Tracker Database Schema
## Overview

This document defines the PostgreSQL schema for the City Air Tracker pipeline. The schema is based on the Sprint 2 raw response contract, Sprint 3 transform data dictionary, city input contract, and pipeline run tracking requirements.

The City Air Tracker PostgreSQL database contains five tables:

| Table                         | Purpose                                                     |
| ----------------------------- | ----------------------------------------------------------- |
| `cities`                      | Stores configured cities and location reference data        |
| `pipeline_runs`               | Tracks each pipeline execution                              |
| `raw_geocoding_responses`     | Stores raw geocoding API responses                          |
| `raw_air_pollution_responses` | Stores raw air pollution API responses                      |
| `air_pollution_gold`          | Stores transformed and validated air pollution observations |