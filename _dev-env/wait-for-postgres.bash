#!/bin/bash

MAX_TRIES=30
RETRY_INTERVAL=3
count=0

# making sure `psql` is available
command -v psql >/dev/null 2>&1 || { echo >&2 "psql is required but it's not installed. Aborting."; exit 1; }

echo "Waiting for PostgreSQL to become available..."

while [ $count -lt $MAX_TRIES ]; do
    echo "Attempting to connect to PostgreSQL, host '$DEV_DATABASE_HOST' port '$DEV_DATABASE_PORT' user '$DEV_DATABASE_USER'..."

    PGPASSWORD=$DEV_DATABASE_PASSWORD psql \
        -h "$DEV_DATABASE_HOST" \
        -p "$DEV_DATABASE_PORT" \
        -U "$DEV_DATABASE_USER" \
        -d "$DEV_DATABASE_NAME" \
        -c "SELECT 1;"

    # shellcheck disable=SC2181
    if [ $? -eq 0 ]; then
        echo "Successfully connected to PostgreSQL!"
        exit 0
    fi

    echo "Attempt $((count + 1))/$MAX_TRIES failed. Retrying in $RETRY_INTERVAL seconds..."
    sleep $RETRY_INTERVAL
    count=$((count + 1))
done

echo "Failed to connect to PostgreSQL after $MAX_TRIES attempts."
exit 1