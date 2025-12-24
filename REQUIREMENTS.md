# Initial thoughts/needs:

- Should continuosely monitor the logs and detect anomaly.
- anomaly detection should happen <30 secs of the log comes.
- we can expect 50k-200k logs/min.
- So the total time to get the alert is < 1 min.
- There should not be any data lose.


# Real-Time Log Anomaly Detection – Requirements

## 1. Overview

This system is designed to detect anomalies in application logs in **near real-time** using a streaming architecture. The solution supports continuous ingestion, scalable processing, and timely alerting while ensuring reliability and fault tolerance.

---

## 2. Functional Requirements

1. **Near Real-Time Anomaly Detection**

   * The system must detect log anomalies within **30 seconds** of their occurrence.

2. **Continuous Log Ingestion**

   * The system must support uninterrupted ingestion of logs from multiple services.

3. **High-Volume Handling**

   * The system must handle sudden spikes in log volume without data loss or service degradation.

---

## 3. Non-Functional Requirements

1. **Throughput**

   * The system must process up to **50k-200k log events per minute**.

2. **End-to-End Latency**

   * The time from log generation to anomaly detection must be **less than 30 seconds**.

3. **Fault Tolerance**

   * The system must ensure **no data loss**, even during component failures or restarts.

4. **Scalability**

   * The system must support **horizontal scaling** to accommodate increased load.

---

## 4. Real-Time Classification

The system operates in a **near real-time (soft real-time)** mode, where low-latency processing is prioritized, but strict millisecond-level guarantees are not required.

---

## 5. Design Implication

Meeting these requirements requires:

* Stream-based ingestion (Kafka)
* Windowed processing (Dask)
* Distributed, fault-tolerant execution
* Lightweight anomaly detection models suitable for streaming environments

---
