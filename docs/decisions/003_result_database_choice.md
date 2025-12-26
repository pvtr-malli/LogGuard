# ADR-003: Database Choice for Storing Streaming Anomaly Detection Results

## Status

**Accepted**

---

## Context

The system produces **windowed anomaly detection results** (every 30 seconds) from a real-time log processing pipeline.
Each result represents an **event in time** with associated metadata such as service name, anomaly score, and derived metrics.

The database must support:

* High-frequency inserts
* Time-windowed queries
* Efficient dashboarding
* Retention management
* Easy debugging and ad-hoc analysis

Several storage options were considered, including PostgreSQL, Prometheus, and TimescaleDB.

---

## Decision

We chose **TimescaleDB** as the primary database for storing anomaly detection results.

---

## Rationale

### Nature of the Data

The anomaly outputs are:

* **Event-based**
* **Time-indexed**
* **Append-only**
* Queried primarily by **time ranges**

This classifies the data as **time-series events**, not metrics or generic relational data.

---

### Why TimescaleDB

#### mainly
- fast for inserting into the table - best for streaming.
- it provides Continuous Aggregates that make rollups(horly/daily/weekly) extremely easy to set up.


TimescaleDB extends PostgreSQL with native time-series capabilities:

* Automatic time-based partitioning (hypertables)
* High-throughput inserts for streaming workloads
* Fast time-window aggregations
* Built-in data retention and compression
* Full SQL support
* Native integration with Grafana

This aligns perfectly with storing anomaly scores and window-level results.

---

### Why Not PostgreSQL (Plain)

PostgreSQL can store the data but is not optimized for:

* Large append-only time-series workloads
* Efficient long-term retention management
* High-performance windowed aggregations at scale

Using TimescaleDB provides these benefits **without losing PostgreSQL compatibility**, making plain PostgreSQL a strictly weaker choice for this use case.

---

### Why Not Prometheus

Prometheus is designed for:

* Numeric metrics
* Counters and gauges
* Pull-based scraping

It is **not designed** for:

* Event storage
* Rich metadata per record
* Arbitrary SQL queries
* Long-term anomaly record analysis

Anomaly detection results are **events**, not metrics, making Prometheus an unsuitable fit.

---

## Rule of Thumb Applied

The following classification guided the decision:

> **Metrics → Prometheus**
> **Events with time → TimescaleDB**
> **General relational data → PostgreSQL**

Anomaly detection results clearly fall into **events with time**.

---



## Alternatives Considered

* **Plain PostgreSQL** – rejected due to lack of time-series optimizations
* **Prometheus** – rejected due to metrics-only design
* **ClickHouse** – considered but deemed unnecessary for project scale

---

