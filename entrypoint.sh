#!/bin/sh
set -e

# Run database migrations
echo "Running database migrations..."
flask db upgrade

echo "Migrations complete."

# Execute the command passed into the script
exec "$@"
