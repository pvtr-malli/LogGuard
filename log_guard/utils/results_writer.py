"""
Results writer that consumes anomaly detection results from Kafka
and writes them to TimescaleDB for storage and querying.
"""

import json
import signal
import sys
from datetime import datetime
from typing import Optional
import psycopg2
from psycopg2.extras import execute_values
from kafka import KafkaConsumer
from kafka.errors import KafkaError


class ResultsWriter:
    """
    Consumes anomaly results from Kafka and writes to TimescaleDB.
    """

    def __init__(
        self,
        kafka_brokers: str = 'localhost:9092',
        topic: str = 'anomaly-results',
        consumer_group: str = 'logguard-writer',
        db_host: str = 'localhost',
        db_port: int = 5432,
        db_name: str = 'logguard',
        db_user: str = 'logguard',
        db_password: str = 'logguard123',
        batch_size: int = 100
    ):
        """
        Initialize the results writer.

        param kafka_brokers: Kafka bootstrap servers.
        param topic: Kafka topic to consume results from.
        param consumer_group: Kafka consumer group ID.
        param db_host: Database host.
        param db_port: Database port.
        param db_name: Database name.
        param db_user: Database user.
        param db_password: Database password.
        param batch_size: Number of records to batch before writing.
        """
        self.kafka_brokers = kafka_brokers
        self.topic = topic
        self.consumer_group = consumer_group
        self.db_host = db_host
        self.db_port = db_port
        self.db_name = db_name
        self.db_user = db_user
        self.db_password = db_password
        self.batch_size = batch_size

        self.running = False
        self.consumer: Optional[KafkaConsumer] = None
        self.db_conn: Optional[psycopg2.extensions.connection] = None
        self.db_cursor: Optional[psycopg2.extensions.cursor] = None

        # Buffer for batch inserts.
        self.result_buffer = []

        # Statistics.
        self.results_written = 0
        self.batches_written = 0

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

    def _connect_kafka(self):
        """
        Connect to Kafka.
        """
        print(f"Connecting to Kafka at {self.kafka_brokers}...")

        try:
            self.consumer = KafkaConsumer(
                self.topic,
                bootstrap_servers=self.kafka_brokers,
                group_id=self.consumer_group,
                value_deserializer=lambda m: json.loads(m.decode('utf-8')),
                auto_offset_reset='earliest',  # Start from beginning if no offset.
                enable_auto_commit=True,
                auto_commit_interval_ms=1000
            )

            print("✓ Connected to Kafka successfully")

        except KafkaError as e:
            print(f"✗ Failed to connect to Kafka: {e}")
            raise

    def _connect_database(self):
        """
        Connect to TimescaleDB.
        """
        print(f"Connecting to TimescaleDB at {self.db_host}:{self.db_port}...")

        try:
            self.db_conn = psycopg2.connect(
                host=self.db_host,
                port=self.db_port,
                dbname=self.db_name,
                user=self.db_user,
                password=self.db_password
            )
            self.db_cursor = self.db_conn.cursor()

            print("✓ Connected to TimescaleDB successfully")

        except psycopg2.Error as e:
            print(f"✗ Failed to connect to TimescaleDB: {e}")
            raise

    def _write_batch(self):
        """
        Write buffered results to database.
        """
        if not self.result_buffer:
            return

        try:
            # Prepare data for batch insert.
            values = [
                (
                    result['timestamp'],
                    result['window_start'],
                    result['window_end'],
                    result['is_anomaly'],
                    result['anomaly_score'],
                    result['cluster_label'],
                    result['log_count'],
                    result['error_count'],
                    result['critical_count'],
                    result['error_count'] / result['log_count'] if result['log_count'] > 0 else 0,
                    result['critical_count'] / result['log_count'] if result['log_count'] > 0 else 0,
                    result.get('ground_truth', 0)  # Ground truth (0 if not present)
                )
                for result in self.result_buffer
            ]

            # Batch insert.
            execute_values(
                self.db_cursor,
                """
                INSERT INTO anomaly_results (
                    timestamp, window_start, window_end,
                    is_anomaly, anomaly_score, cluster_label,
                    log_count, error_count, critical_count,
                    error_rate, critical_rate, ground_truth
                ) VALUES %s
                ON CONFLICT (timestamp, window_start) DO UPDATE SET
                    window_end = EXCLUDED.window_end,
                    is_anomaly = EXCLUDED.is_anomaly,
                    anomaly_score = EXCLUDED.anomaly_score,
                    cluster_label = EXCLUDED.cluster_label,
                    log_count = EXCLUDED.log_count,
                    error_count = EXCLUDED.error_count,
                    critical_count = EXCLUDED.critical_count,
                    error_rate = EXCLUDED.error_rate,
                    critical_rate = EXCLUDED.critical_rate
                """,
                values
            )

            self.db_conn.commit()

            self.results_written += len(self.result_buffer)
            self.batches_written += 1

            print(f"[{datetime.now().strftime('%H:%M:%S')}] "
                  f"Batch {self.batches_written}: "
                  f"Wrote {len(self.result_buffer)} results "
                  f"(Total: {self.results_written:,})")

        except psycopg2.Error as e:
            print(f"✗ Database error: {e}")
            self.db_conn.rollback()

        finally:
            # Clear buffer.
            self.result_buffer = []

    def start(self):
        """
        Start the results writer.
        """
        # Connect to Kafka and database.
        self._connect_kafka()
        self._connect_database()

        self.running = True

        print(f"\n{'='*60}")
        print(f"Starting results writer")
        print(f"{'='*60}")
        print(f"Kafka topic: {self.topic}")
        print(f"Database: {self.db_name}@{self.db_host}:{self.db_port}")
        print(f"Batch size: {self.batch_size}")
        print(f"\nPress Ctrl+C to stop\n")

        try:
            while self.running:
                # Poll for messages.
                messages = self.consumer.poll(timeout_ms=1000)

                for topic_partition, records in messages.items():
                    for record in records:
                        result = record.value
                        self.result_buffer.append(result)

                        # Write batch if buffer is full.
                        if len(self.result_buffer) >= self.batch_size:
                            self._write_batch()

        except KeyboardInterrupt:
            print("\nKeyboard interrupt received")
        finally:
            self.stop()

    def stop(self):
        """
        Stop the writer gracefully.
        """
        self.running = False

        # Write remaining results.
        if self.result_buffer:
            print("\nWriting remaining results...")
            self._write_batch()

        # Close connections.
        if self.db_cursor:
            self.db_cursor.close()

        if self.db_conn:
            self.db_conn.close()
            print("✓ Database connection closed")

        if self.consumer:
            self.consumer.close()
            print("✓ Kafka consumer closed")

        print(f"\n{'='*60}")
        print(f"Results writer stopped")
        print(f"{'='*60}")
        print(f"Results written: {self.results_written:,}")
        print(f"Batches written: {self.batches_written:,}")


