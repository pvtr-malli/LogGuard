# ADR-001: Log Message Representation for Anomaly Detection

## Status

**Accepted**

---

## Context

The system performs anomaly detection on application logs in a near real-time streaming environment.
Log messages are semi-structured, repetitive, and often contain variable components such as IDs, timestamps, paths, and numeric values.

A decision was required on how to represent log messages for semantic anomaly detection in a way that balances:

* Detection quality
* Scalability
* Latency
* Explainability

Two approaches were considered:

1. TF-IDF + message template–based features
2. Deep language model embeddings (e.g., BERT)

---

## Decision

We chose to use **text preprocessing + TF-IDF embeddings + message template extraction + clustering-based anomaly scoring** as the primary approach.

Deep language model embeddings (e.g., BERT) are **explicitly deferred** and considered an optional future enhancement.

---

## Rationale

### Why TF-IDF + Templates

* Log messages are **semi-structured**, not natural language
* Most anomalies are caused by:

  * New message templates
  * Rare message patterns
  * Sudden frequency changes
* TF-IDF captures key error tokens efficiently
* Template frequency and rarity are strong anomaly signals
* Clustering distance provides an intuitive anomaly score

### Advantages

* Low-latency and streaming-friendly
* Scales well with Kafka + Dask
* Highly explainable (tokens, templates, rarity)
* Lower operational complexity
* Widely used in production log analytics systems

---

## Alternatives Considered

### BERT / Transformer-based embeddings

**Pros**

* Better semantic understanding
* Handles paraphrased messages

**Cons**

* High inference cost
* Harder to scale in real-time pipelines
* Reduced explainability
* Overkill for structured logs

---

## Consequences

### Positive

* Efficient real-time processing
* Simple deployment and maintenance
* Clear anomaly explanations
* Strong baseline suitable for production

### Negative

* Limited semantic generalization across very different phrasings
* May miss anomalies expressed with completely new vocabulary

---

## Future Considerations

* Introduce sentence embeddings selectively for:

  * Rare templates
  * Low-confidence anomalies
* Hybrid scoring combining:

  * Template rarity
  * TF-IDF cluster distance
  * Optional semantic embedding distance

---

## Summary

TF-IDF and template-based anomaly detection provide a robust, scalable, and explainable solution for log anomaly detection. Deep language models are intentionally deferred until their added complexity is justified by clear limitations.

---
