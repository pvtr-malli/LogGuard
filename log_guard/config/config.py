"""
Configuration settings for LogGuard anomaly detection system.
"""

from pathlib import Path


class Config:
    """
    Configuration parameters for the anomaly detection pipeline.
    """

    # Project paths.
    BASE_DIR = Path(__file__).parent.parent
    DATA_DIR = BASE_DIR / 'data'
    MODEL_DIR = BASE_DIR / 'models'
    NOTEBOOKS_DIR = BASE_DIR / 'notebooks'

    # Model paths.
    DBSCAN_MODEL_PATH = MODEL_DIR / 'dbscan_model.pkl'
    SCALER_PATH = MODEL_DIR / 'scaler.pkl'
    TFIDF_PATH = MODEL_DIR / 'tfidf_vectorizer.pkl'
    SVD_PATH = MODEL_DIR / 'svd_reducer.pkl'
    KMEANS_PATH = MODEL_DIR / 'message_clusters.pkl'
    RARITY_PATH = MODEL_DIR / 'message_rarity.pkl'

    # Feature engineering parameters.
    WINDOW_SIZE = '30s'
    ROLLING_WINDOWS = {
        '5min': '5min',
        '15min': '15min',
        '1h': '1h'
    }
    TF_IDF_DIMENSIONS = 15

    # DBSCAN hyperparameters (best from tuning).
    DBSCAN_EPS = 15.0
    DBSCAN_MIN_SAMPLES = 15

    # Performance requirements.
    MAX_LATENCY_SECONDS = 30
    TARGET_THROUGHPUT_PER_MINUTE = 50000  # 50k-200k range.

    # Alerting thresholds.
    ANOMALY_SCORE_THRESHOLD = 0.7
    ANOMALY_RATE_THRESHOLD = 0.1  # Alert if >10% of windows are anomalous.

    # Logging.
    LOG_LEVEL = 'INFO'
    LOG_FORMAT = '%(asctime)s - %(name)s - %(levelname)s - %(message)s'


class ProductionConfig(Config):
    """
    Production-specific configuration.
    """

    # Kafka settings (for streaming ingestion).
    KAFKA_BOOTSTRAP_SERVERS = 'localhost:9092'
    KAFKA_TOPIC_LOGS = 'log-events'
    KAFKA_TOPIC_ANOMALIES = 'anomaly-alerts'
    KAFKA_CONSUMER_GROUP = 'logguard-anomaly-detector'

    # Alerting endpoints.
    SLACK_WEBHOOK_URL = None  # Set via environment variable.
    PAGERDUTY_API_KEY = None  # Set via environment variable.

    # Monitoring.
    METRICS_PORT = 9090
    HEALTH_CHECK_PORT = 8080


class DevelopmentConfig(Config):
    """
    Development-specific configuration.
    """

    # Use local CSV files for testing.
    TEST_LOG_FILE = Config.DATA_DIR / 'synthetic_logs.csv'
    TEST_OUTPUT_FILE = Config.DATA_DIR / 'anomaly_predictions.csv'

    # Debug mode.
    DEBUG = True
    LOG_LEVEL = 'DEBUG'


def get_config(env: str = 'development'):
    """
    Get configuration based on environment.

    param env: Environment name ('development' or 'production').
    """
    if env == 'production':
        return ProductionConfig()
    else:
        return DevelopmentConfig()
