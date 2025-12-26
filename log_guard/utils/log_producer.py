"""
Continuous log producer that generates synthetic logs and sends them to Kafka.

This simulates a real production system generating logs continuously.
"""

import time
import json
import random
import signal
import sys
from datetime import datetime, timezone
from typing import Optional
from kafka import KafkaProducer
from kafka.errors import KafkaError


class LogProducer:
    """
    Continuous log producer that generates synthetic logs.
    """

    def __init__(
        self,
        kafka_brokers: str = 'localhost:9092',
        topic: str = 'log-events',
        logs_per_second: int = 100,
        anomaly_probability: float = 0.005
    ):
        """
        Initialize the log producer.

        param kafka_brokers: Kafka bootstrap servers.
        param topic: Kafka topic to send logs to.
        param logs_per_second: Rate of log generation.
        param anomaly_probability: Probability of generating anomaly logs.
        """
        self.kafka_brokers = kafka_brokers
        self.topic = topic
        self.logs_per_second = logs_per_second
        self.anomaly_probability = anomaly_probability
        self.running = False
        self.producer: Optional[KafkaProducer] = None

        # Log templates.
        self.normal_templates = [
            "Database query completed - rows: {rows}, duration: {duration}ms",
            "Payment processed - transaction_id: txn_{txn_id}, amount: ${amount}",
            "Inventory updated - item_id: item_{item_id}, quantity: {quantity}",
            "Email notification sent to user{user_id}@example.com",
            "Cache hit for key: cache_{cache_id}",
            "Cache miss for key: cache_{cache_id}",
            "Request processed successfully - user_id: {user_id}, duration: {duration}ms",
            "Order created successfully - order_id: ord_{order_id}",
            "Authentication successful for user {user_id}",
            "User session created - session_id: sess_{session_id}",
            "API request received - endpoint: /api/{endpoint}, method: {method}",
            "Query plan: {plan}",
        ]

        self.anomaly_templates = [
            "Connection timeout to database - retrying in 5s",
            "Memory usage critical - 95% utilized",
            "Disk space low - 2GB remaining",
            "Slow query detected - duration: {slow_duration}ms",
            "Rate limit exceeded for user {user_id}",
            "Failed authentication attempt for user {user_id}",
            "Payment failed - insufficient funds - txn_{txn_id}",
            "Database connection pool exhausted",
            "Thread pool exhausted - queue size: {queue_size}",
            "Unhandled exception in request handler - {error}",
            "Invalid request - malformed JSON in request body",
            "Potential SQL injection attempt in query",
            "Service unavailable - external API timeout",
            "Circuit breaker opened for service: {service}",
        ]

        # Log levels.
        self.normal_levels = ['INFO', 'DEBUG']
        self.anomaly_levels = ['WARN', 'ERROR', 'FATAL']

        # Components.
        self.components = ['auth', 'payment', 'inventory', 'notification', 'database', 'cache', 'api']

        # Setup signal handlers for graceful shutdown.
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

    def _generate_log(self) -> dict:
        """
        Generate a single log entry.
        """
        is_anomaly = random.random() < self.anomaly_probability

        if is_anomaly:
            template = random.choice(self.anomaly_templates)
            level = random.choice(self.anomaly_levels)
        else:
            template = random.choice(self.normal_templates)
            level = random.choice(self.normal_levels)

        # Generate parameters.
        message = template.format(
            rows=random.randint(1, 1000),
            duration=random.randint(10, 500),
            slow_duration=random.randint(1000, 5000),
            txn_id=random.randint(100000, 999999),
            amount=f"{random.randint(10, 1000)}.{random.randint(10, 99)}",
            item_id=random.randint(1, 1000),
            quantity=random.randint(1, 100),
            user_id=random.randint(1000, 9999),
            cache_id=random.randint(1, 100),
            order_id=random.randint(100000, 999999),
            session_id=random.randint(100000, 999999),
            endpoint=random.choice(['users', 'payments', 'orders', 'products']),
            method=random.choice(['GET', 'POST', 'PUT', 'DELETE']),
            plan=random.choice(['index_scan', 'seq_scan', 'bitmap_scan']),
            queue_size=random.randint(10000, 50000),
            error=random.choice(['ValueError', 'KeyError', 'TypeError']),
            service=random.choice(['payment-service', 'inventory-service', 'notification-service'])
        )

        log_entry = {
            'timestamp': datetime.now(timezone.utc).isoformat(),
            'level': level,
            'component': random.choice(self.components),
            'message': message,
            'is_anomaly': 1 if is_anomaly else 0  # Ground truth for testing.
        }

        return log_entry

    def connect(self):
        """
        Connect to Kafka.
        """
        try:
            print(f"Connecting to Kafka at {self.kafka_brokers}...")
            self.producer = KafkaProducer(
                bootstrap_servers=self.kafka_brokers,
                value_serializer=lambda v: json.dumps(v).encode('utf-8'),
                acks='all',  # Wait for all replicas to acknowledge.
                retries=3,
                max_in_flight_requests_per_connection=1  # Ensure ordering.
            )
            print("✓ Connected to Kafka successfully")
        except KafkaError as e:
            print(f"✗ Failed to connect to Kafka: {e}")
            raise

    def start(self):
        """
        Start producing logs continuously.
        """
        if not self.producer:
            self.connect()

        self.running = True
        print(f"\n{'='*60}")
        print(f"Starting log producer")
        print(f"{'='*60}")
        print(f"Topic: {self.topic}")
        print(f"Rate: {self.logs_per_second} logs/second")
        print(f"Anomaly probability: {self.anomaly_probability * 100:.2f}%")
        print(f"\nPress Ctrl+C to stop\n")

        logs_sent = 0
        start_time = time.time()
        delay = 1.0 / self.logs_per_second

        try:
            while self.running:
                # Generate and send log.
                log_entry = self._generate_log()

                self.producer.send(self.topic, value=log_entry).add_callback(
                    self._on_send_success
                ).add_errback(
                    self._on_send_error
                )

                logs_sent += 1

                # Print stats every 1000 logs.
                if logs_sent % 1000 == 0:
                    elapsed = time.time() - start_time
                    rate = logs_sent / elapsed
                    print(f"[{datetime.now().strftime('%H:%M:%S')}] "
                          f"Sent {logs_sent:,} logs | "
                          f"Rate: {rate:.1f} logs/sec")

                # Sleep to maintain rate.
                time.sleep(delay)

        except KeyboardInterrupt:
            print("\nKeyboard interrupt received")
        finally:
            self.stop()
            elapsed = time.time() - start_time
            print(f"\n{'='*60}")
            print(f"Producer stopped")
            print(f"{'='*60}")
            print(f"Total logs sent: {logs_sent:,}")
            print(f"Total time: {elapsed:.1f} seconds")
            print(f"Average rate: {logs_sent / elapsed:.1f} logs/sec")

    def stop(self):
        """
        Stop the producer gracefully.
        """
        self.running = False
        if self.producer:
            print("\nFlushing remaining messages...")
            self.producer.flush(timeout=10)
            self.producer.close()
            print("✓ Producer closed")

    def _on_send_success(self, record_metadata):
        """
        Callback for successful send.

        param record_metadata: Metadata about the sent record.
        """
        pass  # Silent success.

    def _on_send_error(self, exception):
        """
        Callback for send errors.

        param exception: Exception that occurred.
        """
        print(f"\n✗ Failed to send log: {exception}")


