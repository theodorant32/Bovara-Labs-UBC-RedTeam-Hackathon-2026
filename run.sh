#!/bin/bash
# FindMyForce - Run both API bridge server and Web frontend
# Usage: bash run.sh

set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
API_DIR="$SCRIPT_DIR/FindMyForce-API"
WEB_DIR="$SCRIPT_DIR/FindMyForce-Web"

echo "========================================"
echo "  FindMyForce - Common Operating Picture"
echo "========================================"
echo ""

# Check dependencies
if ! command -v python &> /dev/null; then
    echo "ERROR: Python not found. Install Python 3.13+."
    exit 1
fi

if ! command -v npm &> /dev/null; then
    echo "ERROR: npm not found. Install Node.js."
    exit 1
fi

# Install web dependencies if needed
if [ ! -d "$WEB_DIR/node_modules/leaflet" ]; then
    echo "[WEB] Installing npm dependencies..."
    cd "$WEB_DIR" && npm install
    cd "$SCRIPT_DIR"
fi

# Start API bridge server in background
echo "[API] Starting bridge server on http://localhost:5000 ..."
cd "$API_DIR"
python -m findmyforce.web_server &
API_PID=$!
cd "$SCRIPT_DIR"

# Give the API server a moment to start
sleep 2

# Start web dev server
echo "[WEB] Starting Vite dev server..."
cd "$WEB_DIR"
npm run dev &
WEB_PID=$!
cd "$SCRIPT_DIR"

echo ""
echo "Services running:"
echo "  API Bridge:  http://localhost:5000  (PID: $API_PID)"
echo "  Web Frontend: http://localhost:5173  (PID: $WEB_PID)"
echo ""
echo "Press Ctrl+C to stop both services."
echo ""

# Trap Ctrl+C to kill both processes
cleanup() {
    echo ""
    echo "Shutting down..."
    kill $API_PID 2>/dev/null
    kill $WEB_PID 2>/dev/null
    wait $API_PID 2>/dev/null
    wait $WEB_PID 2>/dev/null
    echo "Done."
}

trap cleanup SIGINT SIGTERM

# Wait for either process to exit
wait
