#!/bin/bash

# Exit immediately if a command exits with a non-zero status.
set -e

# Create log directory for Supervisor-managed processes (Celery)
LOG_DIR="/app/logs"
mkdir -p $LOG_DIR
# Optionally, set permissions if needed, e.g., chown user:group $LOG_DIR

echo "Running Database Migrations..."
python manage.py makemigrations store_monitor_api
python manage.py migrate --noinput

# If INGEST is present in the environment, run the data ingestion script.
if [ -n "$INGEST" ]; then
    echo "Ingesting data..."
    python manage.py load_csv_data
fi

echo "Starting Django Development Server..."
# Using 0.0.0.0 makes the server accessible from outside the container.
# This will be the main foreground process for the Docker container.
exec python manage.py runserver 0.0.0.0:8000