def main():
    """
    Main entry point for the results writer.
    """
    import argparse

    parser = argparse.ArgumentParser(
        description='Results writer for LogGuard',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Start writer with default settings.
  python results_writer.py

  # Connect to remote Kafka and database.
  python results_writer.py \\
      --kafka-brokers kafka:9092 \\
      --db-host timescaledb \\
      --db-password mypassword

  # Use larger batch size.
  python results_writer.py --batch-size 500
        """
    )

    parser.add_argument(
        '--kafka-brokers',
        default='localhost:9092',
        help='Kafka bootstrap servers (default: localhost:9092)'
    )
    parser.add_argument(
        '--topic',
        default='anomaly-results',
        help='Kafka topic to consume results from (default: anomaly-results)'
    )
    parser.add_argument(
        '--consumer-group',
        default='logguard-writer',
        help='Kafka consumer group ID (default: logguard-writer)'
    )
    parser.add_argument(
        '--db-host',
        default='localhost',
        help='Database host (default: localhost)'
    )
    parser.add_argument(
        '--db-port',
        type=int,
        default=5432,
        help='Database port (default: 5432)'
    )
    parser.add_argument(
        '--db-name',
        default='logguard',
        help='Database name (default: logguard)'
    )
    parser.add_argument(
        '--db-user',
        default='logguard',
        help='Database user (default: logguard)'
    )
    parser.add_argument(
        '--db-password',
        default='logguard123',
        help='Database password (default: logguard123)'
    )
    parser.add_argument(
        '--batch-size',
        type=int,
        default=100,
        help='Batch size for database writes (default: 100)'
    )

    args = parser.parse_args()

    # Create and start writer.
    writer = ResultsWriter(
        kafka_brokers=args.kafka_brokers,
        topic=args.topic,
        consumer_group=args.consumer_group,
        db_host=args.db_host,
        db_port=args.db_port,
        db_name=args.db_name,
        db_user=args.db_user,
        db_password=args.db_password,
        batch_size=args.batch_size
    )

    writer.start()


if __name__ == '__main__':
    main()
