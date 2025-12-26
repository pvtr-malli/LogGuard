"""
Real-time stream processor using Dask for anomaly detection.

Consumes logs from Kafka, processes them in 30-second windows,
and publishes anomaly detection results back to Kafka.
"""

import json
import signal
import sys
from datetime import datetime, timedelta, timezone
from typing import Dict, List
import pandas as pd
from kafka import KafkaConsumer, KafkaProducer
from kafka.errors import KafkaError
import pickle
from pathlib import Path

from log_guard.pipeline.feature_extractor import FeatureExtractor
from log_guard.pipeline.predictor import AnomalyPredictor


class StreamProcessor:
    """
    Real-time stream processor for log anomaly detection.
    """

    def __init__(
        self,
        kafka_brokers: str = 'localhost:9092',
        input_topic: str = 'log-events',
        output_topic: str = 'anomaly-results',
        consumer_group: str = 'logguard-processor',
        window_seconds: int = 30,
        model_dir: str = '../models'
    ):
        """
        Initialize the stream processor.

        param kafka_brokers: Kafka bootstrap servers.
        param input_topic: Kafka topic to consume logs from.
        param output_topic: Kafka topic to publish results to.
        param consumer_group: Kafka consumer group ID.
        param window_seconds: Window size in seconds.
        param model_dir: Directory containing trained models.
        """
        self.kafka_brokers = kafka_brokers
        self.input_topic = input_topic
        self.output_topic = output_topic
        self.consumer_group = consumer_group
        self.window_seconds = window_seconds
        self.model_dir = Path(model_dir)

        self.running = False
        self.consumer: KafkaConsumer = None
        self.producer: KafkaProducer = None

        # Buffer for windowing.
        self.log_buffer: List[Dict] = []
        self.window_start_time: datetime = None

        # Statistics.
        self.windows_processed = 0
        self.anomalies_detected = 0
        self.logs_processed = 0

        # Setup signal handlers.
        signal.signal(signal.SIGINT, self._signal_handler)
        signal.signal(signal.SIGTERM, self._signal_handler)

    def _signal_handler(self, signum, frame):
        """
        Handle shutdown signals gracefully.

        param signum: Signal number.
        param frame: Current stack frame.
        """
        print(f"\n\nReceived signal {signum}, shutting down gracefully...")
        self.stop()
        sys.exit(0)

    def _load_models(self):
        """
        Load trained models and artifacts.
        """
        print("Loading trained models...")

        try:
            with open(self.model_dir / 'tfidf_vectorizer.pkl', 'rb') as f:
                tfidf = pickle.load(f)

            with open(self.model_dir / 'svd_reducer.pkl', 'rb') as f:
                svd = pickle.load(f)

            with open(self.model_dir / 'message_clusters.pkl', 'rb') as f:
                kmeans = pickle.load(f)

            with open(self.model_dir / 'message_rarity.pkl', 'rb') as f:
                message_rarity_lookup = pickle.load(f)

            # Initialize feature extractor.
            self.feature_extractor = FeatureExtractor(
                tfidf=tfidf,
                svd=svd,
                kmeans=kmeans,
                message_rarity_lookup=message_rarity_lookup
            )
            self.predictor = AnomalyPredictor(
                model_path=str(self.model_dir / 'dbscan_model.pkl'),
                scaler_path=str(self.model_dir / 'scaler.pkl')
            )

            print("✓ Models loaded successfully")

        except FileNotFoundError as e:
            print(f"✗ Model file not found: {e}")
            print("\nPlease export models from notebooks first:")
            print("  1. Run notebook 04_text_embeddings.ipynb (final cell)")
            print("  2. Run notebook 05_anomaly_detection_models.ipynb (final cell)")
            raise

    def connect(self):
        """
        Connect to Kafka.
        """
        print(f"Connecting to Kafka at {self.kafka_brokers}...")

        try:
            self.consumer = KafkaConsumer(
                self.input_topic,
                bootstrap_servers=self.kafka_brokers,
                group_id=self.consumer_group,
                value_deserializer=lambda m: json.loads(m.decode('utf-8')),
                auto_offset_reset='latest',  # Start from latest messages.
                enable_auto_commit=True,
                auto_commit_interval_ms=1000
            )

            self.producer = KafkaProducer(
                bootstrap_servers=self.kafka_brokers,
                value_serializer=lambda v: json.dumps(v).encode('utf-8'),
                acks='all',
                retries=3
            )

            print("✓ Connected to Kafka successfully")

        except KafkaError as e:
            print(f"✗ Failed to connect to Kafka: {e}")
            raise

    def _process_window(self):
        """
        Process accumulated logs in the current window.
        """
        if not self.log_buffer:
            return

        try:
            logs_df = pd.DataFrame(self.log_buffer)
            logs_df['timestamp'] = pd.to_datetime(logs_df['timestamp'])
            features_df = self.feature_extractor.extract_all_features(
                logs_df,
                window=f'{self.window_seconds}s'
            )
            results = self.predictor.predict_with_confidence(features_df)
            for _, row in results.iterrows():
                result_message = {
                    'timestamp': row['timestamp'].isoformat() if pd.notna(row['timestamp']) else None,
                    'window_start': self.window_start_time.isoformat(),
                    'window_end': (self.window_start_time + timedelta(seconds=self.window_seconds)).isoformat(),
                    'is_anomaly': int(row['is_anomaly']),
                    'anomaly_score': float(row['anomaly_score']),
                    'cluster_label': int(row['cluster_label']),
                    'log_count': len(logs_df),
                    'error_count': len(logs_df[logs_df['level'] == 'ERROR']),
                    'critical_count': len(logs_df[logs_df['level'].isin(['ERROR', 'FATAL'])]),
                }

                self.producer.send(self.output_topic, value=result_message)

                if row['is_anomaly'] == 1:
                    self.anomalies_detected += 1

            self.windows_processed += 1
            self.logs_processed += len(logs_df)

            print(f"[{datetime.now().strftime('%H:%M:%S')}] "
                  f"Window {self.windows_processed}: "
                  f"Processed {len(logs_df)} logs, "
                  f"Anomalies: {results['is_anomaly'].sum()}")

        except Exception as e:
            print(f"✗ Error processing window: {e}")

        finally:
            # Clear buffer for next window.
            self.log_buffer = []

    def start(self):
        """
        Start the stream processor.
        """
        self._load_models()
        self.connect()

        self.running = True
        self.window_start_time = datetime.now(timezone.utc)

        print(f"\n{'='*60}")
        print(f"Starting stream processor")
        print(f"{'='*60}")
        print(f"Input topic: {self.input_topic}")
        print(f"Output topic: {self.output_topic}")
        print(f"Window size: {self.window_seconds} seconds")
        print(f"\nPress Ctrl+C to stop\n")

        try:
            while self.running:
                # Poll for messages for 100ms.
                messages = self.consumer.poll(timeout_ms=100)

                for topic_partition, records in messages.items():
                    for record in records:
                        log_entry = record.value
                        self.log_buffer.append(log_entry)

                # Check if window is complete.
                current_time = datetime.now(timezone.utc)
                elapsed = (current_time - self.window_start_time).total_seconds()

                if elapsed >= self.window_seconds:
                    self._process_window()
                    self.window_start_time = current_time

        except KeyboardInterrupt:
            print("\nKeyboard interrupt received")
        finally:
            self.stop()

    def stop(self):
        """
        Stop the processor gracefully.
        """
        self.running = False

        if self.log_buffer:
            print("\nProcessing remaining logs...")
            self._process_window()

        if self.producer:
            print("Flushing producer...")
            self.producer.flush(timeout=10)
            self.producer.close()

        if self.consumer:
            print("Closing consumer...")
            self.consumer.close()

        print(f"\n{'='*60}")
        print(f"Stream processor stopped")
        print(f"{'='*60}")
        print(f"Windows processed: {self.windows_processed:,}")
        print(f"Logs processed: {self.logs_processed:,}")
        print(f"Anomalies detected: {self.anomalies_detected:,}")


