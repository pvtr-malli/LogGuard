#!/bin/bash
# Stop script for LogGuard streaming pipeline.

set -e

echo "╔════════════════════════════════════════════════════════════╗"
echo "║     Stopping LogGuard Streaming Pipeline                  ║"
echo "╚════════════════════════════════════════════════════════════╝"
echo ""

# Stop components.
if [ -f pids/producer.pid ]; then
    PID=$(cat pids/producer.pid)
    echo "Stopping log producer (PID: $PID)..."
    kill $PID 2>/dev/null || echo "  Already stopped"
    rm pids/producer.pid
fi

if [ -f pids/processor.pid ]; then
    PID=$(cat pids/processor.pid)
    echo "Stopping stream processor (PID: $PID)..."
    kill $PID 2>/dev/null || echo "  Already stopped"
    rm pids/processor.pid
fi

if [ -f pids/writer.pid ]; then
    PID=$(cat pids/writer.pid)
    echo "Stopping results writer (PID: $PID)..."
    kill $PID 2>/dev/null || echo "  Already stopped"
    rm pids/writer.pid
fi

echo ""
echo "Stopping infrastructure (Kafka, Zookeeper, TimescaleDB)..."
docker-compose down

echo ""
echo "✓ Pipeline stopped successfully"
echo ""
echo "Logs are preserved in logs/ directory:"
echo "  • logs/producer.log"
echo "  • logs/processor.log"
echo "  • logs/writer.log"
echo ""
