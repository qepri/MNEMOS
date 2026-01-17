#!/bin/bash
set -e

# Run migrations only if the environment variable is set
if [ "$RUN_MIGRATIONS" = "true" ]; then
    echo "Running database migrations..."
    flask db upgrade
else
    echo "Skipping database migrations (RUN_MIGRATIONS not set to true)"
fi

# Execute the main command
exec "$@"
