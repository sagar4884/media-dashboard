#!/bin/sh
set -e

DB_FILE="/appdata/database/app.db"

# Ensure the database directory exists
mkdir -p /appdata/database
# Create a symlink for the posters directory
mkdir -p /app/app/static
ln -sfn /appdata/posters /app/app/static/posters

# Check for the database file
if [ -f "$DB_FILE" ]; then
    echo "Existing database found. Running integrity check..."
    # The output of the pragma is piped to grep. If it's "ok", grep returns 0.
    # The `if` statement checks this exit code.
    if echo "PRAGMA integrity_check;" | sqlite3 "$DB_FILE" | grep -q "ok"; then
        echo "Integrity check passed."
    else
        echo "Integrity check failed. Please check the database file."
        # You might want to exit here in a production environment
        # exit 1
    fi
else
    echo "No database found. Creating a new one..."
    # Use flask shell to create tables from models
    echo "from app import db; db.create_all()" | flask shell
    
    # Verify that the new database is valid
    if echo "PRAGMA integrity_check;" | sqlite3 "$DB_FILE" | grep -q "ok"; then
        echo "New database created and verified successfully."
    else
        echo "Error: Failed to create a valid database."
        exit 1
    fi
fi

echo "Startup complete."

# Execute the command passed into the script
exec "$@"
