#!/bin/bash

# Define required buckets here - add more as needed
declare -a BUCKETS=(
    "${S3__BUCKETS__WORK_AREA}"
)

declare -a PUBLIC_BUCKETS=()

MAX_TRIES=30
RETRY_INTERVAL=3
count=0

# if no 'mc' binary, bail
if ! command -v mc &> /dev/null; then
    echo "mc command not found. Please install mc and try again."
    exit 1
fi

echo "Configuring MinIO client..."

# Configure mc with our MinIO instance
if [ "$S3__SSL" = "true" ]; then
    PROTOCOL="https://"
else
    PROTOCOL="http://"
fi
ENDPOINT_URL="${PROTOCOL}${S3__ENDPOINT}"

# Validate endpoint URL
if [ -z "$S3__ENDPOINT" ]; then
    echo "Error: CENTRAL_S3__ENDPOINT is not set"
    exit 1
fi

echo "Using endpoint: $ENDPOINT_URL"

# Add our MinIO instance as an alias called 'local'
mc alias set local "$ENDPOINT_URL" "$S3__ACCESS_KEY" "$S3__SECRET_KEY" --api S3v4

echo "Waiting for MinIO to become available..."

while [ $count -lt $MAX_TRIES ]; do
    # Try to list buckets using mc
    if mc ls local > /dev/null 2>&1; then
        echo "Successfully connected to MinIO!"
        
        # Check and create each bucket as needed
        for BUCKET in "${BUCKETS[@]}"; do
            echo "Checking bucket '$BUCKET'..."
            
            if mc ls "local/${BUCKET}" 2>&1; then
                echo "Bucket '$BUCKET' exists!"
            else
                echo "Creating bucket '$BUCKET'..."
                if ! mc mb "local/${BUCKET}" 2>&1; then
                    echo "Failed to create bucket '$BUCKET'."
                    exit 1
                fi
                echo "Successfully created bucket '$BUCKET'!"
            fi

            # Set public download permissions for public buckets
            for PUBLIC_BUCKET in "${PUBLIC_BUCKETS[@]}"; do
                if [ "$BUCKET" = "$PUBLIC_BUCKET" ]; then
                    echo "Setting public download access for bucket '$BUCKET'..."
                    if ! mc anonymous set download "local/${BUCKET}"; then
                        echo "Failed to set public access for bucket '$BUCKET'."
                        exit 1
                    fi
                    echo "Successfully set public access for bucket '$BUCKET'!"
                fi
            done
        done

        echo "All buckets verified and ready!"
        exit 0
    fi

    echo "Attempt $((count + 1))/$MAX_TRIES failed. Retrying in $RETRY_INTERVAL seconds..."
    sleep $RETRY_INTERVAL
    count=$((count + 1))
done

echo "Failed to connect to MinIO after $MAX_TRIES attempts."
exit 1