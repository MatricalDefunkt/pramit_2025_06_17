#!/bin/bash

# Store Monitor API - A tool for monitoring store performance and uptime.
# Copyright (C) 2025 Pramit Sharma
#
# This file is part of pramit_2025_06_17.
#
# pramit_2025_06_17 is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as published by
# the Free Software Foundation, either version 3 of the License, or (at your
# option) any later version.
#
# pramit_2025_06_17 is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU Affero General Public License for more details.
#
# You should have received a copy of the GNU Affero General Public License
# along with this program.  If not, see <https://www.gnu.org/licenses/>.


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
