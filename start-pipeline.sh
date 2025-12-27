#!/bin/bash
# Quick start script for LogGuard streaming pipeline.

set -e

echo "╔════════════════════════════════════════════════════════════╗"
echo "║     LogGuard Streaming Pipeline - Quick Start             ║"
echo "╚════════════════════════════════════════════════════════════╝"
echo ""

# Check if models exist.
if [ ! -f "models/dbscan_model.pkl" ] || [ ! -f "models/scaler.pkl" ]; then
    echo "❌ Models not found!"
    echo ""
    echo "Please export models from notebooks first:"
    echo "  1. Run notebook 04_text_embeddings.ipynb (final cell)"
    echo "  2. Run notebook 05_anomaly_detection_models.ipynb (final cell)"
    echo ""
    exit 1
fi

echo "✓ Models found"
echo ""

# Create directories.
mkdir -p logs pids

# Start infrastructure.
echo "Starting Kafka, Zookeeper, and TimescaleDB..."
docker-compose up -d

echo "Waiting for services to be ready (30 seconds)..."
sleep 30

# Check if services are running.
if ! docker-compose ps | grep -q "Up"; then
    echo "❌ Services failed to start"
    echo "Check logs with: docker-compose logs"
    exit 1
fi

echo "✓ Infrastructure started"
echo ""

# Start log producer.
echo "Starting log producer (100 logs/sec)..."
cd src
python log_producer.py --rate 100 > ../logs/producer.log 2>&1 &
PRODUCER_PID=$!
echo $PRODUCER_PID > ../pids/producer.pid
echo "  PID: $PRODUCER_PID"

# Give producer time to start.
sleep 5

# Start stream processor.
echo "Starting stream processor (30s windows)..."
python stream_processor.py --window 30 > ../logs/processor.log 2>&1 &
PROCESSOR_PID=$!
echo $PROCESSOR_PID > ../pids/processor.pid
echo "  PID: $PROCESSOR_PID"

# Give processor time to load models.
sleep 5

# Start results writer.
echo "Starting results writer (batch size 100)..."
python results_writer.py --batch-size 100 > ../logs/writer.log 2>&1 &
WRITER_PID=$!
echo $WRITER_PID > ../pids/writer.pid
echo "  PID: $WRITER_PID"

cd ..

echo ""
echo "╔════════════════════════════════════════════════════════════╗"
echo "║                    Pipeline Started!                       ║"
echo "╚════════════════════════════════════════════════════════════╝"
echo ""
echo "Services:"
echo "  • Kafka UI:      http://localhost:8080"
echo "  • TimescaleDB:   localhost:5432 (user: logguard, pass: logguard123)"
echo ""
echo "Component PIDs:"
echo "  • Producer:      $PRODUCER_PID"
echo "  • Processor:     $PROCESSOR_PID"
echo "  • Writer:        $WRITER_PID"
echo ""
echo "Logs:"
echo "  • Producer:      tail -f logs/producer.log"
echo "  • Processor:     tail -f logs/processor.log"
echo "  • Writer:        tail -f logs/writer.log"
echo ""
echo "To stop the pipeline:"
echo "  • Run: ./stop-pipeline.sh"
echo ""
echo "To query results:"
echo "  • docker exec -it logguard-timescaledb psql -U logguard -d logguard"
echo ""
