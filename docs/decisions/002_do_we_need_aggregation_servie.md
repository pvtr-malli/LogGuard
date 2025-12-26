# ADR-002: Placement of Log Aggregation in the Streaming Pipeline

## Status

**Accepted**

---

## Context

The system processes high-volume application logs for near real-time anomaly detection.
An initial design option considered performing **5-second window aggregation in a dedicated aggregation service before sending data to Kafka**, in order to reduce downstream processing load.

However, the system also requires:

* Debuggability
* Replayability
* Flexibility to evolve aggregation logic and window sizes

---

## Decision

We decided **not to perform aggregation before Kafka**.
Instead, all **raw log events are published to Kafka**, and **windowed aggregation is performed downstream in the streaming processing layer**.

---

## mainly:
- we can't change the window size later.
- we will loose the raw data -without that the debussing will be hard.
- extra time for aggregating.

## Rationale

### Why aggregation before Kafka was considered

* Reduces downstream data volume
* Simplifies consumer logic
* Lowers processing cost per event

### Why it was rejected

* Raw logs would be lost, preventing replay and reprocessing
* Debugging anomalies without raw events would be difficult
* Aggregation logic would be tightly coupled to log producers
* Window size and feature logic would be hard to change later

Kafka is intended to act as the **system of record for raw events**, not derived data.

---

## Consequences

### Positive

* Raw data is preserved for debugging and replay
* Aggregation logic can evolve independently
* **Multiple downstream consumers can reuse raw logs - like I can have 5sec and 10sec aggregation prediciton at the same time**
* Better observability and operational flexibility

### Negative

* Slightly higher downstream processing load
* Additional compute required for aggregation

---

## Alternatives Considered

* **Upstream aggregation service before Kafka**
  Rejected due to loss of raw data and reduced flexibility.

* **Hybrid approach (raw + aggregated topics)**
  Considered as a future optimization if throughput becomes a bottleneck.

