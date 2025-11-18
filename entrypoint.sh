#!/bin/sh
set -e

# If migrations directory doesn't exist, initialize it
if [ ! -d "migrations" ]; then
    echo "Migrations directory not found. Initializing..."
    flask db init
    flask db migrate -m "Initial database setup"
fi

# Run database migrations
echo "Running database migrations..."
flask db upgrade

echo "Migrations complete."
