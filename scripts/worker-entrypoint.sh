#!/bin/sh

until cd /app
do
    echo "Waiting for server volume..."
done

# run a worker :)
celery -A food_order_api worker --loglevel=info --concurrency 1 -E
