-- Initialize TimescaleDB for LogGuard anomaly detection results.

-- Enable TimescaleDB extension.
CREATE EXTENSION IF NOT EXISTS timescaledb CASCADE;

-- Table for storing anomaly detection results.
CREATE TABLE IF NOT EXISTS anomaly_results (
    timestamp TIMESTAMPTZ NOT NULL,
    window_start TIMESTAMPTZ NOT NULL,
    window_end TIMESTAMPTZ NOT NULL,
    is_anomaly INTEGER NOT NULL,
    anomaly_score DOUBLE PRECISION,
    cluster_label INTEGER,
    log_count INTEGER,
    error_count INTEGER,
    critical_count INTEGER,
    error_rate DOUBLE PRECISION,
    critical_rate DOUBLE PRECISION,
    ground_truth INTEGER DEFAULT 0,
    PRIMARY KEY (timestamp, window_start)
);

-- Convert to hypertable for time-series optimization.
SELECT create_hypertable('anomaly_results', 'timestamp', if_not_exists => TRUE);

-- Create index on anomaly flag for fast filtering.
CREATE INDEX IF NOT EXISTS idx_anomaly_results_is_anomaly
ON anomaly_results (is_anomaly, timestamp DESC);

-- Create index on window start for fast range queries.
CREATE INDEX IF NOT EXISTS idx_anomaly_results_window_start
ON anomaly_results (window_start);

-- Table for storing raw log events (optional, for debugging).
CREATE TABLE IF NOT EXISTS log_events (
    timestamp TIMESTAMPTZ NOT NULL,
    level VARCHAR(10) NOT NULL,
    component VARCHAR(50),
    message TEXT NOT NULL,
    is_anomaly INTEGER
);

-- Convert to hypertable.
SELECT create_hypertable('log_events', 'timestamp', if_not_exists => TRUE);

-- Create index on log level.
CREATE INDEX IF NOT EXISTS idx_log_events_level
ON log_events (level, timestamp DESC);

-- Continuous aggregate for hourly anomaly summaries.
CREATE MATERIALIZED VIEW IF NOT EXISTS anomaly_summary_hourly
WITH (timescaledb.continuous) AS
SELECT
    time_bucket('1 hour', timestamp) AS bucket,
    COUNT(*) AS total_windows,
    SUM(is_anomaly) AS anomaly_count,
    AVG(anomaly_score) AS avg_anomaly_score,
    MAX(anomaly_score) AS max_anomaly_score,
    AVG(error_rate) AS avg_error_rate,
    AVG(critical_rate) AS avg_critical_rate
FROM anomaly_results
GROUP BY bucket
WITH NO DATA;

-- Refresh policy for continuous aggregate (refresh every 10 minutes).
SELECT add_continuous_aggregate_policy('anomaly_summary_hourly',
    start_offset => INTERVAL '1 day',
    end_offset => INTERVAL '10 minutes',
    schedule_interval => INTERVAL '10 minutes',
    if_not_exists => TRUE
);

-- Data retention policy (keep detailed data for 30 days).
SELECT add_retention_policy('anomaly_results', INTERVAL '30 days', if_not_exists => TRUE);
SELECT add_retention_policy('log_events', INTERVAL '7 days', if_not_exists => TRUE);

-- Grant permissions.
GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA public TO logguard;
GRANT ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA public TO logguard;
