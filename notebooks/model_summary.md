## Anomaly Detection

### Model Selection Process

#### Evaluation Methodology

**Dataset**: 25,921 windows (131,935 logs over 9 days)
- Training set: 70% (18,144 windows)
- Test set: 30% (7,777 windows)
- Anomalies: 115 windows (0.44%)

**Metrics**:
- **Precision**: % of predicted anomalies that are true anomalies
- **Recall**: % of true anomalies that are detected
- **F1-Score**: Harmonic mean of precision and recall

#### Model Comparison

| Model | Precision | Recall | F1-Score | Best Use Case |
|-------|-----------|--------|----------|---------------|
| **Isolation Forest** | 0.5217 | 0.5217 | 0.5217 | High-dimensional data |
| **DBSCAN** | 0.8318 | 0.7739 | **0.8018** ✅ | Density-based anomalies |
| **HDBSCAN** | 0.4769 | 0.8957 | 0.6224 | Hierarchical clusters |

**Winner**: DBSCAN
- **Best F1-score**: Optimal balance of precision and recall
- **High precision**: Few false positives (83%)
- **Good recall**: Catches most anomalies (77%)

---