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
        logs_per_second: float = 100,
        anomaly_probability: float = 0.005
    ):
        """
        Initialize the log producer.

        param kafka_brokers: Kafka bootstrap servers.
        param topic: Kafka topic to send logs to.
        param logs_per_second: Rate of log generation (can be fractional, e.g., 0.5 for 1 log per 2 seconds).
        param anomaly_probability: Probability of generating anomaly logs.
        """
        self.kafka_brokers = kafka_brokers
        self.topic = topic
        self.logs_per_second = logs_per_second
        self.anomaly_probability = anomaly_probability
        self.running = False
        self.producer: Optional[KafkaProducer] = None

        # Log templates (MUST match training data structure - each level has specific messages).
        self.normal_templates = {
            'INFO': [
                'Request processed successfully - user_id: {user_id}, duration: {duration}ms',
                'Authentication successful for user {user_id}',
                'Payment processed - transaction_id: {txn_id}, amount: ${amount}',
                'Order created successfully - order_id: {order_id}',
                'Cache hit for key: {cache_key}',
                'Database query completed - rows: {rows}, duration: {duration}ms',
                'API request received - endpoint: {endpoint}, method: {method}',
                'User session created - session_id: {session_id}',
                'Email notification sent to {email}',
                'Inventory updated - item_id: {item_id}, quantity: {quantity}',
            ],
            'DEBUG': [
                'Entering function: {function_name}',
                'Cache miss for key: cache_{cache_id}',
                'Query plan: {plan}',
                'Response payload size: {size} bytes',
                'Connection pool stats: active={active}, idle={idle}',
            ],
            'WARN': [
                'High memory usage detected: {memory}%',
                'Slow query detected - duration: {slow_duration}ms',
                'Rate limit approaching for user {user_id}',
                'Connection retry attempt {attempt} of 3',
                'Cache eviction due to size limit',
                'Service latency above threshold: {duration}ms',
            ],
            # EXPECTED ERRORS (business logic, user errors - NOT anomalies when isolated).
            'ERROR': [
                'Authentication failed - invalid password for user {user_id}',
                'Validation error - missing required field: {field_name}',
                'Order failed - insufficient inventory for item {item_id}',
                'Payment declined - insufficient funds for user {user_id}',
                'Invalid request - malformed JSON in request body',
                'Resource not found - user_id {user_id} does not exist',
                'Session expired for user {user_id}',
                'Rate limit exceeded for user {user_id} - retry after {retry_after}s',
            ],
            'FATAL': [
                'Unhandled exception in request handler - {error}',
            ]
        }

        # Anomaly templates (TRUE system anomalies - pattern-based detection).
        self.anomaly_templates = {
            'spike_error': [
                'Database connection pool exhausted - max connections: {max_conn}',
                'Service unavailable - {service} not responding after {attempts} attempts',
                'Connection timeout to {host} - {error_msg}',
                'Failed to acquire database lock - deadlock detected',
            ],
            'cascade': [
                'Circuit breaker opened for {service} - failure threshold exceeded',
                'Upstream service {service} unavailable - cascading failure',
                'Database cluster unreachable - all nodes down',
                'Message queue full - dropping messages',
            ],
            'resource': [
                'Disk space critically low: {disk_space}% remaining',
                'Memory usage critical: {memory}% used',
                'CPU usage sustained above 95% for {duration} seconds',
                'Thread pool exhausted - queue size: {queue_size}',
            ],
            'security': [
                'Suspicious activity detected from IP: {ip_address}',
                'Brute force attack detected - {attempts} failed login attempts',
                'Potential SQL injection attempt in query',
                'Unauthorized access attempt to admin endpoint',
            ]
        }

        # Log levels (MUST match training data distribution).
        # Training uses: ['INFO', 'DEBUG', 'WARN', 'ERROR', 'FATAL'] with weights [0.65, 0.20, 0.10, 0.045, 0.005]
        # IMPORTANT: Normal logs can have ERROR/FATAL (business errors like "invalid password").
        self.log_levels = ['INFO', 'DEBUG', 'WARN', 'ERROR', 'FATAL']
        self.normal_level_weights = [0.65, 0.20, 0.10, 0.045, 0.005]

        # Services (MUST match training data format exactly).
        self.services = [
            'auth-service',
            'payment-service',
            'order-service',
            'inventory-service',
            'user-service',
            'notification-service',
            'api-gateway'
        ]

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

        IMPORTANT: Matches training data exactly:
        1. Pick log level first (weighted distribution for normal logs)
        2. Pick template from that level's templates
        3. Normal logs can have ERROR/FATAL (business errors, not anomalies)
        """
        is_anomaly = random.random() < self.anomaly_probability

        if is_anomaly:
            # Anomalies: Pick anomaly category, then template.
            anomaly_category = random.choice(list(self.anomaly_templates.keys()))
            template = random.choice(self.anomaly_templates[anomaly_category])
            # Anomalies are typically ERROR/FATAL/WARN.
            level = random.choice(['ERROR', 'FATAL', 'WARN'])
        else:
            # Normal logs: Pick level first (weighted), then template from that level.
            level = random.choices(self.log_levels, weights=self.normal_level_weights)[0]
            template = random.choice(self.normal_templates[level])

        # Generate parameters (all possible template variables).
        # IMPORTANT: Parameter names must match template placeholders exactly.
        message = template.format(
            # Normal log parameters.
            rows=random.randint(1, 1000),
            duration=random.randint(10, 500),
            txn_id=random.randint(100000, 999999),
            amount=round(random.uniform(10, 1000), 2),
            order_id=random.randint(100000, 999999),
            cache_id=random.randint(1, 100),
            cache_key=f'cache_{random.randint(1, 100)}',
            endpoint=random.choice(['/api/users', '/api/orders', '/api/payments']),
            method=random.choice(['GET', 'POST', 'PUT']),
            session_id=random.randint(100000, 999999),
            email=f'user{random.randint(1, 1000)}@example.com',
            item_id=random.randint(1, 500),
            quantity=random.randint(1, 100),
            function_name=random.choice(['processPayment', 'validateUser', 'updateInventory']),
            query_plan='index_scan',
            size=random.randint(100, 50000),
            active=random.randint(5, 20),
            idle=random.randint(10, 50),
            user_id=random.randint(1000, 9999),
            memory=random.randint(40, 75),
            slow_duration=random.randint(1000, 5000),
            attempt=random.randint(1, 3),
            field_name=random.choice(['email', 'password', 'amount', 'item_id']),
            retry_after=random.randint(30, 300),
            error=random.choice(['ValueError', 'TypeError', 'KeyError']),
            plan=random.choice(['index_scan', 'seq_scan', 'bitmap_scan']),
            # Anomaly log parameters.
            max_conn=random.choice([50, 100, 200]),
            service=random.choice(self.services),
            attempts=random.randint(3, 10),
            host=f'db-{random.randint(1, 5)}.example.com',
            error_msg=random.choice(['Connection refused', 'Timeout', 'Network unreachable']),
            disk_space=random.randint(1, 5),
            queue_size=random.randint(10000, 50000),
            ip_address=f'{random.randint(1,255)}.{random.randint(1,255)}.{random.randint(1,255)}.{random.randint(1,255)}'
        )

        # CRITICAL: Must match training data format exactly.
        log_entry = {
            'timestamp': datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%S.%f')[:-3] + 'Z',  # Always include milliseconds.
            'level': level,
            'service': random.choice(self.services),  # MUST be 'service', not 'component'.
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
        type=float,
        default=100,
        help='Logs per second, can be fractional (default: 100). Examples: 0.5 = 1 log per 2s, 0.17 = ~5 logs per 30s'
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
