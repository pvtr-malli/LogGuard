

## Latency Testing

### Overview

The latency testing script measures end-to-end latency from log production to anomaly alarm. It helps verify that the system meets the **< 30 seconds** latency requirement.

### What It Measures

1. **Kafka → Detection**: Time from log reaching Kafka to anomaly detection result
2. **Detection → Alarm**: Time from detection result to alarm file write
3. **Total Latency**: End-to-end time from log production to alarm

### Prerequisites

1. **Infrastructure Running**:
   ```bash
   docker-compose up -d
   ```

2. **Stream Processor Running**:
   ```bash
   python -m log_guard.stream_processor \
       --kafka-brokers localhost:9092 \
       --topic log-events \
       --window-seconds 30 \
       --anomaly-log logs/anomalies.log
   ```

3. **Models Trained**: Ensure model artifacts exist in `/models`

### Running Latency Tests

#### Basic Test (5 iterations)

```bash
cd tests/
python test_latency.py
```

**Expected Output**:
```
================================================================================
LOGGUARD LATENCY TESTING
================================================================================
Configuration:
  • Kafka Brokers: localhost:9092
  • Input Topic: log-events
  • Output Topic: anomaly-results
  • Anomaly Log: logs/anomalies.log
  • Number of Tests: 5
  • Interval: 35s (allows 30s window + 5s buffer)
================================================================================

================================================================================
LATENCY TEST #1
================================================================================

[Test 1] Sending burst of 50 anomaly logs...
[Test 1] ✓ Sent 50 logs at 10:30:00.123
[Test 1] Waiting for anomaly result (timeout: 60s)...
[Test 1] ✓ Received anomaly result at 10:30:31.456
[Test 1] Waiting for anomaly alarm in log file (timeout: 10s)...
[Test 1] ✓ Anomaly alarm logged at 10:30:31.789

[Test 1] RESULTS:
  • Kafka → Detection: 31.333s (31333.0ms)
  • Detection → Alarm: 0.333s (333.0ms)
  • Total Latency: 31.666s (31666.0ms)
  • Anomaly Score: 0.873
  • Alarm Logged: ✓ Yes

[Test 1] ✓ PASSED

Waiting 35s before next test...
```

#### Custom Configuration

```bash
# Run 10 tests with 40-second interval
python test_latency.py --num-tests 10 --interval 40

# Test against remote Kafka
python test_latency.py --kafka-brokers kafka1:9092,kafka2:9092

# Custom anomaly log file
python test_latency.py --anomaly-log /var/log/logguard/anomalies.log
```

### Understanding Results



#### Latency Breakdown

**Kafka → Detection (~31 seconds)**:
- Window accumulation: 30 seconds (by design)
- Feature extraction: ~500ms
- Anomaly prediction: ~200ms
- Kafka publish: ~10ms

**Detection → Alarm (~300ms)**:
- Result consumption: ~10ms
- Alarm file write: ~50ms
- Disk flush: ~50ms

**Total Latency (~31.5 seconds)**:
- Meets requirement if < 30 seconds
- Typical range: 30-32 seconds (depending on exact window timing)