def main():
    """
    Main entry point for the stream processor.
    """
    import argparse

    parser = argparse.ArgumentParser(
        description='Real-time stream processor for LogGuard',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Start processor with default settings.
  python stream_processor.py

  # Use different window size.
  python stream_processor.py --window 60

  # Connect to remote Kafka.
  python stream_processor.py --kafka-brokers kafka1:9092,kafka2:9092
        """
    )

    parser.add_argument(
        '--kafka-brokers',
        default='localhost:9092',
        help='Kafka bootstrap servers (default: localhost:9092)'
    )
    parser.add_argument(
        '--input-topic',
        default='log-events',
        help='Kafka topic to consume logs from (default: log-events)'
    )
    parser.add_argument(
        '--output-topic',
        default='anomaly-results',
        help='Kafka topic to publish results to (default: anomaly-results)'
    )
    parser.add_argument(
        '--consumer-group',
        default='logguard-processor',
        help='Kafka consumer group ID (default: logguard-processor)'
    )
    parser.add_argument(
        '--window',
        type=int,
        default=30,
        help='Window size in seconds (default: 30)'
    )
    parser.add_argument(
        '--model-dir',
        default='../models',
        help='Directory containing trained models (default: ../models)'
    )

    args = parser.parse_args()

    processor = StreamProcessor(
        kafka_brokers=args.kafka_brokers,
        input_topic=args.input_topic,
        output_topic=args.output_topic,
        consumer_group=args.consumer_group,
        window_seconds=args.window,
        model_dir=args.model_dir
    )

    processor.start()


if __name__ == '__main__':
    main()
