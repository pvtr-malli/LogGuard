# Kafka Consumer - Deep Dive

This document explains how Kafka consumers work in the LogGuard streaming pipeline, covering offset management, single vs multiple consumers, and time-series ordering challenges.

---

## Table of Contents
1. [How Kafka Tracks What's Been Read](#1-how-kafka-tracks-whats-been-read)
2. [Single vs Multiple Consumers](#2-single-vs-multiple-consumers)
3. [Time-Series Ordering Problem](#3-time-series-ordering-problem)

---

## 1. How Kafka Tracks What's Been Read

### The Offset System

Every message in a Kafka topic has a unique **offset** (like an array index):

```
Topic: log-events, Partition 0:
┌────────┬────────┬────────┬────────┬────────┬────────┐
│ Msg 0  │ Msg 1  │ Msg 2  │ Msg 3  │ Msg 4  │ Msg 5  │
└────────┴────────┴────────┴────────┴────────┴────────┘
  offset=0 offset=1 offset=2 offset=3 offset=4 offset=5
                                        ↑
                                   Current offset
                                   (consumer position)
```

**Key concept:** Offset is an **incrementing integer** that never resets. It's Kafka's way of keeping track of message position.

### Consumer Groups and Offset Storage

When you create a consumer with a `group_id`:

```python
self.consumer = KafkaConsumer(
    'log-events',
    bootstrap_servers='localhost:9092',
    group_id='logguard-processor',      # ← Consumer group ID
    enable_auto_commit=True,             # ← Auto-save offset
    auto_commit_interval_ms=1000         # ← Save every 1 second
)
```

**Kafka internally stores:**
```
Consumer Group: "logguard-processor"
├─ Topic: log-events, Partition 0 → Last committed offset: 1523
├─ Topic: log-events, Partition 1 → Last committed offset: 1498
└─ Topic: log-events, Partition 2 → Last committed offset: 1510
```

This metadata is stored in a special internal Kafka topic called `__consumer_offsets`.

### How `poll()` Works Step-by-Step

```python
messages = self.consumer.poll(timeout_ms=100)
```

**Behind the scenes:**

#### Step 1: Fetch Current Offset
Consumer asks Kafka: "What's my last committed offset for group 'logguard-processor'?"

```
Request:  GetOffset(group='logguard-processor', topic='log-events')
Response: Partition 0 → offset 1523
          Partition 1 → offset 1498
          Partition 2 → offset 1510
```

#### Step 2: Request New Messages
Consumer asks: "Give me all messages starting from these offsets"

```
Request:  FetchMessages(
            topic='log-events',
            partition=0,
            offset=1523,
            max_bytes=1MB
          )

Response: [
            {offset: 1523, timestamp: '10:30:15', value: {...}},
            {offset: 1524, timestamp: '10:30:15', value: {...}},
            {offset: 1525, timestamp: '10:30:16', value: {...}},
            ...
          ]
```

#### Step 3: Process Messages
Your code processes the messages:

```python
for topic_partition, records in messages.items():
    for record in records:
        log_entry = record.value
        self.log_buffer.append(log_entry)  # Add to buffer
```

#### Step 4: Commit Offset (Auto or Manual)

**Auto-commit (your current setup):**
Every 1 second, consumer automatically tells Kafka:
```
CommitOffset(
    group='logguard-processor',
    topic='log-events',
    partition=0,
    offset=1530  # Last successfully processed
)
```

**Manual commit alternative:**
```python
enable_auto_commit=False

# In your code:
for record in records:
    process(record)

consumer.commit()  # Commit only after successful processing
```

#### Step 5: Next Poll
Next time you call `poll()`, it starts from offset **1531** (where you left off).

### Visual Flow Diagram

```
┌─────────────────────────────────────────────────────────┐
│                    Kafka Broker                         │
│                                                          │
│  Topic: log-events (Partition 0)                        │
│  ┌───┬───┬───┬───┬───┬───┬───┬───┬───┬───┬───┐        │
│  │100│101│102│103│104│105│106│107│108│109│110│        │
│  └───┴───┴───┴───┴───┴───┴───┴───┴───┴───┴───┘        │
│                          ↑                               │
│              Committed offset: 105                       │
│              (stored in __consumer_offsets)              │
│                                                          │
│  Internal Topic: __consumer_offsets                     │
│  {                                                       │
│    "group": "logguard-processor",                       │
│    "topic": "log-events",                               │
│    "partition": 0,                                      │
│    "offset": 105                                        │
│  }                                                       │
└─────────────────────────────────────────────────────────┘
                          ↕
                   Kafka Protocol
                   (TCP Socket)
                          ↕
┌─────────────────────────────────────────────────────────┐
│            Stream Processor (Consumer)                  │
│                                                          │
│  messages = consumer.poll(timeout_ms=100)               │
│  # 1. Fetches current offset: 105                       │
│  # 2. Requests messages from offset 106 onwards         │
│  # 3. Receives: [106, 107, 108, 109, 110]              │
│                                                          │
│  for record in messages:                                │
│      process(record)  # Your logic                      │
│                                                          │
│  # 4. Auto-commits new offset: 110                      │
│  #    (happens every 1 second automatically)            │
└─────────────────────────────────────────────────────────┘
```

### Key Configuration Parameters

#### `auto_offset_reset`
```python
auto_offset_reset='latest'   # Start from newest messages
# or
auto_offset_reset='earliest' # Start from beginning (oldest)
```

**When this applies:**
- **First time** a consumer with this `group_id` connects
- **OR** the stored offset is no longer valid (data was deleted due to retention policy)

**Example:**
```python
# First run
consumer = KafkaConsumer('log-events', group_id='new-group', auto_offset_reset='earliest')
# Starts reading from offset 0 (beginning of topic)

# Second run (same group_id)
consumer = KafkaConsumer('log-events', group_id='new-group', auto_offset_reset='earliest')
# Starts from last committed offset (e.g., 1530), NOT from beginning
```

#### `enable_auto_commit`
```python
enable_auto_commit=True   # Automatically save offset progress
auto_commit_interval_ms=1000  # How often to save (milliseconds)
```

**Auto-commit timeline:**
```
Time:     0s          1s          2s          3s
Offsets:  100 → 150 → 200 → 250 → 300
          ↓           ↓           ↓
       Commit 100  Commit 200  Commit 250
```

**Manual commit alternative:**
```python
enable_auto_commit=False

for record in records:
    try:
        process(record)
        consumer.commit()  # Commit only on success
    except Exception as e:
        # Don't commit on error - will reprocess this message
        handle_error(e)
```

### What Happens If Consumer Crashes?

#### Scenario 1: Auto-commit ON (Your Current Setup)

```
Timeline:
10:30:00  Process offsets 100-150
10:30:01  Auto-commit offset 150 ✓
10:30:02  Process offsets 151-250
10:30:03  Auto-commit offset 250 ✓
10:30:04  Process offsets 251-300
10:30:05  CRASH! 💥 (before next auto-commit)
```

**On restart:**
- Consumer reads last committed offset from Kafka: **250**
- Resumes from offset **251**
- Messages 251-300 are **reprocessed** (duplicates!)

**Trade-off:**
- ✅ Simple, no code changes needed
- ❌ Possible duplicate processing (at-least-once delivery)
- ❌ Small data loss window (1 second of uncommitted offsets)

#### Scenario 2: Manual Commit (Exactly-Once Processing)

```python
def _process_window(self):
    if not self.log_buffer:
        return

    try:
        # Extract features
        features = self.feature_extractor.extract_all_features(self.log_buffer)

        # Make predictions
        results = self.predictor.predict(features)

        # Publish results
        self.producer.send('anomaly-results', results)

        # Only commit AFTER everything succeeds
        self.consumer.commit()  # ← Guarantees no data loss

    except Exception as e:
        # Don't commit - will retry these messages
        logging.error(f"Processing failed: {e}")
        raise
```

**On crash:**
- Consumer restarts from last successful commit
- No duplicates, no data loss
- **Exactly-once semantics**

### How to Check Consumer Status

#### Command-Line Tool
```bash
# Inside Kafka container
docker exec -it logguard-kafka bash

# List all consumer groups
kafka-consumer-groups --bootstrap-server localhost:9092 --list

# Describe specific consumer group
kafka-consumer-groups --bootstrap-server localhost:9092 \
    --group logguard-processor \
    --describe
```

**Output:**
```
GROUP              TOPIC          PARTITION  CURRENT-OFFSET  LOG-END-OFFSET  LAG
logguard-processor log-events     0          1523           1568            45
logguard-processor log-events     1          1498           1550            52
logguard-processor log-events     2          1510           1548            38
```

**Columns explained:**
- `CURRENT-OFFSET`: Last committed offset (where consumer is)
- `LOG-END-OFFSET`: Latest available message offset
- `LAG`: How many messages behind (LOG-END - CURRENT)

#### Programmatically
```python
from kafka import KafkaAdminClient

admin = KafkaAdminClient(bootstrap_servers='localhost:9092')

# Get consumer group details
groups = admin.describe_consumer_groups(['logguard-processor'])

for group in groups:
    print(f"Group: {group.group_id}")
    print(f"State: {group.state}")
    print(f"Members: {len(group.members)}")

    for member in group.members:
        print(f"  Consumer: {member.client_id}")
        print(f"  Host: {member.client_host}")
```

### Resetting Offsets

If you want to **reprocess old messages**:

```bash
# Reset to beginning
kafka-consumer-groups --bootstrap-server localhost:9092 \
    --group logguard-processor \
    --topic log-events \
    --reset-offsets --to-earliest \
    --execute

# Reset to specific offset
kafka-consumer-groups --bootstrap-server localhost:9092 \
    --group logguard-processor \
    --topic log-events \
    --reset-offsets --to-offset 1000 \
    --execute

# Reset to timestamp
kafka-consumer-groups --bootstrap-server localhost:9092 \
    --group logguard-processor \
    --topic log-events \
    --reset-offsets --to-datetime 2025-12-26T10:00:00.000 \
    --execute
```

**Important:** Consumer must be **stopped** before resetting offsets!

---

## 2. Single vs Multiple Consumers

### Can You Have a Single Consumer?


You create **ONE consumer instance** that reads from the topic.

### Single Consumer Architecture

```
┌──────────────────┐
│  Log Producer    │ Generates 100 logs/sec
└────────┬─────────┘
         │
         ▼
    ┌────────────────────────────┐
    │ Kafka Topic: log-events    │
    │                            │
    │ ├─ Partition 0: [msgs...]  │
    │ ├─ Partition 1: [msgs...]  │
    │ └─ Partition 2: [msgs...]  │
    └────────┬───────────────────┘
             │
             ▼
    ┌─────────────────────────────┐
    │  Single Stream Processor    │
    │  (Reads ALL 3 partitions)   │
    │                             │
    │  Consumer Group:            │
    │  "logguard-processor"       │
    └─────────────────────────────┘
```

**What happens:**
- Single consumer assigned to **ALL partitions** (0, 1, 2)
- Processes messages **sequentially**
- Simple, predictable behavior

### Multiple Consumers Architecture

Running multiple consumers with the **SAME consumer group**:

```bash
# Terminal 1
python stream_processor.py --consumer-group shared-group

# Terminal 2
python stream_processor.py --consumer-group shared-group

# Terminal 3
python stream_processor.py --consumer-group shared-group
```

**Kafka's automatic partition assignment:**

```
┌──────────────────┐
│  Log Producer    │ Generates 1000 logs/sec
└────────┬─────────┘
         │
         ▼
    ┌─────────────────────────────────────┐
    │ Kafka Topic: log-events             │
    │                                     │
    │ ├─ Partition 0: [msgs...]           │
    │ ├─ Partition 1: [msgs...]           │
    │ └─ Partition 2: [msgs...]           │
    └─┬────────┬──────────┬───────────────┘
      │        │          │
      ▼        ▼          ▼
    ┌───┐    ┌───┐     ┌───┐
    │ C1│    │ C2│     │ C3│  Consumer Group: "shared-group"
    └───┘    └───┘     └───┘
     P0       P1        P2   (Each gets 1 partition)
```

**Key rule:** Kafka assigns each partition to exactly **ONE consumer** within a group.

### Partition Assignment Examples

#### Example 1: Consumers = Partitions (Optimal)
```
3 partitions, 3 consumers (same group)

Consumer 1 → Partition 0 (reads offsets 0-999)
Consumer 2 → Partition 1 (reads offsets 0-856)
Consumer 3 → Partition 2 (reads offsets 0-923)

Result: Perfect parallelism, max throughput
```

#### Example 2: Consumers < Partitions
```
3 partitions, 2 consumers (same group)

Consumer 1 → Partition 0 + Partition 1
Consumer 2 → Partition 2

Result: Consumer 1 does more work
```

#### Example 3: Consumers > Partitions
```
3 partitions, 5 consumers (same group)

Consumer 1 → Partition 0
Consumer 2 → Partition 1
Consumer 3 → Partition 2
Consumer 4 → (idle, no partition)
Consumer 5 → (idle, no partition)

Result: 2 consumers sit idle, wasted resources
```

### Different Consumer Groups (Independent Consumers)

Multiple consumers with **DIFFERENT consumer groups** = completely independent:

```bash
# Application 1: Anomaly detection
python stream_processor.py --consumer-group anomaly-detector

# Application 2: Log archiver
python log_archiver.py --consumer-group archiver

# Application 3: Real-time dashboard
python dashboard.py --consumer-group dashboard
```

**Each group reads ALL messages independently:**

```
    ┌────────────────────┐
    │ Kafka: log-events  │
    └─┬───────┬──────┬───┘
      │       │      │
      │       │      └──────────────┐
      │       │                     │
      ▼       ▼                     ▼
   ┌─────┐ ┌─────┐            ┌─────┐
   │ AD  │ │ Arch│            │ Dash│
   │Group│ │Group│            │Group│
   └─────┘ └─────┘            └─────┘
   offset:  offset:            offset:
   1523     5       (start)    1523

   All read the SAME messages!
```

### Performance Comparison

#### Single Consumer
```
Throughput: ~10,000 logs/sec
Latency:    30 seconds (window size)
CPU:        1 core
Memory:     ~500MB
```

**Good for:**
- Development/testing
- Low-medium throughput (< 10k logs/sec)
- Simple deployment

#### Multiple Consumers (3x)
```
Throughput: ~30,000 logs/sec
Latency:    30 seconds (window size)
CPU:        3 cores (1 per consumer)
Memory:     ~1.5GB (500MB × 3)
```

**Good for:**
- High throughput (> 10k logs/sec)
- Production systems
- Fault tolerance

### When to Use Each

| Scenario | Recommendation |
|----------|---------------|
| **Development** | Single consumer |
| **Throughput < 5k/sec** | Single consumer |
| **Throughput 5-50k/sec** | 2-5 consumers (same group) |
| **Throughput > 50k/sec** | Many consumers + more partitions |
| **Need simplicity** | Single consumer |
| **Need fault tolerance** | Multiple consumers |

### How to Verify Your Setup

```bash
# Check how many consumers are active
docker exec -it logguard-kafka bash

kafka-consumer-groups --bootstrap-server localhost:9092 \
    --group logguard-processor \
    --describe

# Output shows consumer assignment:
TOPIC       PARTITION  CONSUMER-ID              HOST
log-events  0          consumer-1-abc123        /172.18.0.1
log-events  1          consumer-1-abc123        /172.18.0.1
log-events  2          consumer-1-abc123        /172.18.0.1
            ↑          ↑ Same ID = single consumer

# Multiple consumers would show:
log-events  0          consumer-1-abc123        /172.18.0.1
log-events  1          consumer-2-def456        /172.18.0.2
log-events  2          consumer-3-ghi789        /172.18.0.3
            ↑          ↑ Different IDs = multiple consumers
```

---

## 3. Time-Series Ordering Problem

### The Critical Issue with Parallel Consumers

When you have **multiple consumers processing different partitions in parallel**, you **LOSE global time ordering**. This breaks time-series analysis!

### Why This Happens

Kafka only guarantees ordering **within a partition**, NOT across partitions.

```
Partition 0 (Consumer 1):
  10:00:00 → {"message": "Cache hit", "level": "INFO"}
  10:00:15 → {"message": "Query slow", "level": "WARN"}
  10:00:45 → {"message": "Cache hit", "level": "INFO"}

Partition 1 (Consumer 2):
  10:00:05 → {"message": "Payment OK", "level": "INFO"}
  10:00:25 → {"message": "Error 500", "level": "ERROR"}
  10:00:50 → {"message": "Payment OK", "level": "INFO"}

Partition 2 (Consumer 3):
  10:00:10 → {"message": "Auth success", "level": "INFO"}
  10:00:35 → {"message": "Auth failed", "level": "WARN"}
  10:00:55 → {"message": "Auth success", "level": "INFO"}
```

**Problem:** Each consumer calculates features **independently**!

### Impact on Rolling Features

Your [feature_extractor.py](src/feature_extractor.py) calculates rolling statistics:

```python
def extract_rolling_features(self, df):
    """Extract rolling mean, std, max, min, p95, p99."""

    # Rolling 5-minute window
    df['log_count_rolling_mean_5min'] = df['log_count'].rolling('5min').mean()

    # Rolling 15-minute window
    df['log_count_rolling_mean_15min'] = df['log_count'].rolling('15min').mean()

    # Rolling 1-hour window
    df['log_count_rolling_mean_1h'] = df['log_count'].rolling('1h').mean()
```

**With parallel consumers:**

```
Consumer 1 (Partition 0):
  Rolling 5-min average at 10:05:00:
    Only sees logs from Partition 0 (10:00-10:05)
    Missing logs from Partitions 1, 2!

    Calculates: avg = 150 logs/min
    Reality:    avg = 450 logs/min (all partitions)

    ERROR: ❌ Incorrect rolling average!

Consumer 2 (Partition 1):
  Rolling 5-min average at 10:05:00:
    Only sees logs from Partition 1
    Missing logs from Partitions 0, 2!

    Calculates: avg = 148 logs/min
    Reality:    avg = 450 logs/min

    ERROR: ❌ Incorrect rolling average!
```

### Visual Example

**Global timeline (reality):**
```
10:00  10:01  10:02  10:03  10:04  10:05
  |      |      |      |      |      |
  A      D      G      J      M      P
   B      E      H      K      N      Q
    C      F      I      L      O      R

Rolling 5-min at 10:05 should see: [A,B,C,D,E,F,G,H,I,J,K,L,M,N,O,P,Q,R]
```

**What each consumer sees:**
```
Consumer 1 (Partition 0):
  A      D      G      J      M      P
  Rolling 5-min sees: [A, D, G, J, M, P]  ❌ Incomplete!

Consumer 2 (Partition 1):
   B      E      H      K      N      Q
   Rolling 5-min sees: [B, E, H, K, N, Q]  ❌ Incomplete!

Consumer 3 (Partition 2):
    C      F      I      L      O      R
    Rolling 5-min sees: [C, F, I, L, O, R]  ❌ Incomplete!
```

### Concrete Example: Error Rate Spike

**Scenario:** Database goes down, causing error spike across all services.

**Reality:**
```
10:00:00-10:01:00
  Partition 0: 10 errors
  Partition 1: 12 errors
  Partition 2: 11 errors
  Total: 33 errors
  Error rate: 33/3000 = 1.1%  ← Should trigger anomaly!
```

**What happens with parallel consumers:**
```
Consumer 1 (Partition 0):
  Sees: 10 errors / 1000 logs = 1.0% error rate
  Rolling avg last 5min: 0.5%
  Anomaly score: Low (only 2x increase)

Consumer 2 (Partition 1):
  Sees: 12 errors / 1000 logs = 1.2% error rate
  Rolling avg last 5min: 0.5%
  Anomaly score: Low

Consumer 3 (Partition 2):
  Sees: 11 errors / 1000 logs = 1.1% error rate
  Rolling avg last 5min: 0.5%
  Anomaly score: Low

Result: ❌ Anomaly MISSED because each consumer sees incomplete data!
```

---

## Solutions to Time-Series Ordering Problem

### Solution 1: Single Partition ✅ **RECOMMENDED for LogGuard**

**Use only 1 partition** to preserve global time ordering.

```bash
# Create topic with 1 partition
docker exec -it logguard-kafka bash

kafka-topics --create \
    --topic log-events \
    --partitions 1 \
    --replication-factor 1 \
    --bootstrap-server localhost:9092
```

**Architecture:**
```
Log Producer → Kafka (1 partition) → Single Consumer
```

**Pros:**
- ✅ Time-series order guaranteed
- ✅ Rolling features 100% correct
- ✅ Simple architecture
- ✅ Sufficient for < 200k logs/min (LogGuard requirement)

**Cons:**
- ❌ Limited to single consumer throughput (~10k logs/sec)
- ❌ No parallel processing

**Performance:**
```
Throughput: ~10,000 logs/sec = 600,000 logs/min
Requirement: 50k-200k logs/min
Result: ✅ More than enough!
```

### Solution 2: Partition by Time Window

Partition logs by time bucket (e.g., by minute or hour):

```python
# In log_producer.py
def _generate_log(self):
    log_entry = {
        'timestamp': datetime.now(timezone.utc).isoformat(),
        'level': level,
        'component': component,
        'message': message
    }

    # Use timestamp minute as partition key
    key = datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M')

    self.producer.send(
        self.topic,
        key=key.encode('utf-8'),  # Same minute → same partition
        value=log_entry
    )
```

**How it works:**
- All logs within same minute go to same partition
- Different minutes can be processed in parallel
- Kafka assigns partition based on hash of key

**Pros:**
- ✅ Logs within same time window stay together
- ✅ Can process different time periods in parallel
- ✅ Better than random partitioning

**Cons:**
- ❌ Still can't compute rolling features across partitions
- ❌ Uneven load (some minutes have more logs)
- ❌ Complex consumer logic needed

### Solution 3: Pre-Aggregate Before Kafka

Aggregate logs **before** sending to Kafka:

```
Log Sources → Aggregator (30s windows) → Kafka → Consumers
              │
              ├─ Computes rolling features
              ├─ Aggregates volume metrics
              └─ Sends pre-computed features
```

**Implementation:**
```python
class PreAggregator:
    def __init__(self):
        self.buffer = []
        self.feature_extractor = FeatureExtractor(...)

    def add_log(self, log):
        self.buffer.append(log)

        # Every 30 seconds
        if len(self.buffer) >= 3000:
            # Extract features from raw logs
            features = self.feature_extractor.extract_all_features(self.buffer)

            # Send aggregated features to Kafka (not raw logs!)
            producer.send('aggregated-features', features)

            self.buffer = []
```

**Pros:**
- ✅ Consumers receive pre-computed features
- ✅ No rolling calculation needed in consumers
- ✅ Can scale consumers independently

**Cons:**
- ❌ Complex architecture (new component)
- ❌ Pre-aggregator becomes bottleneck
- ❌ Less flexible (can't recompute features with different windows)

### Solution 4: Global State Store (Advanced)

Use shared database (Redis/PostgreSQL) for global rolling window state:

```python
def extract_rolling_features(self, df):
    # Read last 5 minutes of data from ALL partitions
    past_logs = redis.get('global_logs_last_5min')

    # Combine with current window
    all_logs = pd.concat([past_logs, df])

    # Calculate rolling features on complete data
    rolling_mean = all_logs['log_count'].rolling('5min').mean()

    # Update global state for next consumer
    redis.set('global_logs_last_5min', all_logs[-300:])  # Keep last 5 min

    return rolling_mean
```

**Architecture:**
```
Consumer 1 (P0) ──┐
Consumer 2 (P1) ──┼──> Redis (global state)
Consumer 3 (P2) ──┘
```

**Pros:**
- ✅ Rolling features correct across partitions
- ✅ Parallel processing possible
- ✅ Flexible

**Cons:**
- ❌ Network overhead (Redis calls)
- ❌ Race conditions (need locking)
- ❌ Complexity
- ❌ Redis becomes single point of failure

### Solution 5: Post-Aggregation Layer

Write raw results to database, then aggregate:

```
Consumers → Write to DB → Aggregation Query → Dashboard
```

```python
# Consumers write raw window results
results = {
    'window_start': '10:00:00',
    'window_end': '10:00:30',
    'partition': 0,
    'log_count': 1000,
    'error_count': 10
}
db.insert('raw_results', results)

# Separate process aggregates across partitions
def aggregate_windows():
    # Query all partitions for same time window
    results = db.query("""
        SELECT
            window_start,
            SUM(log_count) as total_logs,
            SUM(error_count) as total_errors
        FROM raw_results
        WHERE window_start >= NOW() - INTERVAL '5 minutes'
        GROUP BY window_start
    """)

    # Now compute rolling features on aggregated data
    rolling_features = compute_rolling(results)
```

**Pros:**
- ✅ Correct aggregation across partitions
- ✅ Can recompute features retroactively
- ✅ Simple consumer logic

**Cons:**
- ❌ Higher latency (wait for DB aggregation)
- ❌ Extra database load
- ❌ More complex pipeline

---

## Recommendation for LogGuard

### Use **Solution 1: Single Partition**

**Why:**

1. **Throughput is sufficient:**
   ```
   Required:  50k-200k logs/min = 833-3,333 logs/sec
   Single partition capacity: ~10,000 logs/sec
   Margin: 3-10x headroom ✅
   ```

2. **Correctness is critical:**
   - Time-series ordering preserved
   - Rolling features accurate
   - Anomaly detection reliable

3. **Simplicity:**
   - No complex coordination
   - Easy to debug
   - Clear data flow

4. **Your current architecture already works:**
   - No code changes needed
   - Just ensure 1 partition

### How to Configure

**Option 1: Update docker-compose.yml**

```yaml
# Add Kafka environment variable
kafka:
  environment:
    # ... existing vars ...
    KAFKA_NUM_PARTITIONS: 1  # Default partitions for auto-created topics
```

**Option 2: Explicitly create topic**

```bash
docker exec -it logguard-kafka bash

# Delete existing topic (if any)
kafka-topics --delete --topic log-events --bootstrap-server localhost:9092

# Create with 1 partition
kafka-topics --create \
    --topic log-events \
    --partitions 1 \
    --replication-factor 1 \
    --bootstrap-server localhost:9092

# Verify
kafka-topics --describe --topic log-events --bootstrap-server localhost:9092
```

**Expected output:**
```
Topic: log-events  PartitionCount: 1  ReplicationFactor: 1
  Topic: log-events  Partition: 0  Leader: 1  Replicas: 1  Isr: 1
```

### Future Scaling (If Needed)

If you ever need > 10k logs/sec:

1. **Option A:** Use Solution 3 (Pre-aggregation)
   - Add aggregator service before Kafka
   - Send aggregated features instead of raw logs

2. **Option B:** Use Solution 4 (Global state store)
   - Add Redis for shared rolling window state
   - Coordinate consumers via Redis

3. **Option C:** Use columnar database
   - Use ClickHouse or Druid for real-time aggregation
   - Query across partitions in milliseconds

---

## Summary Table

| Question | Answer |
|----------|--------|
| **How does Kafka track what's read?** | Stores offset per consumer group in `__consumer_offsets` topic |
| **How does poll() get data?** | Fetches messages from last committed offset onwards |
| **What if consumer crashes?** | Restarts from last committed offset (may reprocess recent messages with auto-commit) |
| **Can I have single consumer?** | ✅ Yes! Run `python stream_processor.py` once |
| **What are multiple consumers?** | Same consumer group → Kafka assigns each partition to different consumer |
| **Time-series ordering problem?** | Parallel consumers break global ordering, incorrect rolling features |
| **Solution for LogGuard?** | **Use 1 partition + 1 consumer** (sufficient throughput, preserves ordering) |

---

## Additional Resources

- [Kafka Consumer Documentation](https://kafka.apache.org/documentation/#consumerapi)
- [Consumer Group Protocol](https://kafka.apache.org/documentation/#consumerconfigs)
- [Offset Management](https://kafka.apache.org/documentation/#offsetmgmt)
- [LogGuard Streaming Setup](STREAMING_SETUP.md)
