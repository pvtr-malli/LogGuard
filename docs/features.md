## Feature Engineering

### Volume Features (12 features)

#### Raw Counts

| Feature | Description | Example |
|---------|-------------|---------|
| `log_count` | Total logs in window | 150 |
| `error_count` | Number of ERROR logs | 5 |
| `fatal_count` | Number of FATAL logs | 0 |
| `warn_count` | Number of WARN logs | 10 |
| `info_count` | Number of INFO logs | 100 |
| `debug_count` | Number of DEBUG logs | 35 |

#### Derived Rates

| Feature | Formula | Example |
|---------|---------|---------|
| `error_rate` | `error_count / log_count` | 0.033 |
| `fatal_rate` | `fatal_count / log_count` | 0.0 |
| `warn_rate` | `warn_count / log_count` | 0.067 |
| `warn_to_info_ratio` | `warn_count / info_count` | 0.1 |
| `critical_count` | `error_count + fatal_count` | 5 |
| `critical_rate` | `critical_count / log_count` | 0.033 |

#### Why These Features Matter

**Anomaly Detection Patterns**:
- **Error Spike**: High `error_count`, high `error_rate`
- **Log Flood**: Very high `log_count` (10x normal)
- **Silent Failure**: Low `log_count` (system stopped logging)
- **Cascading Failure**: High `critical_count` across services
- **Warning Storm**: High `warn_to_info_ratio` (>1.0)

---
### Text Features (18 features)

#### TF-IDF Features (15 dimensions)

**Purpose**: Capture semantic content of log messages.

**Process**:
1. **Normalize** messages (replace numbers, IDs, etc.)
2. **Vectorize** with TF-IDF (100 most important terms, unigrams + bigrams)
3. **Reduce** dimensions with TruncatedSVD (100→15, 91% variance retained)

**Features**: `tfidf_0`, `tfidf_1`, ..., `tfidf_14`

**Example Terms Captured**:
- `api request`, `authentication`, `cache hit`
- `database query`, `connection`, `timeout`
- `error`, `failed`, `invalid`

**Why This Matters**:
- Detects **new error types** (messages with unusual terms)
- Identifies **semantic shifts** (different vocabulary appearing)
- Complements volume features (what vs. how many)

#### Message Clustering Features (3 dimensions)

**1. Message Cluster** (`message_cluster`)
- **Algorithm**: KMeans with 20 clusters
- **Input**: 15-dimensional TF-IDF embeddings
- **Output**: Cluster ID (0-19)
- **Purpose**: Group similar messages together

**Cluster Examples**:
- Cluster 0: "Order created successfully" messages
- Cluster 1: "Authentication successful" messages
- Cluster 2: "Slow query detected" messages

**2. Message Rarity** (`message_rarity`)
- **Formula**: `1.0 / frequency_of_template`
- **Range**: [0, 1]
- **Purpose**: Identify unusual message templates
- **Example**:
  - Common message "User login successful": rarity = 0.0001
  - Rare message "Connection timeout to db-5": rarity = 0.9

**3. Message Anomaly Score** (`message_anomaly_score`)
- **Formula**: Euclidean distance to assigned cluster centroid
- **Range**: [0, 1] (normalized)
- **Purpose**: Measure how unusual a message is within its cluster
- **Example**:
  - Message close to cluster center: score = 0.01
  - Message far from cluster center: score = 0.95


#### Anomaly Score Calculation

**For Noise Points** (cluster_label = -1):
```python
# Distance to nearest cluster centroid
distance = min(distances_to_all_centroids)
anomaly_score = normalize(distance, min=0, max=max_distance)
```

**For Normal Points** (cluster_label >= 0):
```python
# Distance to own cluster centroid
distance = distance_to_assigned_centroid
anomaly_score = normalize(distance, min=0, max=max_distance)
```

**Interpretation**:
- `anomaly_score < 0.3`: Definitely normal
- `anomaly_score 0.3-0.6`: Borderline
- `anomaly_score > 0.6`: Likely anomaly
- `anomaly_score > 0.8`: Definitely anomaly

---