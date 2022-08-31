#!/usr/bin/env bash
echo "Start migrations..."
python manage.py migrate

echo "Collect static..."
python manage.py collectstatic --no-input

echo "Load ingredients..."
python manage.py load_data

echo "Start foodgram..."
gunicorn foodgram.wsgi:application --bind 127.0.0.1:8000