def main():
    """
    Main entry point for the log producer.
    """
    import argparse

    parser = argparse.ArgumentParser(
        description='Continuous log producer for LogGuard',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Start producer with default settings (100 logs/sec).
  python log_producer.py

  # Generate 500 logs/sec.
  python log_producer.py --rate 500

  # Higher anomaly rate for testing.
  python log_producer.py --anomaly-prob 0.02

  # Connect to remote Kafka.
  python log_producer.py --kafka-brokers kafka1:9092,kafka2:9092
        """
    )

    parser.add_argument(
        '--kafka-brokers',
        default='localhost:9092',
        help='Kafka bootstrap servers (default: localhost:9092)'
    )
    parser.add_argument(
        '--topic',
        default='log-events',
        help='Kafka topic to send logs to (default: log-events)'
    )
    parser.add_argument(
        '--rate',
        type=int,
        default=100,
        help='Logs per second (default: 100)'
    )
    parser.add_argument(
        '--anomaly-prob',
        type=float,
        default=0.005,
        help='Probability of generating anomaly logs (default: 0.005)'
    )

    args = parser.parse_args()

    # Create and start producer.
    producer = LogProducer(
        kafka_brokers=args.kafka_brokers,
        topic=args.topic,
        logs_per_second=args.rate,
        anomaly_probability=args.anomaly_prob
    )

    producer.start()


if __name__ == '__main__':
    main()
