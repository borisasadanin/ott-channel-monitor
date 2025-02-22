#!/bin/sh

echo "Waiting for database service API to be ready..."
until curl -s http://database_service:5000/health | grep "ok" > /dev/null; do
    echo "Still waiting for database API..."
    sleep 5
done

echo "Database API is ready, starting monitor service..."
exec python monitor.py
