#!/usr/bin/env bash
set -euo pipefail

# Use application environment variables
HOST=${SERVER__HOST:-0.0.0.0}
PORT=${SERVER__PORT:-8000}

# Replace 0.0.0.0 with localhost for client connections
if [ "$HOST" = "0.0.0.0" ]; then
    HOST="localhost"
fi

MAX_ATTEMPTS=${MAX_ATTEMPTS:-30}
INTERVAL=${INTERVAL:-2}

echo "Waiting for API to be ready at http://${HOST}:${PORT}/health..."

# Try to connect to the API
for i in $(seq 1 $MAX_ATTEMPTS); do
    echo "Attempt $i of $MAX_ATTEMPTS..."
    
    # Use curl to check the health endpoint
    response=$(curl -s -o /dev/null -w "%{http_code}" http://${HOST}:${PORT}/health 2>/dev/null) || response="000"
    
    if [ "$response" = "200" ]; then
        # Verify the content contains "status": "ok"
        content=$(curl -s http://${HOST}:${PORT}/health)
        if echo "$content" | grep -q '"status":"ok"'; then
            echo "API is ready!"
            exit 0
        fi
    fi
    
    echo "API not ready yet (HTTP status: $response). Waiting ${INTERVAL}s..."
    sleep $INTERVAL
done

echo "Timed out waiting for API to be ready after $((MAX_ATTEMPTS * INTERVAL)) seconds."
exit 1
