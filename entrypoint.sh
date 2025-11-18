#!/bin/sh
set -e

# Ensure the instance folder exists and create an empty db file to ensure writability
mkdir -p /app/instance
touch /app/instance/app.db

# If migrations directory doesn't exist, initialize it
if [ ! -d "/app/migrations" ]; then
    echo "Migrations directory not found. Initializing..."
    flask db init
    flask db migrate -m "Initial database setup"
fi


# Run database migrations
echo "Running database migrations..."
flask db upgrade

echo "Migrations complete."

# Execute the command passed into the script
exec "$@"

