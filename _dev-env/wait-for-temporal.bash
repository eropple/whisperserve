#!/bin/bash

MAX_TRIES=30
RETRY_INTERVAL=3
count=0

# making sure `temporal` is available
command -v temporal >/dev/null 2>&1 || { echo >&2 "temporal is required but it's not installed. Aborting."; exit 1; }

echo "Waiting for Temporal to become available..."

while [ $count -lt $MAX_TRIES ]; do
    temporal operator cluster health \
        --address "$TEMPORAL__SERVER_ADDRESS"

    # shellcheck disable=SC2181
    if [ $? -eq 0 ]; then
        echo "Successfully connected to Temporal!"
        exit 0
    fi

    echo "Attempt $((count + 1))/$MAX_TRIES failed. Retrying in $RETRY_INTERVAL seconds..."
    sleep $RETRY_INTERVAL
    count=$((count + 1))
done

echo "Failed to connect to Temporal after $MAX_TRIES attempts."
exit 1