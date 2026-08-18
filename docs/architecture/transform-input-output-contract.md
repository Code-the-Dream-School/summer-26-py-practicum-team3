# Transform Input and Output Contract

## Purpose

The Transform stage converts raw air-pollution API responses produced by the Extract stage into clean application records for downstream use.

This contract defines:

* What the Transform stage receives.
* The extraction context available with each raw response.
* The granularity of each transformed record.
* How raw API fields map to clean fields.
* What the Transform stage returns.
* An example transformed record.

This contract describes **application data**, not a final PostgreSQL schema. The output may later be persisted in PostgreSQL or another storage system, but the Transform contract is independent of that storage design.

---
