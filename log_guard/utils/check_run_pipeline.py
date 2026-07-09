"""
Command-line interface for running the LogGuard anomaly detection pipeline.
"""

import argparse
import sys
from pathlib import Path

from log_guard.detection_pipeline import AnomalyDetectionPipeline
from log_guard.config.config import get_config


def run_batch_detection(args):
    """
    Run anomaly detection on a batch of logs from a CSV file.

    param args: Command-line arguments.
    """
    config = get_config(args.env)

    # Initialize pipeline.
    print("Initializing anomaly detection pipeline...")
    pipeline = AnomalyDetectionPipeline(
        model_path=str(config.DBSCAN_MODEL_PATH),
        scaler_path=str(config.SCALER_PATH),
        tfidf_path=str(config.TFIDF_PATH),
        svd_path=str(config.SVD_PATH),
        kmeans_path=str(config.KMEANS_PATH),
        rarity_path=str(config.RARITY_PATH),
        window=args.window
    )

    # Process logs.
    print(f"Processing logs from {args.input}...")
    results = pipeline.detect_anomalies_in_file(
        log_file_path=args.input,
        output_path=args.output
    )

    print("\n✓ Anomaly detection completed")

    # Show sample results.
    if args.show_samples:
        print("\nSample anomalies detected:")
        anomalies = results[results['is_anomaly'] == 1].head(10)
        if len(anomalies) > 0:
            print(anomalies[['timestamp', 'anomaly_score', 'cluster_label']])
        else:
            print("No anomalies detected")


def main():
    """
    Main CLI entry point.
    """
    parser = argparse.ArgumentParser(
        description='LogGuard: Real-time Log Anomaly Detection',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Run batch detection on a CSV file.
  python run_pipeline.py batch --input data/logs.csv --output data/predictions.csv

  # Use different time window.
  python run_pipeline.py batch --input data/logs.csv --window 60s

  # Run in production mode.
  python run_pipeline.py batch --input data/logs.csv --env production
        """
    )

    parser.add_argument(
        '--env',
        choices=['development', 'production'],
        default='development',
        help='Environment configuration to use'
    )

    subparsers = parser.add_subparsers(dest='command', help='Command to run')

    # Batch mode.
    batch_parser = subparsers.add_parser(
        'batch',
        help='Run anomaly detection on a batch of logs from CSV file'
    )
    batch_parser.add_argument(
        '--input',
        required=True,
        help='Path to input CSV file with logs'
    )
    batch_parser.add_argument(
        '--output',
        help='Path to save predictions CSV (optional)'
    )
    batch_parser.add_argument(
        '--window',
        default='30s',
        help='Time window for aggregation (default: 30s)'
    )
    batch_parser.add_argument(
        '--show-samples',
        action='store_true',
        help='Show sample anomalies detected'
    )

    # Streaming mode.
    stream_parser = subparsers.add_parser(
        'stream',
        help='Run anomaly detection in streaming mode (Kafka)'
    )
    stream_parser.add_argument(
        '--kafka-brokers',
        default='localhost:9092',
        help='Kafka bootstrap servers'
    )
    stream_parser.add_argument(
        '--input-topic',
        default='log-events',
        help='Kafka topic to consume logs from'
    )
    stream_parser.add_argument(
        '--output-topic',
        default='anomaly-alerts',
        help='Kafka topic to publish anomalies to'
    )

    args = parser.parse_args()

    if args.command == 'batch':
        run_batch_detection(args)
    elif args.command == 'stream':
        run_streaming_mode(args)
    else:
        parser.print_help()
        sys.exit(1)


if __name__ == '__main__':
    main()
